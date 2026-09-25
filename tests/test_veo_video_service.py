from types import SimpleNamespace

import pytest

from aitihasik_katha.services import veo_video_service
from aitihasik_katha.services.veo_video_service import veo_duration


@pytest.mark.parametrize(
    "seconds, expected",
    [(0.6, 4), (3.2, 4), (4.0, 4), (4.1, 6), (6.0, 6), (7.5, 8), (8.0, 8), (11.0, 8)],
)
def test_veo_duration_picks_shortest_allowed_clip_that_covers_the_scene(seconds, expected):
    assert veo_duration(seconds) == expected


class _FakeVideo:
    def save(self, path):
        with open(path, "wb") as f:
            f.write(b"mp4-bytes")


def _operation(done, error=None, videos=None, filtered=None):
    response = SimpleNamespace(
        generated_videos=[SimpleNamespace(video=_FakeVideo())] * (videos or 0),
        rai_media_filtered_reasons=filtered,
    )
    return SimpleNamespace(done=done, error=error, response=response)


class _FakeClient:
    def __init__(self, polls):
        self._polls = iter(polls)
        self.requests = []
        self.models = SimpleNamespace(generate_videos=self._generate)
        self.operations = SimpleNamespace(get=lambda op: next(self._polls))
        self.files = SimpleNamespace(download=lambda file: None)

    def _generate(self, **kwargs):
        self.requests.append(kwargs)
        return next(self._polls)


@pytest.fixture
def fast(monkeypatch):
    monkeypatch.setattr(veo_video_service.time, "sleep", lambda s: None)
    monkeypatch.setattr("aitihasik_katha.utils.retry.time.sleep", lambda s: None)


def _use(monkeypatch, client):
    monkeypatch.setattr(veo_video_service, "get_genai_client", lambda: client)
    return client


def test_generate_scene_clip_polls_until_done_and_saves_video(fast, monkeypatch, tmp_path):
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"png")
    client = _use(monkeypatch, _FakeClient([_operation(False), _operation(False), _operation(True, videos=1)]))

    out = veo_video_service.generate_scene_clip("prompt", str(frame), 6, str(tmp_path / "clip.mp4"))

    assert (tmp_path / "clip.mp4").read_bytes() == b"mp4-bytes"
    assert out == str(tmp_path / "clip.mp4")
    config = client.requests[0]["config"]
    assert (config.aspect_ratio, config.duration_seconds, config.resolution) == ("9:16", 6, "720p")
    assert client.requests[0]["source"].image.image_bytes == b"png"


def test_filtered_generation_is_retried_then_raises(fast, monkeypatch, tmp_path):
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"png")
    _use(monkeypatch, _FakeClient([_operation(True, filtered=["unsafe"])] * 4))

    with pytest.raises(RuntimeError, match="returned no video"):
        veo_video_service.generate_scene_clip("prompt", str(frame), 4, str(tmp_path / "clip.mp4"))


def test_operation_error_raises(fast, monkeypatch, tmp_path):
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"png")
    _use(monkeypatch, _FakeClient([_operation(True, error={"message": "boom"})] * 4))

    with pytest.raises(RuntimeError, match="boom"):
        veo_video_service.generate_scene_clip("prompt", str(frame), 4, str(tmp_path / "clip.mp4"))


def test_stuck_operation_times_out(fast, monkeypatch, tmp_path):
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"png")
    _use(monkeypatch, _FakeClient([_operation(False)] * 50))
    clock = iter(range(0, 10_000, 100))
    monkeypatch.setattr(veo_video_service.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(veo_video_service.settings, "GENAI_REQUEST_TIMEOUT_SECONDS", 250)
    monkeypatch.setattr(veo_video_service, "_generate_video", veo_video_service._generate_video.__wrapped__)

    with pytest.raises(TimeoutError):
        veo_video_service.generate_scene_clip("prompt", str(frame), 4, str(tmp_path / "clip.mp4"))


def test_invalid_request_is_not_retried(fast, monkeypatch, tmp_path):
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"png")
    calls = []

    def _reject(**kwargs):
        calls.append(kwargs)
        raise veo_video_service.errors.ClientError(
            400, {"error": {"code": 400, "message": "`x` isn't supported", "status": "INVALID_ARGUMENT"}}
        )

    client = _use(monkeypatch, _FakeClient([]))
    client.models = SimpleNamespace(generate_videos=_reject)

    with pytest.raises(veo_video_service.errors.ClientError):
        veo_video_service.generate_scene_clip("prompt", str(frame), 4, str(tmp_path / "clip.mp4"))
    assert len(calls) == 1
