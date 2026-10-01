import os
from datetime import timedelta

import pytest

from aitihasik_katha import pipeline
from aitihasik_katha.core.settings import settings
from aitihasik_katha.services.reference_service import Reference
from aitihasik_katha.services.story_service import Story
from aitihasik_katha.storage import run_store


class _FakeInstagram:
    def __init__(self, calls):
        self._calls = calls

    def upload_media(self, media_url, caption, media_type, cover_url=None):
        self._calls.append(("instagram", media_url, caption, media_type, cover_url))


@pytest.fixture
def wired_pipeline(tmp_path, monkeypatch):
    """Point the pipeline at a scratch directory and stub out every external call."""
    monkeypatch.setattr(settings, "RUNS_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "CLIP_MODE", "video")
    monkeypatch.setattr(settings, "AUTO_PUBLISH", True)

    calls = []

    def _generate_audio(story, output_path):
        calls.append(("audio", output_path))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("fake-audio")
        return output_path

    def _build_character_sheet(story):
        calls.append(("sheet",))
        return {
            "style": "Malla-era Kathmandu",
            "supporting": "soldiers in period dress",
            "characters": [{"id": "king", "name": "The King", "description": "grey beard, red robe"}],
        }

    def _plan_scenes(scenes, sheet):
        calls.append(("plan",))
        return [
            {"characters": ["king"], "shot": "king on balcony", "clip": "video"},
            {"characters": [], "shot": "city", "clip": "image"},
        ]

    def _resolve_reference(character, style, image_path):
        # Like the real one: an existing reference is reused rather than re-fetched.
        if not os.path.exists(image_path):
            calls.append(("reference", character["id"]))
            with open(image_path, "w", encoding="utf-8") as f:
                f.write("fake-reference")
        return Reference(
            image_path=image_path,
            source="wikimedia",
            description="portrait: grey beard, red robe",
            credit='The King: "King.jpg" by Court Painter, Public domain, via Wikimedia Commons',
        )

    def _generate_scene_frame(prompt, reference_paths, output_path):
        calls.append(("frame", prompt, tuple(reference_paths)))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("fake-frame")
        return output_path

    def _generate_scene_clip(prompt, first_frame_path, seconds, output_path):
        calls.append(("clip", prompt, first_frame_path, seconds))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("fake-raw-clip")
        return output_path

    def _animate_still(image_path, duration, output_path, zoom_in=True):
        calls.append(("still", image_path, duration))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("fake-still-clip")
        return output_path

    def _fit_clip_to_duration(input_path, duration, output_path):
        calls.append(("fit", duration))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("fake-clip")
        return output_path

    def _merge_video_clips(output_path, voice_over, subtitles, clip_filenames, hook_title=None):
        calls.append(("merge", tuple(clip_filenames), hook_title))
        return output_path

    def _plan_cover(scenes):
        calls.append(("cover_plan",))
        return {"title": "राजाको रहस्य", "highlight": "रहस्य", "scene": 1}

    def _render_cover(frame_path, title, highlight, output_path):
        calls.append(("cover", frame_path, title, highlight))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("fake-cover")
        return output_path

    monkeypatch.setattr(
        pipeline,
        "write_story",
        lambda topic=None: Story(
            text="one two three. four five six.",
            research_brief="Hook: a surprising fact.",
            sources=[{"title": "britannica.com", "uri": "https://example.com/1"}],
            plan={"seconds": 45, "reason": "a story", "target_words": 99},
        ),
    )
    monkeypatch.setattr(pipeline, "generate_audio", _generate_audio)
    monkeypatch.setattr(pipeline, "get_audio_duration", lambda path: timedelta(seconds=6))
    monkeypatch.setattr(pipeline, "generate_transcription", lambda path: object())
    monkeypatch.setattr(pipeline, "get_subtitle", lambda response: [])
    monkeypatch.setattr(pipeline, "build_character_sheet", _build_character_sheet)
    monkeypatch.setattr(pipeline, "plan_scenes", _plan_scenes)
    monkeypatch.setattr(pipeline, "resolve_reference", _resolve_reference)
    monkeypatch.setattr(pipeline, "generate_scene_frame", _generate_scene_frame)
    monkeypatch.setattr(pipeline, "generate_scene_clip", _generate_scene_clip)
    monkeypatch.setattr(pipeline, "fit_clip_to_duration", _fit_clip_to_duration)
    monkeypatch.setattr(pipeline, "animate_still", _animate_still)
    monkeypatch.setattr(pipeline, "merge_video_clips", _merge_video_clips)
    monkeypatch.setattr(pipeline, "plan_cover", _plan_cover)
    monkeypatch.setattr(pipeline, "render_cover", _render_cover)
    monkeypatch.setattr(pipeline, "upload_file_to_gcs", lambda bucket, src, dst: "https://example.com/cover.jpg")
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
    # Audio and the visuals stage (sheet -> references -> plan -> frames) run concurrently,
    # so only counts and dependency ordering are checked, not the exact interleaving.
    for kind, expected in [
        ("audio", 1), ("sheet", 1), ("reference", 1), ("plan", 1), ("frame", 2),
        ("clip", 2), ("fit", 2), ("merge", 1), ("instagram", 1), ("cover_plan", 1), ("cover", 1),
    ]:
        assert kinds.count(kind) == expected, kind

    first_frame = min(i for i, kind in enumerate(kinds) if kind == "frame")
    last_frame = max(i for i, kind in enumerate(kinds) if kind == "frame")
    first_clip = min(i for i, kind in enumerate(kinds) if kind == "clip")
    assert kinds.index("sheet") < kinds.index("reference") < kinds.index("plan") < first_frame
    assert last_frame < first_clip
    assert kinds.index("audio") < first_clip
    last_fit = max(i for i, kind in enumerate(kinds) if kind == "fit")
    assert last_fit < kinds.index("merge") < kinds.index("instagram")

    output_dir = os.path.join(run_path, settings.OUTPUT_PATH)
    for name in ("story.txt", "research.md", "sources.json", "caption.txt", "characters.json", "scene_plan.json",
                 "cover.json", "cover.jpg", "script_plan.json"):
        assert os.path.exists(os.path.join(output_dir, name)), name


def test_scene_frames_use_their_characters_references_and_clips_animate_them(wired_pipeline):
    tmp_path, calls = wired_pipeline

    pipeline.run_pipeline_v1(topic="test", run_id="refs")

    images = os.path.join(str(tmp_path), "refs", settings.IMAGE_PATH)
    frames = {prompt: refs for _, prompt, refs in (c for c in calls if c[0] == "frame")}
    king_frame = next(p for p in frames if "king on balcony" in p)
    city_frame = next(p for p in frames if "city" in p)
    assert frames[king_frame] == (os.path.join(images, "ref_king.png"),)
    # The description taken from the real portrait replaces the character sheet's guess.
    assert "portrait: grey beard, red robe" in king_frame
    assert frames[city_frame] == ()
    assert "grey beard" not in city_frame

    clips = {frame: (prompt, seconds) for _, prompt, frame, seconds in (c for c in calls if c[0] == "clip")}
    king_clip_prompt, king_seconds = clips[os.path.join(images, "scene_0.png")]
    assert "king on balcony" in king_clip_prompt
    assert king_seconds == 4  # 3s of narration -> shortest Veo clip that covers it


def test_caption_credits_the_reference_portraits(wired_pipeline):
    tmp_path, _ = wired_pipeline

    pipeline.run_pipeline_v1(topic="test", run_id="credits")

    caption = open(os.path.join(str(tmp_path), "credits", settings.OUTPUT_PATH, "caption.txt"), encoding="utf-8").read()
    assert caption.startswith("a caption")
    assert '"King.jpg" by Court Painter, Public domain, via Wikimedia Commons' in caption


def test_failed_scene_clip_fails_the_run_instead_of_publishing(wired_pipeline, monkeypatch):
    _, calls = wired_pipeline

    def _broken_clip(prompt, first_frame_path, seconds, output_path):
        raise RuntimeError("video model unavailable")

    monkeypatch.setattr(pipeline, "generate_scene_clip", _broken_clip)

    with pytest.raises(RuntimeError, match="video model unavailable"):
        pipeline.run_pipeline_v1(topic="test", run_id="broken")

    record = run_store.get_run("broken")
    assert record.status == "failed"
    assert record.video_ready is False
    assert "instagram" not in [call[0] for call in calls]


def test_blocked_scene_clip_falls_back_to_the_still_and_the_run_completes(wired_pipeline, monkeypatch):
    _, calls = wired_pipeline

    def _blocked_clip(prompt, first_frame_path, seconds, output_path):
        raise pipeline.VideoBlockedError("Input blocked: real people's likenesses")

    monkeypatch.setattr(pipeline, "generate_scene_clip", _blocked_clip)

    pipeline.run_pipeline_v1(topic="test", run_id="blocked")

    assert run_store.get_run("blocked").video_ready is True
    assert any(call[0] == "still" for call in calls)


def test_cover_comes_from_the_planned_scene_and_is_posted_and_shown_over_the_video(wired_pipeline):
    tmp_path, calls = wired_pipeline

    pipeline.run_pipeline_v1(topic="test", run_id="covers")

    images = os.path.join(str(tmp_path), "covers", settings.IMAGE_PATH)
    cover_call = next(c for c in calls if c[0] == "cover")
    assert cover_call[1:] == (os.path.join(images, "scene_1.png"), "राजाको रहस्य", "रहस्य")
    merge_call = next(c for c in calls if c[0] == "merge")
    assert merge_call[2] == {"title": "राजाको रहस्य", "highlight": "रहस्य", "scene": 1}
    instagram_call = next(c for c in calls if c[0] == "instagram")
    assert instagram_call[4] == "https://example.com/cover.jpg"


def test_a_cover_that_cannot_be_rendered_does_not_stop_the_post(wired_pipeline, monkeypatch):
    _, calls = wired_pipeline

    def _broken_cover(frame_path, title, highlight, output_path):
        raise OSError("disk full")

    monkeypatch.setattr(pipeline, "render_cover", _broken_cover)

    pipeline.run_pipeline_v1(topic="test", run_id="no-cover")

    instagram_call = next(c for c in calls if c[0] == "instagram")
    assert instagram_call[4] is None


def test_without_auto_publish_the_run_stops_for_review(wired_pipeline, monkeypatch):
    tmp_path, calls = wired_pipeline
    monkeypatch.setattr(settings, "AUTO_PUBLISH", False)

    result = pipeline.run_pipeline_v1(topic="test", run_id="review")

    assert result is not None
    assert "instagram" not in [call[0] for call in calls]
    output_dir = os.path.join(str(tmp_path), "review", settings.OUTPUT_PATH)
    for name in ("caption.txt", "cover.jpg"):
        assert os.path.exists(os.path.join(output_dir, name)), name
    record = run_store.get_run("review")
    assert record.status == "video_ready"
    assert record.video_ready is True
    assert record.instagram_uploaded is False


def test_run_pipeline_v1_resume_skips_completed_stages_and_does_not_republish(wired_pipeline):
    tmp_path, calls = wired_pipeline

    pipeline.run_pipeline_v1(topic="test", run_id="abc123")
    calls.clear()

    pipeline.run_pipeline_v1(topic="test", run_id="abc123")

    # Story, audio, character sheet, references and clips already exist on disk,
    # so a resume should only redo transcription/merge, not regenerate media. The
    # run was already fully published on the first call, so resuming it must not
    # post to Instagram again.
    kinds = [call[0] for call in calls]
    for kind in ("audio", "sheet", "plan", "reference", "frame", "clip", "fit", "cover_plan", "cover"):
        assert kind not in kinds, kind
    assert "merge" in kinds
    assert "instagram" not in kinds


def test_run_pipeline_v1_recovers_and_retries_publish_after_earlier_failure(wired_pipeline, monkeypatch):
    tmp_path, calls = wired_pipeline

    attempt_count = {"n": 0}

    class _FlakyInstagram:
        def upload_media(self, media_url, caption, media_type, cover_url=None):
            attempt_count["n"] += 1
            if attempt_count["n"] == 1:
                raise RuntimeError("simulated instagram outage")
            calls.append(("instagram", media_url, caption, media_type, cover_url))

    monkeypatch.setattr(pipeline, "get_instagram_service", lambda: _FlakyInstagram())

    with pytest.raises(RuntimeError, match="simulated instagram outage"):
        pipeline.run_pipeline_v1(topic="test", run_id="flaky-run")

    record = run_store.get_run("flaky-run")
    assert record.status == "failed"
    assert record.video_ready is True
    assert record.instagram_uploaded is False

    calls.clear()
    result = pipeline.run_pipeline_v1(topic="test", run_id="flaky-run")

    # Generation stages stay skipped (already on disk); publish is retried and succeeds.
    kinds = [call[0] for call in calls]
    assert "audio" not in kinds
    assert "instagram" in kinds
    assert result is not None

    record = run_store.get_run("flaky-run")
    assert record.instagram_uploaded is True


@pytest.mark.parametrize(
    "mode, expected_kinds",
    [
        ("video", ["clip", "clip"]),
        ("image", ["still", "still"]),
        # Scene 0 is the hook (always video); scene 1 follows the planner's "image" choice.
        ("mixed", ["clip", "still"]),
    ],
)
def test_clip_mode_decides_how_each_scene_is_rendered(wired_pipeline, monkeypatch, mode, expected_kinds):
    tmp_path, calls = wired_pipeline
    monkeypatch.setattr(settings, "CLIP_MODE", mode)

    pipeline.run_pipeline_v1(topic="test", run_id=f"mode-{mode}")

    videos = os.path.join(str(tmp_path), f"mode-{mode}", settings.IMAGE_PATH)
    per_scene = {}
    for call in calls:
        if call[0] == "clip":
            per_scene[call[2]] = "clip"
        elif call[0] == "still":
            per_scene[call[1]] = "still"
    assert [per_scene[os.path.join(videos, f"scene_{i}.png")] for i in range(2)] == expected_kinds
    if mode == "image":
        assert "fit" not in [call[0] for call in calls]


def test_invalid_clip_mode_is_rejected_before_any_work(wired_pipeline, monkeypatch):
    _, calls = wired_pipeline
    monkeypatch.setattr(settings, "CLIP_MODE", "slideshow")

    with pytest.raises(ValueError, match="CLIP_MODE"):
        pipeline.run_pipeline_v1(topic="test", run_id="bad-mode")
    assert calls == []
