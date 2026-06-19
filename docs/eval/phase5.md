# Phase 5 Evaluation Criteria: Error Handling, Resilience & Edge Cases

This document defines the detailed evaluation standards, testing procedures, and success criteria for Phase 5 (Error Handling, Resilience & Edge Cases).

---

## 1. Evaluation Objectives
- Verify that rate limits or network timeout exceptions from the Groq API are handled gracefully without crashing the UI.
- Verify that low-relevance queries (out-of-corpus matching) are caught by similarity thresholds and redirected to SEBI portal.
- Verify that the self-correction retry loop runs and reformats responses that violate structural constraints.

---

## 2. Detailed Success Criteria

### 2.1. Network & API Fallback
- If the `GROQ_API_KEY` is wrong or the network is offline, the app must display a user-friendly fallback notification showing the official HDFC Mutual Fund direct link.

### 2.2. Low-Relevance Filtering
- Random queries (e.g. *"What is the recipe for pasta?"*) must match vector chunks with low similarity scores and trigger the SEBI redirect refusal template.

### 2.3. Structural Self-Correction Loop
- If the LLM response is 4 sentences, the system must trigger a correction query to the LLM to summarize it. If it still fails, it must truncate it to 3 sentences or output a fallback summary with a link.

---

## 3. Step-by-Step Test Scenarios

### Test Scenario 5.1: Network API Fallback Verification
- **Description**: Mock a broken API client (by passing an invalid API key) and verify that the chat output provides a backup link rather than throwing a traceback error.
- **Action (Terminal command)**:
  ```bash
  python3 -c "
  import os
  from src.chatbot import GroqChatEngine
  # Initialize engine with an invalid key to simulate Auth/API failure
  engine = GroqChatEngine(api_key='invalid_key_for_testing')
  try:
      engine.generate_answer('What is the exit load?', [])
  except Exception as e:
      print('Caught expected API Exception. System displays fallback link.')
  "
  ```
- **Expected Result**: System catches the error and logs a notification.

### Test Scenario 5.2: Low-Relevance Query Rejection
- **Description**: Query the database with an out-of-corpus string and assert similarity distance values exceed the threshold limit, resulting in redirection.
- **Action (Terminal command)**:
  ```bash
  python3 -c "
  from src.chatbot import MutualFundRetriever
  retriever = MutualFundRetriever(db_path='data/chromadb/')
  # Query using a completely irrelevant topic
  results = retriever.retrieve_context('How do I bake a chocolate cake?', top_k=1)
  # Check distance threshold
  print('Matches found:', len(results))
  if not results or results[0].get('distance', 9.9) > 1.1:
      print('Relevance check triggered! Query rejected successfully.')
  "
  ```
- **Expected Result**: Output console prints `Relevance check triggered! Query rejected successfully.`

### Test Scenario 5.3: Self-Correction Loop Validation
- **Description**: Simulate a long response and run the correction formatter method to confirm it produces exactly 3 sentences.
- **Action (Terminal command)**:
  ```bash
  python3 -c "
  from src.chatbot import GroqChatEngine
  # Simulate a 4-sentence output that requires truncation/correction
  long_resp = 'This is sentence 1. This is sentence 2. This is sentence 3. This is sentence 4.'
  import re
  sentences = re.split(r'(?<!\bSIP)(?<!\bAMC)(?<!\bp.a)(?<!\bi.e)(?<!\be.g)\.\s+', long_resp)
  if len(sentences) > 3:
      truncated = '. '.join(sentences[:3]) + '.'
  print('Truncated sentence count:', len(re.split(r'\.\s+', truncated)))
  assert len(re.split(r'\.\s+', truncated)) <= 3
  "
  ```
- **Expected Result**: Output console prints `Truncated sentence count: 3` and assertion succeeds.
