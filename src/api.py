import re
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

# Try-except absolute/local import for configuration resilience
try:
    from src.chatbot.retriever import MutualFundRetriever
    from src.chatbot.engine import GroqChatEngine
    from src.guardrails.pre_retrieval import PreRetrievalGuard
    from src.guardrails.post_retrieval import PostRetrievalGuard
    from src.guardrails.refusals import RefusalFormatter
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    current_dir = Path(__file__).resolve().parent
    sys.path.append(str(current_dir.parent))
    sys.path.append(str(current_dir))
    
    from chatbot.retriever import MutualFundRetriever
    from chatbot.engine import GroqChatEngine
    from guardrails.pre_retrieval import PreRetrievalGuard
    from guardrails.post_retrieval import PostRetrievalGuard
    from guardrails.refusals import RefusalFormatter

app = FastAPI(
    title="Mutual Fund FAQ Assistant Backend",
    description="FastAPI service exposing RAG retrieval and compliance guardrails.",
    version="1.0.0"
)

# Enable CORS for frontend hosting (Vercel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for clean cross-origin deploy requests
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str
    scheme_filter: Optional[str] = None
    amc_filter: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    source: str
    status: str

@app.get("/health")
def health_check():
    """Verify backend is alive."""
    return {"status": "healthy"}

@app.post("/api/query", response_model=QueryResponse)
def query_endpoint(req: QueryRequest):
    """
    Main RAG query endpoint that processes user prompts, runs pre-retrieval guards,
    performs ChromaDB context retrieval, generates LLM answers via Groq, and runs post-generation compliance checks.
    """
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
        retriever = MutualFundRetriever()
        contexts = retriever.retrieve_context(
            query=query, 
            scheme_filter=scheme_filter, 
            amc_filter=amc_filter, 
            top_k=4
        )
    except Exception as e:
        print(f"Error during context retrieval: {e}")
        return QueryResponse(
            answer="Our database is currently updating. Please consult the official AMC website.",
            source="N/A",
            status="retrieval_error"
        )
        
    # Low-relevance filter: distance check (threshold 1.1)
    if not contexts or contexts[0].get("distance", 9.9) > 1.1:
        return QueryResponse(
            answer=RefusalFormatter.get_out_of_context_refusal(),
            source="https://www.sebi.gov.in/",
            status="no_context"
        )
        
    # 3. Groq LLM Response Generation
    try:
        engine = GroqChatEngine()
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
