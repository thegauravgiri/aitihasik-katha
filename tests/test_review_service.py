import pytest

from aitihasik_katha.services import review_service


def test_reply_is_turned_into_a_review(monkeypatch):
    prompts = []

    def _ask(prompt):
        prompts.append(prompt)
        return {
            "answers_topic": False,
            "unsupported_claims": ["built in 1832", " "],
            "weak_hook": True,
            "hook_issue": "it opens with scenery",
        }

    monkeypatch.setattr(review_service, "ask_json", _ask)

    review = review_service.review_story("Why kites?", "a story", "a brief")

    assert review.answers_topic is False
    assert review.unsupported_claims == ["built in 1832"]
    assert review.weak_hook is True
    assert review.hook_issue == "it opens with scenery"
    assert "Why kites?" in prompts[0] and "a story" in prompts[0] and "a brief" in prompts[0]


def test_missing_fields_default_to_a_passing_review(monkeypatch):
    monkeypatch.setattr(review_service, "ask_json", lambda prompt: {})

    review = review_service.review_story(None, "a story", "")

    assert review.answers_topic is True
    assert review.unsupported_claims == []
    assert review.weak_hook is False


def test_an_unexpected_reply_is_an_error(monkeypatch):
    monkeypatch.setattr(review_service, "ask_json", lambda prompt: ["not", "an", "object"])
    monkeypatch.setattr("aitihasik_katha.utils.retry.time.sleep", lambda seconds: None)

    with pytest.raises(ValueError, match="unexpected shape"):
        review_service.review_story("t", "s", "b")
