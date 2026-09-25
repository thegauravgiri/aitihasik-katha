from datetime import timedelta

from aitihasik_katha.services.subtitle_service import get_subtitle


class _FakeWord:
    def __init__(self, word: str, start: float, end: float):
        self.word = word
        self.start_offset = timedelta(seconds=start)
        self.end_offset = timedelta(seconds=end)


class _FakeAlternative:
    def __init__(self, words: list[_FakeWord]):
        self.words = words


class _FakeResult:
    def __init__(self, words: list[_FakeWord]):
        self.alternatives = [_FakeAlternative(words)]


class _FakeResponse:
    def __init__(self, results: list[_FakeResult]):
        self.results = results


def test_get_subtitle_flattens_word_level_timings_across_results():
    response = _FakeResponse(
        [
            _FakeResult([_FakeWord("hello", 0.0, 0.5), _FakeWord("world", 0.5, 1.2)]),
            _FakeResult([_FakeWord("again", 1.2, 1.8)]),
        ]
    )

    assert get_subtitle(response) == [
        ((0.0, 0.5), "hello"),
        ((0.5, 1.2), "world"),
        ((1.2, 1.8), "again"),
    ]


def test_get_subtitle_returns_empty_list_for_no_results():
    assert get_subtitle(_FakeResponse([])) == []
