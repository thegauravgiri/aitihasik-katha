"""Find real photos and footage on Wikimedia Commons for a scene.

A scene's `real_search` phrase is searched on Commons; freely licensed, large enough files are
shown to the chat model together with the narration line, and it picks the one that really
shows what is being said (or none). The chosen file is saved in the media library, so any
later video that needs the same thing reuses it.
"""
import json
import re
from dataclasses import dataclass

import requests
from google.genai import types

from ..core.logging import get_logger
from ..core.settings import settings
from ..utils.genai_client import get_genai_client
from ..utils.retry import retry
from .media_library import LibraryItem, MediaLibrary
from .reference_service import COMMONS_API, HTTP_HEADERS, _strip_html, is_publishable_license


logger = get_logger(__name__)

MIN_SHORT_SIDE = 1000  # a photo is cropped and zoomed for a vertical video, so it needs real resolution
MAX_VIDEO_BYTES = 60_000_000
CANDIDATES_SHOWN = 6
IMAGE_WIDTH = 2000


@dataclass
class RealMedia:
    path: str
    kind: str  # "image" or "video"
    credit: str
    title: str


def _license_ok(name: str) -> bool:
    if is_publishable_license(name):
        return True
    return settings.REAL_MEDIA_ALLOW_SHAREALIKE and re.match(r"^cc[- ]by[- ]sa[- ]\d", name.strip().lower()) is not None


@retry(exceptions=(requests.RequestException,), max_attempts=3, delay_seconds=5)
def _search(query: str, kind: str, limit: int) -> list[dict]:
    """Commons files for `query`: [{title, url, thumb, width, height, size, license, artist, page_url,
    description}], best match first, already filtered by licence, resolution and size."""
    pages = requests.get(
        COMMONS_API,
        headers=HTTP_HEADERS,
        params={
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": limit,
            "gsrsearch": f"{query} filetype:{'video' if kind == 'video' else 'bitmap'}",
            "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": IMAGE_WIDTH,
            "iiextmetadatafilter": "LicenseShortName|Artist|ImageDescription",
        },
        timeout=30,
    ).json().get("query", {}).get("pages", {})

    found = []
    for page in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        info = (page.get("imageinfo") or [None])[0]
        if not info:
            continue
        metadata = info.get("extmetadata", {})
        license_name = metadata.get("LicenseShortName", {}).get("value", "")
        width, height = info.get("width", 0), info.get("height", 0)
        if not _license_ok(license_name) or min(width, height) < MIN_SHORT_SIDE:
            continue
        if kind == "video" and (info.get("size", 0) > MAX_VIDEO_BYTES or not info.get("thumburl")):
            continue
        if kind == "image" and info.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
            continue
        found.append({
            "title": page["title"].removeprefix("File:"),
            "url": info["url"],
            "thumb": info.get("thumburl") or info["url"],
            "width": width,
            "height": height,
            "license": license_name,
            "artist": _strip_html(metadata.get("Artist", {}).get("value", "")) or "unknown",
            "page_url": info.get("descriptionurl", ""),
            "description": _strip_html(metadata.get("ImageDescription", {}).get("value", ""))[:240],
        })
    return found


@retry(exceptions=(requests.RequestException,), max_attempts=3, delay_seconds=5)
def _download(url: str) -> bytes:
    response = requests.get(url, headers=HTTP_HEADERS, timeout=120)
    response.raise_for_status()
    return response.content


PICK_PROMPT = """You are choosing real archive material for a short history video about Nepal.

The narration line this picture will play under: {line}
What the picture should show: {subject}

Below are {count} candidate files from Wikimedia Commons, numbered from 0, each with its file name
and caption. Choose the ONE that best shows the subject, or none.

Accept a candidate only if ALL of these hold:
- It clearly shows the subject (the right place, object, custom or person), not just something nearby.
- It is sharp, well composed and good-looking at the size of a phone screen.
- It has no watermark, logo, text overlay, border, collage or heavy filter.
- It would not mislead: nothing in it obviously contradicts the narration (modern cars, signs or
  buildings in a scene about an old event, unless the subject itself is a landmark that still stands).

Return ONLY JSON: {{"best": the number, or null if none qualifies, "reason": "short"}}"""


@retry(exceptions=(Exception,), max_attempts=2, delay_seconds=5)
def _pick(candidates: list[dict], thumbs: list[bytes], line: str, subject: str) -> int | None:
    settings.require("CHAT_MODEL")
    contents: list = []
    for idx, (candidate, thumb) in enumerate(zip(candidates, thumbs)):
        contents.append(f"Candidate {idx}: {candidate['title']}. {candidate['description']}")
        contents.append(types.Part.from_bytes(data=thumb, mime_type="image/jpeg"))
    contents.append(PICK_PROMPT.format(line=line, subject=subject, count=len(candidates)))
    response = get_genai_client().models.generate_content(
        model=settings.CHAT_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    verdict = json.loads(response.text)
    if not isinstance(verdict, dict):
        raise ValueError(f"Unexpected media pick response: {response.text!r}")
    best = verdict.get("best")
    logger.info("Media pick for %r: %s (%s)", subject, best, verdict.get("reason", ""))
    return best if isinstance(best, int) and 0 <= best < len(candidates) else None


def _fresh_thumb(candidate: dict) -> bytes:
    from io import BytesIO

    from PIL import Image

    image = Image.open(BytesIO(_download(candidate["thumb"]))).convert("RGB")
    image.thumbnail((640, 640))
    buffer = BytesIO()
    image.save(buffer, "JPEG", quality=80)
    return buffer.getvalue()


def _from_item(item: LibraryItem, library: MediaLibrary) -> RealMedia:
    return RealMedia(path=library.path_of(item), kind=item.kind, credit=item.credit, title=item.title)


def find_real_media(
    query: str, line: str, used: set[str] | None = None, library: MediaLibrary | None = None
) -> RealMedia | None:
    """Real media for a scene: from the library if this search was answered before, otherwise from
    Commons. `used` holds the titles already placed in this video so no photo repeats.
    Returns None when nothing good enough exists; the scene then uses a generated shot."""
    used = used if used is not None else set()
    library = library or MediaLibrary()

    for item in library.for_query(query):
        if item.title not in used:
            logger.info("Reusing %s from the media library for %r", item.title, query)
            return _from_item(item, library)

    candidates = [c for c in _search(query, "image", 15) if c["title"] not in used][:CANDIDATES_SHOWN]
    candidates += [c for c in _search(query, "video", 6) if c["title"] not in used][:2]
    if not candidates:
        logger.info("No usable real media on Commons for %r", query)
        return None

    thumbs = [_fresh_thumb(c) for c in candidates]
    best = _pick(candidates, thumbs, line, query)
    if best is None:
        return None

    chosen = candidates[best]
    is_video = chosen["title"].lower().endswith((".webm", ".ogv", ".mp4"))
    item = library.get(chosen["title"])
    if not item:
        path = library.file_path_for(chosen["title"])
        path.write_bytes(_download(chosen["url"] if is_video else chosen["thumb"]))
        item = LibraryItem(
            title=chosen["title"], file=path.name, kind="video" if is_video else "image",
            license=chosen["license"], artist=chosen["artist"], page_url=chosen["page_url"],
            width=chosen["width"], height=chosen["height"], description=chosen["description"],
        )
    item = library.add(item, query)
    logger.info("Using real %s %s (%s) for %r", item.kind, item.title, item.license, query)
    return _from_item(item, library)
