# Phase 2 Evaluation Criteria: RAG Retrieval and Chat Engine

This document defines the detailed evaluation standards, testing procedures, and success criteria for Phase 2 (RAG Retrieval and Chat Engine).

---

## 1. Evaluation Objectives
- Verify that `MutualFundRetriever` correctly connects to ChromaDB and retrieves closest matching context chunks.
- Confirm metadata filtering works, returning chunks restricted to a specific scheme when requested.
- Ensure the Groq chat client compiles system instructions and retrieved context to output a structured response.

---

## 2. Detailed Success Criteria

### 2.1. Retrieval Accuracy & Relevance
- Searching for specific metrics (e.g. exit load) must return contexts that contain relevant information.
- Cosine/Euclidean distance scores must match expectations (lower distance/higher similarity for accurate matches).

### 2.2. Scheme Filtering Constraints
- When a search query calls for scheme-specific filtering (e.g. `scheme_filter='HDFC Mid-Cap Fund'`), all returned chunks in the list must have `metadata['scheme_name']` matching that key.

### 2.3. LLM Response Completion
- The engine must successfully generate an answer string based on the context.
- Output text must be structured to match the query response tags (Answer: ... / Source: ...).

---

## 3. Step-by-Step Test Scenarios

### Test Scenario 2.1: Context Retrieval and Similarity Scores
- **Description**: Search for a query and print the similarity scores and contents of the top 3 matches.
- **Action (Terminal command)**:
  ```bash
  python3 -c "
  from src.chatbot import MutualFundRetriever
  retriever = MutualFundRetriever(db_path='data/chromadb/')
  results = retriever.retrieve_context('What is the exit load for HDFC Mid-Cap?', top_k=3)
  for i, res in enumerate(results):
      print(f'Match {i}: {res[\"text\"][:80]}... | URL: {res[\"source_url\"]}')
  "
  ```
- **Expected Result**: Output prints 3 match snippets, containing details about exit load and linking to the HDFC Mid-Cap source URLs.

### Test Scenario 2.2: Metadata Filtering Test
- **Description**: Verify that the metadata filter restricts chunk sources to the target scheme.
- **Action (Terminal command)**:
  ```bash
  python3 -c "
  from src.chatbot import MutualFundRetriever
  retriever = MutualFundRetriever(db_path='data/chromadb/')
  results = retriever.retrieve_context('benchmark index', scheme_filter='HDFC Mid-Cap Opportunities Fund', top_k=3)
  assert all(res['scheme_name'] == 'HDFC Mid-Cap Opportunities Fund' for res in results)
  print('Filter validation passed!')
  "
  ```
- **Expected Result**: Program prints `Filter validation passed!` indicating all results matched the target scheme filter.

### Test Scenario 2.3: Chat Client Execution
- **Description**: Run a mock inference execution utilizing Groq API with cached context blocks.
- **Action (Terminal command)**:
  ```bash
  python3 -c "
  import os
  from dotenv import load_dotenv
  from src.chatbot import GroqChatEngine
  load_dotenv()
  engine = GroqChatEngine(api_key=os.getenv('GROQ_API_KEY'))
  mock_context = [{'text': 'HDFC Mid-Cap Fund has an exit load of 1.00% if redeemed within 1 year.', 'source_url': 'https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth'}]
  response = engine.generate_answer('What is HDFC Mid-Cap exit load?', mock_context)
  print('Raw Response:\n', response)
  "
  ```
- **Expected Result**: Console logs a response indicating exit load is 1% with the source URL, confirming LLM connection and system prompt compatibility.
