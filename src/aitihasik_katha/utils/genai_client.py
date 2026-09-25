import threading

from google import genai
from google.genai import types

from ..core.settings import settings


_client: genai.Client | None = None
_client_lock = threading.Lock()


def get_genai_client() -> genai.Client:
    """Shared Gemini API client.

    Locked rather than lru_cache'd: it's used from many threads, and a duplicate
    Client built by a losing thread closes the shared HTTP connection when it's
    garbage-collected, failing in-flight requests on the other threads.
    """
    global _client
    with _client_lock:
        if _client is None:
            settings.require("GEMINI_API_KEY")
            _client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                # The SDK otherwise retries 429s itself, silently, honouring Retry-After;
                # a rate-limited run then just stalls. Keep its retries minimal and bound
                # every request so failures reach our own logged retry/backoff instead.
                http_options=types.HttpOptions(
                    timeout=settings.GENAI_REQUEST_TIMEOUT_SECONDS * 1000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
        return _client
