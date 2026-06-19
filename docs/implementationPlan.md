# Phase-Wise Implementation Plan: Decoupled Mutual Fund FAQ Assistant

This implementation plan breaks down the development of the Mutual Fund FAQ Assistant into structured, sequential phases, separating the backend FastAPI server (Railway) from the static web client (Vercel). It aligns with the architecture specified in [architecture.md](file:///Users/esvarnatarajan/Desktop/Airtribe/Projects/Mutual-Fund-FAQ-Assistant/docs/architecture.md).

---

## Project Directory Structure

```text
Mutual-Fund-FAQ-Assistant/
├── .env.example           # Environment variables template
├── .github/
│   └── workflows/
│       └── daily_ingestion.yml # GitHub Actions workflow scheduler
├── .gitignore
├── Dockerfile             # Container configuration for Railway
├── vercel.json            # Static routing settings for Vercel
├── docs/
│   ├── problemStatement.md
│   ├── architecture.md
│   ├── deploymentPlan.md  # Steps to link Railway and Vercel services
│   └── implementationPlan.md
├── config/
│   └── schemes.json       # Dynamic configuration containing schemes and AMC groupings
├── data/
│   ├── Corpus/            # Consolidated corpus storage directory
│   │   ├── raw/           # Cached raw HTML files (data/Corpus/raw/hdfc_mutual_fund/)
│   │   ├── processed/     # Structured JSON document cache (data/Corpus/processed/hdfc_mutual_fund/)
│   │   ├── chunks.json    # Compiled chunk metadata cache
│   │   └── embeddings.json# Computed embeddings cache
│   └── chromadb/          # Embedded vector store (ChromaDB)
├── frontend/              # Static frontend folder for Vercel
│   ├── index.html         # Premium dark-mode HTML interface
│   ├── style.css          # Glassmorphism visual styling
│   └── app.js             # API query controller and status checker
├── src/
│   ├── __init__.py
│   ├── api.py             # FastAPI backend endpoint handler (GET /health, POST /api/query)
│   ├── config.py          # Configuration parser for schemes.json
│   ├── chatbot/           # Packaged RAG search elements
│   │   ├── __init__.py    # Package-level exports
│   │   ├── retriever.py   # ChromaDB search and query embeddings
│   │   └── engine.py      # Groq API LLM generation engine
│   ├── guardrails/        # Packaged guardrails components
│   │   ├── __init__.py    # Package-level exports
│   │   ├── pre_retrieval.py  # PII filter and intent routing
│   │   ├── post_retrieval.py # Citation and sentence count validators
│   │   └── refusals.py       # Refusal templates pointing to SEBI/AMFI
│   └── ingestion/         # Packaged ingestion pipeline scripts
│       ├── __init__.py    # Package-level exports
│       ├── fetcher.py     # HTML crawling script
│       ├── parser.py      # Groww HTML parsing script
│       ├── chunker.py     # Paragraph text chunking utility
│       ├── indexer.py     # Vector generation and indexing
│       └── ingestion.py   # Ingestion orchestrator
├── requirements.txt       # Dependencies (including fastapi and uvicorn)
└── README.md              # Project developer setup and execution guides
```

---

## Phase 1: Environment Setup & Data Ingestion Pipeline
**Goal**: Initialize workspace components, download/scrape raw HTML files for target mutual fund schemes across different AMCs, extract processed structured JSON documents, chunk their content, and index them in a local vector database.

### Tasks
1.  **Initialize Configuration**:
    - Implement `config/schemes.json` to register schemes, categories, and official PDF documents.
    - Implement `src/config.py` to parse `schemes.json` dynamically. Exposes default fallback parameters and ports.
2.  **Implement Crawler & Processed JSON Parser (`src/ingestion/`)**:
    - Crawl pages and save raw HTML responses to `data/Corpus/raw/{amc_slug}/{scheme_slug}.html`.
    - Clean crawled HTML to extract plain text. Write to `data/Corpus/processed/{amc_slug}/{scheme_slug}.json`.
3.  **Implement Chunker, Indexer, and Cleanup routines**:
    - Chunk JSON paragraphs (~400-500 tokens) with metadata schema tags (`source_url`, `scheme_name`, `doc_type`, etc.).
    - Embed chunks using the BGE model and write them to ChromaDB.
    - Clean up legacy folder contents (subfolders in raw/processed under Corpus/, old runs, and orphaned index folders) on every trigger.
4.  **Configure Daily Workflow Scheduler (`.github/workflows/daily_ingestion.yml`)**.

---

## Phase 2: RAG Retrieval and Chat Engine API
**Goal**: Decouple the query processing flow by exposing retrieval and Groq LLM generations through a REST API.

### Tasks
1.  **Implement Vector Search (`src/chatbot/retriever.py`)**:
    - Connect to local ChromaDB and define similarity search query retrieval.
    - Support metadata-based filtering by `scheme_name`.
2.  **Implement LLM Client (`src/chatbot/engine.py`)**:
    - Generate answers via Groq completion with strict system instructions (<=3 sentences, facts-only, cite 1 source).
3.  **Create FastAPI Backend Endpoint (`src/api.py`)**:
    - Create a FastAPI application instance exposing `GET /health` and `POST /api/query`.
    - Implement CORS middleware to enable cross-origin calls.

---

## Phase 3: Pre- & Post-Retrieval Guardrails
**Goal**: Implement pre-retrieval validation (PII checks, intent classification) and post-generation constraint checks.

### Tasks
1.  **Implement Pre-Retrieval Guardrails (`src/guardrails/pre_retrieval.py`)**:
    - Filter PII (Aadhaar, PAN, phone, email, OTP) using regex patterns.
    - Classify query intent into `"advisory"`, `"performance_comparison"`, or `"factual"`.
2.  **Implement Post-Retrieval Output Validation (`src/guardrails/post_retrieval.py`)**:
    - Verify generated sentence count <= 3 and ensure the citation matches one of the retrieved source URLs.
3.  **Refusal System (`src/guardrails/refusals.py`)**:
    - Link routing failures to standard redirection footers pointing to AMFI, SEBI, or HDFC login screens.

---

## Phase 4: Web UI Development & Decoupling
**Goal**: Build a responsive static front-end chat dashboard deploying to Vercel that queries the Railway backend.

### Tasks
1.  **Design Static Layout (`frontend/index.html` & `frontend/style.css`)**:
    - UI header, compliance disclaimer sidebar card, suggestion cards, scrollable chat logs, input box, and bouncing loader dots.
2.  **State Controller & Connection Setting (`frontend/app.js`)**:
    - Create an input field to configure and save the Railway backend URL in `localStorage`.
    - Automatically check backend health (`GET /health`) to update the Online/Offline status dot.
    - Dispatch AJAX `POST` requests to `/api/query` and render user/assistant bubbles.
3.  **Vercel Deployment Mapping (`vercel.json`)**:
    - Configure clean rewrite rules to serve static assets from the `frontend/` directory.

---

## Phase 5: Error Handling, Resilience & Edge Cases
**Goal**: Handle missing context, API auth failures, low-relevance queries, and constraint violation fallbacks.

### Tasks
1.  **Configure API fallbacks**:
    - Handle invalid `GROQ_API_KEY` errors or network timeouts by rendering local fallback links to HDFC AMC portals.
2.  **Low-Relevance Query Filters**:
    - Reject queries with similarity distances exceeding a set threshold (e.g. random non-financial prompts) with SEBI redirects.
3.  **Sentence Count Self-Correction**:
    - Implement fallback truncations or summaries if the LLM output violates constraints.
