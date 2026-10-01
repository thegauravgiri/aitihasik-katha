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
from .review_service import review_story
from .script_planner import ScriptPlan, plan_script


logger = get_logger(__name__)

MAX_ARCHIVE_CHARS = 25_000

MAX_REVISIONS = 2

STORY_PROMPT = """You write the narration for a vertical history video about Nepal (Instagram Reels,
TikTok, YouTube Shorts) planned to run about {seconds} seconds. It is read aloud by a voice-over and
shown as word-by-word captions. The goal: viewers stay until the last second, watch it again, learn something real, and send
it to a friend.

The video must be about the topic below and answer what it asks. Use ONLY the research brief and
archive excerpts below for facts, and ignore any excerpt that is not about the topic. If something is a
legend or disputed, say so in the narration (for example "किंवदन्ती अनुसार..." or
"इतिहासकारहरू अझै विवाद गर्छन्...").

Structure:
1. HOOK - the first sentence, spoken in under 3 seconds: one specific, visual shock that a stranger
   understands at once. Name the concrete thing: a number, a ban, a death, a betrayal, an "only place on
   Earth" claim, or a strange ritual together with its consequence. Never open with scenery, background,
   dates, "कल्पना गर्नुहोस्...", "यदि मैले भनें...", or "एक समयको कुरा हो".
2. CONTEXT - one sentence: who, where, when. Just enough to follow.
3. ESCALATION - short sentences told as a story with rising stakes and vivid, concrete details, about
   one new fact or turn every four to five seconds. Around 12-15 seconds in, open a second loop with a
   turn that makes the viewer need the answer ("तर यो त सुरुवात मात्र थियो...", "तर त्यसपछि जे भयो..."),
   and open a fresh one about every 15 seconds after that if the video is longer.
4. PAYOFF - one sentence: the twist, outcome or answer the hook promised.
5. LOOP ENDING - the last sentence calls back to the hook's image or words, or leaves one sharp question
   unanswered, so the video feels like it starts again. Do NOT ask viewers to like, comment or follow;
   that goes in the caption.

Style:
- Nepali only. Spoken, energetic, simple language - a gripping storyteller, not a textbook.
- Short sentences of 5 to 12 words. Each sentence becomes its own on-screen shot, so each should paint one
  clear picture.
- {min_words} to {max_words} words in total, which is the planned length. Do not pad: every sentence must
  add something new, because viewers who reach the end are what the platforms reward.
- Plain text only: no headings, labels, emojis, bullet points, quotation marks or stage directions.

Hooks that worked best on this channel (translated; copy the pattern, not the topic):
- They banned this ancient dance forever after a man was swallowed alive. (a ban plus a shocking consequence)
- There is only one country on Earth where... (a uniqueness claim)
- Before celebrating its biggest festival, an entire nation pauses for... (a festival plus an unexpected ritual)
- This king died 300 years ago, but his palace still prepares his bed. (a present-day fact that sounds impossible)
Hooks that got almost no views: "Imagine a land where the peaks touch the sky", "A land where history
breathes in every stone", "Where the earth finally touches the sky".

## Topic
{topic}

## Research brief
{research}

## Archive excerpts
{archive}
"""

REVISION_NOTE = """

## Revision needed
Your previous draft:
{draft}

Fix these problems:
{feedback}

Write the full corrected narration again, following every rule above."""


@dataclass
class Story:
    text: str
    research_brief: str = ""
    sources: list[dict] = field(default_factory=list)
    plan: dict = field(default_factory=dict)  # the planned length, see script_planner.ScriptPlan


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
        except Exception as exc:  # noqa: BLE001
            # A requested topic is rarely covered by the archive, which would then steer the
            # story to an unrelated subject; fail so the run can be resumed instead.
            if topic:
                raise RuntimeError(f"Web research failed for the topic, not writing the story: {exc}") from exc
            logger.warning("Web research failed, writing from the archive only: %s", exc)

    plan = plan_script(topic, brief, archive)
    logger.info("Planned a %ss video (about %d words): %s", plan.seconds, plan.target_words, plan.reason)
    prompt = STORY_PROMPT.format(
        seconds=plan.seconds,
        min_words=plan.min_words,
        max_words=plan.max_words,
        topic=topic or "(none: tell the story from the archive excerpts)",
        research=brief or "(none)",
        archive=archive or "(none)",
    )
    text = _invoke(prompt)
    for revision in range(MAX_REVISIONS + 1):
        problems, off_topic = _find_problems(topic, text, brief, plan)
        if not problems:
            break
        logger.warning("Draft %d needs changes: %s", revision + 1, "; ".join(problems))
        if revision == MAX_REVISIONS:
            if off_topic:
                raise RuntimeError(f"The story still does not answer the topic after {MAX_REVISIONS} rewrites")
            logger.warning("Using the last draft despite the notes above")
            break
        feedback = "\n".join(f"- {problem}" for problem in problems)
        text = _invoke(prompt + REVISION_NOTE.format(draft=text, feedback=feedback))
    return Story(text=text, research_brief=brief, sources=sources, plan=plan.to_dict())


def _find_problems(
    topic: str | None, text: str, brief: str, plan: ScriptPlan
) -> tuple[list[str], bool]:
    """What is wrong with a draft, and whether it misses the requested topic."""
    problems: list[str] = []
    words = len(text.split())
    if words > plan.ceiling_words:
        problems.append(
            f"It is {words} words. Cut it to at most {plan.max_words} words by removing detail, not the hook."
        )
    elif words < plan.floor_words:
        problems.append(
            f"It is only {words} words. Write {plan.min_words} to {plan.max_words} words with the full structure."
        )

    off_topic = False
    if settings.USE_STORY_REVIEW:
        try:
            review = review_story(topic, text, brief)
        except Exception as exc:  # noqa: BLE001 - a broken reviewer must not block the video
            logger.warning("Story review failed, skipping it: %s", exc)
            return problems, False
        if topic and not review.answers_topic:
            off_topic = True
            problems.append(f"It does not answer the topic: {topic}")
        problems.extend(
            f"Remove or soften this claim, which the research does not support: {claim}"
            for claim in review.unsupported_claims
        )
        if review.weak_hook:
            problems.append(f"The hook is weak ({review.hook_issue or 'vague'}). Open with one specific, visual shock.")
    return problems, off_topic
