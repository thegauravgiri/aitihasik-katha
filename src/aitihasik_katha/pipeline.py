import json
import os
import random
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path
from urllib.parse import urljoin

from .core.logging import get_logger
from .core.settings import ensure_directories, settings
from .services.audio_service import generate_audio, get_audio_duration
from .services.caption_service import generate_caption
from .services.character_service import (
    build_character_sheet,
    build_frame_prompt,
    build_scene_prompt,
    plan_scenes,
)
from .services.image_service import generate_scene_frame
from .services.real_media_service import find_real_media
from .services.instagram_service import get_instagram_service
from .services.reference_service import resolve_reference
from .services.video_generation_service import VideoBlockedError, clip_duration, generate_scene_clip
from .services.scene_timing import Subtitle, compute_scene_durations, split_into_scenes
from .services.story_service import write_story
from .services.subtitle_service import generate_transcription, get_subtitle
from .services.thumbnail_service import plan_cover, render_cover
from .services.video_service import MOTIONS, animate_still, fit_clip_to_duration, merge_video_clips, real_video_clip
from .storage import run_store
from .utils.gcs import upload_file_to_gcs, upload_folder_to_gcs
from .utils.nepali import nepali_punctuation


logger = get_logger(__name__)


def _run_path(run_id: str) -> str:
    return os.path.join(settings.RUNS_PATH, run_id)


def _generate_story_stage(run_path: str, topic: str | None) -> str:
    story_path = Path(run_path) / settings.OUTPUT_PATH / "story.txt"
    if story_path.exists():
        logger.info("Reusing existing story at %s", story_path)
        return story_path.read_text(encoding="utf-8")

    story = write_story(topic=topic)
    logger.info("Story written (%d words)", len(story.text.split()))
    story_path.write_text(story.text, encoding="utf-8")
    output_dir = story_path.parent
    if story.research_brief:
        (output_dir / "research.md").write_text(story.research_brief, encoding="utf-8")
    (output_dir / "sources.json").write_text(json.dumps(story.sources, ensure_ascii=False, indent=2), encoding="utf-8")
    if story.plan:
        (output_dir / "script_plan.json").write_text(json.dumps(story.plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return story.text


def _generate_audio_stage(
    story: str, run_path: str
) -> tuple[str, timedelta, list[Subtitle]]:
    audio_output_filepath = os.path.join(run_path, settings.AUDIO_PATH, "story.mp3")
    if os.path.exists(audio_output_filepath):
        logger.info("Reusing existing audio at %s", audio_output_filepath)
    else:
        generate_audio(story, audio_output_filepath)

    total_audio_duration = get_audio_duration(audio_output_filepath)
    subs_path = Path(run_path) / settings.OUTPUT_PATH / "subtitles.json"
    if subs_path.exists():
        logger.info("Reusing existing subtitles at %s", subs_path)
        raw_subs = json.loads(subs_path.read_text(encoding="utf-8"))
        subtitles = [((float(item[0][0]), float(item[0][1])), nepali_punctuation(item[1])) for item in raw_subs]
    else:
        transcription = generate_transcription(audio_output_filepath)
        subtitles = get_subtitle(transcription)
        subs_path.parent.mkdir(parents=True, exist_ok=True)
        subs_path.write_text(json.dumps(subtitles, ensure_ascii=False, indent=2), encoding="utf-8")
    return audio_output_filepath, total_audio_duration, subtitles


def _scene_worker_count(scene_count: int) -> int:
    return max(1, min(scene_count, settings.MAX_PARALLEL_SCENES))


MAX_REFERENCE_IMAGES = 3
CLIP_MODES = ("image", "mixed", "video")


MAX_REAL_SHARE = 0.4


def _find_real_media_stage(scenes: list[str], plan: list[dict], run_path: str) -> dict[int, dict]:
    """Real photos and footage for the scenes the planner marked as photographable, keyed by scene
    index. Nothing found, or any failure, simply leaves that scene to a generated shot."""
    path = Path(run_path) / settings.OUTPUT_PATH / "real_media.json"
    if path.exists():
        logger.info("Reusing existing %s", path)
        return {int(idx): item for idx, item in json.loads(path.read_text(encoding="utf-8")).items()}
    if not settings.USE_REAL_MEDIA:
        return {}

    wanted = [idx for idx, entry in enumerate(plan) if entry.get("real_search")]
    wanted = wanted[: max(1, round(len(scenes) * MAX_REAL_SHARE))]

    def _lookup(idx: int):
        try:
            return idx, find_real_media(plan[idx]["real_search"], scenes[idx])
        except Exception as exc:  # noqa: BLE001 - a missing photo must never fail the video
            logger.warning("Real media lookup failed for scene %d (%s): %s", idx, plan[idx]["real_search"], exc)
            return idx, None

    found: dict[int, dict] = {}
    taken: set[str] = set()
    if wanted:
        with ThreadPoolExecutor(max_workers=_scene_worker_count(len(wanted))) as executor:
            for idx, media in sorted(executor.map(_lookup, wanted)):
                if media and media.title not in taken:
                    taken.add(media.title)
                    found[idx] = {"path": media.path, "kind": media.kind, "credit": media.credit, "title": media.title}
    logger.info("Found real media for %d of %d scene(s)", len(found), len(scenes))
    path.write_text(json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8")
    return found


def _still_of_real_media(item: dict, idx: int, run_path: str) -> str:
    """An image to stand in for the scene (the cover may use it): a photo is itself, a video gives its first frame."""
    if item["kind"] == "image":
        return item["path"]
    from moviepy import VideoFileClip

    still = os.path.join(run_path, settings.IMAGE_PATH, f"real_{idx}.jpg")
    if not os.path.exists(still):
        clip = VideoFileClip(item["path"], audio=False)
        try:
            clip.save_frame(still, t=min(1.0, clip.duration / 2))
        finally:
            clip.close()
    return still


def _clip_kind(idx: int, scene_plan: dict, real: dict | None = None) -> str:
    """"real_image", "real_video", "video" or "image" for a scene under the current CLIP_MODE."""
    if real and idx in real:
        return f"real_{real[idx]['kind']}"
    if settings.CLIP_MODE == "mixed":
        return "video" if idx == 0 or scene_plan.get("clip") == "video" else "image"
    return settings.CLIP_MODE


def _load_or_create_json(path: Path, create):
    if path.exists():
        logger.info("Reusing existing %s", path)
        return json.loads(path.read_text(encoding="utf-8"))
    data = create()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def _generate_visuals_stage(
    story: str, scenes: list[str], run_path: str
) -> tuple[dict, list[dict], list[str], dict[int, dict]]:
    """Decide how every character looks, get one reference image per character,
    plan each scene's shot, and draw each scene's opening frame from those references.

    Every clip is animated from a frame drawn from the same shared references and
    character descriptions, which is what keeps characters consistent across
    independently generated clips. Doesn't depend on audio, so it runs
    alongside `_generate_audio_stage`.
    """
    output_dir = Path(run_path) / settings.OUTPUT_PATH
    sheet = _load_or_create_json(output_dir / "characters.json", lambda: build_character_sheet(story))
    logger.info(
        "Character sheet: %s",
        ", ".join(c["id"] for c in sheet["characters"]) or "(no recurring characters)",
    )

    def _reference_for(character: dict):
        image_path = os.path.join(run_path, settings.IMAGE_PATH, f"ref_{character['id']}.png")
        return resolve_reference(character, sheet["style"], image_path)

    references = {}
    characters = sheet["characters"]
    if characters:
        with ThreadPoolExecutor(max_workers=_scene_worker_count(len(characters))) as executor:
            futures = {executor.submit(_reference_for, c): c["id"] for c in characters}
            for future in as_completed(futures):
                references[futures[future]] = future.result()

    # A real portrait's appearance wins over the sheet's guess, so prompts and image agree.
    for character in characters:
        if references[character["id"]].description:
            character["description"] = references[character["id"]].description
    credits = [ref.credit for ref in references.values() if ref.credit]
    (output_dir / "references.json").write_text(json.dumps(credits, ensure_ascii=False, indent=2), encoding="utf-8")

    plan = _load_or_create_json(output_dir / "scene_plan.json", lambda: plan_scenes(scenes, sheet))
    real = _find_real_media_stage(scenes, plan, run_path)
    if real:
        credits += [item["credit"] for item in real.values()]
        (output_dir / "references.json").write_text(json.dumps(credits, ensure_ascii=False, indent=2), encoding="utf-8")

    def _frame_for(idx: int) -> str:
        if idx in real:
            return _still_of_real_media(real[idx], idx, run_path)
        frame_path = os.path.join(run_path, settings.IMAGE_PATH, f"scene_{idx}.png")
        if os.path.exists(frame_path):
            logger.info("Reusing existing scene frame %s", frame_path)
            return frame_path
        reference_paths = [
            references[cid].image_path for cid in plan[idx]["characters"] if cid in references
        ][:MAX_REFERENCE_IMAGES]
        return generate_scene_frame(build_frame_prompt(sheet, plan[idx]), reference_paths, frame_path)

    frame_paths: list[str] = [""] * len(scenes)
    with ThreadPoolExecutor(max_workers=_scene_worker_count(len(scenes))) as executor:
        futures = {executor.submit(_frame_for, idx): idx for idx in range(len(scenes))}
        for future in as_completed(futures):
            frame_paths[futures[future]] = future.result()

    return sheet, plan, frame_paths, real


def _generate_clips_stage(
    scenes: list[str],
    sheet: dict,
    plan: list[dict],
    frame_paths: list[str],
    run_path: str,
    subtitles: list[Subtitle],
    total_audio_seconds: float,
    real: dict[int, dict] | None = None,
) -> list[str]:
    """Turn each scene's opening frame into a clip of exactly that scene's narration time:
    animated by VIDEO_MODEL for "video" scenes, a slow camera move over the still for
    "image" scenes (see CLIP_MODE).

    Scenes are generated concurrently; each is independent because consistency
    comes from the shared references rather than from chaining clips together.
    """
    durations = compute_scene_durations(scenes, subtitles, total_audio_seconds)
    clip_paths: list[str] = [""] * len(scenes)
    fallbacks: dict[int, str] = {}

    def _create_one(idx: int) -> str:
        final_path = os.path.join(run_path, settings.VIDEO_PATH, f"video_clip_{idx}.mp4")
        if os.path.exists(final_path):
            logger.info("Reusing existing clip %s", final_path)
            return final_path

        kind = _clip_kind(idx, plan[idx], real)
        if kind == "real_video":
            return real_video_clip(real[idx]["path"], durations[idx], final_path)
        if kind == "real_image":
            return animate_still(real[idx]["path"], durations[idx], final_path, motion=MOTIONS[idx % len(MOTIONS)])
        if kind == "image":
            return animate_still(frame_paths[idx], durations[idx], final_path, motion=MOTIONS[idx % len(MOTIONS)])

        raw_path = os.path.join(run_path, settings.VIDEO_PATH, f"raw_clip_{idx}.mp4")
        if not os.path.exists(raw_path):
            seconds = clip_duration(durations[idx])
            try:
                generate_scene_clip(build_scene_prompt(sheet, plan[idx], seconds), frame_paths[idx], seconds, raw_path)
            except VideoBlockedError as exc:
                logger.warning("Scene %s was blocked by the video model (%s); using a camera move over the still", idx, exc)
                fallbacks[idx] = str(exc)[:300]
                return animate_still(frame_paths[idx], durations[idx], final_path, motion=MOTIONS[idx % len(MOTIONS)])
        return fit_clip_to_duration(raw_path, durations[idx], final_path)

    with ThreadPoolExecutor(max_workers=_scene_worker_count(len(scenes))) as executor:
        futures = {executor.submit(_create_one, idx): idx for idx in range(len(scenes))}
        for future in as_completed(futures):
            clip_paths[futures[future]] = future.result()

    if fallbacks:
        logger.warning("%d scene(s) used a camera move over the still because the video model blocked them: %s",
                       len(fallbacks), sorted(fallbacks))
        report = Path(run_path) / settings.OUTPUT_PATH / "clip_fallbacks.json"
        report.write_text(json.dumps({str(i): why for i, why in sorted(fallbacks.items())}, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    return clip_paths


def _cover_plan_stage(run_path: str, scenes: list[str]) -> dict:
    """The cover's title, highlighted word and source scene (also shown over the video's first seconds)."""
    return _load_or_create_json(Path(run_path) / settings.OUTPUT_PATH / "cover.json", lambda: plan_cover(scenes))


def _cover_stage(run_path: str, cover: dict, frame_paths: list[str]) -> str | None:
    """Render the cover image from the chosen scene's frame. A cover problem never fails the run:
    Instagram then picks a frame from the video itself."""
    cover_path = os.path.join(run_path, settings.OUTPUT_PATH, "cover.jpg")
    if os.path.exists(cover_path):
        logger.info("Reusing existing cover %s", cover_path)
        return cover_path
    try:
        return render_cover(frame_paths[cover["scene"]], cover["title"], cover.get("highlight"), cover_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not render the cover image: %s", exc)
        return None


def _pick_music() -> str | None:
    """A random track from BACKGROUND_MUSIC_DIR, if any were added."""
    folder = Path(settings.BACKGROUND_MUSIC_DIR)
    tracks = sorted(p for p in folder.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a")) if folder.is_dir() else []
    return str(random.choice(tracks)) if tracks else None


def _assemble_video_stage(
    run_path: str, audio_filepath: str, subtitles: list[Subtitle], clip_filenames: list[str], cover: dict | None = None
) -> str | None:
    final_video_output_filepath = os.path.join(run_path, settings.OUTPUT_PATH, "final_video.mp4")
    return merge_video_clips(
        final_video_output_filepath,
        voice_over=audio_filepath,
        subtitles=subtitles,
        clip_filenames=clip_filenames,
        hook_title=cover,
        branding=True,
        background_music=_pick_music(),
    )


def _write_caption(run_path: str, story: str) -> str:
    caption_path = Path(run_path) / settings.OUTPUT_PATH / "caption.txt"
    if caption_path.exists():
        logger.info("Reusing existing caption at %s", caption_path)
        return caption_path.read_text(encoding="utf-8")
    logger.info("Generating caption for final video")
    caption = generate_caption(story)
    credits_path = Path(run_path) / settings.OUTPUT_PATH / "references.json"
    credits = json.loads(credits_path.read_text(encoding="utf-8")) if credits_path.exists() else []
    if credits:
        caption += "\n\nPhoto credits:\n" + "\n".join(credits)
    caption_path.write_text(caption, encoding="utf-8")
    return caption


def _upload_cover(run_path: str) -> str | None:
    cover_path = os.path.join(run_path, settings.OUTPUT_PATH, "cover.jpg")
    if not os.path.exists(cover_path):
        return None
    try:
        return upload_file_to_gcs(settings.BUCKET, cover_path, cover_path.replace("\\", "/"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not upload the cover image, posting without it: %s", exc)
        return None


def _publish_stage(run_path: str, story: str, run_id: str) -> None:
    caption = _write_caption(run_path, story)

    run_record = run_store.get_run(run_id)
    if run_record and run_record.media_uri:
        media_uri = run_record.media_uri
        logger.info("Reusing previously uploaded media at %s", media_uri)
    else:
        folder_uri = upload_folder_to_gcs(settings.BUCKET, run_path, run_path)
        logger.info("All artifacts uploaded to %s", folder_uri)
        media_uri = urljoin(folder_uri, "output/final_video.mp4")
        run_store.upsert_run(run_id, media_uri=media_uri)
        logger.info("Video uploaded to %s", media_uri)

    logger.info("Uploading media to Instagram")
    get_instagram_service().upload_media(
        media_uri, caption=caption, media_type="REELS", cover_url=_upload_cover(run_path)
    )
    run_store.upsert_run(run_id, status="published", instagram_uploaded=True)
    logger.info("Instagram upload complete")


def run_pipeline_v1(topic: str | None = None, run_id: str | None = None) -> str | None:
    """Run the end-to-end story -> video -> publish pipeline.

    Pass `run_id` to resume a previous run: any stage whose output already
    exists on disk for that run is reused instead of regenerated. Progress
    and failures are recorded in the run registry (see storage/run_store.py)
    so incomplete or unpublished runs can be recovered later via
    `publish_run`/`publish_all_pending`, or by re-running with the same
    `run_id`.

    Audio generation (TTS + transcription) and the visuals stage (character
    sheet, scene plan, reference images) are independent, so they run
    concurrently; clip generation then fans out across scenes once both are
    done, since each clip's length comes from the narration timing. A scene
    that still fails after retries fails the run rather than publishing a
    video with a missing scene.
    """
    if settings.CLIP_MODE not in CLIP_MODES:
        raise ValueError(f"CLIP_MODE must be one of {', '.join(CLIP_MODES)}, got {settings.CLIP_MODE!r}")
    current_run_id = run_id or str(uuid.uuid4())
    logger.info(
        "Starting pipeline run_id=%s topic=%s mode=%s video_model=%s",
        current_run_id, topic or "auto", settings.CLIP_MODE, settings.VIDEO_MODEL,
    )
    ensure_directories(current_run_id)
    run_path = _run_path(current_run_id)

    initial_fields = {"status": "running"}
    if topic is not None:
        initial_fields["topic"] = topic
    run_store.upsert_run(current_run_id, **initial_fields)

    try:
        story = _generate_story_stage(run_path, topic)
        run_store.upsert_run(current_run_id, status="story_ready")

        scenes = split_into_scenes(story)
        logger.info("Prepared %s scene(s) for image/video generation", len(scenes))
        cover = _cover_plan_stage(run_path, scenes)

        with ThreadPoolExecutor(max_workers=2) as executor:
            audio_future = executor.submit(_generate_audio_stage, story, run_path)
            visuals_future = executor.submit(_generate_visuals_stage, story, scenes, run_path)
            audio_filepath, total_audio_duration, subtitles = audio_future.result()
            sheet, plan, frame_paths, real = visuals_future.result()
        run_store.upsert_run(current_run_id, status="audio_ready")
        _cover_stage(run_path, cover, frame_paths)

        generated_video_clips = _generate_clips_stage(
            scenes,
            sheet,
            plan,
            frame_paths,
            run_path,
            subtitles,
            total_audio_duration.total_seconds(),
            real,
        )
        run_store.upsert_run(current_run_id, status="media_ready")

        final_video_path = _assemble_video_stage(run_path, audio_filepath, subtitles, generated_video_clips, cover)

        if not final_video_path:
            logger.warning("Pipeline completed without creating final video for run_id=%s", current_run_id)
            run_store.upsert_run(current_run_id, status="failed", error="Video assembly produced no output")
            return None

        logger.info("Final video ready at %s", final_video_path)
        run_store.upsert_run(
            current_run_id, status="video_ready", video_ready=True, final_video_path=final_video_path
        )

        run_record = run_store.get_run(current_run_id)
        if run_record and run_record.instagram_uploaded:
            logger.info(
                "Run %s was already published to Instagram; skipping re-publish "
                "(use `instagram upload --run-id %s` to force a republish).",
                current_run_id, current_run_id,
            )
            return final_video_path

        if not settings.AUTO_PUBLISH:
            _write_caption(run_path, story)
            logger.info(
                "Ready for review in %s/ (final_video.mp4, cover.jpg, caption.txt). Post it with: "
                "python -m aitihasik_katha instagram upload --run-id %s",
                os.path.join(run_path, settings.OUTPUT_PATH), current_run_id,
            )
            return final_video_path

        _publish_stage(run_path, story, current_run_id)
        return final_video_path
    except Exception as exc:
        run_store.upsert_run(current_run_id, status="failed", error=str(exc))
        raise


def publish_run(run_id: str) -> None:
    """(Re)publish a single run to Instagram.

    Requires that run's video already be assembled on disk. Safe to call
    repeatedly: an already-uploaded GCS folder or already-generated caption
    is reused rather than redone.
    """
    run_path = _run_path(run_id)
    final_video_path = Path(run_path) / settings.OUTPUT_PATH / "final_video.mp4"
    if not final_video_path.exists():
        raise RuntimeError(f"No final_video.mp4 found for run {run_id} at {final_video_path}; nothing to publish.")

    story_path = Path(run_path) / settings.OUTPUT_PATH / "story.txt"
    story = story_path.read_text(encoding="utf-8") if story_path.exists() else ""

    run_store.upsert_run(run_id, status="video_ready", video_ready=True, final_video_path=str(final_video_path))
    _publish_stage(run_path, story, run_id)


def publish_all_pending() -> list[str]:
    """Publish every tracked run whose video is ready but hasn't reached Instagram yet.

    Returns the run ids that were successfully published; failures are
    logged and skipped so one bad run doesn't block the rest of the batch.
    """
    published = []
    for record in run_store.list_pending_publish():
        try:
            publish_run(record.run_id)
            published.append(record.run_id)
        except Exception as exc:  # noqa: BLE001 - best-effort batch publish, keep going
            logger.error("Failed to publish run %s: %s", record.run_id, exc)
    return published


if __name__ == "__main__":
    run_pipeline_v1()
