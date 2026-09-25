from types import SimpleNamespace

import pytest

from aitihasik_katha.services import research_service


def _response(text, chunks=(), queries=()):
    metadata = SimpleNamespace(
        grounding_chunks=[SimpleNamespace(web=SimpleNamespace(title=t, uri=u)) for t, u in chunks],
        web_search_queries=list(queries),
    )
    return SimpleNamespace(text=text, candidates=[SimpleNamespace(grounding_metadata=metadata)])


class _FakeClient:
    def __init__(self, response):
        self.requests = []
        self.models = SimpleNamespace(generate_content=self._generate)
        self._response = response

    def _generate(self, **kwargs):
        self.requests.append(kwargs)
        return self._response


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("aitihasik_katha.utils.retry.time.sleep", lambda s: None)


def test_research_uses_google_search_and_collects_unique_sources(monkeypatch):
    client = _FakeClient(_response(
        "Summary: Battle of Kirtipur",
        chunks=[("britannica.com", "https://a"), ("britannica.com", "https://a"), ("nepal.gov.np", "https://b")],
        queries=["Battle of Kirtipur"],
    ))
    monkeypatch.setattr(research_service, "get_genai_client", lambda: client)

    result = research_service.research(topic="Battle of Kirtipur")

    assert result.brief == "Summary: Battle of Kirtipur"
    assert result.sources == [{"title": "britannica.com", "uri": "https://a"}, {"title": "nepal.gov.np", "uri": "https://b"}]
    request = client.requests[0]
    assert request["config"].tools[0].google_search is not None
    assert "Subject: Battle of Kirtipur" in request["contents"]


def test_research_without_topic_identifies_subject_from_the_archive_passage(monkeypatch):
    client = _FakeClient(_response("Summary: Licchavi inscriptions"))
    monkeypatch.setattr(research_service, "get_genai_client", lambda: client)

    research_service.research(archive_passage="Mānadeva's inscription at Changu Narayan...")

    prompt = client.requests[0]["contents"]
    assert "identify the main historical subject" in prompt
    assert "Changu Narayan" in prompt


def test_empty_brief_is_an_error(monkeypatch):
    monkeypatch.setattr(research_service, "get_genai_client", lambda: _FakeClient(_response("  ")))

    with pytest.raises(RuntimeError, match="empty brief"):
        research_service.research(topic="x")
