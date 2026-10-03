from functools import lru_cache

from google.api_core.exceptions import GoogleAPICallError
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from aitihasik_katha.core.settings import settings
from aitihasik_katha.core.logging import get_logger
from aitihasik_katha.utils.nepali import nepali_punctuation, stray_characters
from aitihasik_katha.utils.retry import retry


CAPTION_PROMPT = """You write the Instagram caption for a short Nepal-history video, for a Nepali audience.

LANGUAGE
- Everyday spoken Nepali in Devanagari, the way people talk to friends, mixed naturally with common English
  words (king, palace, festival, secret, real story, share, save). No bookish or Sanskritised words:
  never "किंवदन्ती", "जनविश्वास", "संस्थागत", "दर्शाउँछ", "विराजमान"; say "भनिन्छ", "मान्छेले विश्वास
  गर्छन्", "रोक", "देखाउँछ".
- End Nepali sentences with "।", never ".". Use "?" for questions.
- Hashtags are in English.

STRUCTURE
1. HOOK - the first line, at most 90 characters so it shows in full before Instagram's "more" cut: the
   most shocking concrete fact from the story, in plain words. It makes people stop scrolling.
2. SHORT STORY - 2 to 4 short lines that tell the heart of the video again in a way that makes people want
   to watch. Do not add facts that are not in the story. Mark anything that is only a legend as
   "भनिन्छ".
3. ONE QUESTION - a specific question about this story people can answer in a few words (for example
   "तपाईं भए ढोका खोल्नुहुन्थ्यो?"). Never a generic "तपाईंलाई के लाग्छ?".
4. SEND LINE - one line naming a specific kind of person to send it to, tied to this story (for example
   "यो भिडियो दसैँमा पनि घर नफर्कने साथीलाई पठाउनुहोस्।").
5. SAVE LINE - one short line giving viewers a clear reason to save/bookmark this video for later
   (for example "नेपालको यो अनौठो इतिहास सम्झिराख्न अहिले नै save गरिहाल्नुस्।" or "गोरखा जाँदा नबिर्सिन यो भिडियो save गर्नुहोस्।").
6. FOLLOW LINE - one short, natural line that tells people why to follow: "हरेक हप्ता नेपालको एउटा
   अनसुनेको इतिहास चाहिन्छ भने फलो गर्नुहोस्।" Do not sound salesy.
7. HASHTAGS - 4 to 6 relevant English hashtags at the end, mixing niche and broad.

FORMAT
- Line breaks between parts. No large blocks of text.

Output ONLY the final caption."""

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

    caption = ""
    for attempt in range(3):
        response = _invoke(messages)
        content = response.content
        if isinstance(content, list):
            content = next((item.get("text") for item in content if item.get("type") == "text"), "")
        caption = nepali_punctuation(str(content).strip())
        stray = stray_characters(caption)
        if not stray:
            return caption
        logger.warning("Caption has stray letters %s (attempt %d); asking again", " ".join(stray), attempt + 1)
    # Still glitched after three tries: drop only the stray letters rather than post them.
    return "".join(ch for ch in caption if ch not in stray)
