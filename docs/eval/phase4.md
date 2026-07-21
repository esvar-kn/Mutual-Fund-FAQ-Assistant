# Phase 4 Evaluation Criteria: Web UI Development & Decoupling

This document defines the detailed evaluation standards, testing procedures, and success criteria for Phase 4 (Web UI Development & Decoupling).

---

## 1. Evaluation Objectives
- Verify that the static frontend files (`frontend/index.html`, `frontend/style.css`, `frontend/app.js`) and `vercel.json` are present and correct.
- Confirm the UI renders essential elements (header title, compliance disclaimer card, connection settings panel, quick-start question buttons).
- Ensure JavaScript binds click events, handles API loading/typing status, and appends user/assistant chat bubbles dynamically.
- Verify CORS and cross-origin connection setup allows the frontend to link with the FastAPI backend on Railway.

---

## 2. Detailed Success Criteria

### 2.1. UI Layout & Rendering
- Loading the UI must render the main header *"FundFacts"*.
- The sidebar must show a prominent compliance disclaimer card detailing the facts-only nature of the tool.
- The sidebar must include a **Connection Settings** input field `#api-url-input` to set the backend URL.

### 2.2. Interactive Buttons & Hooks
- Clicking on any of the 3 quick-start sample query buttons must populate the input field, submit the query, and hide the welcome screen card.
- The interface must disable inputs during active requests and render a loading spinner/bouncing dots.
- Responses must be rendered in distinct message row elements (User row aligned right, AI row aligned left).

### 2.3. State & Connection Persistence
- Connection settings (FastAPI backend URL) must be persisted securely in the browser's `localStorage` (surviving page reloads).
- The top-right status dot must fetch the backend's `/health` endpoint to show whether the API is Online or Offline.

---

## 3. Step-by-Step Test Scenarios

### Test Scenario 4.1: Frontend Static Assets Check
- **Description**: Verify that the static assets and Vercel routing configurations are present in the workspace.
- **Action (Terminal command)**:
  ```bash
  python3 -c "
  import os
  assert os.path.exists('frontend/index.html') == True
  assert os.path.exists('frontend/style.css') == True
  assert os.path.exists('frontend/app.js') == True
  assert os.path.exists('vercel.json') == True
  print('Frontend static assets check passed!')
  "
  ```
- **Expected Result**: Console prints `Frontend static assets check passed!`.

### Test Scenario 4.2: Connection Settings Configuration
- **Description**: Verify that the JavaScript controller initializes settings and updates status based on localStorage configuration.
- **Action**: Check if the `#api-url-input` value gets stored in `localStorage` under `mf_rag_backend_url` and is loaded correctly on page boot.
- **Expected Result**: Changing the backend URL input triggers `localStorage.setItem("mf_rag_backend_url", ...)` and fires a health check request.

### Test Scenario 4.3: Suggestion Buttons Action Hook
- **Description**: Verify suggestion buttons bind correctly and trigger query dispatch.
- **Expected Result**: Clicking suggestion cards fills the input field, hides `#welcome-message-card`, shows user bubble, shows typing loading indicator, and fires query.
