# Deployment Plan: Split Frontend & Backend Architecture

This document guides you through deploying the **Mutual Fund FAQ Assistant** using a decoupled architecture:
1. **Backend API (RAG Engine & Database)**: Deployed on **Railway** via Docker.
2. **Frontend UI (Chat Dashboard)**: Deployed on **Vercel** as a static single-page app.

---

## 🛠️ Decoupled Layout Overview

* **Vercel Frontend**: Hosts static assets (`frontend/index.html`, `frontend/style.css`, `frontend/app.js`) and communicates with the backend via AJAX `fetch()` calls.
* **Railway Backend**: Hosts the FastAPI server (`src/api.py`), executes compliance guardrails, queries the local ChromaDB database, and queries Groq LLM completions.

---

## 💻 1. Deploying the Backend (Railway)

Railway detects the `Dockerfile` at the root of the project to automatically build and expose the FastAPI app.

### Steps:
1. **Log in & Initialize Project**:
   - Go to [Railway.app](https://railway.app) and sign in.
   - Click **New Project** -> **Deploy from GitHub repository**.
   - Select your mutual fund RAG assistant repository.
2. **Set Environment Variables**:
   - In your Railway project, navigate to the **Variables** tab for the service.
   - Add:
     - `GROQ_API_KEY`: *(Your Groq API key used for Llama completions)*
     - `PORT`: `8080` *(FastAPI port)*
3. **Deploy**:
   - Railway will trigger the container build, installing dependencies listed in `requirements.txt` (including `fastapi`, `uvicorn`, `chromadb`, and `sentence-transformers`).
   - It will run: `uvicorn src.api:app --host 0.0.0.0 --port $PORT`
4. **Copy Public Domain**:
   - In the **Settings** tab for your Railway service, scroll down to **Environment** and click **Generate Domain** (or copy your custom domain).
   - The API endpoint URL will look like: `https://mutual-fund-faq-assistant-production.up.railway.app`

---

## 🌐 2. Deploying the Frontend (Vercel)

Vercel reads `vercel.json` to route incoming web traffic directly to the static `frontend/` directory.

### Steps:
1. **Create Vercel Project**:
   - Go to [Vercel.com](https://vercel.com) and log in.
   - Click **Add New** -> **Project**.
   - Select the same GitHub repository.
2. **Configure Settings**:
   - **Framework Preset**: Choose **Other**.
   - **Root Directory**: Leave as `./` (Vercel reads our root `vercel.json` rewrites to serve `/frontend/`).
3. **Deploy**:
   - Click **Deploy**. Vercel will build and launch your static frontend in seconds.
4. **Copy Frontend Domain**:
   - Vercel generates a public URL, such as: `https://mutual-fund-faq-assistant.vercel.app`

---

## 🔗 3. Connecting the Frontend to the Backend

To establish communication between your deployed Vercel frontend and Railway backend:

1. Open your Vercel deployment URL in a web browser.
2. Locate the **⚙️ Connection Settings** card in the left sidebar.
3. Paste your public **Railway Backend URL** (e.g. `https://mutual-fund-faq-assistant-production.up.railway.app`) into the text box.
4. The system status indicator in the top-right header will dynamically query the backend health check (`GET /health`) and transition to a green **Online** dot once connected!
5. This settings configuration is persisted securely in your browser's `localStorage` (no rebuilds required if the backend URL changes).
