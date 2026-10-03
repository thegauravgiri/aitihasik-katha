import pytest
from PIL import Image

from aitihasik_katha.services import thumbnail_service
from aitihasik_katha.services.title_card import title_layer

SCENES = ["पहिलो वाक्य यहाँ छ", "दोस्रो वाक्य", "तेस्रो वाक्य"]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("aitihasik_katha.utils.retry.time.sleep", lambda seconds: None)


def test_plan_cover_returns_the_title_highlight_and_zero_based_scene(monkeypatch):
    monkeypatch.setattr(
        thumbnail_service, "ask_json", lambda prompt: {"title": "राजा मर्छन् भने", "highlight": "मर्छन्", "scene": 2}
    )

    assert thumbnail_service.plan_cover(SCENES) == {"title": "राजा मर्छन् भने", "highlight": "मर्छन्", "scene": 1}


def test_plan_cover_numbers_the_scenes_for_the_model(monkeypatch):
    prompts = []
    monkeypatch.setattr(thumbnail_service, "ask_json", lambda prompt: prompts.append(prompt) or {"title": "क ख"})

    thumbnail_service.plan_cover(SCENES)

    assert "1. पहिलो वाक्य यहाँ छ" in prompts[0] and "3. तेस्रो वाक्य" in prompts[0]


def test_plan_cover_repairs_a_bad_reply(monkeypatch):
    monkeypatch.setattr(
        thumbnail_service,
        "ask_json",
        lambda prompt: {"title": "एक दुई तीन चार पाँच छ सात आठ नौ", "highlight": "छैन", "scene": 99},
    )

    cover = thumbnail_service.plan_cover(SCENES)

    assert cover["title"] == "एक दुई तीन चार पाँच छ सात"  # at most seven words
    assert cover["highlight"] is None  # not one of the title's words
    assert cover["scene"] == 0  # out of range


def test_plan_cover_falls_back_to_the_opening_line_when_the_model_fails(monkeypatch):
    def _broken(prompt):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(thumbnail_service, "ask_json", _broken)

    cover = thumbnail_service.plan_cover(["एक दुई तीन चार पाँच छ सात आठ", "अर्को"])

    assert cover == {"title": "एक दुई तीन चार पाँच छ", "highlight": None, "scene": 0}


def test_render_cover_makes_a_reel_sized_jpeg_with_the_title_on_it(tmp_path):
    frame = tmp_path / "frame.png"
    Image.new("RGB", (768, 1376), (30, 60, 110)).save(frame)
    out = tmp_path / "out" / "cover.jpg"

    thumbnail_service.render_cover(str(frame), "राजा मर्छन् भने", "मर्छन्", str(out))

    cover = Image.open(out)
    assert cover.format == "JPEG"
    assert cover.size == (1080, 1920)
    # The title area is much brighter than the plain dark frame behind it.
    centre = cover.crop((90, 1000, 990, 1300)).convert("L")
    assert max(centre.getdata()) > 200


def test_title_layer_fits_the_requested_width_and_uses_the_accent_colour():
    layer = title_layer("एक दुई तीन चार पाँच छ सात", "तीन", max_width=600, max_font_size=140)

    assert layer.mode == "RGBA"
    assert layer.width >= 600
    colours = {pixel[:3] for pixel in layer.getdata() if pixel[3] == 255}
    assert (0xF2, 0xB6, 0x32) in colours  # the highlighted word
    assert (255, 255, 255) in colours  # the rest of the title


def test_a_cover_title_with_letters_from_another_script_falls_back(monkeypatch):
    monkeypatch.setattr(thumbnail_service, "ask_json", lambda prompt: {"title": "दसैँ अधուրो कथा", "scene": 1})

    cover = thumbnail_service.plan_cover(["एक दुई तीन", "चार"])

    assert cover["title"] == "एक दुई तीन"
