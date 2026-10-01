import pytest

from aitihasik_katha.core.settings import settings
from aitihasik_katha.services import story_service
from aitihasik_katha.services.research_service import Research
from aitihasik_katha.services.review_service import Review
from aitihasik_katha.services.script_planner import ScriptPlan

GOOD = " ".join(["शब्द"] * 90)
TOO_LONG = " ".join(["शब्द"] * 140)
LONG_STORY = " ".join(["शब्द"] * 190)
TOPIC = "Why are kites flown during Dashain?"


class _FakeStore:
    def get_random_document(self):
        return {"documents": "a random archive passage"}

    def get_similar_documents(self, seed):
        return ["King Yognarendra Malla and the golden bird"]


@pytest.fixture
def wired(monkeypatch):
    """Drafts come from `drafts` in order (the last one repeats); reviews from `reviews`."""
    state = {"prompts": [], "drafts": [GOOD], "reviews": [Review()], "review_calls": [], "plan": ScriptPlan(45, "a story with turns")}
    monkeypatch.setattr(story_service, "get_store", lambda: _FakeStore())
    monkeypatch.setattr(story_service, "research", lambda topic, archive_passage: Research(brief="kite facts"))
    monkeypatch.setattr(settings, "USE_WEB_RESEARCH", True)
    monkeypatch.setattr(settings, "USE_STORY_REVIEW", True)

    def _invoke(prompt):
        state["prompts"].append(prompt)
        index = min(len(state["prompts"]) - 1, len(state["drafts"]) - 1)
        return state["drafts"][index]

    def _review(topic, text, brief):
        state["review_calls"].append((topic, text, brief))
        return state["reviews"][min(len(state["review_calls"]) - 1, len(state["reviews"]) - 1)]

    monkeypatch.setattr(story_service, "_invoke", _invoke)
    monkeypatch.setattr(story_service, "review_story", _review)
    monkeypatch.setattr(story_service, "plan_script", lambda topic, brief, archive: state["plan"])
    return state


def test_the_requested_topic_reaches_the_story_prompt(wired):
    story_service.write_story(topic=TOPIC)

    assert TOPIC in wired["prompts"][0]
    assert "kite facts" in wired["prompts"][0]


def test_the_prompt_asks_for_the_planned_length_a_loop_ending_and_no_spoken_call_to_action(wired):
    story_service.write_story(topic=TOPIC)

    prompt, plan = wired["prompts"][0], wired["plan"]
    assert "about 45 seconds" in prompt
    assert f"{plan.min_words} to {plan.max_words} words" in prompt
    assert "LOOP ENDING" in prompt
    assert "Do NOT ask viewers to like, comment or follow" in prompt


def test_failed_research_for_a_topic_stops_instead_of_writing_from_the_archive(wired, monkeypatch):
    def _broken(topic, archive_passage):
        raise RuntimeError("search unavailable")

    monkeypatch.setattr(story_service, "research", _broken)

    with pytest.raises(RuntimeError, match="Web research failed for the topic"):
        story_service.write_story(topic=TOPIC)

    assert wired["prompts"] == []


def test_failed_research_without_a_topic_still_writes_from_the_archive(wired, monkeypatch):
    def _broken(topic, archive_passage):
        raise RuntimeError("search unavailable")

    monkeypatch.setattr(story_service, "research", _broken)

    story = story_service.write_story()

    assert story.text == GOOD
    assert "golden bird" in wired["prompts"][0]


def test_a_draft_that_passes_review_is_used_as_is(wired):
    story = story_service.write_story(topic=TOPIC)

    assert story.text == GOOD
    assert len(wired["prompts"]) == 1
    assert wired["review_calls"][0][0] == TOPIC


def test_a_draft_that_is_too_long_is_rewritten_shorter(wired):
    wired["drafts"] = [TOO_LONG, GOOD]

    story = story_service.write_story(topic=TOPIC)

    assert story.text == GOOD
    assert "It is 140 words" in wired["prompts"][1]
    assert f"at most {wired['plan'].max_words} words" in wired["prompts"][1]
    assert TOO_LONG in wired["prompts"][1]


def test_an_explanatory_topic_gets_a_longer_script_without_being_cut(wired):
    wired["plan"] = ScriptPlan(85, "why and how: needs time")
    wired["drafts"] = [LONG_STORY]

    story = story_service.write_story(topic=TOPIC)

    assert story.text == LONG_STORY
    assert len(wired["prompts"]) == 1
    assert "about 85 seconds" in wired["prompts"][0]
    assert story.plan == {"seconds": 85, "reason": "why and how: needs time", "target_words": 187}


def test_the_same_draft_is_too_long_for_a_short_plan_and_too_short_for_a_long_one(wired):
    wired["plan"] = ScriptPlan(30)
    wired["drafts"] = [GOOD, " ".join(["शब्द"] * 66)]
    short_story = story_service.write_story(topic=TOPIC)
    assert "It is 90 words" in wired["prompts"][1]
    assert len(short_story.text.split()) == 66

    wired["prompts"].clear()
    wired["plan"] = ScriptPlan(90)
    wired["drafts"] = [GOOD, LONG_STORY]
    story_service.write_story(topic=TOPIC)
    assert "It is only 90 words" in wired["prompts"][1]


def test_review_notes_are_given_to_the_rewrite(wired):
    wired["drafts"] = [GOOD, GOOD + " नयाँ"]
    wired["reviews"] = [
        Review(unsupported_claims=["the king ruled for 40 years"], weak_hook=True, hook_issue="it opens with scenery"),
        Review(),
    ]

    story = story_service.write_story(topic=TOPIC)

    assert story.text.endswith("नयाँ")
    rewrite_prompt = wired["prompts"][1]
    assert "the king ruled for 40 years" in rewrite_prompt
    assert "it opens with scenery" in rewrite_prompt


def test_a_story_that_never_answers_the_topic_fails_the_run(wired):
    wired["reviews"] = [Review(answers_topic=False)]

    with pytest.raises(RuntimeError, match="still does not answer the topic"):
        story_service.write_story(topic=TOPIC)

    assert len(wired["prompts"]) == story_service.MAX_REVISIONS + 1


def test_minor_problems_do_not_fail_the_run_after_the_rewrites(wired):
    wired["reviews"] = [Review(weak_hook=True, hook_issue="vague")]

    story = story_service.write_story(topic=TOPIC)

    assert story.text == GOOD
    assert len(wired["prompts"]) == story_service.MAX_REVISIONS + 1


def test_topic_check_is_skipped_when_no_topic_was_requested(wired):
    wired["reviews"] = [Review(answers_topic=False)]

    story = story_service.write_story()

    assert story.text == GOOD
    assert len(wired["prompts"]) == 1


def test_a_broken_reviewer_does_not_block_the_story(wired, monkeypatch):
    def _broken(topic, text, brief):
        raise RuntimeError("reviewer unavailable")

    monkeypatch.setattr(story_service, "review_story", _broken)

    assert story_service.write_story(topic=TOPIC).text == GOOD


def test_review_can_be_turned_off(wired, monkeypatch):
    monkeypatch.setattr(settings, "USE_STORY_REVIEW", False)

    story_service.write_story(topic=TOPIC)

    assert wired["review_calls"] == []
