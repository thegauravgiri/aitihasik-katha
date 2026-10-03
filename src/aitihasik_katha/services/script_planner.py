from dataclasses import dataclass, field

from ..core.logging import get_logger
from ..utils.llm_json import ask_json
from ..utils.retry import retry


logger = get_logger(__name__)

# The Nepali voice-over averages about 2.2 words a second across the channel's runs.
WORDS_PER_SECOND = 2.2
MIN_SECONDS, MAX_SECONDS, DEFAULT_SECONDS = 30, 90, 45

PLAN_PROMPT = """You plan a vertical history video about Nepal (Instagram Reels, TikTok, YouTube Shorts)
before it is written: its length, its single through-line and its story beats.

LENGTH. Pick the shortest length that tells THIS topic well. Viewers who stay to the end are what the platforms
reward, so never pad: every extra 15 seconds must add new information the viewer wants.
- 30 to 40 seconds: one event, one surprising fact, a legend or a single twist.
- 45 to 60 seconds: a story with a few turns, or an event with its cause and its result.
- 65 to 90 seconds: something the viewer needs time to follow: why something started, how a tradition,
  law or institution came about, several linked events, a comparison, or a topic that asks for numbers
  and statistics.

Topic: {topic}

Source material:
{material}

THROUGH-LINE. A confusing video tries to say everything. Choose ONE question the video answers and the
answer in one plain sentence. If the topic asks several things, answer the one viewers care about most and
drop or fold in the rest. Use only what the source material supports: if it does not confirm part of the
question (for example an official declaration or a date), the through-line must say that plainly instead of
pretending it does. A legend is told as a legend, in plain words like "people say".

BEATS. 4 to 7 short English beats in order, each a single idea that follows from the last: the hook (the most
surprising concrete fact, stated first), the context, the turns that raise the stakes, the payoff that
answers the question, and a closing line that points back to the hook so the video feels like it starts again.

Return ONLY a JSON object with this shape:
{{"seconds": 45, "reason": "one short sentence", "angle": "the question and its one-sentence answer",
  "beats": ["...", "..."]}}
"seconds" is a whole number from {low} to {high}."""


@dataclass
class ScriptPlan:
    seconds: int = DEFAULT_SECONDS
    reason: str = ""
    angle: str = ""
    beats: list[str] = field(default_factory=list)

    @property
    def target_words(self) -> int:
        return round(self.seconds * WORDS_PER_SECOND)

    @property
    def min_words(self) -> int:
        """The range the writer is asked for."""
        return round(self.target_words * 0.85)

    @property
    def max_words(self) -> int:
        return round(self.target_words * 1.1)

    @property
    def floor_words(self) -> int:
        """A draft below this is sent back for a rewrite; the range above is a request, this is a limit."""
        return round(self.target_words * 0.7)

    @property
    def ceiling_words(self) -> int:
        return round(self.target_words * 1.25)

    def to_dict(self) -> dict:
        return {
            "seconds": self.seconds,
            "reason": self.reason,
            "angle": self.angle,
            "beats": self.beats,
            "target_words": self.target_words,
        }


@retry(exceptions=(Exception,), max_attempts=2, delay_seconds=5)
def _ask_for_plan(topic: str | None, material: str) -> ScriptPlan:
    data = ask_json(PLAN_PROMPT.format(
        topic=topic or "(none: judge it from the source material)",
        material=material or "(none)",
        low=MIN_SECONDS,
        high=MAX_SECONDS,
    ))
    if not isinstance(data, dict):
        raise ValueError(f"Script plan has unexpected shape: {data!r}")
    seconds = round(float(data["seconds"]))
    beats = data.get("beats") or []
    return ScriptPlan(
        seconds=max(MIN_SECONDS, min(MAX_SECONDS, seconds)),
        reason=str(data.get("reason") or "").strip(),
        angle=str(data.get("angle") or "").strip(),
        beats=[str(b).strip() for b in beats if str(b).strip()] if isinstance(beats, list) else [],
    )


def plan_script(topic: str | None, research_brief: str, archive: str = "") -> ScriptPlan:
    """How long the video should be for this topic. A planning failure falls back to the default
    length: a typical video beats a failed run."""
    try:
        return _ask_for_plan(topic, research_brief or archive[:3000])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Script planning failed, using %ss: %s", DEFAULT_SECONDS, exc)
        return ScriptPlan(DEFAULT_SECONDS, "default length (planning failed)")
