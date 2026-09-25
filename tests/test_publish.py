import os
from pathlib import Path

import pytest

from aitihasik_katha import pipeline
from aitihasik_katha.core.settings import settings
from aitihasik_katha.storage import run_store


class _FakeInstagram:
    def __init__(self, calls):
        self._calls = calls

    def upload_media(self, media_url, caption, media_type):
        self._calls.append((media_url, caption, media_type))


def _make_completed_run(tmp_path, run_id, seed_registry=True):
    run_path = os.path.join(str(tmp_path), run_id)
    output_dir = Path(run_path) / settings.OUTPUT_PATH
    output_dir.mkdir(parents=True)
    (output_dir / "story.txt").write_text("a story", encoding="utf-8")
    video_path = output_dir / "final_video.mp4"
    video_path.write_text("fake video bytes", encoding="utf-8")

    if seed_registry:
        run_store.upsert_run(
            run_id, status="video_ready", video_ready=True, final_video_path=str(video_path)
        )
    return run_path


@pytest.fixture
def wired_publish(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RUNS_PATH", str(tmp_path))

    calls = {"caption": 0, "gcs_upload": 0, "instagram": []}

    def _generate_caption(story):
        calls["caption"] += 1
        return "a caption"

    def _upload_folder_to_gcs(bucket, src, dst):
        calls["gcs_upload"] += 1
        return "https://example.com/"

    monkeypatch.setattr(pipeline, "generate_caption", _generate_caption)
    monkeypatch.setattr(pipeline, "upload_folder_to_gcs", _upload_folder_to_gcs)
    monkeypatch.setattr(pipeline, "get_instagram_service", lambda: _FakeInstagram(calls["instagram"]))

    return tmp_path, calls


def test_publish_run_uploads_and_records_state(wired_publish):
    tmp_path, calls = wired_publish
    _make_completed_run(tmp_path, "run-a")

    pipeline.publish_run("run-a")

    assert calls["caption"] == 1
    assert calls["gcs_upload"] == 1
    assert len(calls["instagram"]) == 1

    record = run_store.get_run("run-a")
    assert record.instagram_uploaded is True
    assert record.media_uri == "https://example.com/output/final_video.mp4"


def test_publish_run_reuses_existing_caption_and_upload_on_retry(wired_publish):
    tmp_path, calls = wired_publish
    _make_completed_run(tmp_path, "run-b")

    pipeline.publish_run("run-b")
    calls["instagram"].clear()

    # Simulate retrying a publish (e.g. after a transient Instagram failure):
    # caption + GCS upload should not be redone.
    pipeline.publish_run("run-b")

    assert calls["caption"] == 1
    assert calls["gcs_upload"] == 1
    assert len(calls["instagram"]) == 1


def test_publish_run_raises_if_video_missing(wired_publish):
    tmp_path, _ = wired_publish
    run_path = Path(str(tmp_path)) / "run-missing" / settings.OUTPUT_PATH
    run_path.mkdir(parents=True)

    with pytest.raises(RuntimeError):
        pipeline.publish_run("run-missing")


def test_publish_run_registers_untracked_run_on_first_publish(wired_publish):
    tmp_path, calls = wired_publish
    _make_completed_run(tmp_path, "not-in-registry-yet", seed_registry=False)

    assert run_store.get_run("not-in-registry-yet") is None

    pipeline.publish_run("not-in-registry-yet")

    assert len(calls["instagram"]) == 1
    assert run_store.get_run("not-in-registry-yet").instagram_uploaded is True


def test_publish_all_pending_only_publishes_ready_unpublished_runs(wired_publish):
    tmp_path, calls = wired_publish
    _make_completed_run(tmp_path, "ready-1")
    _make_completed_run(tmp_path, "ready-2")
    _make_completed_run(tmp_path, "already-done")
    run_store.upsert_run("already-done", status="published", instagram_uploaded=True)

    published = pipeline.publish_all_pending()

    assert sorted(published) == ["ready-1", "ready-2"]
    assert len(calls["instagram"]) == 2
