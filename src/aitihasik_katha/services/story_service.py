import re
from dataclasses import dataclass, field
from functools import lru_cache

# Must be imported before langchain_google_genai below: faiss's native library needs to
# init before anything pulling in gRPC/protobuf, or the process segfaults. See cli.py.
from ..storage.vector_store import get_store

from langchain_google_genai import ChatGoogleGenerativeAI

from ..core.logging import get_logger
from ..core.settings import settings
from ..utils.nepali import bookish_words, long_sentences, nepali_punctuation, stray_characters
from ..utils.retry import retry
from .research_service import research
from .review_service import review_story
from .script_planner import ScriptPlan, plan_script


logger = get_logger(__name__)

MAX_ARCHIVE_CHARS = 25_000

MAX_REVISIONS = 3
BANNED_OPENERS = ("तपाईंलाई थाहा छ", "के तपाईंलाई", "कल्पना गर्नुहोस्", "भनिन्छ", "किंवदन्ती", "एक समयको")

STORY_PROMPT = """You write the narration for a vertical history video about Nepal (Instagram Reels, TikTok,
YouTube Shorts) planned to run about {seconds} seconds. It is read aloud by a voice-over and shown as
word-by-word captions. The goal: a viewer who knows NOTHING about history understands every sentence the
first time they hear it, stays to the end, watches again, and sends it to a friend.

LANGUAGE - this matters most
- Write the way a Nepali YouTuber talks to friends in Kathmandu: everyday spoken Nepali in Devanagari,
  mixed naturally with common English words people really say (king, palace, festival, secret, real story,
  wait, seriously, shocking, viral, officially). Not a news anchor, not a textbook, not a poem.
- Use simple, everyday words. Never use bookish or Sanskritised words. Say "भनिन्छ" or "मान्छेहरू भन्छन्",
  never "किंवदन्ती" or "जनविश्वास"; "रोक" never "प्रतिबन्ध"; "देखाउँछ" never "दर्शाउँछ"; "मरिसकेका"
  never "दिवंगत".
- If you must use an old or unfamiliar word (पिङ, तान्त्रिक, नरबलि), explain it in plain words the first
  time ("पिङ, मतलब बाँसको ठूलो झुला").
- Use the sentence-ending "।" in Nepali, never ".".

CLARITY
- The video answers ONE question. Follow the plan below; do not add facts from outside it, and do not try
  to cover everything.
- Leave out side details that do not move the answer forward (what an object's shape resembles, which god a
  thing is linked to, extra names). Keep religion out unless the topic is about it, and then stay neutral.
- Each sentence must follow from the one before it, so the viewer can say why it comes next. No list of
  loosely related facts, no sentence that contradicts or repeats another, and no empty filler such as
  "अनौठो", "रहस्यमय" or "तर यो त सुरुवात मात्र थियो" unless the next sentence delivers something that
  really is bigger.
- Use ONLY the research brief and archive excerpts for facts. If they do not confirm something the
  topic asks about (an official declaration, a date, a number), say so in one short plain sentence such as
  "यसको पक्का प्रमाण भने भेटिँदैन।" Never invent it. A legend is told as a legend: "भनिन्छ ... ।"

STRUCTURE
1. HOOK - the first sentence, under 3 seconds: one specific, visual shock a stranger understands at once:
   a number, a ban, a death, a betrayal, an "only place on Earth" claim, or a strange ritual with its
   consequence. It must stand on its own and follow the plan's first beat. Never open with "तपाईंलाई थाहा
   छ", "कल्पना गर्नुहोस्", "भनिन्छ", a date, scenery or background, and never with a question that merely
   restates the topic ("दसैँमा पिङ किन खेलिन्छ?"). A legend can be the hook: tell it as the surprising story
   itself, then say in the very next sentence that it is a folk tale ("यो लोककथा हो।").
2. CONTEXT - one short sentence: who, where, when.
3. STORY - short sentences with rising stakes and concrete details (names, numbers, places), about one new
   fact or turn every four to five seconds. Around 12-15 seconds in, and about every 15 seconds after that,
   open a new question the viewer needs answered, using a real turn from the plan, not a stock phrase.
4. PAYOFF - the answer the hook promised, in plain words.
5. LOOP ENDING - the last sentence points back to the hook's image or words, or leaves one sharp question
   open, so the video feels like it starts again. No call to like, comment or follow; that goes in the
   caption.

STYLE
- Only Nepali (Devanagari) and English letters. No letters from any other script.
- Sentences of 5 to 10 words, never more than 12. Each becomes its own on-screen shot, so each paints one
  clear picture.
- {min_words} to {max_words} words in total, the planned length. Do not pad: every sentence must add
  something new.
- Plain text only: no headings, labels, emojis, bullet points, quotation marks or stage directions.

This is the voice to aim for (a different story, shown only for tone):
३०० वर्ष अघि मरेको राजाको ओछ्यान आज पनि हरेक दिन सजाइन्छ। पाटनका राजा योगनरेन्द्र मल्लले मर्नु अघि अचम्मको कसम खाएका थिए। उनले आफ्नै मूर्तिमाथि सुनको चरा राखे। अनि भने, यो चरा नउडेसम्म म मरेको होइन।

Hooks that worked best on this channel (translated; copy the pattern, not the topic):
- They banned this ancient dance forever after a man was swallowed alive. (a ban plus a shocking consequence)
- There is only one country on Earth where... (a uniqueness claim)
- Before celebrating its biggest festival, an entire nation pauses for... (a festival plus a surprising act)
- This king died 300 years ago, but his palace still prepares his bed. (a present-day fact that sounds impossible)
Hooks that got almost no views: "Imagine a land where the peaks touch the sky", "A land where history
breathes in every stone", "Where the earth finally touches the sky".

## Topic
{topic}

## Plan
Through-line: {angle}
Beats, in order:
{beats}

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

IMPORTANT RULES FOR THIS REWRITE:
- If a sentence was flagged as an unsupported claim or unconfirmed fact, REMOVE that sentence entirely from the story or replace it only with facts confirmed in the research brief. Do NOT repeat or rephrase the unconfirmed claim.
- If a word was flagged as bookish, replace it with the suggested everyday spoken word.
- Keep the exact word count within the planned budget.

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
        angle=plan.angle or "(choose one clear question and answer it)",
        beats="\n".join(f"- {beat}" for beat in plan.beats) or "- (hook, context, turns, payoff, loop ending)",
        research=brief or "(none)",
        archive=archive or "(none)",
    )
    text = nepali_punctuation(_invoke(prompt))
    for revision in range(MAX_REVISIONS + 1):
        found = _find_problems(topic, text, brief, plan)
        if not found.problems:
            break
        logger.warning("Draft %d needs changes: %s", revision + 1, "; ".join(found.problems))
        if revision == MAX_REVISIONS:
            if found.off_topic:
                raise RuntimeError(f"The story still does not answer the topic after {MAX_REVISIONS} rewrites")
            if found.unsupported:
                raise RuntimeError(
                    f"The story still contains claims the research does not support after {MAX_REVISIONS} rewrites: "
                    + "; ".join(found.unsupported)
                )
            logger.warning("Using the last draft despite the notes above")
            break
        feedback = "\n".join(f"- {problem}" for problem in found.problems)
        text = nepali_punctuation(_invoke(prompt + REVISION_NOTE.format(draft=text, feedback=feedback)))
    return Story(text=text, research_brief=brief, sources=sources, plan=plan.to_dict())


@dataclass
class _Problems:
    problems: list[str] = field(default_factory=list)
    off_topic: bool = False
    unsupported: list[str] = field(default_factory=list)


def _find_problems(topic: str | None, text: str, brief: str, plan: ScriptPlan) -> _Problems:
    """What is wrong with a draft. Off-topic drafts and claims the research does not support are
    kept apart because they are the ones that must never be published."""
    found = _Problems()
    words = len(text.split())
    if words > plan.ceiling_words:
        found.problems.append(
            f"It is {words} words. Cut it to at most {plan.max_words} words by removing detail, not the hook."
        )
    elif words < plan.floor_words:
        found.problems.append(
            f"It is only {words} words. Write {plan.min_words} to {plan.max_words} words with the full structure."
        )

    if text.lstrip().startswith(BANNED_OPENERS):
        found.problems.append("The first sentence is a stock opener. Open with the specific, visual shock itself.")
    if stray := stray_characters(text):
        found.problems.append("These letters do not belong in Nepali or English text, remove them: " + " ".join(stray))
    if bookish := bookish_words(text):
        found.problems.append("These words are too bookish to say out loud, use the plain word: " + "; ".join(bookish))
    sentence_count = max(1, len([s for s in re.split(r"[.!?।]+", text) if s.strip()]))
    if (long := long_sentences(text)) and len(long) / sentence_count > 0.25:
        found.problems.append(
            f"{len(long)} sentences are longer than 12 words. Split them so each is 5 to 10 words, for example: {long[0]}"
        )

    if settings.USE_STORY_REVIEW:
        try:
            review = review_story(topic, text, brief)
        except Exception as exc:  # noqa: BLE001 - a broken reviewer must not block the video
            logger.warning("Story review failed, skipping it: %s", exc)
            return found
        if topic and not review.answers_topic:
            found.off_topic = True
            found.problems.append(f"It does not answer the topic: {topic}")
        for claim in review.unsupported_claims:
            found.unsupported.append(claim)
            found.problems.append(
                f"Remove this claim or say plainly that it is not confirmed, because the research does not support it: {claim}"
            )
        found.problems.extend(f"This is confusing or does not follow from the sentence before: {part}" for part in review.confusing_parts)
        if review.weak_hook:
            found.problems.append(f"The hook is weak ({review.hook_issue or 'vague'}). Open with one specific, visual shock.")
    return found
