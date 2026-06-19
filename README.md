# Mutual Fund FAQ Assistant (Decoupled RAG)

A highly compliant, dynamic, facts-only Retrieval-Augmented Generation (RAG) chatbot that retrieves objective information from Asset Management Company (AMC) scheme pages. 

The application is structured as a decoupled architecture: a **FastAPI backend** (containerized for Railway) and a **static Vanilla HTML/JS frontend** client (optimized for Vercel). The codebase is configuration-driven, enabling easy expansion to **multiple AMCs** and **new fund schemes** simply by editing a JSON configuration file.

---

## 📂 Project Directory Structure

```text
Mutual-Fund-FAQ-Assistant/
├── config/
│   └── schemes.json       # Dynamic configuration containing schemes and AMC groupings
├── data/
│   ├── Corpus/            # Consolidated corpus storage directory
│   │   ├── raw/           # Cached raw HTML files grouped by AMC (e.g. data/Corpus/raw/hdfc_mutual_fund/)
│   │   ├── processed/     # Structured JSON document cache (e.g. data/Corpus/processed/hdfc_mutual_fund/)
│   │   ├── chunks.json    # Compiled chunk metadata cache
│   │   └── embeddings.json# Computed embeddings cache
│   └── chromadb/          # Embedded vector store (ChromaDB)
├── docs/
│   ├── architecture.md    # System component details, pipeline flows, and design
│   ├── edgeCase.md        # Edge cases, compliance rules, and mitigation strategies
│   ├── implementationPlan.md # Step-by-step development roadmap
│   ├── deploymentPlan.md  # Step-by-step guides for Railway & Vercel deployment
│   └── eval/              # Phase-wise testing and verification scripts
├── frontend/              # Static frontend directory for Vercel
│   ├── index.html         # Premium dark-mode HTML interface
│   ├── style.css          # Glassmorphism visual styling
│   └── app.js             # API query controller, status check, and theme toggle
├── src/
│   ├── __init__.py
│   ├── api.py             # FastAPI backend endpoint handler (GET /health, POST /api/query)
│   ├── config.py          # Configuration parser for schemes.json, endpoints, and fallbacks
│   ├── chatbot/           # Packaged RAG search elements
│   │   ├── __init__.py    # Package exports
│   │   ├── retriever.py   # ChromaDB search and query embeddings
│   │   └── engine.py      # Groq API LLM generation engine
│   ├── guardrails/        # Packaged guardrails components
│   │   ├── __init__.py    # Package exports
│   │   ├── pre_retrieval.py  # PII filter and intent routing
│   │   ├── post_retrieval.py # Citation and sentence count validators
│   │   └── refusals.py       # Refusal templates pointing to SEBI/AMFI
│   └── ingestion/         # Packaged directory containing pipeline stage scripts
│       ├── __init__.py    # Package indicator
│       ├── fetcher.py     # Webpage crawler component
│       ├── parser.py      # BS4 & regex details parser (NAV, AUM, SIP, managers, exit load)
│       ├── chunker.py     # Semantic paragraph text chunker
│       ├── indexer.py     # BGE embedding generator and ChromaDB indexer
│       └── ingestion.py   # Ingestion pipeline orchestration runner & legacy unlinker
├── Dockerfile             # Container configuration for Railway
├── vercel.json            # Static routing settings for Vercel
├── requirements.txt       # Dependencies list (including fastapi and uvicorn)
├── .env.example           # Environment template
└── README.md              # Project developer setup and expansion instructions (This file)
```

---

## 🛠️ Setup & Installation

1. **Install Dependencies**:
   Ensure you have Python 3.8+ installed, then run:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**:
   Create a `.env` file at the project root based on `.env.example`:
   ```bash
   cp .env.example .env
   ```
   Add your Groq API key:
   ```env
   GROQ_API_KEY=your_actual_groq_api_key_here
   ```

---

## 🔄 Running the Ingestion Pipeline

To fetch the latest scheme data, cache raw HTML files, preprocess them into structured JSON, and re-index the Chroma vector store, run:
```bash
python3 src/ingestion/ingestion.py
```

### Ingestion Pipeline Stages:
1. **Raw Storage**: Downloads the webpage HTML dynamically and caches it under `data/Corpus/raw/{amc_slug}/{scheme_slug}.html`.
2. **Processed Storage**: BeautifulSoup parses the HTML, extracts metrics (NAV, Expense Ratio, AUM, Min SIP, Exit Load, Fund Managers), and saves a structured JSON file to `data/Corpus/processed/{amc_slug}/{scheme_slug}.json`.
3. **Indexing**: The vector indexer reads the JSON files, partitions text into logical paragraph chunks (~400-500 tokens), embeds them using local BGE embeddings (`BAAI/bge-small-en-v1.5`), and indexes them in ChromaDB.

---

## 🖥️ Running Locally (FastAPI + Static Frontend)

1. **Start Backend FastAPI Server**:
   ```bash
   python3 -m uvicorn src.api:app --host 127.0.0.1 --port 8080
   ```
   Verify health by navigating to `http://localhost:8080/health`.

2. **Start Static Frontend Client**:
   ```bash
   python3 -m http.server 3000 --directory frontend
   ```
   Navigate to `http://localhost:3000/` in your browser. Configure the **Backend API URL** to `http://localhost:8080` in the Connection Settings popover in the top right header (gear icon) to verify status becomes **System Online**.

---

## 🚀 How to Expand the Application

The codebase is configuration-driven. You can scale the system without editing Python source files.

### 1. Adding a Scheme to an Existing AMC
To add a new scheme (e.g. *HDFC Flexi Cap Fund*), open [config/schemes.json](file:///Users/esvarnatarajan/Desktop/Airtribe/Projects/Mutual-Fund-FAQ-Assistant/config/schemes.json) and append a scheme object to HDFC's `schemes` list:
```json
{
  "name": "HDFC Flexi Cap Fund",
  "category": "Flexi Cap",
  "url": "https://groww.in/mutual-funds/hdfc-flexi-cap-fund-direct-growth",
  "official_links": {
    "sid": "https://www.hdfcfund.com/investor-services/fund-documents/scheme-information-documents/hdfc-flexi-cap-fund-sid",
    "kim": "https://www.hdfcfund.com/investor-services/fund-documents/key-information-memorandum/hdfc-flexi-cap-fund-kim",
    "factsheet": "https://www.hdfcfund.com/investor-services/fund-documents/factsheet/hdfc-flexi-cap-fund-factsheet"
  }
}
```
Run `python3 src/ingestion/ingestion.py` to crawl, process, and index the new scheme.

### 2. Adding a New Asset Management Company (AMC)
To support a completely new AMC (e.g. *SBI Mutual Fund*), open [config/schemes.json](file:///Users/esvarnatarajan/Desktop/Airtribe/Projects/Mutual-Fund-FAQ-Assistant/config/schemes.json) and add a new entry block to the `amcs` array:
```json
{
  "amc_name": "SBI Mutual Fund",
  "schemes": [
    {
      "name": "SBI Bluechip Fund",
      "category": "Large Cap",
      "url": "https://groww.in/mutual-funds/sbi-bluechip-fund-direct-growth",
      "official_links": {
        "sid": "https://sbi-sid-url.pdf",
        "kim": "https://sbi-kim-url.pdf",
        "factsheet": "https://sbi-factsheet-url.pdf"
      }
    }
  ]
}
```
Run `python3 src/ingestion/ingestion.py` to create the folders `data/Corpus/raw/sbi_mutual_fund/` and `data/Corpus/processed/sbi_mutual_fund/`, fetch raw HTML, save processed JSON files, and append SBI vector chunks into the collection.

### 3. Upgrading Embedding or LLM Models
To switch models, update the global properties at the top of [config/schemes.json](file:///Users/esvarnatarajan/Desktop/Airtribe/Projects/Mutual-Fund-FAQ-Assistant/config/schemes.json):
- `"embedding_model"`: Change BGE to another SentenceTransformer model.
- `"groq_model"`: Change the Groq LLM model name (e.g., `llama-3.1-8b-instant`).
The system will dynamically load them on startup.
