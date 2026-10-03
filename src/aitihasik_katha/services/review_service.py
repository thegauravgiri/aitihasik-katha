from dataclasses import dataclass, field

from ..utils.llm_json import ask_json
from ..utils.retry import retry


REVIEW_PROMPT = """You are the editor and fact-checker for short history videos about Nepal.
Check the narration below against the topic and the research brief.

Topic: {topic}

Research brief:
{research}

Narration:
{story}

Return ONLY a JSON object with this shape:
{{
  "answers_topic": true or false,
  "unsupported_claims": ["..."],
  "weak_hook": true or false,
  "hook_issue": "...",
  "confusing_parts": ["..."]
}}

- answers_topic: true only if the narration is about the topic and answers what it asks. If the topic
  is "(none)", answer true.
- unsupported_claims: specific names, dates, numbers or events in the narration that the research
  brief does not support, and legends stated as fact. Quote each briefly. Use an empty list if there
  are none, or if the research brief is "(none)".
- weak_hook: true if the first sentence would not make a stranger stop scrolling: vague scenery, a generic
  "imagine..." or "what if..." opener, background information, or a question that only restates the
  topic. A strong hook is one specific, surprising, concrete fact or event that the viewer needs
  explained. Be strict: when in doubt, answer true.
- hook_issue: one short sentence on what is wrong with the hook, or an empty string.
- confusing_parts: put yourself in the place of a 16-year-old in Kathmandu who knows no history and hears
  this once at normal speed. Quote any sentence they would not understand, that does not follow from the
  sentence before it, that contradicts another sentence, that repeats a point, or that uses a word they
  would have to look up. Use an empty list if everything is clear.
"""


@dataclass
class Review:
    answers_topic: bool = True
    unsupported_claims: list[str] = field(default_factory=list)
    weak_hook: bool = False
    hook_issue: str = ""
    confusing_parts: list[str] = field(default_factory=list)


def _strings(value) -> list[str]:
    return [str(v).strip() for v in value if str(v).strip()] if isinstance(value, list) else []


@retry(exceptions=(Exception,), max_attempts=2, delay_seconds=5)
def review_story(topic: str | None, story: str, research_brief: str) -> Review:
    data = ask_json(REVIEW_PROMPT.format(topic=topic or "(none)", research=research_brief or "(none)", story=story))
    if not isinstance(data, dict):
        raise ValueError(f"Review has unexpected shape: {data!r}")
    return Review(
        answers_topic=bool(data.get("answers_topic", True)),
        unsupported_claims=_strings(data.get("unsupported_claims")),
        weak_hook=bool(data.get("weak_hook", False)),
        hook_issue=str(data.get("hook_issue") or "").strip(),
        confusing_parts=_strings(data.get("confusing_parts")),
    )
