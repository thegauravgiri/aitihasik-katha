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
    EMBEDDING_MODEL: str = ""
    CHAT_MODEL: str = ""
    AUDIO_MODEL: str = ""
    # Animates each scene's opening frame (Veo image-to-video).
    VIDEO_MODEL: str = "veo-3.1-lite-generate-preview"
    # Draws character references (when no real portrait is used) and each scene's opening frame.
    IMAGE_MODEL: str = "gemini-3.1-flash-image"
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
