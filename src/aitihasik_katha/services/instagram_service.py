from functools import lru_cache
import time

import requests
from requests.exceptions import ConnectionError, Timeout

from aitihasik_katha.core.settings import settings
from aitihasik_katha.core.logging import get_logger
from aitihasik_katha.utils.retry import retry


logger = get_logger(__name__)

class InstagramService:
    """Publishes pre-generated media to Instagram.

    Credentials (page access token, user id) are provisioned once via
    instagram_oauth.py, not by this class.
    """

    BASE_URL = "https://graph.facebook.com/v25.0"

    def __init__(self, user_id: str, page_access_token: str):
        self.user_id = user_id
        self.page_access_token = page_access_token

    @retry(exceptions=(ConnectionError, Timeout), max_attempts=3, delay_seconds=5)
    def _get(self, url: str, params: dict) -> dict:
        """Helper: GET request with error handling."""
        response = requests.get(url, params=params, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            try:
                details = response.json()
            except ValueError:
                details = {"raw": response.text}
            raise RuntimeError(f"Request failed: {details}") from exc
        logger.debug("Instagram GET %s returned status %s", url, response.status_code)
        return response.json()

    @retry(exceptions=(ConnectionError, Timeout), max_attempts=3, delay_seconds=5)
    def _post(self, url: str, params: dict) -> dict:
        """Helper: POST request with error handling."""
        response = requests.post(url, params=params, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            try:
                details = response.json()
            except ValueError:
                details = {"raw": response.text}
            raise RuntimeError(f"Request failed: {details}") from exc
        return response.json()

    def create_media_container(self, media_url, caption, media_type="REELS", cover_url=None):
        url = f"{self.BASE_URL}/{self.user_id}/media"
        media_type = media_type.strip().upper()
        reel = {"media_type": "REELS", "video_url": media_url, "caption": caption}
        # A cover image replaces the frame Instagram would otherwise pick from the video.
        reel.update({"cover_url": cover_url} if cover_url else {"thumb_offset": 0})
        media_configs = {
            "IMAGE": {
                "image_url": media_url,
                "caption": caption,
            },
            "REELS": reel,
        }

        if media_type not in media_configs:
            raise ValueError(f"Unsupported media_type: {media_type}")

        params = {
            **media_configs[media_type],
            "access_token": self.page_access_token
        }
        try:
            response = self._post(url, params)
            media_id = response.get("id")
            return media_id
        except RuntimeError as exc:
            logger.error("Failed creating media container: %s", exc)
            return ""


    def upload_media(
        self,
        media_url,
        caption,
        media_type="REELS",
        max_wait_seconds: int = 900,
        poll_interval_seconds: int = 60,
        cover_url=None,
    ):
        media_container_id = self.create_media_container(
            media_url, caption, media_type, cover_url
        )
        if not media_container_id and cover_url:
            logger.warning("Instagram rejected the cover image; posting with an automatic cover instead")
            media_container_id = self.create_media_container(media_url, caption, media_type)

        if not media_container_id:
            logger.error("Failed to create media container")
            return

        publish_url = f"{self.BASE_URL}/{self.user_id}/media_publish"
        params = {
            "creation_id": media_container_id,
            "access_token": self.page_access_token,
        }

        waited_seconds = 0
        while not self.is_media_ready(media_container_id):
            if waited_seconds >= max_wait_seconds:
                logger.error("Media still not ready after %ss, giving up", max_wait_seconds)
                return
            logger.info("Media not ready, retrying in %ss", poll_interval_seconds)
            time.sleep(poll_interval_seconds)
            waited_seconds += poll_interval_seconds

        try:
            response = self._post(publish_url, params)
            if response:
                logger.info(
                    "Post published for caption preview: %s...",
                    caption if len(caption) < 50 else caption[:50],
                )
        except RuntimeError as exc:
            logger.error("Error uploading to Instagram: %s", exc)
    
    def is_media_ready(self, media_container_id: str) -> bool:
        """Check Instagram media container processing status."""
        url = f"{self.BASE_URL}/{media_container_id}"
        params = {
            "access_token": self.page_access_token,
            "fields": "status_code",
        }
        data = self._get(url, params)
        if data.get("status_code") == "ERROR":
            raise RuntimeError("Media upload failed!")
        return data.get("status_code") == "FINISHED"


@lru_cache(maxsize=1)
def get_instagram_service() -> InstagramService:
    settings.require("INSTAGRAM_USER_ID", "INSTAGRAM_PAGE_ACCESS_TOKEN")
    return InstagramService(
        user_id=settings.INSTAGRAM_USER_ID,
        page_access_token=settings.INSTAGRAM_PAGE_ACCESS_TOKEN,
    )