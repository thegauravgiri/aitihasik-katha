import math
import os
import re
from pathlib import Path
from typing import Iterable

import numpy as np
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
    afx,
    vfx,
)
from moviepy.video.tools.subtitles import file_to_subtitles

from ..core.logging import get_logger
from ..core.settings import settings
from .title_card import plain_layer, title_layer


logger = get_logger(__name__)


def format_text(text: str) -> str:
    text = text.strip().replace("\n", " ")
    words = text.split()
    formatted_text = ""
    while len(words) > 5:
        first_part = " ".join(words[:5])
        formatted_text += f" {first_part} \n"
        words = words[5:]
    formatted_text += f" {' '.join(words)} "
    return formatted_text


REEL_SIZE = (720, 1280)


def _cover(clip, size: tuple[int, int]):
    """Scale to fill `size` and center-crop the overflow, preserving aspect ratio."""
    target_w, target_h = size
    scale = max(target_w / clip.w, target_h / clip.h)
    resized = clip.resized(scale)
    return resized.cropped(
        x_center=resized.w / 2, y_center=resized.h / 2, width=target_w, height=target_h
    )


def _vignette(size: tuple[int, int]) -> np.ndarray:
    w, h = size
    y, x = np.ogrid[:h, :w]
    distance = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2)
    return (1 - 0.34 * np.clip(distance - 0.45, 0, 1) ** 1.6)[..., None].astype(np.float32)


def _with_film_look(clip):
    """Fine grain, a soft vignette and a little contrast, so every shot looks like part of one film."""
    if not settings.FILM_LOOK:
        return clip
    vignette = _vignette(tuple(clip.size))
    rng = np.random.default_rng(7)

    def _look(frame):
        graded = (frame.astype(np.float32) - 128) * 1.07 + 128
        graded = graded * vignette + rng.normal(0, 3.2, frame.shape[:2] + (1,))
        return np.clip(graded, 0, 255).astype(np.uint8)

    return clip.image_transform(_look)


MOTIONS = ("zoom_in", "pan_right", "zoom_out", "pan_left")


def animate_still(
    image_path: str,
    duration: float,
    output_path: str,
    zoom_in: bool = True,
    size: tuple[int, int] = REEL_SIZE,
    motion: str | None = None,
) -> str:
    """A `duration`-second silent clip of a still image with a slow, eased camera move.

    `motion` is one of MOTIONS; without it `zoom_in` picks between a slow zoom in and out. A wide
    photo (landscape) is always shown by panning across it, so its subject is not cropped away.
    """
    motion = motion or ("zoom_in" if zoom_in else "zoom_out")
    target_w, target_h = size
    source = ImageClip(image_path)
    wide = source.w / source.h > 0.8

    def _eased(t: float) -> float:
        progress = min(1.0, max(0.0, t / duration))
        return progress * progress * (3 - 2 * progress)

    if wide:
        scale = max(target_w / source.w, target_h * 1.1 / source.h)
        scaled = source.resized(scale).with_duration(duration)
        travel_x, travel_y = scaled.w - target_w, scaled.h - target_h
        rightwards = motion in ("pan_right", "zoom_in")
        moving = scaled.with_position(
            lambda t: (-travel_x * (_eased(t) if rightwards else 1 - _eased(t)), -travel_y * (0.5 + 0.15 * (_eased(t) - 0.5)))
        )
    else:
        still = _cover(source.with_duration(duration), size)
        zoom = 0.15
        zooming_in = motion != "zoom_out"

        def _scale(t: float) -> float:
            return 1 + zoom * _eased(t) if zooming_in else 1 + zoom * (1 - _eased(t))

        moving = still.with_effects([vfx.Resize(_scale)]).with_position(("center", "center"))
    clip = _with_film_look(CompositeVideoClip([moving], size=size).with_duration(duration))
    try:
        clip.write_videofile(output_path, codec="libx264", fps=24, audio=False, logger=None)
    finally:
        clip.close()
        source.close()
    return output_path


def real_video_clip(
    input_path: str, duration: float, output_path: str, size: tuple[int, int] = REEL_SIZE
) -> str:
    """A `duration`-second silent vertical clip of real footage. Wide footage is shown whole over a
    darkened, blurred copy of itself instead of being cropped to its middle."""
    clip = VideoFileClip(input_path, audio=False)
    try:
        if clip.duration >= duration:
            fitted = clip.subclipped(0, duration)
        else:
            fitted = clip.with_effects([vfx.MultiplySpeed(final_duration=duration)])
        if fitted.w / fitted.h > 0.8:
            background = _cover(fitted, size).resized((size[0] // 16, size[1] // 16)).resized(size)
            background = background.with_effects([vfx.MultiplyColor(0.5)])
            foreground = fitted.resized(width=size[0]).with_position(("center", "center"))
            composed = CompositeVideoClip([background, foreground], size=size).with_duration(duration)
        else:
            composed = _cover(fitted, size) if tuple(fitted.size) != tuple(size) else fitted
        _with_film_look(composed).write_videofile(output_path, codec="libx264", fps=24, audio=False, logger=None)
    finally:
        clip.close()
    return output_path


def fit_clip_to_duration(
    input_path: str, duration: float, output_path: str, size: tuple[int, int] = REEL_SIZE
) -> str:
    """Make a generated clip exactly `duration` seconds long, silent, and `size` pixels.

    Longer clips are cut; shorter ones are slowed down rather than looped or frozen.
    The model's own soundtrack is dropped since the narration replaces it.
    """
    clip = VideoFileClip(input_path, audio=False)
    try:
        if clip.duration >= duration:
            fitted = clip.subclipped(0, duration)
        else:
            fitted = clip.with_effects([vfx.MultiplySpeed(final_duration=duration)])
        if tuple(fitted.size) != tuple(size):
            fitted = _cover(fitted, size)
        _with_film_look(fitted).write_videofile(output_path, codec="libx264", fps=24, audio=False, logger=None)
    finally:
        clip.close()
    return output_path


def _build_reels_caption_clip(text: str, start_time: float, end_time: float, video_w: int, video_h: int):
    duration = max(0.1, float(end_time) - float(start_time))
    caption_text = format_text(text).upper()
    caption_font = str(Path("data/fonts/NotoSerifDevanagari-ExtraBold.ttf"))

    font_size = max(48, int(video_w * 0.076))
    max_text_width = int(video_w * 0.88)
    caption_box_h = int(video_h * 0.22)

    text_kwargs = dict(
        text=caption_text,
        method="caption",
        size=(max_text_width, caption_box_h),
        font=caption_font,
        margin=(16, 16),
        font_size=font_size,
        text_align="center",
        horizontal_align="center",
        vertical_align="center",
        transparent=True,
        interline=6,
        duration=duration,
    )

    # Clean high-contrast documentary typography: crisp dark drop shadow + bold white text with sharp dark outline
    shadow = TextClip(**text_kwargs, color="black", stroke_color="black", stroke_width=6).with_opacity(0.40).with_position((3, 3))
    main = TextClip(**text_kwargs, color="#ffffff", stroke_color="#0b1020", stroke_width=4)

    def _bump_scale(t: float) -> float:
        pop_duration = 0.12
        if t >= pop_duration:
            return 1.0
        p = t / pop_duration
        return 0.95 + 0.05 * p

    pad = max(20, int(font_size * 0.8))
    layer_w = max(shadow.w, main.w)
    layer_h = max(shadow.h, main.h)
    canvas_size = (layer_w + 2 * pad, layer_h + 2 * pad)

    animated_caption = CompositeVideoClip(
        [
            shadow.with_position(("center", "center")),
            main.with_position(("center", "center")),
        ],
        size=canvas_size,
        bg_color=None,
    ).with_effects([vfx.Resize(_bump_scale)])

    # Position in the lower-middle safe zone (above native social captions and controls)
    target_center_y = int(video_h * 0.65)
    caption_y = max(0, target_center_y - (animated_caption.h // 2))

    full_frame_caption = CompositeVideoClip(
        [animated_caption.with_position(("center", caption_y))],
        size=(video_w, video_h),
        bg_color=None,
    )
    return full_frame_caption.with_start(start_time).with_end(end_time)


HOOK_TITLE_SECONDS = 2.4
FOLLOW_TAG_SECONDS = 2.6


def _build_branding_clips(duration: float, video_w: int, video_h: int) -> list:
    """A small channel handle in the corner from the 3rd second on, and a "follow" line over the
    closing seconds. Both sit clear of Instagram's buttons and caption."""
    clips = []
    if settings.CHANNEL_HANDLE and duration > 5:
        handle = plain_layer(settings.CHANNEL_HANDLE, int(video_w * 0.5), int(video_w * 0.042), stroke=2)
        clips.append(
            ImageClip(np.array(handle)).with_opacity(0.8).with_start(HOOK_TITLE_SECONDS + 0.4)
            .with_end(duration).with_position((int(video_w * 0.04), int(video_h * 0.115)))
        )
    if settings.FOLLOW_TAG and duration > FOLLOW_TAG_SECONDS + 4:
        tag = plain_layer(settings.FOLLOW_TAG, int(video_w * 0.8), int(video_w * 0.05), fill="#F2B632", stroke=3)
        clips.append(
            ImageClip(np.array(tag)).with_start(duration - FOLLOW_TAG_SECONDS).with_end(duration)
            .with_position(("center", int(video_h * 0.8))).with_effects([vfx.CrossFadeIn(0.3)])
        )
    return clips


def _build_hook_title_clip(title: str, highlight: str | None, video_w: int, video_h: int):
    """The cover title shown over the opening seconds, for viewers watching without sound."""
    layer = title_layer(title, highlight, max_width=int(video_w * 0.86), max_font_size=int(video_w * 0.13))
    clip = ImageClip(np.array(layer)).with_duration(HOOK_TITLE_SECONDS)
    clip = clip.with_position(("center", int(video_h * 0.2) - layer.height // 2))
    return clip.with_effects([vfx.CrossFadeOut(0.35)])


def apply_cinematic_transitions(
    clips: list, style: str | None = None, duration: float | None = None
) -> list:
    """Apply smooth transitions between consecutive scene clips.

    'dissolve' (or 'dip_to_black') applies a soft fade-out and fade-in at scene boundaries,
    eliminating jarring jump cuts while preserving exact clip timing and audio synchronization.
    """
    style = settings.TRANSITION_STYLE if style is None else style
    duration = settings.TRANSITION_DURATION if duration is None else duration

    if style in ("none", "", None) or duration <= 0 or len(clips) <= 1:
        return clips

    result = []
    n = len(clips)
    for i, clip in enumerate(clips):
        effects = []
        clip_dur = getattr(clip, "duration", None)
        eff_dur = min(duration, clip_dur / 2.5) if clip_dur else duration
        if i > 0 and style in ("dissolve", "dip_to_black"):
            effects.append(vfx.FadeIn(eff_dur))
        if i < n - 1 and style in ("dissolve", "dip_to_black"):
            effects.append(vfx.FadeOut(eff_dur))
        result.append(clip.with_effects(effects) if effects else clip)
    return result


def merge_video_clips(
    output_path: str | None = None,
    voice_over: str | None = None,
    subtitles: str | Iterable[tuple[tuple[float, float], str]] | None = None,
    background_music: str | None = None,
    clip_filenames: list[str] | None = None,
    video_path: str = "",
    hook_title: dict | None = None,
    branding: bool = False,
    show_hook_title: bool | None = None,
    transition_style: str | None = None,
    transition_duration: float | None = None,
) -> str | None:
    if clip_filenames:
        videos = [v for v in clip_filenames if v.lower().endswith(".mp4")]
    else:
        videos = [v for v in video_path if v.lower().endswith(".mp4")]

    def _video_sort_key(video_name: str):
        stem = os.path.splitext(video_name)[0]
        match = re.search(r"(\d+)$", stem)
        index = int(match.group(1)) if match else float("inf")
        return (index, stem)

    videos = sorted(videos, key=_video_sort_key)
    if not videos:
        logger.warning("No video clips found. Skipping merge")
        return None

    logger.info("Merging %s video clip(s)", len(videos))

    video_clips = []
    for video in videos:
        try:
            video_clips.append(VideoFileClip(video))
        except (OSError, ValueError) as exc:
            logger.error("Error occurred while loading clip '%s': %s", video, exc)

    if not video_clips:
        logger.warning("No valid video clips could be loaded. Skipping merge")
        return None

    video_clips = apply_cinematic_transitions(video_clips, style=transition_style, duration=transition_duration)
    final_clip = concatenate_videoclips(video_clips)
    voice_clip = None
    bgm_clip = None

    if voice_over:
        voice_clip = AudioFileClip(voice_over)
        final_clip = final_clip.with_audio(voice_clip)

    overlays = []
    if subtitles:
        subtitle_items = file_to_subtitles(subtitles) if isinstance(subtitles, (str, os.PathLike)) else subtitles
        overlays = [
            _build_reels_caption_clip(text, start, end, final_clip.w, final_clip.h)
            for (start, end), text in subtitle_items
        ]
    should_show_hook = settings.SHOW_HOOK_TITLE if show_hook_title is None else show_hook_title
    if hook_title and hook_title.get("title") and should_show_hook:
        overlays.append(_build_hook_title_clip(hook_title["title"], hook_title.get("highlight"), final_clip.w, final_clip.h))
    if branding:
        overlays.extend(_build_branding_clips(final_clip.duration, final_clip.w, final_clip.h))
    if overlays:
        final_clip = CompositeVideoClip([final_clip, *overlays])

    if background_music:
        bgm_clip = AudioFileClip(background_music).with_effects(
            [afx.AudioLoop(duration=final_clip.duration), afx.MultiplyVolume(settings.BACKGROUND_MUSIC_VOLUME),
             afx.AudioFadeOut(1.0)]
        )
        tracks = [final_clip.audio, bgm_clip] if final_clip.audio else [bgm_clip]
        final_clip = final_clip.with_audio(CompositeAudioClip(tracks))

    final_clip.write_videofile(output_path, codec="libx264", fps=24)

    final_clip.close()
    for clip in video_clips:
        clip.close()
    if voice_clip:
        voice_clip.close()
    if bgm_clip:
        bgm_clip.close()

    return output_path
