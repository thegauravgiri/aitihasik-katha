from dataclasses import dataclass, field
from functools import lru_cache

# Must be imported before langchain_google_genai below: faiss's native library needs to
# init before anything pulling in gRPC/protobuf, or the process segfaults. See cli.py.
from ..storage.vector_store import get_store

from langchain_google_genai import ChatGoogleGenerativeAI

from ..core.logging import get_logger
from ..core.settings import settings
from ..utils.retry import retry
from .research_service import research


logger = get_logger(__name__)

MAX_ARCHIVE_CHARS = 25_000

STORY_PROMPT = """You write the narration for 45-60 second vertical history videos about Nepal
(Instagram Reels, TikTok, YouTube Shorts). It is read aloud by a voice-over and shown as word-by-word
captions. The goal: viewers stay until the last second, learn something real, and feel compelled to
like, comment and share.

Use ONLY the research brief and archive excerpts below for facts. If something is a legend or disputed,
say so in the narration (for example "किंवदन्ती अनुसार..." or "इतिहासकारहरू अझै विवाद गर्छन्...").

Structure:
1. HOOK - the first sentence, spoken in under 3 seconds: the most shocking, surprising or dramatic fact,
   a bold claim, or a question that opens a curiosity gap. Never open with background, dates, or
   "एक समयको कुरा हो".
2. CONTEXT - one or two sentences: who, where, when. Just enough to follow.
3. ESCALATION - four to seven sentences told as a story with rising stakes, conflict and vivid, concrete
   details. Every two or three sentences, open a new loop or turn ("तर यो त सुरुवात मात्र थियो...",
   "तर त्यसपछि जे भयो, कसैले सोचेका थिएनन्...") so the viewer needs to keep watching.
4. PAYOFF - one or two sentences: the twist, outcome or revelation the hook promised.
5. CLOSE - one sentence on why it still matters today or a question that invites comments, then a short,
   natural nudge to like and follow for more hidden history of Nepal.

Style:
- Nepali only. Spoken, energetic, simple language - a gripping storyteller, not a textbook.
- Short sentences of 5 to 12 words. Each sentence becomes its own on-screen shot, so each should paint one
  clear picture.
- 100 to 140 words in total.
- Plain text only: no headings, labels, emojis, bullet points, quotation marks or stage directions.

## Research brief
{research}

## Archive excerpts
{archive}
"""


@dataclass
class Story:
    text: str
    research_brief: str = ""
    sources: list[dict] = field(default_factory=list)


@lru_cache(maxsize=1)
def _get_llm() -> ChatGoogleGenerativeAI:
    settings.require("CHAT_MODEL", "GEMINI_API_KEY")
    return ChatGoogleGenerativeAI(model=settings.CHAT_MODEL, api_key=settings.GEMINI_API_KEY)


def get_archive_context(topic: str | None = None) -> tuple[str, str]:
    """Matching passages from the local archive, plus the passage the story is seeded
    from (a random one when there's no topic)."""
    store = get_store()
    seed = topic or store.get_random_document()["documents"]
    documents = store.get_similar_documents(seed)
    return "---\n".join(document.strip() for document in documents)[:MAX_ARCHIVE_CHARS], seed


@retry(exceptions=(Exception,), max_attempts=3, delay_seconds=5)
def _invoke(prompt: str) -> str:
    content = _get_llm().invoke(prompt).content
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    text = str(content).strip()
    if not text:
        raise RuntimeError("Story generation returned empty text")
    return text


def write_story(topic: str | None = None) -> Story:
    """Narration for one video.

    With a topic, the web research on that topic leads and matching archive passages
    support it. Without one, a random archive passage picks the subject and the web
    research expands on it.
    """
    archive, seed = get_archive_context(topic)

    brief, sources = "", []
    if settings.USE_WEB_RESEARCH:
        try:
            result = research(topic=topic, archive_passage=None if topic else seed)
            brief, sources = result.brief, result.sources
        except Exception as exc:  # noqa: BLE001 - the archive alone is still enough to write a story
            logger.warning("Web research failed, writing from the archive only: %s", exc)

    text = _invoke(STORY_PROMPT.format(research=brief or "(none)", archive=archive or "(none)"))
    return Story(text=text, research_brief=brief, sources=sources)
