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


RESEARCH_PROMPT = """You are the lead historical researcher for an authoritative, high-engagement documentary channel about Nepal.
Conduct exhaustive, deep, multi-angle research using Google Search on the subject below. Do NOT settle for superficial summaries, textbook clichés, or basic Wikipedia trivia. Uncover authentic, deeply researched, and unique historical details that educate the viewer and make the content undeniably trustworthy and fascinating.

{subject}

Research & Sourcing Standards:
- Prioritize reputable academic works, historical archives, established historians (such as Mahesh Chandra Regmi, Baburam Acharya, Ludwig Stiller, John Whelpton, Rishikesh Shaha, D.R. Regmi), official gazettes (नेपाल राजपत्र), museum collections, and verified accounts.
- Filter out fan wikis, shallow travel blogs, and unverified social media claims.
- Search specifically for obscure behind-the-scenes mechanics: secret letters, eyewitness memoirs, exact treaties/agreements, code words, specific dates, financial sums, or physical relics.

Write the research brief in English with these structured sections:
- Summary: Subject, exact historical era, and geographical setting.
- Hook: The single most shocking, dramatic, or counter-intuitive revelation—an unexpected betrayal, strange ritual, secret escape, or hidden consequence that shatters common assumptions.
- Untold & Unique Details: 3 to 5 little-known, fascinating facts that ordinary people and standard school curricula never teach (e.g. behind-the-scenes negotiations, concealed motivations, bizarre coincidences, or covert operations).
- Trust Anchors & Primary Evidence: Specific archival evidence, treaties/pacts (e.g. दिल्ली सम्झौता, सुगौली सन्धि), royal seals (लालमोहर, खड्ग निशाना), exact dates, primary quotes, memoirs, or surviving monuments/artifacts that prove the reality of this event.
- Chronological Facts: 6 to 10 concrete, verifiable facts in chronological order, each anchored to its exact date or year where documented.
- Legends vs. Reality: Popular traditions, court rumours, or folklore, clearly distinguished from what documented archival evidence confirms.
- Disputed & Open Mysteries: Areas where reputable historians disagree, or questions that remain unsolved.
- Viral Psychology & Sharing Triggers: Why will people share this video on TikTok/Instagram Reels? (Identify the emotional awe, cultural identity pride, or surprising insight that provides social currency to the viewer).
Only include what the sources support."""


def _subject(topic: str | None) -> str:
    if topic:
        return f"Subject: {topic}"
    return (
        "Subject: Pick an authentic, compelling, and little-known historical event, royal mystery, or turning point "
        "from Nepal's history (such as Licchavi, Malla, Shah unification, or Rana era) that ordinary people would be "
        "fascinated to learn about."
    )


@retry(
    exceptions=(Exception,),
    max_attempts=4,
    delay_seconds=10,
    backoff_keywords=RATE_LIMIT_KEYWORDS,
    backoff_delay_seconds=60,
)
def research(topic: str | None = None) -> Research:
    """A web-grounded research brief for a topic, or for an untold Nepali historical subject."""
    settings.require("CHAT_MODEL")
    response = get_genai_client().models.generate_content(
        model=settings.CHAT_MODEL,
        contents=RESEARCH_PROMPT.format(subject=_subject(topic)),
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
