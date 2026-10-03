import pytest

from aitihasik_katha.core.settings import settings
from aitihasik_katha.services import real_media_service
from aitihasik_katha.services.media_library import MediaLibrary


def _file(title, license_name="CC BY 4.0", width=3000, height=2000, size=900_000, mime="image/jpeg"):
    return {
        "title": f"File:{title}", "index": 1,
        "imageinfo": [{
            "url": f"https://upload.example/{title}", "thumburl": f"https://thumb.example/{title}",
            "width": width, "height": height, "size": size, "mime": mime,
            "descriptionurl": f"https://commons.example/{title}",
            "extmetadata": {
                "LicenseShortName": {"value": license_name},
                "Artist": {"value": "<a>A Photographer</a>"},
                "ImageDescription": {"value": "A swing at sunset"},
            },
        }],
    }


class _Response:
    def __init__(self, pages):
        self._pages = pages

    def json(self):
        return {"query": {"pages": {str(i): p for i, p in enumerate(self._pages)}}}


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("aitihasik_katha.utils.retry.time.sleep", lambda seconds: None)
    monkeypatch.setattr(settings, "REAL_MEDIA_ALLOW_SHAREALIKE", False)


def _wire(monkeypatch, images=(), videos=(), best=0):
    searches, downloads, picks = [], [], []

    def _get(url, headers=None, params=None, timeout=None):
        searches.append(params["gsrsearch"])
        return _Response(images if "bitmap" in params["gsrsearch"] else videos)

    monkeypatch.setattr(real_media_service.requests, "get", _get)
    monkeypatch.setattr(real_media_service, "_download", lambda url: downloads.append(url) or b"bytes")
    monkeypatch.setattr(real_media_service, "_fresh_thumb", lambda candidate: b"thumb")
    monkeypatch.setattr(
        real_media_service, "_pick", lambda candidates, thumbs, line, subject: picks.append([c["title"] for c in candidates]) or best
    )
    return searches, downloads, picks


def test_a_good_photo_is_downloaded_credited_and_kept_in_the_library(monkeypatch, tmp_path):
    searches, downloads, picks = _wire(monkeypatch, images=[_file("Linge Ping.jpg")])
    library = MediaLibrary(tmp_path)

    media = real_media_service.find_real_media("Linge Ping Dashain", "बाँसको पिङ", library=library)

    assert media.kind == "image"
    assert media.credit == '"Linge Ping.jpg" by A Photographer, CC BY 4.0, via Wikimedia Commons'
    assert downloads == ["https://thumb.example/Linge Ping.jpg"]  # a 2000px copy, not the 6000px original
    assert (tmp_path / "files" / "Linge_Ping.jpg").read_bytes() == b"bytes"
    assert library.for_query("linge ping dashain")[0].title == "Linge Ping.jpg"


def test_the_same_search_is_answered_from_the_library_without_the_network(monkeypatch, tmp_path):
    searches, downloads, picks = _wire(monkeypatch, images=[_file("Linge Ping.jpg")])
    library = MediaLibrary(tmp_path)
    real_media_service.find_real_media("Linge Ping Dashain", "x", library=library)
    searches.clear()
    downloads.clear()

    again = real_media_service.find_real_media("linge ping DASHAIN", "y", library=library)

    assert again.title == "Linge Ping.jpg"
    assert searches == [] and downloads == []


def test_a_photo_already_used_in_this_video_is_not_used_again(monkeypatch, tmp_path):
    _wire(monkeypatch, images=[_file("Linge Ping.jpg")])
    library = MediaLibrary(tmp_path)
    real_media_service.find_real_media("Linge Ping Dashain", "x", library=library)

    assert real_media_service.find_real_media("Linge Ping Dashain", "x", used={"Linge Ping.jpg"}, library=library) is None


@pytest.mark.parametrize("license_name", ["CC BY-SA 4.0", "CC BY-NC 2.0", "All rights reserved"])
def test_only_publishable_licences_are_considered(monkeypatch, tmp_path, license_name):
    _, _, picks = _wire(monkeypatch, images=[_file("A.jpg", license_name)])

    assert real_media_service.find_real_media("q", "x", library=MediaLibrary(tmp_path)) is None
    assert picks == []


def test_share_alike_photos_are_used_only_when_switched_on(monkeypatch, tmp_path):
    _wire(monkeypatch, images=[_file("A.jpg", "CC BY-SA 4.0")])
    monkeypatch.setattr(settings, "REAL_MEDIA_ALLOW_SHAREALIKE", True)

    assert real_media_service.find_real_media("q", "x", library=MediaLibrary(tmp_path)).title == "A.jpg"


def test_small_photos_and_wrong_formats_are_skipped(monkeypatch, tmp_path):
    _, _, picks = _wire(monkeypatch, images=[
        _file("small.jpg", width=800, height=600), _file("scan.tiff", mime="image/tiff"), _file("good.jpg"),
    ])

    real_media_service.find_real_media("q", "x", library=MediaLibrary(tmp_path))

    assert picks == [["good.jpg"]]


def test_nothing_is_used_when_the_model_finds_no_good_match(monkeypatch, tmp_path):
    _wire(monkeypatch, images=[_file("A.jpg"), _file("B.jpg")], best=None)
    library = MediaLibrary(tmp_path)

    assert real_media_service.find_real_media("q", "x", library=library) is None
    assert library.for_query("q") == []


def test_footage_is_downloaded_in_full_and_oversized_videos_are_skipped(monkeypatch, tmp_path):
    _, downloads, picks = _wire(monkeypatch, videos=[
        _file("Huge.webm", size=200_000_000, mime="video/webm"), _file("Festival.webm", size=9_000_000, mime="video/webm"),
    ])

    media = real_media_service.find_real_media("festival", "x", library=MediaLibrary(tmp_path))

    assert picks == [["Festival.webm"]]
    assert media.kind == "video"
    assert downloads == ["https://upload.example/Festival.webm"]
