"""One-time OAuth helpers for provisioning Instagram credentials.

These are setup steps, not part of the runtime publishing pipeline: run this
module directly once when connecting a new Instagram Business account, then
store the resulting page access token and user id as
INSTAGRAM_PAGE_ACCESS_TOKEN / INSTAGRAM_USER_ID in your .env file for
InstagramService (see instagram_service.py) to use on every pipeline run.
"""
import requests

from ..core.logging import get_logger
from ..core.settings import settings


logger = get_logger(__name__)
BASE_URL = "https://graph.facebook.com/v25.0"


def _get(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, timeout=30)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        try:
            details = response.json()
        except ValueError:
            details = {"raw": response.text}
        raise RuntimeError(f"Request failed: {details}") from exc
    return response.json()


def get_long_lived_token(short_lived_token: str) -> str:
    """Step 1: exchange a short-lived user token for a long-lived one (~60 days)."""
    settings.require("INSTAGRAM_CLIENT_ID", "INSTAGRAM_CLIENT_SECRET")
    data = _get(
        f"{BASE_URL}/oauth/access_token",
        {
            "grant_type": "fb_exchange_token",
            "client_id": settings.INSTAGRAM_CLIENT_ID,
            "client_secret": settings.INSTAGRAM_CLIENT_SECRET,
            "fb_exchange_token": short_lived_token,
        },
    )
    return data["access_token"]


def get_page_access_token(long_lived_token: str) -> str:
    """Step 2: get the (effectively) never-expiring Page Access Token."""
    data = _get(f"{BASE_URL}/me/accounts", {"access_token": long_lived_token})
    pages = data.get("data", [])
    if not pages:
        raise RuntimeError("No pages found. Make sure your app is linked to a Facebook Page.")
    return pages[0]["access_token"]


def get_user_id(page_access_token: str) -> str:
    """Step 3: look up the Instagram Business Account id linked to the Page."""
    data = _get(
        f"{BASE_URL}/me",
        {"fields": "instagram_business_account", "access_token": page_access_token},
    )
    return data["instagram_business_account"]["id"]


if __name__ == "__main__":
    short_lived = input("Paste a short-lived user access token: ").strip()
    long_lived = get_long_lived_token(short_lived)
    page_token = get_page_access_token(long_lived)
    user_id = get_user_id(page_token)
    logger.info("INSTAGRAM_PAGE_ACCESS_TOKEN=%s", page_token)
    logger.info("INSTAGRAM_USER_ID=%s", user_id)
