import pytest
from moviepy import ColorClip, VideoFileClip
from PIL import Image

from aitihasik_katha.services.video_service import animate_still, fit_clip_to_duration, format_text


def test_format_text_wraps_after_five_words():
    result = format_text("one two three four five six seven")
    assert result == " one two three four five \n six seven "


def test_format_text_normalizes_whitespace_and_newlines():
    result = format_text(" hello   world \n")
    assert result == " hello world "


def test_format_text_short_text_is_not_wrapped():
    result = format_text("a b c")
    assert result == " a b c "


@pytest.fixture
def landscape_clip(tmp_path):
    """A 2s 16:9 clip, like the model sometimes returns."""
    path = str(tmp_path / "raw.mp4")
    ColorClip(size=(320, 180), color=(200, 30, 30), duration=2).write_videofile(
        path, fps=24, codec="libx264", logger=None
    )
    return path


@pytest.mark.parametrize("target", [1.0, 3.5])
def test_fit_clip_to_duration_trims_or_stretches_to_exact_reel_clip(landscape_clip, tmp_path, target):
    output = str(tmp_path / "fitted.mp4")

    fit_clip_to_duration(landscape_clip, target, output)

    clip = VideoFileClip(output)
    try:
        assert clip.duration == pytest.approx(target, abs=0.1)
        assert tuple(clip.size) == (720, 1280)
        assert clip.audio is None
    finally:
        clip.close()


@pytest.mark.parametrize("zoom_in", [True, False])
def test_animate_still_makes_an_exact_length_silent_reel_clip(tmp_path, zoom_in):
    image = str(tmp_path / "frame.png")
    Image.new("RGB", (400, 700), (40, 90, 160)).save(image)
    output = str(tmp_path / "still.mp4")

    animate_still(image, 2.5, output, zoom_in=zoom_in)

    clip = VideoFileClip(output)
    try:
        assert clip.duration == pytest.approx(2.5, abs=0.1)
        assert tuple(clip.size) == (720, 1280)
        assert clip.audio is None
    finally:
        clip.close()
