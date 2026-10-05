import html
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import requests
from google.genai import types

from ..core.logging import get_logger
from ..core.settings import settings
from ..core.visual_styles import get_style
from ..utils.genai_client import get_genai_client
from ..utils.retry import retry
from .image_service import generate_image, save_png


logger = get_logger(__name__)

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
HTTP_HEADERS = {"User-Agent": "aitihasik-katha/0.1 (https://github.com/thegauravgiri/aitihasik-katha)"}


@dataclass
class Reference:
    image_path: str
    source: str  # "wikimedia" or "generated"
    description: str | None = None  # appearance as seen in the image, replaces the sheet's guess
    credit: str | None = None  # attribution line for published media


@dataclass
class Portrait:
    file_name: str
    image_url: str
    license: str
    artist: str
    page_url: str


def is_publishable_license(license_name: str) -> bool:
    """Public domain, CC0 and CC BY only.

    CC BY-SA is excluded: its share-alike term would arguably apply to the published
    video. NC/ND variants forbid commercial use or adaptation.
    """
    name = license_name.strip().lower()
    return (
        "public domain" in name
        or name.startswith(("pd", "cc0", "cc-zero"))
        or re.match(r"^cc[- ]by[- ]\d", name) is not None
    )


def _strip_html(value: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", value))
    text = re.sub(r"\s*\(\s*(talk|contribs)\s*\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Commons often nests the same name in several tags ("Unknown author Unknown author").
    half = len(text) // 2
    if len(text) % 2 == 1 and text[:half] == text[half + 1:]:
        return text[:half]
    return text


@retry(exceptions=(requests.RequestException,), max_attempts=3, delay_seconds=5)
def find_historical_portrait(wikipedia_title: str) -> Portrait | None:
    """The lead image of the person's English Wikipedia article, if freely licensed."""
    pages = requests.get(
        WIKIPEDIA_API,
        headers=HTTP_HEADERS,
        params={"action": "query", "titles": wikipedia_title, "prop": "pageimages",
                "piprop": "name", "redirects": 1, "format": "json"},
        timeout=30,
    ).json()["query"]["pages"]
    file_name = next(iter(pages.values())).get("pageimage")
    if not file_name:
        return None

    files = requests.get(
        COMMONS_API,
        headers=HTTP_HEADERS,
        params={"action": "query", "titles": f"File:{file_name}", "prop": "imageinfo",
                "iiprop": "url|extmetadata", "iiurlwidth": 1024, "format": "json"},
        timeout=30,
    ).json()["query"]["pages"]
    info = (next(iter(files.values())).get("imageinfo") or [None])[0]
    if not info:
        return None

    metadata = info.get("extmetadata", {})
    license_name = metadata.get("LicenseShortName", {}).get("value", "")
    if not is_publishable_license(license_name):
        logger.info("Skipping %s for %s: license %r", file_name, wikipedia_title, license_name)
        return None

    return Portrait(
        file_name=file_name,
        image_url=info.get("thumburl") or info["url"],
        license=license_name,
        artist=_strip_html(metadata.get("Artist", {}).get("value", "")) or "unknown",
        page_url=info.get("descriptionurl", ""),
    )


PORTRAIT_CHECK_PROMPT = """This image is the Wikipedia lead image for {name}.
Decide whether it can serve as a visual reference for how {name} looked. It must clearly show that one
person - a portrait painting, photograph or statue of them - with the face visible. Coins, inscriptions,
maps, buildings, symbols, or group scenes where the subject isn't clear do not qualify.

Return ONLY JSON:
{{"usable": true or false,
  "reason": "short reason",
  "description": "if usable: fixed physical appearance of the person, for a film costume and casting team: sex, apparent age, build, face, skin tone, hair and facial hair, clothing with exact colours, headwear, jewellery, weapons. English. Empty string if not usable."}}

The description must describe a real, living human. If the image is a statue or painting, translate what it
depicts into how the person would look in life (natural skin tone, real fabrics and colours appropriate to
their period) and never mention the medium (bronze, stone, paint, patina, pedestal). Describe only fixed
appearance, never pose, gesture, expression or action - each scene decides those."""


@retry(exceptions=(Exception,), max_attempts=3, delay_seconds=5)
def _assess_portrait(image_png: bytes, name: str) -> dict:
    settings.require("CHAT_MODEL")
    response = get_genai_client().models.generate_content(
        model=settings.CHAT_MODEL,
        contents=[
            types.Part.from_bytes(data=image_png, mime_type="image/png"),
            PORTRAIT_CHECK_PROMPT.format(name=name),
        ],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    verdict = json.loads(response.text)
    if not isinstance(verdict, dict) or "usable" not in verdict:
        raise ValueError(f"Unexpected portrait check response: {response.text!r}")
    return verdict


def _historical_reference(character: dict, image_path: str) -> Reference | None:
    title = character.get("wikipedia_title")
    if not title:
        return None
    portrait = find_historical_portrait(title)
    if portrait is None:
        logger.info("No freely licensed portrait found for %s (%s)", character["id"], title)
        return None

    download = requests.get(portrait.image_url, headers=HTTP_HEADERS, timeout=60)
    download.raise_for_status()
    png = save_png(download.content, image_path)

    verdict = _assess_portrait(png, character["name"])
    if not verdict.get("usable") or not verdict.get("description"):
        logger.info("Portrait %s rejected for %s: %s", portrait.file_name, character["id"], verdict.get("reason"))
        Path(image_path).unlink(missing_ok=True)
        return None

    logger.info("Using Wikimedia portrait %s (%s) for %s", portrait.file_name, portrait.license, character["id"])
    return Reference(
        image_path=image_path,
        source="wikimedia",
        description=verdict["description"],
        credit=f'{character["name"]}: "{portrait.file_name}" by {portrait.artist}, {portrait.license}, via Wikimedia Commons',
    )


def _generated_reference(character: dict, style: str, image_path: str, visual_style: str | None = None) -> Reference:
    style_obj = get_style(visual_style or settings.VISUAL_STYLE)
    style_prompt = "Photorealistic" if style_obj.name == "realistic" else f"{style_obj.label} art style. {style_obj.character_style_guidance}"
    prompt = (
        f"Character reference image of {character['name']}: {character['description']}. "
        "Full body, standing still and facing the camera, soft even lighting, plain neutral background. "
        f"{style_prompt}. No text. Overall look: {style}"
    )
    save_png(generate_image(prompt), image_path)
    logger.info("Generated reference image for %s (%s)", character["id"], style_obj.name)
    return Reference(image_path=image_path, source="generated")


def resolve_reference(character: dict, style: str, image_path: str, visual_style: str | None = None) -> Reference:
    """Reference image for a character: a real historical portrait when one is freely
    available and actually depicts them, otherwise a generated one.

    The choice is saved next to the image so a resumed run reuses it unchanged.
    """
    sidecar = Path(image_path).with_suffix(".json")
    if sidecar.exists() and Path(image_path).exists():
        logger.info("Reusing existing reference %s", image_path)
        return Reference(**json.loads(sidecar.read_text(encoding="utf-8")))

    style_obj = get_style(visual_style or settings.VISUAL_STYLE)
    reference = None
    if settings.USE_HISTORICAL_PORTRAITS and style_obj.allow_real_media:
        try:
            reference = _historical_reference(character, image_path)
        except Exception as exc:  # noqa: BLE001 - a lookup failure just means we generate one instead
            logger.warning("Portrait lookup failed for %s, generating instead: %s", character["id"], exc)
    if reference is None:
        reference = _generated_reference(character, style, image_path, visual_style=style_obj.name)

    sidecar.write_text(json.dumps(asdict(reference), ensure_ascii=False, indent=2), encoding="utf-8")
    return reference
