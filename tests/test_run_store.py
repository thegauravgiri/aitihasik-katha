import pytest

from aitihasik_katha.core.settings import settings
from aitihasik_katha.storage import run_store


@pytest.fixture(autouse=True)
def isolated_runs_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RUNS_PATH", str(tmp_path))


def test_upsert_and_get_run_roundtrip():
    run_store.upsert_run("run-1", topic="unification", status="running")
    record = run_store.get_run("run-1")

    assert record is not None
    assert record.run_id == "run-1"
    assert record.topic == "unification"
    assert record.status == "running"
    assert record.video_ready is False
    assert record.instagram_uploaded is False


def test_upsert_run_merges_fields_without_clobbering_others():
    run_store.upsert_run("run-1", topic="unification", status="running")
    run_store.upsert_run("run-1", status="video_ready", video_ready=True, final_video_path="/tmp/out.mp4")

    record = run_store.get_run("run-1")
    assert record.topic == "unification"
    assert record.status == "video_ready"
    assert record.video_ready is True
    assert record.final_video_path == "/tmp/out.mp4"


def test_get_run_returns_none_for_unknown_id():
    assert run_store.get_run("does-not-exist") is None


def test_list_runs_orders_newest_first():
    run_store.upsert_run("first")
    run_store.upsert_run("second")

    ids = [record.run_id for record in run_store.list_runs()]
    assert ids == ["second", "first"]


def test_list_pending_publish_only_returns_ready_unpublished_runs():
    run_store.upsert_run("done-and-published", status="published", video_ready=True, instagram_uploaded=True)
    run_store.upsert_run("ready-not-published", status="video_ready", video_ready=True, instagram_uploaded=False)
    run_store.upsert_run("still-generating", status="story_ready", video_ready=False, instagram_uploaded=False)

    pending = run_store.list_pending_publish()
    assert [record.run_id for record in pending] == ["ready-not-published"]
