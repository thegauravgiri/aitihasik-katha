import math
import os
import re
from pathlib import Path
from typing import Iterable

from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)
from moviepy.video.tools.subtitles import file_to_subtitles

from ..core.logging import get_logger


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


def create_video_from_image(image_path: str, duration: float, output_path: str) -> str:
    safe_duration = max(0.6, float(duration))
    image_clip = ImageClip(image_path).with_duration(safe_duration)

    def _ease_in_zoom_scale(t: float) -> float:
        zoom_target = 1.3
        progress = min(1.0, max(0.0, t / safe_duration))
        eased_progress = 0.65 * progress + 0.35 * (1.0 - (1.0 - progress) * (1.0 - progress))
        return 1.0 + (zoom_target - 1.0) * eased_progress

    zoomed_image = image_clip.with_effects([vfx.Resize(_ease_in_zoom_scale)]).with_position(
        ("center", "center")
    )
    video = CompositeVideoClip([zoomed_image], size=(image_clip.w, image_clip.h))
    video.write_videofile(output_path, codec="libx264", fps=24)
    video.close()
    zoomed_image.close()
    image_clip.close()
    return output_path


def _build_reels_caption_clip(text: str, start_time: float, end_time: float, video_w: int, video_h: int):
    duration = max(0.1, float(end_time) - float(start_time))
    caption_text = format_text(text).upper()
    caption_font = str(Path("data/fonts/NotoSerifDevanagari-ExtraBold.ttf"))

    font_size = max(52, int(video_w * 0.082))
    max_text_width = int(video_w * 0.9)
    caption_box_h = int(video_h * 0.24)

    text_kwargs = dict(
        text=caption_text,
        method="caption",
        size=(max_text_width, caption_box_h),
        font=caption_font,
        margin=(20, 20),
        font_size=font_size,
        text_align="center",
        horizontal_align="center",
        vertical_align="center",
        transparent=True,
        interline=8,
        duration=duration,
    )

    shadow = TextClip(**text_kwargs, color="black", stroke_color="black", stroke_width=8).with_opacity(0.28).with_position((2, 3))
    glow_halo = TextClip(**text_kwargs, color="#fff8d6", stroke_color="#fff8d6", stroke_width=16).with_opacity(0.18)
    glow_outer = TextClip(**text_kwargs, color="#fff7b0", stroke_color="#fff7b0", stroke_width=12).with_opacity(0.30)
    glow_inner = TextClip(**text_kwargs, color="#fffdf2", stroke_color="#ffffff", stroke_width=9).with_opacity(0.22)
    main = TextClip(**text_kwargs, color="#ffffff", stroke_color="#0b1020", stroke_width=4)

    def _bump_scale(t: float) -> float:
        intro_duration = 0.22
        settled_scale = 1.06
        if t >= intro_duration:
            return settled_scale
        p = t / intro_duration
        base_lift = (settled_scale - 1.0) * p
        overshoot = 0.10 * math.sin(math.pi * p) * math.exp(-3.8 * p)
        return 1.0 + base_lift + overshoot

    pad = max(24, int(font_size * 0.9))
    layer_w = max(shadow.w, glow_halo.w, glow_outer.w, glow_inner.w, main.w)
    layer_h = max(shadow.h, glow_halo.h, glow_outer.h, glow_inner.h, main.h)
    canvas_size = (layer_w + 2 * pad, layer_h + 2 * pad)

    animated_caption = CompositeVideoClip(
        [
            shadow.with_position(("center", "center")),
            glow_halo.with_position(("center", "center")),
            glow_outer.with_position(("center", "center")),
            glow_inner.with_position(("center", "center")),
            main.with_position(("center", "center")),
        ],
        size=canvas_size,
        bg_color=None,
    ).with_effects([vfx.Resize(_bump_scale)])

    max_scale = 1.16
    reserved_h = int(animated_caption.h * max_scale)
    target_center_y = int(video_h * 0.62)
    caption_y = max(0, target_center_y - (reserved_h // 2))

    full_frame_caption = CompositeVideoClip(
        [animated_caption.with_position(("center", caption_y))],
        size=(video_w, video_h),
        bg_color=None,
    )
    return full_frame_caption.with_start(start_time).with_end(end_time)


def merge_video_clips(
    output_path: str | None = None,
    voice_over: str | None = None,
    subtitles: str | Iterable[tuple[tuple[float, float], str]] | None = None,
    background_music: str | None = None,
    clip_filenames: list[str] | None = None,
    video_path: str = "",
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

    final_clip = concatenate_videoclips(video_clips)
    voice_clip = None
    bgm_clip = None

    if voice_over:
        voice_clip = AudioFileClip(voice_over)
        final_clip = final_clip.with_audio(voice_clip)

    if subtitles:
        subtitle_items = file_to_subtitles(subtitles) if isinstance(subtitles, (str, os.PathLike)) else subtitles
        subtitle_overlays = [
            _build_reels_caption_clip(text, start, end, final_clip.w, final_clip.h)
            for (start, end), text in subtitle_items
        ]
        final_clip = CompositeVideoClip([final_clip, *subtitle_overlays])

    if background_music:
        bgm_clip = AudioFileClip(background_music)
        final_clip = final_clip.with_audio(bgm_clip)

    final_clip.write_videofile(output_path, codec="libx264", fps=24)

    final_clip.close()
    for clip in video_clips:
        clip.close()
    if voice_clip:
        voice_clip.close()
    if bgm_clip:
        bgm_clip.close()

    return output_path
