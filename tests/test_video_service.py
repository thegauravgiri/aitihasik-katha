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


def test_merge_omits_hook_title_by_default(tmp_path):
    from aitihasik_katha.services.video_service import merge_video_clips

    clips = []
    for idx in range(2):
        path = str(tmp_path / f"video_clip_{idx}.mp4")
        ColorClip(size=(720, 1280), color=(20, 30, 60), duration=2).write_videofile(
            path, fps=24, codec="libx264", logger=None
        )
        clips.append(path)
    output = str(tmp_path / "final_clean.mp4")

    merge_video_clips(output, clip_filenames=clips, hook_title={"title": "राजा मर्छन् भने", "highlight": "मर्छन्"})

    video = VideoFileClip(output)
    try:
        assert video.duration == pytest.approx(4, abs=0.2)
        # By default, hook title is omitted for a clean cinematic look
        title_frame = video.get_frame(0.5)[100:420].astype(int)
        assert title_frame.max() < 100
    finally:
        video.close()


def test_merge_shows_the_hook_title_when_enabled(tmp_path):
    from aitihasik_katha.services.video_service import HOOK_TITLE_SECONDS, merge_video_clips

    clips = []
    for idx in range(2):
        path = str(tmp_path / f"video_clip_{idx}.mp4")
        ColorClip(size=(720, 1280), color=(20, 30, 60), duration=2).write_videofile(
            path, fps=24, codec="libx264", logger=None
        )
        clips.append(path)
    output = str(tmp_path / "final_with_title.mp4")

    merge_video_clips(output, clip_filenames=clips, hook_title={"title": "राजा मर्छन् भने", "highlight": "मर्छन्"}, show_hook_title=True)

    video = VideoFileClip(output)
    try:
        assert video.duration == pytest.approx(4, abs=0.2)
        title_frame = video.get_frame(0.5)[100:420].astype(int)  # the title sits in the top fifth
        later_frame = video.get_frame(HOOK_TITLE_SECONDS + 0.8)[100:420].astype(int)
        assert title_frame.max() > 200  # white title text over a dark clip
        assert later_frame.max() < 100  # gone again after the opening seconds
    finally:
        video.close()


def _pixel_spread(frame):
    return int(frame.astype(int).max() - frame.astype(int).min())


def test_a_wide_photo_is_panned_across_so_its_subject_is_not_cropped_away(tmp_path):
    from aitihasik_katha.services.video_service import animate_still

    # Red on the left, blue on the right: a centre crop would show neither end.
    image = Image.new("RGB", (1800, 1000), (0, 0, 0))
    image.paste((230, 20, 20), (0, 0, 300, 1000))
    image.paste((20, 20, 230), (1500, 0, 1800, 1000))
    path = str(tmp_path / "wide.png")
    image.save(path)
    output = str(tmp_path / "pan.mp4")

    animate_still(path, 2.0, output, motion="pan_right")

    clip = VideoFileClip(output)
    try:
        assert tuple(clip.size) == (720, 1280)
        first, last = clip.get_frame(0.05).astype(int), clip.get_frame(1.9).astype(int)
        assert first[..., 0].max() > 150 > first[..., 2].max()  # starts on the red end
        assert last[..., 2].max() > 150 > last[..., 0].max()  # ends on the blue end
    finally:
        clip.close()


def test_every_motion_makes_a_valid_reel_clip(tmp_path):
    from aitihasik_katha.services.video_service import MOTIONS, animate_still

    image = str(tmp_path / "tall.png")
    Image.new("RGB", (576, 1024), (60, 80, 120)).save(image)
    for motion in MOTIONS:
        output = str(tmp_path / f"{motion}.mp4")
        animate_still(image, 1.0, output, motion=motion)
        clip = VideoFileClip(output)
        try:
            assert tuple(clip.size) == (720, 1280) and clip.duration == pytest.approx(1.0, abs=0.1)
        finally:
            clip.close()


def test_real_wide_footage_is_shown_whole_over_a_blurred_copy(tmp_path):
    from aitihasik_katha.services.video_service import real_video_clip

    source = str(tmp_path / "wide.mp4")
    ColorClip(size=(640, 360), color=(240, 240, 240), duration=2).write_videofile(source, fps=24, codec="libx264", logger=None)
    output = str(tmp_path / "real.mp4")

    real_video_clip(source, 1.5, output)

    clip = VideoFileClip(output)
    try:
        assert tuple(clip.size) == (720, 1280) and clip.duration == pytest.approx(1.5, abs=0.1)
        frame = clip.get_frame(0.5).astype(int)
        assert frame[640, 360].min() > 200  # the footage fills the middle
        assert frame[40, 360].max() < 160  # the blurred, darkened copy above it
    finally:
        clip.close()


def test_the_film_look_can_be_switched_off(tmp_path, monkeypatch):
    from aitihasik_katha.core.settings import settings
    from aitihasik_katha.services.video_service import animate_still

    image = str(tmp_path / "flat.png")
    Image.new("RGB", (576, 1024), (120, 120, 120)).save(image)
    monkeypatch.setattr(settings, "FILM_LOOK", False)
    plain = str(tmp_path / "plain.mp4")
    animate_still(image, 1.0, plain, motion="zoom_in")
    monkeypatch.setattr(settings, "FILM_LOOK", True)
    graded = str(tmp_path / "graded.mp4")
    animate_still(image, 1.0, graded, motion="zoom_in")

    plain_clip, graded_clip = VideoFileClip(plain), VideoFileClip(graded)
    try:
        flat_frame, look_frame = plain_clip.get_frame(0.5), graded_clip.get_frame(0.5)
        assert _pixel_spread(flat_frame[400:880, 100:620]) < 6  # flat grey
        assert _pixel_spread(look_frame[400:880, 100:620]) > 6  # grain
        assert look_frame[10, 10].mean() < look_frame[640, 360].mean()  # darker corners (vignette)
    finally:
        plain_clip.close()
        graded_clip.close()


def test_merge_adds_the_channel_mark_and_the_follow_tag(tmp_path, monkeypatch):
    from aitihasik_katha.core.settings import settings
    from aitihasik_katha.services.video_service import FOLLOW_TAG_SECONDS, merge_video_clips

    monkeypatch.setattr(settings, "CHANNEL_HANDLE", "@aitihasik_katha")

    clips = []
    for idx in range(2):
        path = str(tmp_path / f"video_clip_{idx}.mp4")
        ColorClip(size=(720, 1280), color=(10, 10, 10), duration=4).write_videofile(path, fps=24, codec="libx264", logger=None)
        clips.append(path)
    output = str(tmp_path / "branded.mp4")

    merge_video_clips(output, clip_filenames=clips, branding=True)

    video = VideoFileClip(output)
    try:
        mark_area = video.get_frame(4.0)[130:200, 20:380].astype(int)  # top left, after the opening seconds
        tag_area = video.get_frame(video.duration - 0.8)[1000:1100, 60:660].astype(int)
        before_tag = video.get_frame(video.duration - FOLLOW_TAG_SECONDS - 1)[1000:1100, 60:660].astype(int)
        assert mark_area.max() > 120
        assert tag_area.max() > 150
        assert before_tag.max() < 60
    finally:
        video.close()


def test_background_music_is_mixed_under_the_voice_not_instead_of_it(tmp_path):
    import numpy as np
    from moviepy import AudioArrayClip, AudioFileClip

    from aitihasik_katha.services.video_service import merge_video_clips

    clip = str(tmp_path / "video_clip_0.mp4")
    ColorClip(size=(720, 1280), color=(10, 10, 10), duration=2).write_videofile(clip, fps=24, codec="libx264", logger=None)
    rate = 44100
    tone = lambda hz: np.sin(2 * np.pi * hz * np.arange(rate * 2) / rate)[:, None].repeat(2, 1) * 0.5  # noqa: E731
    voice, music = str(tmp_path / "voice.wav"), str(tmp_path / "music.wav")
    AudioArrayClip(tone(440), fps=rate).write_audiofile(voice, logger=None)
    AudioArrayClip(tone(880), fps=rate).write_audiofile(music, logger=None)
    output = str(tmp_path / "mixed.mp4")

    merge_video_clips(output, voice_over=voice, clip_filenames=[clip], background_music=music)

    mixed = AudioFileClip(output).to_soundarray(fps=rate)[:, 0]
    spectrum = np.abs(np.fft.rfft(mixed))
    freqs = np.fft.rfftfreq(len(mixed), 1 / rate)
    voice_power, music_power = spectrum[np.argmin(abs(freqs - 440))], spectrum[np.argmin(abs(freqs - 880))]
    assert voice_power > 0 and music_power > 0  # both are there
    assert music_power < voice_power * 0.3  # the music stays quiet


def test_there_is_no_corner_mark_by_default_but_the_follow_tag_still_shows(tmp_path):
    from aitihasik_katha.core.settings import settings
    from aitihasik_katha.services.video_service import merge_video_clips

    assert settings.CHANNEL_HANDLE == ""
    clips = []
    for idx in range(2):
        path = str(tmp_path / f"video_clip_{idx}.mp4")
        ColorClip(size=(720, 1280), color=(10, 10, 10), duration=4).write_videofile(path, fps=24, codec="libx264", logger=None)
        clips.append(path)
    output = str(tmp_path / "plain.mp4")

    merge_video_clips(output, clip_filenames=clips, branding=True)

    video = VideoFileClip(output)
    try:
        assert video.get_frame(4.0)[130:200, 20:380].max() < 60  # nothing in the corner
        assert video.get_frame(video.duration - 0.8)[1000:1100, 60:660].max() > 150  # follow line at the end
    finally:
        video.close()


def test_apply_cinematic_transitions_preserves_total_duration(tmp_path):
    from aitihasik_katha.services.video_service import apply_cinematic_transitions, concatenate_videoclips

    c1 = ColorClip(size=(100, 100), color=(200, 20, 20), duration=2.0)
    c2 = ColorClip(size=(100, 100), color=(20, 200, 20), duration=2.0)
    c3 = ColorClip(size=(100, 100), color=(20, 20, 200), duration=2.0)

    transitioned = apply_cinematic_transitions([c1, c2, c3], style="dissolve", duration=0.25)
    assert len(transitioned) == 3

    final = concatenate_videoclips(transitioned)
    try:
        assert final.duration == pytest.approx(6.0, abs=0.01)
        # Verify boundary transition: c1 fades at t=1.95, c2 fades in at t=2.05
        mid_before = final.get_frame(1.95)
        assert mid_before[50, 50, 0] < 200  # faded down
        mid_after = final.get_frame(2.05)
        assert mid_after[50, 50, 1] < 200  # fading in
    finally:
        final.close()
        for c in (c1, c2, c3):
            c.close()


def test_apply_cinematic_transitions_disabled_when_style_is_none():
    from aitihasik_katha.services.video_service import apply_cinematic_transitions

    c1 = ColorClip(size=(100, 100), color=(200, 20, 20), duration=2.0)
    c2 = ColorClip(size=(100, 100), color=(20, 200, 20), duration=2.0)

    result = apply_cinematic_transitions([c1, c2], style="none")
    assert result == [c1, c2]
    c1.close()
    c2.close()


def test_build_reels_caption_clip_produces_clean_subtitle():
    from aitihasik_katha.services.video_service import _build_reels_caption_clip

    caption = _build_reels_caption_clip("गोरखा दरबार", start_time=0.5, end_time=2.0, video_w=720, video_h=1280)
    try:
        assert caption.duration == pytest.approx(1.5, abs=0.05)
        assert tuple(caption.size) == (720, 1280)
    finally:
        caption.close()
