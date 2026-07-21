import re
import time
import threading
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

from src.config import (
    RETRIEVAL_DISTANCE_THRESHOLD,
    RETRIEVAL_TOP_K,
    ALLOWED_ORIGINS,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    MAX_QUERY_LENGTH,
    get_grouped_schemes,
)
from src.chatbot.retriever import MutualFundRetriever
from src.chatbot.engine import GroqChatEngine
from src.guardrails.pre_retrieval import PreRetrievalGuard
from src.guardrails.post_retrieval import PostRetrievalGuard
from src.guardrails.refusals import RefusalFormatter

app = FastAPI(
    title="FundFacts Backend",
    description="FastAPI service exposing RAG retrieval and compliance guardrails.",
    version="1.0.0"
)

# Enable CORS for frontend hosting (Vercel).
# Origins come from ALLOWED_ORIGINS; credentials stay off because the API is
# stateless (no cookies or auth headers), and "*" + credentials is a combination
# browsers reject outright.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class RateLimiter:
    """
    Fixed-memory sliding-window rate limiter keyed by client IP.

    Deliberately in-process and dependency-free. That means limits are per
    worker process and reset on restart, so this curbs casual abuse of the paid
    Groq endpoint but is not a substitute for a shared limiter (Redis) or an
    edge/WAF rule once the service runs more than one instance.
    """

    def __init__(self, max_requests, window_seconds):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, client_id):
        """Records a hit; returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[client_id]
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.max_requests:
                return False, max(1, int(hits[0] + self.window_seconds - now) + 1)

            hits.append(now)

            # Opportunistically drop idle clients so the dict cannot grow without bound.
            if len(self._hits) > 10_000:
                for key in [k for k, v in self._hits.items() if not v]:
                    del self._hits[key]

            return True, 0


rate_limiter = RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SECONDS)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    scheme_filter: Optional[str] = Field(default=None, max_length=200)
    amc_filter: Optional[str] = Field(default=None, max_length=200)

class QueryResponse(BaseModel):
    answer: str
    source: str
    status: str

# Cached RAG components.
#
# Constructing MutualFundRetriever loads the BGE SentenceTransformer and opens
# ChromaDB, which took ~5s. Doing that per request dominated response time, so
# both components are built once and reused.
#
# The cache is keyed on the current class object rather than a plain "is None"
# check, so that swapping the class (as the tests do) transparently rebuilds
# instead of handing back a stale instance.
_retriever = None
_engine = None
_components_lock = threading.Lock()


def get_retriever():
    """Returns the process-wide retriever, building it on first use."""
    global _retriever
    if type(_retriever) is not MutualFundRetriever:
        with _components_lock:
            if type(_retriever) is not MutualFundRetriever:
                _retriever = MutualFundRetriever()
    return _retriever


def get_engine():
    """Returns the process-wide Groq engine, building it on first use."""
    global _engine
    if type(_engine) is not GroqChatEngine:
        with _components_lock:
            if type(_engine) is not GroqChatEngine:
                _engine = GroqChatEngine()
    return _engine


@app.get("/health")
def health_check():
    """Verify backend is alive."""
    return {"status": "healthy"}

@app.get("/api/schemes")
def list_schemes():
    """Returns indexed schemes grouped by AMC dynamically loaded from configuration."""
    return {"schemes": get_grouped_schemes()}

@app.post("/api/query", response_model=QueryResponse)
def query_endpoint(req: QueryRequest, request: Request):
    """
    Main RAG query endpoint that processes user prompts, runs pre-retrieval guards,
    performs ChromaDB context retrieval, generates LLM answers via Groq, and runs post-generation compliance checks.
    """
    # 0. Rate limit before doing any paid or expensive work
    client_id = request.client.host if request.client else "unknown"
    allowed, retry_after = rate_limiter.allow(client_id)
    if not allowed:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content=QueryResponse(
                answer=(
                    "You have sent too many requests in a short period. "
                    f"Please wait about {retry_after} seconds and try again."
                ),
                source="N/A",
                status="rate_limited",
            ).model_dump(),
        )

    query = req.query
    scheme_filter = req.scheme_filter
    amc_filter = req.amc_filter
    
    # 1. Pre-Retrieval Guardrails: Check for PII
    if PreRetrievalGuard.detect_pii(query):
        return QueryResponse(
            answer=RefusalFormatter.get_pii_refusal(),
            source="N/A",
            status="blocked_pii"
        )
        
    # Pre-Retrieval Guardrails: Check Intent
    intent = PreRetrievalGuard.classify_intent(query)
    if intent == "advisory":
        return QueryResponse(
            answer=RefusalFormatter.get_advisory_refusal(),
            source="N/A",
            status="blocked_advisory"
        )
        
    # 2. RAG Retrieval
    try:
        retriever = get_retriever()
        contexts = retriever.retrieve_context(
            query=query, 
            scheme_filter=scheme_filter, 
            amc_filter=amc_filter,
            top_k=RETRIEVAL_TOP_K
        )
    except Exception as e:
        print(f"Error during context retrieval: {e}")
        return QueryResponse(
            answer="Our database is currently updating. Please consult the official AMC website.",
            source="N/A",
            status="retrieval_error"
        )
        
    # Low-relevance filter: see RETRIEVAL_DISTANCE_THRESHOLD in src/config.py
    if not contexts or contexts[0].get("distance", 9.9) > RETRIEVAL_DISTANCE_THRESHOLD:
        return QueryResponse(
            answer=RefusalFormatter.get_out_of_context_refusal(),
            source="https://www.sebi.gov.in/",
            status="no_context"
        )
        
    # 3. Groq LLM Response Generation
    try:
        engine = get_engine()
        raw_response = engine.generate_answer(query, contexts)
    except Exception as e:
        print(f"Error calling Groq API: {e}")
        source_url = contexts[0]['source_url'] if contexts else "https://www.amfiindia.com/investor-corner"
        return QueryResponse(
            answer=f"Our RAG services are currently busy or authentication failed. Please consult the official website: {source_url}",
            source=source_url,
            status="llm_error"
        )
        
    # 4. Post-Retrieval Validation, Self-Correction, and Truncation
    context_urls = [ctx["source_url"] for ctx in contexts]
    
    def parse_llm_response(resp):
        ans = resp
        src = "N/A"
        m = re.search(r'Answer:\s*(.*?)\s*Source:\s*(\S+)', resp, re.DOTALL | re.IGNORECASE)
        if m:
            ans = m.group(1).strip()
            src = m.group(2).strip()
        return ans, src

    parsed_answer, parsed_source = parse_llm_response(raw_response)
    sentence_count = PostRetrievalGuard.count_sentences(parsed_answer)
    
    if sentence_count > 3:
        print(f"Response exceeds sentence limit ({sentence_count}). Triggering self-correction...")
        try:
            raw_response_corrected = engine.generate_corrected_answer(query, raw_response, contexts)
            parsed_answer_corrected, parsed_source_corrected = parse_llm_response(raw_response_corrected)
            sentence_count_corrected = PostRetrievalGuard.count_sentences(parsed_answer_corrected)
            
            if sentence_count_corrected <= 3:
                raw_response = raw_response_corrected
                parsed_answer = parsed_answer_corrected
                parsed_source = parsed_source_corrected
                print("Self-correction successfully resolved the sentence count limit.")
            else:
                print("Self-correction query returned invalid output. Forcing truncation.")
                sentences = re.split(r'(?<!\bSIP)(?<!\bAMC)(?<!\bp.a)(?<!\bi.e)(?<!\be.g)\.\s+', parsed_answer_corrected)
                parsed_answer = ". ".join(sentences[:3])
                if not parsed_answer.endswith('.'):
                    parsed_answer += '.'
                parsed_source = parsed_source_corrected
                raw_response = f"Answer: {parsed_answer}\nSource: {parsed_source}"
        except Exception as ce:
            print(f"Error during self-correction call: {ce}. Truncating original response.")
            sentences = re.split(r'(?<!\bSIP)(?<!\bAMC)(?<!\bp.a)(?<!\bi.e)(?<!\be.g)\.\s+', parsed_answer)
            parsed_answer = ". ".join(sentences[:3])
            if not parsed_answer.endswith('.'):
                parsed_answer += '.'
            raw_response = f"Answer: {parsed_answer}\nSource: {parsed_source}"

    # Re-evaluate validity after any correction/truncation steps
    is_valid = PostRetrievalGuard.validate_output(query, raw_response, context_urls)
    
    if not is_valid:
        return QueryResponse(
            answer=RefusalFormatter.get_out_of_context_refusal(),
            source="N/A",
            status="failed_validation"
        )
        
    return QueryResponse(
        answer=parsed_answer,
        source=parsed_source,
        status="success"
    )
