from dataclasses import dataclass, field

from google.genai import types

from ..core.logging import get_logger
from ..core.settings import settings
from ..utils.genai_client import get_genai_client
from ..utils.retry import retry
from .image_service import RATE_LIMIT_KEYWORDS


logger = get_logger(__name__)


@dataclass
class Research:
    brief: str
    sources: list[dict] = field(default_factory=list)  # [{"title": ..., "uri": ...}]


RESEARCH_PROMPT = """You are the researcher for a short-form history video channel about Nepal.
Use Google Search to research the subject below and write a research brief for the scriptwriter.

{subject}

Prefer reputable sources: academic publications, encyclopedias, museum and government heritage sites,
and established newspapers. Ignore fan wikis, social media and forums.

Write the brief in English with these sections:
- Summary: one line naming the subject, place and period.
- Key people, places and dates.
- Hook: the single most surprising, dramatic or little-known fact - something that would make someone stop scrolling.
- Facts: 6-10 concrete, verifiable facts in chronological order, each with its date where known.
- Legends: popular stories or traditions about it, clearly labelled as legend or tradition, not fact.
- Disputed: anything historians disagree on, labelled as disputed.
Only include what the sources support."""


def _subject(topic: str | None, archive_passage: str | None) -> str:
    if topic:
        return f"Subject: {topic}"
    return (
        "Subject: identify the main historical subject of this passage from our archive, then research it "
        f"further.\n\nPassage:\n{(archive_passage or '')[:3000]}"
    )


@retry(
    exceptions=(Exception,),
    max_attempts=3,
    delay_seconds=10,
    backoff_keywords=RATE_LIMIT_KEYWORDS,
    backoff_delay_seconds=60,
)
def research(topic: str | None = None, archive_passage: str | None = None) -> Research:
    """A web-grounded research brief for a topic, or for the subject of an archive passage."""
    settings.require("CHAT_MODEL")
    response = get_genai_client().models.generate_content(
        model=settings.CHAT_MODEL,
        contents=RESEARCH_PROMPT.format(subject=_subject(topic, archive_passage)),
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
    )
    brief = (response.text or "").strip()
    if not brief:
        raise RuntimeError("Research returned an empty brief")

    metadata = response.candidates[0].grounding_metadata if response.candidates else None
    sources, seen = [], set()
    for chunk in (metadata.grounding_chunks or []) if metadata else []:
        web = getattr(chunk, "web", None)
        if web and web.uri and web.uri not in seen:
            seen.add(web.uri)
            sources.append({"title": web.title or "", "uri": web.uri})

    logger.info(
        "Research brief ready (%d chars, %d sources; searched: %s)",
        len(brief), len(sources), ", ".join((metadata.web_search_queries or []) if metadata else []),
    )
    return Research(brief=brief, sources=sources)
