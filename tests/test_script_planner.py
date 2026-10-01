import pytest

from aitihasik_katha.services import script_planner
from aitihasik_katha.services.script_planner import ScriptPlan


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("aitihasik_katha.utils.retry.time.sleep", lambda seconds: None)


def test_plan_turns_the_chosen_seconds_into_a_word_budget():
    plan = ScriptPlan(60, "a story with turns")

    assert plan.target_words == 132
    assert (plan.min_words, plan.max_words) == (112, 145)
    assert (plan.floor_words, plan.ceiling_words) == (92, 165)
    assert plan.to_dict() == {"seconds": 60, "reason": "a story with turns", "target_words": 132}


def test_the_model_chooses_the_length_from_the_topic_and_the_research(monkeypatch):
    prompts = []
    monkeypatch.setattr(
        script_planner, "ask_json", lambda prompt: prompts.append(prompt) or {"seconds": 80, "reason": "a why-and-how"}
    )

    plan = script_planner.plan_script("Why are kites flown at Dashain?", "kite research brief")

    assert (plan.seconds, plan.reason) == (80, "a why-and-how")
    assert "Why are kites flown at Dashain?" in prompts[0] and "kite research brief" in prompts[0]


@pytest.mark.parametrize("asked, expected", [(5, 30), (200, 90), (44.6, 45), ("62", 62)])
def test_length_is_kept_within_thirty_to_ninety_seconds(monkeypatch, asked, expected):
    monkeypatch.setattr(script_planner, "ask_json", lambda prompt: {"seconds": asked})

    assert script_planner.plan_script("t", "b").seconds == expected


def test_the_archive_is_the_material_when_there_is_no_research(monkeypatch):
    prompts = []
    monkeypatch.setattr(script_planner, "ask_json", lambda prompt: prompts.append(prompt) or {"seconds": 45})

    script_planner.plan_script(None, "", archive="archive passage about a king")

    assert "archive passage about a king" in prompts[0]


@pytest.mark.parametrize("reply", [None, ["a list"], {"no": "seconds"}, {"seconds": "soon"}])
def test_a_bad_reply_or_failure_falls_back_to_the_default_length(monkeypatch, reply):
    def _ask(prompt):
        if reply is None:
            raise RuntimeError("model unavailable")
        return reply

    monkeypatch.setattr(script_planner, "ask_json", _ask)

    assert script_planner.plan_script("t", "b").seconds == script_planner.DEFAULT_SECONDS
