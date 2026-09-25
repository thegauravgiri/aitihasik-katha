import re

Subtitle = tuple[tuple[float, float], str]


def split_into_scenes(story: str) -> list[str]:
    """Split a story into scenes on sentence boundaries (., !, ?, ।)."""
    scenes = [s.strip() for s in re.split(r"[.!?।]+", story) if s.strip()]
    return scenes or [story.strip()]


def compute_scene_durations(
    scenes: list[str],
    subtitles: list[Subtitle] | None,
    total_audio_seconds: float,
    min_scene_seconds: float = 0.6,
) -> list[float]:
    """Allocate each scene a slice of the narration's runtime.

    When word-level subtitle timings are available, a scene's end time is taken
    from the timing of the word count reached so far (so scene cuts line up
    with what's actually being said). Otherwise, falls back to distributing
    duration proportionally to each scene's word count.
    """
    total_scene_words = max(1, sum(len(scene.split()) for scene in scenes))
    cumulative_words = 0
    start_seconds = 0.0
    durations: list[float] = []

    for idx, scene in enumerate(scenes):
        scene_words = max(1, len(scene.split()))
        cumulative_words += scene_words

        if subtitles:
            subtitle_index = min(cumulative_words - 1, len(subtitles) - 1)
            end_seconds = float(subtitles[subtitle_index][0][1])
        else:
            progress = min(1.0, cumulative_words / total_scene_words)
            end_seconds = total_audio_seconds * progress

        if idx == len(scenes) - 1:
            end_seconds = max(end_seconds, total_audio_seconds)

        end_seconds = max(end_seconds, start_seconds + min_scene_seconds)
        durations.append(end_seconds - start_seconds)
        start_seconds = end_seconds

    return durations
