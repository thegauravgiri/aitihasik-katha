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

    # --- Gemini / Vertex AI models ---
    GEMINI_API_KEY: str = ""
    EMBEDDING_MODEL: str = ""
    CHAT_MODEL: str = ""
    IMAGE_CHAT_MODEL: str = ""
    IMAGE_MODEL: str = ""
    AUDIO_MODEL: str = ""

    # --- Google Cloud project / storage ---
    PROJECT_ID: str = ""
    LOCATION: str = ""
    BUCKET: str = ""
    BUCKET_URI: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # --- Vertex AI Matching Engine (vector store) ---
    DISPLAY_NAME: str = ""
    INDEX_ID: str = ""
    INDEX_ENDPOINT_ID: str = ""
    DEPLOYED_INDEX_ID: str = ""

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
