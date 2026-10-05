import pytest

from aitihasik_katha.services import character_service
from aitihasik_katha.services.character_service import build_frame_prompt, build_scene_prompt, parse_json


SHEET = {
    "style": "Malla-era Kathmandu, warm dusk light",
    "supporting": "soldiers with khukuris and red turbans",
    "characters": [
        {"id": "king", "name": "The King", "description": "grey beard, white topi, red robe"},
        {"id": "queen", "name": "The Queen", "description": "red sari, gold nose ring"},
    ],
}


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch):
    monkeypatch.setattr("aitihasik_katha.utils.retry.time.sleep", lambda seconds: None)


def test_parse_json_strips_markdown_fences():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('  [1, 2]  ') == [1, 2]


def test_build_frame_prompt_includes_only_visible_characters():
    prompt = build_frame_prompt(SHEET, {"characters": ["king"], "shot": "king on a balcony"})

    assert "9:16" in prompt
    assert "grey beard, white topi, red robe" in prompt
    assert "red sari" not in prompt
    assert "reference image" in prompt
    assert "soldiers with khukuris" in prompt and "no modern clothing" in prompt
    assert prompt.rstrip().endswith("Shot: king on a balcony")


def test_build_frame_prompt_without_characters_has_no_reference_instruction():
    prompt = build_frame_prompt(SHEET, {"characters": [], "shot": "misty valley"})
    assert "reference image" not in prompt


def test_build_scene_prompt_describes_the_motion_for_the_frame():
    prompt = build_scene_prompt(SHEET, {"characters": ["queen"], "shot": "queen walks to the temple"}, 6)

    assert "6-second" in prompt
    assert "red sari, gold nose ring" in prompt
    assert "grey beard" not in prompt
    assert prompt.rstrip().endswith("Action and camera: queen walks to the temple")


def test_build_character_sheet_caps_and_fills_characters(monkeypatch):
    raw = {
        "style": "s",
        "characters": [{"id": f"c{i}", "description": "d"} for i in range(6)] + [{"id": "", "description": "x"}],
    }
    monkeypatch.setattr(character_service, "_ask_json", lambda prompt: raw)

    sheet = character_service.build_character_sheet("story")

    assert [c["id"] for c in sheet["characters"]] == ["c0", "c1", "c2", "c3"]
    assert sheet["characters"][0]["name"] == "c0"
    assert sheet["supporting"] == ""


def test_plan_scenes_drops_unknown_character_ids(monkeypatch):
    monkeypatch.setattr(
        character_service,
        "_ask_json",
        lambda prompt: [{"characters": ["king", "ghost"], "shot": "s1"}, {"characters": [], "shot": ""}],
    )

    plan = character_service.plan_scenes(["scene one", "scene two"], SHEET)

    assert plan[0] == {"characters": ["king"], "shot": "s1", "clip": "video", "real_search": None}
    assert plan[1] == {"characters": [], "shot": "scene two", "clip": "image", "real_search": None}


def test_plan_scenes_keeps_the_real_photo_search_phrases(monkeypatch):
    monkeypatch.setattr(
        character_service,
        "_ask_json",
        lambda prompt: [{"shot": "a", "real_search": "  Patan Durbar Square "}, {"shot": "b", "real_search": ""}],
    )

    plan = character_service.plan_scenes(["x", "y"], SHEET)

    assert [p["real_search"] for p in plan] == ["Patan Durbar Square", None]


def test_frame_prompt_asks_for_the_dark_documentary_look():
    prompt = build_frame_prompt(SHEET, {"characters": [], "shot": "a lamp"})

    assert "Dark cinematic documentary" in prompt
    assert "Never bright, glossy, oversaturated" in prompt


def test_plan_scenes_makes_the_hook_video_and_normalises_clip(monkeypatch):
    monkeypatch.setattr(
        character_service,
        "_ask_json",
        lambda prompt: [{"shot": "a", "clip": "image"}, {"shot": "b", "clip": "video"}, {"shot": "c", "clip": "gif"}],
    )

    plan = character_service.plan_scenes(["x", "y", "z"], SHEET)

    assert [p["clip"] for p in plan] == ["video", "video", "image"]


def test_plan_scenes_retries_when_scene_count_is_wrong(monkeypatch):
    responses = iter([[{"characters": [], "shot": "only one"}], [{"shot": "a"}, {"shot": "b"}]])
    monkeypatch.setattr(character_service, "_ask_json", lambda prompt: next(responses))

    plan = character_service.plan_scenes(["x", "y"], SHEET)

    assert [p["shot"] for p in plan] == ["a", "b"]


def test_scene_planner_is_told_not_to_show_idols_or_worship_unless_the_line_is_about_it():
    assert "Do not show idols, shrines or worship" in character_service.SCENE_PLAN_PROMPT


def test_scene_planner_keeps_violent_moments_out_of_video_clips():
    assert "killing, sacrifice, injury" in character_service.SCENE_PLAN_PROMPT


def test_frame_prompt_supports_disney_style():
    prompt = build_frame_prompt(SHEET, {"characters": ["king"], "shot": "king on balcony"}, visual_style="disney")

    assert "Disney and Pixar 3D animated feature film" in prompt
    assert "subsurface scattering" in prompt
    assert "Disney & Pixar 3D Animation style" in prompt
    assert "Shot: king on balcony" in prompt


def test_frame_prompt_supports_anime_style():
    prompt = build_frame_prompt(SHEET, {"characters": [], "shot": "ancient temple"}, visual_style="anime")

    assert "Studio Ghibli" in prompt
    assert "Japanese 2D anime aesthetic" in prompt


def test_build_scene_prompt_supports_stylized_motion():
    prompt = build_scene_prompt(SHEET, {"characters": ["queen"], "shot": "queen turns"}, 4, visual_style="disney")

    assert "Disney-Pixar character animation" in prompt
    assert "4-second" in prompt
