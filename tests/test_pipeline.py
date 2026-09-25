import os
from datetime import timedelta

import pytest

from aitihasik_katha import pipeline
from aitihasik_katha.core.settings import settings


class _FakeInstagram:
    def __init__(self, calls):
        self._calls = calls

    def upload_media(self, media_url, caption, media_type):
        self._calls.append(("instagram", media_url, caption, media_type))


@pytest.fixture
def wired_pipeline(tmp_path, monkeypatch):
    """Point the pipeline at a scratch directory and stub out every external call."""
    monkeypatch.setattr(settings, "RUNS_PATH", str(tmp_path))

    calls = []

    def _generate_audio(story, output_path):
        calls.append(("audio", output_path))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("fake-audio")
        return output_path

    def _generate_image(scene, story, output_path):
        calls.append(("image", output_path))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("fake-image")
        return output_path

    def _create_video_from_image(image_path, duration, output_path):
        calls.append(("clip", output_path, duration))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("fake-clip")
        return output_path

    def _merge_video_clips(output_path, voice_over, subtitles, clip_filenames):
        calls.append(("merge", tuple(clip_filenames)))
        return output_path

    monkeypatch.setattr(pipeline, "generate_story", lambda topic=None: "one two three. four five six.")
    monkeypatch.setattr(pipeline, "generate_audio", _generate_audio)
    monkeypatch.setattr(pipeline, "get_audio_duration", lambda path: timedelta(seconds=6))
    monkeypatch.setattr(pipeline, "generate_transcription", lambda path: object())
    monkeypatch.setattr(pipeline, "get_subtitle", lambda response: [])
    monkeypatch.setattr(pipeline, "generate_image", _generate_image)
    monkeypatch.setattr(pipeline, "create_video_from_image", _create_video_from_image)
    monkeypatch.setattr(pipeline, "merge_video_clips", _merge_video_clips)
    monkeypatch.setattr(pipeline, "generate_caption", lambda story: "a caption")
    monkeypatch.setattr(pipeline, "upload_folder_to_gcs", lambda bucket, src, dst: "https://example.com/")
    monkeypatch.setattr(pipeline, "get_instagram_service", lambda: _FakeInstagram(calls))

    return tmp_path, calls


def test_run_pipeline_v1_happy_path(wired_pipeline):
    tmp_path, calls = wired_pipeline

    result = pipeline.run_pipeline_v1(topic="test", run_id="abc123")

    run_path = os.path.join(str(tmp_path), "abc123")
    assert result == os.path.join(run_path, settings.OUTPUT_PATH, "final_video.mp4")

    kinds = [call[0] for call in calls]
    assert kinds == ["audio", "image", "clip", "image", "clip", "merge", "instagram"]
    assert os.path.exists(os.path.join(run_path, settings.OUTPUT_PATH, "story.txt"))
    assert os.path.exists(os.path.join(run_path, settings.OUTPUT_PATH, "caption.txt"))


def test_run_pipeline_v1_resume_skips_completed_stages(wired_pipeline):
    tmp_path, calls = wired_pipeline

    pipeline.run_pipeline_v1(topic="test", run_id="abc123")
    calls.clear()

    pipeline.run_pipeline_v1(topic="test", run_id="abc123")

    # Story, audio, and per-scene clips already exist on disk, so a resume
    # should only redo transcription/merge/publish, not regenerate media.
    kinds = [call[0] for call in calls]
    assert "audio" not in kinds
    assert "image" not in kinds
    assert "clip" not in kinds
    assert "merge" in kinds
    assert "instagram" in kinds
