from types import SimpleNamespace

from aitihasik_katha.services import caption_service


def _llm(text):
    return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=text))


def test_the_caption_uses_purna_biram_even_if_the_model_wrote_full_stops(monkeypatch):
    monkeypatch.setattr(caption_service, "_get_llm", lambda: _llm("३०० वर्ष अघि मरेका राजा. उनको ओछ्यान आज पनि सजिन्छ.\n\n#Nepal #History"))

    caption = caption_service.generate_caption("a story")

    assert caption == "३०० वर्ष अघि मरेका राजा। उनको ओछ्यान आज पनि सजिन्छ।\n\n#Nepal #History"


def test_a_caption_returned_in_parts_is_joined_from_its_text_part(monkeypatch):
    parts = [{"type": "thinking", "text": "ignore"}, {"type": "text", "text": "यो हो."}]
    monkeypatch.setattr(caption_service, "_get_llm", lambda: _llm(parts))

    assert caption_service.generate_caption("a story") == "यो हो।"


def test_the_prompt_asks_for_plain_nepali_a_specific_question_a_send_line_and_a_follow_line():
    prompt = caption_service.CAPTION_PROMPT

    assert "Everyday spoken Nepali" in prompt
    assert "End Nepali sentences with" in prompt
    assert "ONE QUESTION" in prompt and "SEND LINE" in prompt and "FOLLOW LINE" in prompt
    assert "at most 90 characters" in prompt


def test_a_caption_with_a_stray_foreign_letter_is_asked_for_again(monkeypatch):
    replies = iter(["दसैँ त अधուրो हुन्छ।", "दसैँ त अधुरो हुन्छ।"])
    monkeypatch.setattr(caption_service, "_get_llm", lambda: SimpleNamespace(invoke=lambda m: SimpleNamespace(content=next(replies))))

    assert caption_service.generate_caption("a story") == "दसैँ त अधुरो हुन्छ।"


def test_a_caption_that_stays_glitched_is_cleaned_rather_than_posted_as_is(monkeypatch):
    monkeypatch.setattr(caption_service, "_get_llm", lambda: _llm("दसैँ त अधուրो हुन्छ।"))

    assert caption_service.generate_caption("a story") == "दसैँ त अधो हुन्छ।"
