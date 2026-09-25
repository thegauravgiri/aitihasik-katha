from aitihasik_katha.services.video_service import format_text


def test_format_text_wraps_after_five_words():
    result = format_text("one two three four five six seven")
    assert result == " one two three four five \n six seven "


def test_format_text_normalizes_whitespace_and_newlines():
    result = format_text(" hello   world \n")
    assert result == " hello world "


def test_format_text_short_text_is_not_wrapped():
    result = format_text("a b c")
    assert result == " a b c "
