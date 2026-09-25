import io
import json

import pytest
from PIL import Image

from aitihasik_katha.services import reference_service
from aitihasik_katha.services.reference_service import Portrait, is_publishable_license


KING = {"id": "king", "name": "King Prithvi Narayan Shah", "description": "guess",
        "wikipedia_title": "Prithvi Narayan Shah"}
ELDER = {"id": "elder", "name": "Village Elder", "description": "white beard", "wikipedia_title": None}


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.parametrize(
    "name, allowed",
    [
        ("Public domain", True),
        ("PD-old-100", True),
        ("CC0", True),
        ("CC BY 3.0", True),
        ("CC-BY-4.0", True),
        ("CC BY-SA 4.0", False),
        ("CC BY-NC 2.0", False),
        ("CC BY-ND 3.0", False),
        ("", False),
    ],
)
def test_is_publishable_license(name, allowed):
    assert is_publishable_license(name) is allowed


class _FakeResponse:
    def __init__(self, content=b""):
        self.content = content

    def raise_for_status(self):
        pass


@pytest.fixture
def stubs(monkeypatch):
    calls = {"generated": 0}

    def _generate_image(prompt):
        calls["generated"] += 1
        return _png_bytes()

    monkeypatch.setattr(reference_service, "generate_image", _generate_image)
    monkeypatch.setattr(reference_service.requests, "get", lambda *a, **k: _FakeResponse(_png_bytes()))
    monkeypatch.setattr(reference_service.settings, "USE_HISTORICAL_PORTRAITS", True)
    return calls


def _portrait():
    return Portrait("King.jpg", "https://upload.example/King.jpg", "Public domain", "Court Painter",
                    "https://commons.wikimedia.org/wiki/File:King.jpg")


def test_uses_real_portrait_and_its_description_when_it_shows_the_person(stubs, monkeypatch, tmp_path):
    monkeypatch.setattr(reference_service, "find_historical_portrait", lambda title: _portrait())
    monkeypatch.setattr(reference_service, "_assess_portrait",
                        lambda png, name: {"usable": True, "reason": "portrait", "description": "plumed crown"})

    ref = reference_service.resolve_reference(KING, "style", str(tmp_path / "ref_king.png"))

    assert ref.source == "wikimedia"
    assert ref.description == "plumed crown"
    assert '"King.jpg" by Court Painter, Public domain, via Wikimedia Commons' in ref.credit
    assert (tmp_path / "ref_king.png").exists()
    assert stubs["generated"] == 0


def test_falls_back_to_generated_image_when_portrait_does_not_show_the_person(stubs, monkeypatch, tmp_path):
    monkeypatch.setattr(reference_service, "find_historical_portrait", lambda title: _portrait())
    monkeypatch.setattr(reference_service, "_assess_portrait",
                        lambda png, name: {"usable": False, "reason": "it's a coin", "description": ""})

    ref = reference_service.resolve_reference(KING, "style", str(tmp_path / "ref_king.png"))

    assert ref.source == "generated"
    assert ref.credit is None and ref.description is None
    assert stubs["generated"] == 1


def test_generates_for_characters_without_a_wikipedia_article(stubs, monkeypatch, tmp_path):
    def _should_not_look_up(title):
        raise AssertionError("no lookup expected")

    monkeypatch.setattr(reference_service, "find_historical_portrait", _should_not_look_up)

    ref = reference_service.resolve_reference(ELDER, "style", str(tmp_path / "ref_elder.png"))

    assert ref.source == "generated"
    assert stubs["generated"] == 1


def test_lookup_errors_fall_back_to_generated_image(stubs, monkeypatch, tmp_path):
    def _boom(title):
        raise RuntimeError("wikipedia down")

    monkeypatch.setattr(reference_service, "find_historical_portrait", _boom)

    ref = reference_service.resolve_reference(KING, "style", str(tmp_path / "ref_king.png"))

    assert ref.source == "generated"


def test_resume_reuses_saved_choice(stubs, monkeypatch, tmp_path):
    image = tmp_path / "ref_king.png"
    image.write_bytes(_png_bytes())
    image.with_suffix(".json").write_text(json.dumps(
        {"image_path": str(image), "source": "wikimedia", "description": "saved", "credit": "c"}
    ))
    monkeypatch.setattr(reference_service, "find_historical_portrait",
                        lambda title: pytest.fail("should reuse the saved reference"))

    ref = reference_service.resolve_reference(KING, "style", str(image))

    assert ref.description == "saved"
    assert stubs["generated"] == 0


def test_find_historical_portrait_skips_share_alike_images(monkeypatch):
    responses = iter([
        {"query": {"pages": {"1": {"pageimage": "Statue.jpg"}}}},
        {"query": {"pages": {"2": {"imageinfo": [{"url": "u", "extmetadata": {
            "LicenseShortName": {"value": "CC BY-SA 3.0"}}}]}}}},
    ])

    class _Json:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

    monkeypatch.setattr(reference_service.requests, "get", lambda *a, **k: _Json(next(responses)))

    assert reference_service.find_historical_portrait("Someone") is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('<span class="fn">Unknown author</span><span>Unknown author</span>', "Unknown author"),
        ('<a href="/wiki/User:P">Proteasfanz</a> (<a href="/talk">talk</a>)', "Proteasfanz"),
        ("Dr John William Tyler", "Dr John William Tyler"),
    ],
)
def test_strip_html_cleans_commons_artist_markup(raw, expected):
    assert reference_service._strip_html(raw) == expected
