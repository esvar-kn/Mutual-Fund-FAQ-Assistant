# Phase 1 Evaluation Criteria: Environment Setup & Data Ingestion Pipeline

This document defines the detailed evaluation standards, testing procedures, and success criteria for Phase 1 (Environment Setup & Data Ingestion Pipeline).

---

## 1. Evaluation Objectives
- Verify that all project dependencies import successfully with zero issues.
- Confirm configuration constants (SCHEMES, paths, educational URLs) in `config.py` are structured correctly.
- Ensure the crawling script downloads official factsheet and KIM PDFs to the local cache directory (`data/raw/`).
- Validate that PDF parsing and structural chunking index paragraphs and tables into ChromaDB with proper metadata tags (`source_url`, `scheme_name`, `doc_type`, `last_updated_date`).

---

## 2. Detailed Success Criteria

### 2.1. Dependency and Environment Imports
- Execution of Python library imports must succeed with zero failures.
- Essential libraries to verify: `streamlit`, `groq`, `chromadb`, `pdfplumber`, `beautifulsoup4`, `requests`, `sentence-transformers`, `python-dotenv`, `fastapi`, `uvicorn`.

### 2.2. Corpus Storage & Cache Check
- The local directory `data/raw/` must contain nested folders for each AMC containing crawled raw HTML documents.
- The local directory `data/processed/` must contain nested folders for each AMC containing processed structured JSON files.

### 2.3. Vector database Schema & Contents
- ChromaDB collection `mutual_fund_corpus` must exist and contain vector payloads.
- Each chunk must map to the metadata schema:
  - `source_url`: String format, valid HTTP/HTTPS link.
  - `scheme_name`: String format.
  - `amc_name`: String format, matching the scheme's AMC.
  - `doc_type`: Matches one of `factsheet`, `KIM`, `SID`, or `webpage`.
  - `last_updated_date`: String format date.

---

## 3. Step-by-Step Test Scenarios

### Test Scenario 1.1: Dependency and Imports Check
- **Description**: Ensure all libraries required for backend and UI are successfully referenced in Python.
- **Action (Terminal command)**:
  ```bash
  python3 -c "import streamlit; import groq; import chromadb; import pdfplumber; import bs4; import requests; import sentence_transformers; import dotenv; import fastapi; import uvicorn; print('Imports Successful!')"
  ```
- **Expected Result**: Console prints `Imports Successful!` without raising any `ModuleNotFoundError` or exceptions.

### Test Scenario 1.2: Raw & Processed Directory Verification
- **Description**: Confirm raw document crawler and JSON processor created nested directories successfully.
- **Action**: Check if the raw and processed directories contain the expected folders:
  ```bash
  find data/raw/ data/processed/ -type f
  ```
- **Expected Result**: File list displays HTML and JSON documents for each registered scheme inside their respective AMC slug folders, with non-zero sizes.

### Test Scenario 1.3: Vector DB Index Verification
- **Description**: Run a script command to check the Chroma vector database collection and inspect a sample index metadata dictionary.
- **Action (Terminal command)**:
  ```bash
  python3 -c "
  import chromadb
  client = chromadb.PersistentClient(path='data/chromadb/')
  collection = client.get_collection('mutual_fund_corpus')
  print('Collection size:', collection.count())
  sample = collection.peek(1)
  print('Sample Metadata:', sample['metadatas'][0])
  "
  ```
- **Expected Result**:
  - Collection size prints a positive number representing total indexed chunks.
  - Sample metadata contains the keys: `'source_url'`, `'scheme_name'`, `'amc_name'`, `'doc_type'`, and `'last_updated_date'` with valid values.
