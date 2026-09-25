import pytest

from aitihasik_katha.services.scene_timing import compute_scene_durations, split_into_scenes


def test_split_into_scenes_splits_on_sentence_terminators():
    story = "Once upon a time. There was a king! Did he rule well? यसपछि उनी गए।"
    assert split_into_scenes(story) == [
        "Once upon a time",
        "There was a king",
        "Did he rule well",
        "यसपछि उनी गए",
    ]


def test_split_into_scenes_falls_back_to_whole_story_when_no_terminators():
    assert split_into_scenes("no punctuation here") == ["no punctuation here"]


def test_compute_scene_durations_without_subtitles_splits_by_word_share():
    scenes = ["one two", "three four five six"]
    durations = compute_scene_durations(scenes, subtitles=None, total_audio_seconds=6.0)

    assert durations == pytest.approx([2.0, 4.0])


def test_compute_scene_durations_uses_subtitle_word_timings_when_available():
    scenes = ["one two", "three"]
    subtitles = [
        ((0.0, 0.5), "one"),
        ((0.5, 1.2), "two"),
        ((1.2, 2.0), "three"),
    ]
    durations = compute_scene_durations(scenes, subtitles, total_audio_seconds=2.0)

    assert durations == pytest.approx([1.2, 0.8])


def test_compute_scene_durations_enforces_minimum_scene_length():
    scenes = ["a", "b", "c"]
    durations = compute_scene_durations(
        scenes, subtitles=None, total_audio_seconds=1.0, min_scene_seconds=0.6
    )

    assert all(duration >= 0.6 - 1e-9 for duration in durations)


def test_compute_scene_durations_last_scene_covers_full_audio():
    scenes = ["one", "two"]
    durations = compute_scene_durations(scenes, subtitles=None, total_audio_seconds=10.0)

    assert sum(durations) == pytest.approx(10.0)
