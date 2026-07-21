"""
API-level tests for the /api/query request flow.

The retriever and the Groq engine are stubbed, so these tests exercise routing,
guardrail short-circuits, rate limiting and input validation without loading the
embedding model, opening ChromaDB, or spending a Groq call.
"""
import pytest
from fastapi.testclient import TestClient

from src import api


SOURCE = "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth"


class StubRetriever:
    """Stands in for MutualFundRetriever; returns one close-matching chunk."""
    contexts = [{
        "text": "Exit load of 1% if redeemed within 1 year.",
        "source_url": SOURCE,
        "scheme_name": "HDFC Small Cap Fund",
        "amc_name": "HDFC Mutual Fund",
        "doc_type": "scheme_page",
        "last_updated_date": "2026-07-21",
        "distance": 0.2,
    }]

    def __init__(self, *args, **kwargs):
        pass

    def retrieve_context(self, *args, **kwargs):
        return list(self.contexts)


class StubEngine:
    """Stands in for GroqChatEngine; echoes a canned, well-formed answer."""
    response = f"Answer: The exit load is 1% within one year.\nSource: {SOURCE}"

    def __init__(self, *args, **kwargs):
        pass

    def generate_answer(self, query, contexts):
        return self.response

    def generate_corrected_answer(self, query, raw_response, contexts):
        return self.response


@pytest.fixture(autouse=True)
def _clear_component_cache():
    """The cached retriever/engine are module state; reset around every test."""
    api._retriever = None
    api._engine = None
    yield
    api._retriever = None
    api._engine = None


@pytest.fixture
def client(monkeypatch):
    """A TestClient with stubbed RAG components and a fresh rate limiter."""
    monkeypatch.setattr(api, "MutualFundRetriever", StubRetriever)
    monkeypatch.setattr(api, "GroqChatEngine", StubEngine)
    # Isolate rate-limit state so tests cannot leak counts into each other.
    monkeypatch.setattr(
        api, "rate_limiter", api.RateLimiter(max_requests=1000, window_seconds=60)
    )
    return TestClient(api.app)


def ask(client, query, **kwargs):
    return client.post("/api/query", json={"query": query, **kwargs})


# ------------------------------------------------------------------- Happy path

def test_health(client):
    assert client.get("/health").json() == {"status": "healthy"}


def test_factual_query_returns_answer_and_citation(client):
    body = ask(client, "What is the exit load for HDFC Small Cap Fund?").json()
    assert body["status"] == "success"
    assert body["source"] == SOURCE
    assert "1%" in body["answer"]
    # The "Answer:"/"Source:" scaffolding must be parsed off, not shown to users.
    assert "Answer:" not in body["answer"]


# --------------------------------------------------------- Guardrail short-circuits

def test_pii_query_is_blocked_before_retrieval(client, monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("retriever must not run for a PII query")
    monkeypatch.setattr(api, "MutualFundRetriever", explode)

    body = ask(client, "My PAN is ABCDE1234F, what is my balance?").json()
    assert body["status"] == "blocked_pii"
    assert body["source"] == "N/A"


def test_advisory_query_is_blocked_before_retrieval(client, monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("retriever must not run for an advisory query")
    monkeypatch.setattr(api, "MutualFundRetriever", explode)

    body = ask(client, "Should I invest in HDFC Small Cap Fund?").json()
    assert body["status"] == "blocked_advisory"


def test_low_relevance_context_is_refused(client, monkeypatch):
    """A best-match distance past the threshold must refuse, not hallucinate."""
    class FarRetriever(StubRetriever):
        contexts = [dict(StubRetriever.contexts[0],
                         distance=api.RETRIEVAL_DISTANCE_THRESHOLD + 0.5)]
    monkeypatch.setattr(api, "MutualFundRetriever", FarRetriever)

    body = ask(client, "What is the capital of France?").json()
    assert body["status"] == "no_context"


def test_hallucinated_citation_fails_validation(client, monkeypatch):
    """An answer citing a URL outside the retrieved context must be rejected."""
    class LyingEngine(StubEngine):
        response = "Answer: The exit load is 1%.\nSource: https://evil.example.com/fake"
    monkeypatch.setattr(api, "GroqChatEngine", LyingEngine)

    body = ask(client, "What is the exit load?").json()
    assert body["status"] == "failed_validation"


# ------------------------------------------------------------------ Error handling

def test_retrieval_failure_degrades_gracefully(client, monkeypatch):
    class BrokenRetriever:
        def __init__(self, *a, **k):
            raise RuntimeError("chromadb unavailable")
    monkeypatch.setattr(api, "MutualFundRetriever", BrokenRetriever)

    res = ask(client, "What is the exit load?")
    assert res.status_code == 200          # user sees a message, not a 500
    assert res.json()["status"] == "retrieval_error"


def test_llm_failure_degrades_gracefully(client, monkeypatch):
    class BrokenEngine(StubEngine):
        def generate_answer(self, query, contexts):
            raise RuntimeError("groq 401")
    monkeypatch.setattr(api, "GroqChatEngine", BrokenEngine)

    body = ask(client, "What is the exit load?").json()
    assert body["status"] == "llm_error"
    assert SOURCE in body["answer"]        # still points at a real source


# ---------------------------------------------------------------- Input validation

def test_overlong_query_is_rejected(client):
    assert ask(client, "a" * (api.MAX_QUERY_LENGTH + 1)).status_code == 422


def test_empty_query_is_rejected(client):
    assert ask(client, "").status_code == 422


def test_query_at_length_limit_is_accepted(client):
    assert ask(client, "a" * api.MAX_QUERY_LENGTH).status_code == 200


# ------------------------------------------------------------------- Rate limiting

def test_rate_limit_blocks_after_quota(monkeypatch):
    monkeypatch.setattr(api, "MutualFundRetriever", StubRetriever)
    monkeypatch.setattr(api, "GroqChatEngine", StubEngine)
    monkeypatch.setattr(
        api, "rate_limiter", api.RateLimiter(max_requests=3, window_seconds=60)
    )
    client = TestClient(api.app)

    for _ in range(3):
        assert ask(client, "What is the exit load?").status_code == 200

    res = ask(client, "What is the exit load?")
    assert res.status_code == 429
    assert res.json()["status"] == "rate_limited"
    assert int(res.headers["Retry-After"]) >= 1


def test_rate_limit_window_expires():
    """Hits older than the window must not count against the quota."""
    limiter = api.RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.allow("1.2.3.4")[0] is True
    assert limiter.allow("1.2.3.4")[0] is True
    assert limiter.allow("1.2.3.4")[0] is False

    # Age every recorded hit past the window without sleeping.
    limiter._hits["1.2.3.4"] = type(limiter._hits["1.2.3.4"])(
        t - 61 for t in limiter._hits["1.2.3.4"]
    )
    assert limiter.allow("1.2.3.4")[0] is True


def test_rate_limit_is_per_client():
    limiter = api.RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("1.1.1.1")[0] is True
    assert limiter.allow("1.1.1.1")[0] is False
    assert limiter.allow("2.2.2.2")[0] is True      # a different IP is unaffected


# ------------------------------------------------------- Component caching (perf)

def test_retriever_is_built_once_across_requests(client, monkeypatch):
    """
    Regression: the retriever used to be constructed per request, reloading the
    embedding model (~5s) every time. It must now be built exactly once.
    """
    builds = []

    class CountingRetriever(StubRetriever):
        def __init__(self, *a, **k):
            builds.append(1)

    monkeypatch.setattr(api, "MutualFundRetriever", CountingRetriever)

    for _ in range(5):
        assert ask(client, "What is the exit load?").status_code == 200

    assert len(builds) == 1


def test_engine_is_built_once_across_requests(client, monkeypatch):
    builds = []

    class CountingEngine(StubEngine):
        def __init__(self, *a, **k):
            builds.append(1)

    monkeypatch.setattr(api, "GroqChatEngine", CountingEngine)

    for _ in range(5):
        assert ask(client, "What is the exit load?").status_code == 200

    assert len(builds) == 1


def test_failed_component_build_is_retried_not_cached(client, monkeypatch):
    """A construction failure must not poison the cache forever."""
    class BrokenRetriever:
        def __init__(self, *a, **k):
            raise RuntimeError("chromadb unavailable")

    monkeypatch.setattr(api, "MutualFundRetriever", BrokenRetriever)
    assert ask(client, "What is the exit load?").json()["status"] == "retrieval_error"

    # Once the dependency recovers, the next request should succeed.
    monkeypatch.setattr(api, "MutualFundRetriever", StubRetriever)
    assert ask(client, "What is the exit load?").json()["status"] == "success"


# -------------------------------------------------------------------------- CORS

def test_cors_does_not_allow_wildcard_with_credentials():
    """'*' plus credentials is rejected by browsers and must never ship."""
    assert not (api.ALLOWED_ORIGINS == ["*"] and _credentials_enabled())


def _credentials_enabled():
    for mw in api.app.user_middleware:
        if mw.cls is api.CORSMiddleware:
            return mw.kwargs.get("allow_credentials", False)
    return False


def test_allowed_origin_is_echoed_back(client):
    origin = api.ALLOWED_ORIGINS[0]
    res = client.get("/health", headers={"Origin": origin})
    assert res.headers.get("access-control-allow-origin") == origin


def test_disallowed_origin_is_not_echoed_back(client):
    res = client.get("/health", headers={"Origin": "https://not-my-frontend.example"})
    assert res.headers.get("access-control-allow-origin") is None
