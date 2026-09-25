import json
from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from ..core.settings import settings
from ..utils.retry import retry


MAX_CHARACTERS = 4

CHARACTER_SHEET_PROMPT = """You are the production designer for a short historical documentary video about Nepal.
Read the story below (it may be in Nepali) and define how everything should look, so that every
separately generated video clip shows the same people in the same clothes.

Return ONLY a JSON object with this shape:
{{
  "style": "one paragraph: historical period, region, architecture, colour palette, lighting, camera style. Photorealistic and cinematic.",
  "supporting": "one paragraph: period-accurate clothing, armour and weapons of soldiers, courtiers and common people in this story.",
  "characters": [
    {{
      "id": "snake_case_id",
      "name": "name as it should be referred to",
      "description": "fixed physical appearance: sex, age, build, face, skin tone, hair and beard, clothing with exact colours, headwear, jewellery, weapons",
      "wikipedia_title": "exact English Wikipedia article title if this is a real, documented historical person who has an article; otherwise null"
    }}
  ]
}}

Rules:
- Write everything in English.
- Include at most {max_characters} main characters: the people who appear in more than one moment of the story.
- Be historically accurate to Nepal and South Asia for the period. No European armour or clothing.
- Descriptions must be concrete and visual; never describe personality.

Story:
{story}
"""

SCENE_PLAN_PROMPT = """You are directing a short historical documentary video. Below are the main characters
and a numbered list of narration scenes (the narration may be in Nepali). For each scene, choose which
main characters are visible on screen and describe one shot for it.

Characters:
{characters}

Scenes:
{scenes}

Return ONLY a JSON array with exactly {count} objects, in scene order:
[{{"characters": ["character_id", ...], "shot": "English, one or two sentences: who does what, where, and the camera movement", "clip": "video" or "image"}}]

Rules:
- Use only the character ids listed above; use an empty list when no main character is visible.
- This is a short-form social video: scene 1 is the hook and must be the most visually arresting shot,
  grabbing attention within the first second. Keep every shot visually distinct from the one before it,
  so each cut feels like a fresh image, while staying consistent with the story's setting.
- "clip": "video" when real motion matters to the moment (battle, chase, crowd, a ritual in action, a
  dramatic reveal); "image" when a still with a slow camera move tells it just as well (portraits,
  landscapes, documents, inscriptions, calm or reflective lines). Scene 1 is always "video". Aim for
  roughly a third to a half of the scenes as "video".
- No text, captions or signs in any shot.
"""


@lru_cache(maxsize=1)
def _get_llm() -> ChatGoogleGenerativeAI:
    settings.require("CHAT_MODEL", "GEMINI_API_KEY")
    return ChatGoogleGenerativeAI(
        model=settings.CHAT_MODEL,
        api_key=settings.GEMINI_API_KEY,
        response_mime_type="application/json",
    )


def _response_text(content) -> str:
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content)


def parse_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return json.loads(text)


def _ask_json(prompt: str):
    return parse_json(_response_text(_get_llm().invoke(prompt).content))


@retry(exceptions=(Exception,), max_attempts=3, delay_seconds=5)
def build_character_sheet(story: str) -> dict:
    sheet = _ask_json(CHARACTER_SHEET_PROMPT.format(story=story, max_characters=MAX_CHARACTERS))
    if not isinstance(sheet, dict) or not isinstance(sheet.get("characters"), list):
        raise ValueError(f"Character sheet has unexpected shape: {sheet!r}")
    sheet.setdefault("style", "")
    sheet.setdefault("supporting", "")
    sheet["characters"] = [c for c in sheet["characters"] if c.get("id") and c.get("description")][
        :MAX_CHARACTERS
    ]
    for character in sheet["characters"]:
        character.setdefault("name", character["id"])
        character["wikipedia_title"] = (character.get("wikipedia_title") or "").strip() or None
    return sheet


@retry(exceptions=(Exception,), max_attempts=3, delay_seconds=5)
def plan_scenes(scenes: list[str], sheet: dict) -> list[dict]:
    characters = "\n".join(
        f"- {c['id']}: {c['name']} - {c['description']}" for c in sheet["characters"]
    ) or "(none)"
    numbered = "\n".join(f"{idx + 1}. {scene}" for idx, scene in enumerate(scenes))
    plan = _ask_json(SCENE_PLAN_PROMPT.format(characters=characters, scenes=numbered, count=len(scenes)))
    if not isinstance(plan, list) or len(plan) != len(scenes):
        raise ValueError(f"Scene plan has {len(plan) if isinstance(plan, list) else 'no'} entries, expected {len(scenes)}")

    known_ids = {c["id"] for c in sheet["characters"]}
    return [
        {
            "characters": [cid for cid in entry.get("characters", []) if cid in known_ids],
            "shot": entry.get("shot") or scene,
            "clip": "video" if idx == 0 or entry.get("clip") == "video" else "image",
        }
        for idx, (entry, scene) in enumerate(zip(plan, scenes))
    ]


def _visible_characters(sheet: dict, scene_plan: dict) -> list[dict]:
    by_id = {c["id"]: c for c in sheet["characters"]}
    return [by_id[cid] for cid in scene_plan["characters"] if cid in by_id]


def build_frame_prompt(sheet: dict, scene_plan: dict) -> str:
    """Prompt for a scene's opening frame, drawn from the characters' reference images.

    Character descriptions are repeated verbatim in every scene so the image model
    gets identical wording alongside the same reference images."""
    visible = _visible_characters(sheet, scene_plan)
    lines = [
        "Vertical 9:16 photorealistic cinematic film still: the opening frame of a documentary shot. "
        "One single full-frame image - never a collage, grid, split screen or comic panels. "
        "No text, no captions, no watermark.",
        f"Style: {sheet['style']}",
    ]
    if visible:
        lines.append(
            "Characters (reference images are attached in this same order; each character must look "
            "exactly like their reference image: same face, hair, beard and clothing. A reference may "
            "be a painting or statue; always render the person as a real, living human):"
        )
        lines.extend(f"- {c['name']}: {c['description']}" for c in visible)
    other_people = "Everyone wears period-accurate clothing; no modern clothing."
    if sheet.get("supporting"):
        other_people = f"Other people in the scene: {sheet['supporting']} {other_people}"
    lines.append(other_people)
    lines.append(f"Shot: {scene_plan['shot']}")
    return "\n".join(lines)


def build_scene_prompt(sheet: dict, scene_plan: dict, seconds: int) -> str:
    """Prompt for animating a scene's opening frame into a clip."""
    visible = _visible_characters(sheet, scene_plan)
    lines = [
        f"Animate this opening frame into a {seconds}-second vertical 9:16 photorealistic cinematic shot "
        "with clear, purposeful motion from the very first frame. Keep every person looking exactly as "
        "in the frame. No text, no captions, no dialogue, no music.",
        f"Style: {sheet['style']}",
    ]
    if visible:
        lines.append("People in the shot: " + "; ".join(f"{c['name']} ({c['description']})" for c in visible))
    lines.append(f"Action and camera: {scene_plan['shot']}")
    return "\n".join(lines)
