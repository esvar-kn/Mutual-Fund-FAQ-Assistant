# Phase 3 Evaluation Criteria: Pre- & Post-Retrieval Guardrails & Refusal System

This document defines the detailed evaluation standards, testing procedures, and success criteria for Phase 3 (Pre- & Post-Retrieval Guardrails & Refusal System).

---

## 1. Evaluation Objectives
- Verify that `PreRetrievalGuard.detect_pii(query)` blocks Aadhaar card numbers, PAN numbers, emails, phone numbers, and OTP keywords.
- Verify that `PreRetrievalGuard.classify_intent(query)` detects advisory/opinion keywords and routes them to standard educational refusals.
- Confirm `PostRetrievalGuard.validate_output(query, answer, context_urls)` catches output that exceeds 3 sentences, contains multiple or missing citations, or references external URLs not present in context.

---

## 2. Detailed Success Criteria

### 2.1. PII Extraction & Identification
- Any string containing an Aadhaar (12 digits, with or without spaces) or PAN (5 capital letters, 4 numbers, 1 letter) must return `True` (PII detected).
- Common contact data (e.g. 10-digit Indian phone numbers or standard emails) must be flagged.

### 2.2. Intent Routing Accuracy
- Queries asking for recommendations (*"should I buy"*, *"which is better"*, *"where to invest"*) must be classified as `"advisory"`.
- Performance return comparison queries must be classified as `"performance_comparison"`.

### 2.3. Post-Generation Formatting Constraints
- Sentence count check must correctly split lines based on sentence boundaries, ignoring standard abbreviations like `SIP`, `AMC`, `p.a.`, or `e.g.`
- Citation validation must fail if the URL link inside the response text is not in the list of source URLs returned by ChromaDB metadata.

---

## 3. Step-by-Step Test Scenarios

### Test Scenario 3.1: PII Detection Verification
- **Description**: Feed PII elements (Aadhaar, PAN) into the detector and verify that they are correctly blocked.
- **Action (Terminal command)**:
  ```bash
  python3 -c "
  from src.guardrails import PreRetrievalGuard
  assert PreRetrievalGuard.detect_pii('My Aadhaar is 5432 1098 7654') == True
  assert PreRetrievalGuard.detect_pii('My PAN is ABCDE1234F') == True
  assert PreRetrievalGuard.detect_pii('Normal query about exit loads') == False
  print('PII detector checks passed!')
  "
  ```
- **Expected Result**: Output console prints `PII detector checks passed!`.

### Test Scenario 3.2: Intent Routing Verification
- **Description**: Verify that the intent routing flags advisory queries and factual queries correctly.
- **Action (Terminal command)**:
  ```bash
  python3 -c "
  from src.guardrails import PreRetrievalGuard
  assert PreRetrievalGuard.classify_intent('Should I buy HDFC Mid-Cap?') == 'advisory'
  assert PreRetrievalGuard.classify_intent('HDFC Mid-Cap vs HDFC Small-Cap') == 'performance_comparison'
  assert PreRetrievalGuard.classify_intent('What is the minimum SIP for HDFC Large-Cap?') == 'factual'
  print('Intent classification checks passed!')
  "
  ```
- **Expected Result**: Output console prints `Intent classification checks passed!`.

### Test Scenario 3.3: Post-Generation Constraints Validation
- **Description**: Verify that responses exceeding 3 sentences or containing invalid citations are caught by the post-retrieval validator.
- **Action (Terminal command)**:
  ```bash
  python3 -c "
  from src.guardrails import PostRetrievalGuard
  # Test sentence count
  long_resp = 'This is sentence one. This is sentence two. This is sentence three. This is sentence four.'
  assert PostRetrievalGuard.validate_output(query='test', answer=long_resp, context_urls=['https://hdfc.com']) == False
  
  # Test invalid citation
  invalid_cite = 'The exit load is 1%. Source: https://badurl.com'
  assert PostRetrievalGuard.validate_output(query='test', answer=invalid_cite, context_urls=['https://hdfc.com']) == False
  
  print('Post-retrieval validation checks passed!')
  "
  ```
- **Expected Result**: Output console prints `Post-retrieval validation checks passed!`.
