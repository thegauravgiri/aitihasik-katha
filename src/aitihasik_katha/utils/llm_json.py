import json
from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from ..core.settings import settings


@lru_cache(maxsize=1)
def _get_llm() -> ChatGoogleGenerativeAI:
    settings.require("CHAT_MODEL", "GEMINI_API_KEY")
    return ChatGoogleGenerativeAI(
        model=settings.CHAT_MODEL, api_key=settings.GEMINI_API_KEY, response_mime_type="application/json"
    )


def ask_json(prompt: str):
    """Send a prompt to the chat model and parse its JSON reply."""
    content = _get_llm().invoke(prompt).content
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    text = str(content).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return json.loads(text)
