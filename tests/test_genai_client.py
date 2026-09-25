import threading
import time
from concurrent.futures import ThreadPoolExecutor

from aitihasik_katha.utils import genai_client


def test_concurrent_first_calls_share_a_single_client(monkeypatch):
    built = []

    class _SlowClient:
        def __init__(self, api_key, http_options=None):
            time.sleep(0.05)  # widen the window in which racing threads would each build one
            built.append(threading.get_ident())

    monkeypatch.setattr(genai_client.genai, "Client", _SlowClient)
    monkeypatch.setattr(genai_client, "_client", None)
    monkeypatch.setattr(genai_client.settings, "GEMINI_API_KEY", "test-key")

    with ThreadPoolExecutor(max_workers=8) as executor:
        clients = list(executor.map(lambda _: genai_client.get_genai_client(), range(8)))

    assert len(built) == 1
    assert all(client is clients[0] for client in clients)
