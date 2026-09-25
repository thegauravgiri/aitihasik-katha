import os
import uuid
from datetime import timedelta
from pathlib import Path
from urllib.parse import urljoin

from .core.logging import get_logger
from .core.settings import ensure_directories, settings
from .services.audio_service import generate_audio, get_audio_duration
from .services.caption_service import generate_caption
from .services.image_service import generate_image
from .services.instagram_service import get_instagram_service
from .services.scene_timing import Subtitle, compute_scene_durations, split_into_scenes
from .services.story_service import generate_story
from .services.subtitle_service import generate_transcription, get_subtitle
from .services.video_service import create_video_from_image, merge_video_clips
from .utils.gcs import upload_folder_to_gcs


logger = get_logger(__name__)


def _run_path(run_id: str) -> str:
    return os.path.join(settings.RUNS_PATH, run_id)


def _generate_story_stage(run_path: str, topic: str | None) -> str:
    story_path = Path(run_path) / settings.OUTPUT_PATH / "story.txt"
    if story_path.exists():
        logger.info("Reusing existing story at %s", story_path)
        return story_path.read_text(encoding="utf-8")

    story = generate_story(topic=topic)
    logger.debug("Generated story:\n%s", story)
    story_path.write_text(story, encoding="utf-8")
    return story


def _generate_audio_stage(
    story: str, run_path: str
) -> tuple[str, timedelta, list[Subtitle]]:
    audio_output_filepath = os.path.join(run_path, settings.AUDIO_PATH, "story.mp3")
    if os.path.exists(audio_output_filepath):
        logger.info("Reusing existing audio at %s", audio_output_filepath)
    else:
        generate_audio(story, audio_output_filepath)

    total_audio_duration = get_audio_duration(audio_output_filepath)
    transcription = generate_transcription(audio_output_filepath)
    subtitles = get_subtitle(transcription)
    return audio_output_filepath, total_audio_duration, subtitles


def _generate_media_stage(
    story: str, run_path: str, subtitles: list[Subtitle], total_audio_seconds: float
) -> list[str]:
    scenes = split_into_scenes(story)
    logger.info("Prepared %s scene(s) for image/video generation", len(scenes))
    durations = compute_scene_durations(scenes, subtitles, total_audio_seconds)

    generated_video_clips = []
    for idx, (scene, duration) in enumerate(zip(scenes, durations)):
        imageclip_output_filepath = os.path.join(
            run_path, settings.VIDEO_PATH, f"video_image_clip_{idx}.mp4"
        )
        if os.path.exists(imageclip_output_filepath):
            logger.info("Reusing existing clip %s", imageclip_output_filepath)
            generated_video_clips.append(imageclip_output_filepath)
            continue

        image_output_filepath = os.path.join(run_path, settings.IMAGE_PATH, f"image_{idx}.png")
        image_path = generate_image(scene, story, image_output_filepath)
        imageclip_path = create_video_from_image(image_path, duration, imageclip_output_filepath)
        generated_video_clips.append(imageclip_path)

    return generated_video_clips


def _assemble_video_stage(
    run_path: str, audio_filepath: str, subtitles: list[Subtitle], clip_filenames: list[str]
) -> str | None:
    final_video_output_filepath = os.path.join(run_path, settings.OUTPUT_PATH, "final_video.mp4")
    return merge_video_clips(
        final_video_output_filepath,
        voice_over=audio_filepath,
        subtitles=subtitles,
        clip_filenames=clip_filenames,
    )


def _publish_stage(run_path: str, story: str) -> None:
    logger.info("Generating caption for final video")
    caption = generate_caption(story)
    caption_path = Path(run_path) / settings.OUTPUT_PATH / "caption.txt"
    caption_path.write_text(caption, encoding="utf-8")

    folder_uri = upload_folder_to_gcs(settings.BUCKET, run_path, run_path)
    logger.info("All artifacts uploaded to %s", folder_uri)
    media_uri = urljoin(folder_uri, "output/final_video.mp4")
    logger.info("Video uploaded to %s", media_uri)

    logger.info("Uploading media to Instagram")
    get_instagram_service().upload_media(media_uri, caption=caption, media_type="REELS")
    logger.info("Instagram upload complete")


def run_pipeline_v1(topic: str | None = None, run_id: str | None = None) -> str | None:
    """Run the end-to-end story -> video -> publish pipeline.

    Pass `run_id` to resume a previous run: any stage whose output already
    exists on disk for that run is reused instead of regenerated.
    """
    current_run_id = run_id or str(uuid.uuid4())
    logger.info("Starting pipeline run_id=%s topic=%s", current_run_id, topic or "auto")
    ensure_directories(current_run_id)
    run_path = _run_path(current_run_id)

    story = _generate_story_stage(run_path, topic)
    audio_filepath, total_audio_duration, subtitles = _generate_audio_stage(story, run_path)
    generated_video_clips = _generate_media_stage(
        story, run_path, subtitles, total_audio_duration.total_seconds()
    )
    final_video_path = _assemble_video_stage(run_path, audio_filepath, subtitles, generated_video_clips)

    if not final_video_path:
        logger.warning("Pipeline completed without creating final video for run_id=%s", current_run_id)
        return None

    logger.info("Final video ready at %s", final_video_path)
    _publish_stage(run_path, story)
    return final_video_path


if __name__ == "__main__":
    run_pipeline_v1()
