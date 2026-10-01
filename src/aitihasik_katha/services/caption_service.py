from functools import lru_cache

from google.api_core.exceptions import GoogleAPICallError
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from aitihasik_katha.core.settings import settings
from aitihasik_katha.core.logging import get_logger
from aitihasik_katha.utils.retry import retry


CAPTION_PROMPT = """You are an expert Instagram growth strategist and viral content writer.

Your task is to generate a HIGH-PERFORMING Instagram caption based on the given story or script.

Follow these rules strictly to align with the latest Instagram algorithm (2025–2026):

1. HOOK (First Line is Critical)
- Start with a powerful, curiosity-driven or emotional hook, at most 90 characters, so it shows in full
  before Instagram's "more" cut.
- Make people STOP scrolling within 1–2 seconds. Use the most shocking concrete fact from the story.
- Keep it short, punchy, and relatable.

2. STORY / VALUE
- Convert the provided story into engaging storytelling or value-driven content.
- Make it human, emotional, or insightful.
- Use natural language (no robotic or keyword stuffing).
- Maintain clarity and flow.

3. ENGAGEMENT TRIGGERS
- Ask ONE specific question about this story that people can disagree on or answer in a few words
  (for example "Would you have opened the gates?" or "Which of these two kings was right?").
  Never a generic "What do you think?".
- Aim to increase comments, shares, and saves.

4. SHAREABILITY OPTIMIZATION
- Sends to friends are the strongest signal on Instagram. Include one line that names a specific kind of
  person to send it to, tied to this story.
  Examples:
  “Send this to the friend who still thinks Dashain is only about food.”
  “Send this to someone from Patan.”

5. CALL TO ACTION (CTA)
- Include a soft CTA such as:
  - “Save this”
  - “Share this”
  - “Follow for more”
- Do NOT sound salesy.

6. SEO + KEYWORDS
- Naturally include relevant keywords from the story.
- Make the caption searchable and context-rich.

7. HASHTAGS (Modern Strategy)
- Add 4–6 highly relevant hashtags.
- Mix niche + broad tags.
- Place hashtags at the end.

8. TONE
- Match tone to content (emotional, funny, motivational, educational, etc.)
- Keep it authentic, not generic.

9. LENGTH
- Adapt length based on story:
  - Short for punchy content
  - Longer for storytelling

10. FORMAT
- Use line breaks for readability.
- Avoid large blocks of text.

LANGUAGE: ALWAYS ENGLISH, Despite the story being in other language.

Output ONLY the final Instagram caption."""

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_llm() -> ChatGoogleGenerativeAI:
    settings.require("CHAT_MODEL", "GEMINI_API_KEY")
    return ChatGoogleGenerativeAI(
        model=settings.CHAT_MODEL,
        api_key=settings.GEMINI_API_KEY,
    )


@retry(exceptions=(GoogleAPICallError, RuntimeError, ValueError, TypeError), max_attempts=3, delay_seconds=5)
def _invoke(messages: list) -> object:
    return _get_llm().invoke(messages)


def generate_caption(story) -> str:
    messages = [
        SystemMessage(CAPTION_PROMPT),
        HumanMessage(story)
    ]

    response = _invoke(messages)
    caption = response.content
    if isinstance(caption, list):
        for item in caption:
            if item.get("type") == "text":
                return item.get("text")
    return str(caption)


if __name__ == "__main__":
    logger.info(generate_caption("a man with passion"))