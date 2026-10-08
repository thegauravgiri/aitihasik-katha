import json
from pathlib import Path

import requests

from ..core.logging import get_logger
from ..core.settings import settings
from .reference_service import HTTP_HEADERS


logger = get_logger(__name__)

# Canonical mood categories for historical documentary videos about Nepal
MOOD_TENSION = "tension_intrigue"
MOOD_EPIC = "epic_warfare"
MOOD_MYSTIC = "mystic_ancient"
MOOD_HERITAGE = "heritage_reflective"
MOOD_TRIUMPHANT = "triumphant_revolt"

# Keyword banks for fast, deterministic context-to-mood classification (Nepali + English)
_MOOD_KEYWORDS = {
    MOOD_EPIC: [
        "युद्ध", "लडाइँ", "सेना", "गोर्खाली", "कब्जा", "वीर", "नालापानी", "कीर्तिपुर",
        "बन्दुक", "तलवार", "आक्रमण", "हतियार", "सिपाही", "लडाइ", "कमाण्डर",
        "war", "battle", "army", "soldier", "siege", "warrior", "invasion", "military",
        "sword", "combat", "conquest", "frontline", "fortress"
    ],
    MOOD_MYSTIC: [
        "मन्दिर", "मूर्ति", "तान्त्रिक", "पूजा", "देवी", "कुमारी", "काष्ठमण्डप", "श्राप",
        "गुठी", "जात्रा", "सुनको चरा", "चमत्कार", "रहस्यमय मन्दिर", "मन्त्र",
        "temple", "statue", "tantric", "curse", "ritual", "deity", "sacred", "priest",
        "myth", "mystic", "shrine", "goddess", "kumari", "incantation"
    ],
    MOOD_HERITAGE: [
        "फुटबल", "खेल", "कला", "चाड", "दसैँ", "पिङ", "संस्कृति", "गीत", "इतिहास",
        "पायोनियर", "नेपालको खेल", "दरबार शैली", "भवन", "सडक",
        "football", "sport", "pioneer", "culture", "festival", "tradition", "heritage",
        "legacy", "origin", "kite", "dashain", "architect", "memoir", "everyday"
    ],
    MOOD_TRIUMPHANT: [
        "प्रजातन्त्र", "क्रान्ति", "घोषणा", "संविधान", "अधिकार", "राणा शासन ढल्यो", "विद्रोह",
        "मुक्ति सेना", "स्वतन्त्रता", "दिल्ली सम्झौता", "शाही घोषणा", "विजय",
        "revolution", "democracy", "proclamation", "freedom", "liberation", "reclaimed",
        "triumph", "constitution", "treaty", "independence", "victory"
    ],
    MOOD_TENSION: [
        "षड्यन्त्र", "हत्या", "दरबार", "बन्दी", "पिकनिक", "भागे", "भण्डारखाल", "कोत",
        "राणा", "धोका", "गुपचुप", "कैदी", "खतरा", "आशङ्का",
        "conspiracy", "escape", "murder", "assassination", "secret", "plot", "intrigue",
        "betrayal", "poison", "fled", "danger", "revolt", "coup", "ambush", "suspense",
        "picnic", "prisoner"
    ],
}

# Curated, freely-licensed (CC0 / CC-BY / Public Domain) documentary music sources
TRACK_REGISTRY = {
    MOOD_TENSION: {
        "filename": "cinematic_ambient_tension.wav",
        "title": "Cinematic Ambient Tension",
        "url": "https://upload.wikimedia.org/wikipedia/commons/8/81/The_Escalation_%28ISRC_USUAN1400041%29.mp3",
        "fallback_filename": "tension_the_escalation.mp3",
    },
    MOOD_EPIC: {
        "filename": "epic_exotic_battle.mp3",
        "title": "Exotic Battle (Epic Historical War)",
        "url": "https://upload.wikimedia.org/wikipedia/commons/1/18/Exotic_Battle_%28ISRC_USUAN1100451%29.mp3",
    },
    MOOD_MYSTIC: {
        "filename": "mystic_nu_flute.ogg",
        "title": "Nu Flute (Mystical Ancient Lore)",
        "url": "https://upload.wikimedia.org/wikipedia/commons/1/14/Kevin_MacLeod_-_Nu_Flute.ogg",
    },
    MOOD_HERITAGE: {
        "filename": "heritage_art_of_silence.ogg",
        "title": "Art Of Silence (Heritage & Nostalgia)",
        "url": "https://upload.wikimedia.org/wikipedia/commons/5/52/Uniq_-_Art_Of_Silence_V2.ogg",
    },
    MOOD_TRIUMPHANT: {
        "filename": "triumphant_day_of_chaos.mp3",
        "title": "Day of Chaos (Triumphant Uprising & Revolution)",
        "url": "https://upload.wikimedia.org/wikipedia/commons/3/3a/Day_of_Chaos_%28ISRC_USUAN1300040%29.mp3",
    },
}


def detect_mood(topic: str | None = None, story: str | None = None, plan: dict | None = None) -> str:
    """Classify the emotional context and historical theme of the story into a musical mood."""
    combined_text = " ".join(filter(None, [
        topic or "",
        story or "",
        str(plan.get("angle", "")) if isinstance(plan, dict) else "",
        str(plan.get("reason", "")) if isinstance(plan, dict) else "",
        " ".join(plan.get("beats", [])) if isinstance(plan, dict) and isinstance(plan.get("beats"), list) else "",
    ])).lower()

    if not combined_text.strip():
        return MOOD_TENSION

    scores = {mood: 0 for mood in _MOOD_KEYWORDS}
    for mood, keywords in _MOOD_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in combined_text:
                scores[mood] += 1

    best_mood = max(scores, key=lambda m: scores[m])
    if scores[best_mood] > 0:
        return best_mood

    return MOOD_TENSION


def _catalog_path(music_dir: Path) -> Path:
    return music_dir / "catalog.json"


def _load_catalog(music_dir: Path) -> dict:
    cat_file = _catalog_path(music_dir)
    if cat_file.exists():
        try:
            return json.loads(cat_file.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read music catalog %s: %s", cat_file, exc)
    return {"tracks": []}


def _save_catalog(music_dir: Path, catalog: dict) -> None:
    cat_file = _catalog_path(music_dir)
    try:
        cat_file.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not write music catalog %s: %s", cat_file, exc)


def _find_local_track_for_mood(music_dir: Path, mood: str) -> str | None:
    """Check if an existing local file in music_dir matches the requested mood."""
    catalog = _load_catalog(music_dir)
    for item in catalog.get("tracks", []):
        if item.get("mood") == mood:
            target = music_dir / item.get("filename", "")
            if target.is_file() and target.stat().st_size > 1000:
                return str(target)

    # Check for direct filename matches (e.g. tension, epic, mystic, heritage, triumphant)
    mood_slug = mood.split("_")[0]
    for ext in (".mp3", ".wav", ".ogg", ".m4a"):
        for path in music_dir.glob(f"*{mood_slug}*{ext}"):
            if path.is_file() and path.stat().st_size > 1000:
                return str(path)

    # Also check the canonical filename from TRACK_REGISTRY
    entry = TRACK_REGISTRY.get(mood)
    if entry:
        preferred = music_dir / entry["filename"]
        if preferred.is_file() and preferred.stat().st_size > 1000:
            return str(preferred)

    return None


def _download_track(url: str, dest_path: Path) -> bool:
    """Download a royalty-free audio file with stream writing."""
    try:
        logger.info("Downloading background music for context from %s -> %s", url, dest_path.name)
        response = requests.get(url, headers=HTTP_HEADERS, timeout=30, stream=True)
        response.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        if dest_path.stat().st_size > 1000:
            return True
        dest_path.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to download background music from %s: %s", url, exc)
        dest_path.unlink(missing_ok=True)
    return False


def get_background_music(
    topic: str | None = None,
    story: str | None = None,
    plan: dict | None = None,
    music_dir: str | Path | None = None,
) -> str | None:
    """Find or download appropriate background music for the story context.

    1. Classifies the topic/story context into a musical mood.
    2. Checks music_dir for any existing local track matching that mood.
    3. If none exists, downloads the curated royalty-free track and registers it.
    4. Falls back to any available local audio file if download fails.
    """
    folder = Path(music_dir or settings.BACKGROUND_MUSIC_DIR)
    folder.mkdir(parents=True, exist_ok=True)

    mood = detect_mood(topic, story, plan)
    logger.info("Detected background music mood: %s", mood)

    local_track = _find_local_track_for_mood(folder, mood)
    if local_track:
        logger.info("Using cached background music for mood '%s': %s", mood, Path(local_track).name)
        return local_track

    # Not found locally: download the curated track for this mood
    registry_entry = TRACK_REGISTRY.get(mood)
    if registry_entry and registry_entry.get("url"):
        target_name = registry_entry["filename"]
        target_path = folder / target_name
        if _download_track(registry_entry["url"], target_path):
            catalog = _load_catalog(folder)
            catalog["tracks"].append({
                "filename": target_name,
                "mood": mood,
                "title": registry_entry.get("title", target_name),
                "url": registry_entry["url"],
            })
            _save_catalog(folder, catalog)
            logger.info("Successfully downloaded and cached background music for '%s': %s", mood, target_name)
            return str(target_path)

    # Fallback to any existing audio file in folder if download wasn't possible
    all_local = sorted(p for p in folder.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".m4a"))
    if all_local:
        chosen = str(all_local[0])
        logger.info("Falling back to available local background music: %s", Path(chosen).name)
        return chosen

    return None
