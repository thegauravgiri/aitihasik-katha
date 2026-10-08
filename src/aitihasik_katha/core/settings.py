from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    # --- Gemini models ---
    GEMINI_API_KEY: str = ""
    CHAT_MODEL: str = ""
    AUDIO_MODEL: str = ""
    # Animates each scene's opening frame (Veo image-to-video).
    VIDEO_MODEL: str = "veo-3.1-lite-generate-preview"
    # Tried when VIDEO_MODEL blocks a scene (safety filters). Empty to skip straight to a camera move over the still.
    VIDEO_FALLBACK_MODEL: str = "veo-3.1-lite-generate-preview"
    # Draws character references (when no real portrait is used) and each scene's opening frame.
    IMAGE_MODEL: str = "gemini-3.1-flash-image"
    # Resolution of generated frames: "1K", "2K" or "4K". 2K is noticeably sharper and costs more per frame.
    IMAGE_SIZE: str = "2K"
    # Use freely licensed Wikipedia/Wikimedia portraits of real historical figures as references.
    USE_HISTORICAL_PORTRAITS: bool = True
    # Per-request limit for Gemini API calls; a video clip normally takes 30-60s.
    GENAI_REQUEST_TIMEOUT_SECONDS: int = 300
    # How each scene is shown: "image" (still frame with a slow camera move - cheapest, no
    # video model calls), "video" (every scene animated by VIDEO_MODEL), or "mixed" (the shot
    # planner picks per scene; the opening hook is always video).
    CLIP_MODE: str = "mixed"
    # Research the story's subject on the web (Google Search grounding) in addition to the archive.
    USE_WEB_RESEARCH: bool = True
    # Have the chat model check each draft against the topic and the research (and rewrite it)
    # before the story is used.
    USE_STORY_REVIEW: bool = True
    # Use real photos and footage from Wikimedia Commons where the scene planner finds a good match.
    USE_REAL_MEDIA: bool = True
    # Also accept CC BY-SA media. Off by default: the share-alike term may extend to the published video.
    REAL_MEDIA_ALLOW_SHAREALIKE: bool = False
    # Where real media found for any video is kept, so later videos reuse it instead of searching again.
    MEDIA_LIBRARY_PATH: str = "data/media_library"
    # Post to Instagram as soon as the video is made. Off by default: a run stops after making the
    # video, cover and caption so they can be checked, then `instagram upload --run-id` posts them.
    AUTO_PUBLISH: bool = False

    # --- Google Cloud project / storage ---
    PROJECT_ID: str = ""
    BUCKET: str = ""
    BUCKET_URI: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # --- OCR (Tesseract) ---
    TESS_NEP_CONFIG: str = "--psm 6 --oem 3 -l nep"
    TESS_ENG_NEP_CONFIG: str = "--psm 6 --oem 3 -l eng+nep"

    # --- Instagram publishing ---
    INSTAGRAM_CLIENT_ID: str = ""
    INSTAGRAM_CLIENT_SECRET: str = ""
    INSTAGRAM_ACCESS_TOKEN: str = ""
    INSTAGRAM_PAGE_ACCESS_TOKEN: str = ""
    INSTAGRAM_USER_ID: str = ""

    # Look of the finished video ---
    # Visual generation style for scenes, frames, and characters:
    # "realistic", "animated", "disney", "anime", "dark_fantasy", "oil_painting", "graphic_novel", "claymation", "vintage_documentary"
    VISUAL_STYLE: str = "realistic"
    # Grain, vignette and a touch of contrast on every shot so generated frames and real photos
    # look like one documentary.
    FILM_LOOK: bool = True
    # Show the hook title card overlaid across the video's opening seconds.
    # Off by default: keep opening seconds clean and cinematic without text obscuring the visual hook.
    SHOW_HOOK_TITLE: bool = False
    # A small handle shown in the corner of the video. Off by default (empty).
    CHANNEL_HANDLE: str = ""
    FOLLOW_TAG: str = "फलो गर्नुस् — हरेक हप्ता नेपालको एउटा अनसुनेको इतिहास"
    # Transition style between scenes: "none" (clean cinematic straight cuts - recommended for reels),
    # "crossfade", or "dip_to_black".
    TRANSITION_STYLE: str = "none"
    TRANSITION_DURATION: float = 0.20
    # Royalty-free tracks (mp3/wav/m4a) dropped in this folder are mixed in quietly under the voice-over.
    BACKGROUND_MUSIC_DIR: str = "data/music"
    BACKGROUND_MUSIC_VOLUME: float = 0.10

    # --- Run output layout ---
    RUNS_PATH: str = "runs/"
    IMAGE_PATH: str = "images/"
    VIDEO_PATH: str = "videos/"
    AUDIO_PATH: str = "audios/"
    OUTPUT_PATH: str = "output/"

    # --- Concurrency ---
    # How many clips/reference images to generate at once. Each is a ~30s call
    # to VIDEO_MODEL, so running several concurrently cuts wall-clock time a
    # lot; keep this bounded to stay under the API's rate limits.
    MAX_PARALLEL_SCENES: int = 4

    def require(self, *names: str) -> None:
        """Fail fast if any of the named settings are unset, instead of letting
        an empty string silently propagate into an API call."""
        missing = [name for name in names if not getattr(self, name, "")]
        if missing:
            raise RuntimeError(f"Missing required setting(s): {', '.join(missing)}")


load_dotenv()
settings = Settings()


def ensure_directories(uuid: str) -> None:
    """Create output directories expected by the pipeline."""
    Path(settings.RUNS_PATH).mkdir(parents=True, exist_ok=True)
    for value in [
        settings.IMAGE_PATH,
        settings.VIDEO_PATH,
        settings.AUDIO_PATH,
        settings.OUTPUT_PATH,
    ]:
        Path(os.path.join(settings.RUNS_PATH, uuid, value)).mkdir(parents=True, exist_ok=True)
