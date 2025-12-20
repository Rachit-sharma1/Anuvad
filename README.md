# 🇮🇳🎙️ Multilingual Voice Assistant for Indian Welfare Schemes

A **voice-first assistant** that helps users discover **Indian government/public welfare schemes**, check **eligibility**, list **required documents**, and explain **next steps** — with **Indic language speech** (STT + TTS), optional **web search**, and **memory** via a vector database.

> **What this repo is for:** running a local prototype of a welfare-scheme assistant that speaks in Indian languages while reasoning in English (see `system_prompt.txt`).

---

## ✨ Features

- 🎤 **Voice input** (audio recorded from browser / UI)
- 🗣️ **Indic STT** (speech → text) via **Sarvam AI**
- 🌍 **Language detection + translation** (optional) for smoother reasoning flows
- 🤖 **LLM agent** (reasoning in short, spoken-style English) using the **OpenAI SDK**
- 🧰 **Tool calling** for:
  - 🔎 **Web search** (via a decoupled microservice)
  - 🗂️ **Scheme catalog lookup** (local JSON list of schemes)
  - 💾 **File operations** (save/delete drafts/checklists)
  - 🧠 **Memory retrieval** (ChromaDB vector store)
- 🔊 **TTS output** (text → speech) via **Sarvam AI**, returned as **Base64 audio**
- 🧩 **Decoupled architecture**: core agent + UI + search microservice

---

## 🏗️ Architecture (High-level)

**1) UI (choose one)**
- 🌐 **Flask web UI**: `app.py` serves `templates/index.html`
- 🧪 **Streamlit UI** (optional): `frontend.py`

**2) Agent / Orchestrator**
- 🧠 `conversation_agent.py`:
  - loads env + prompt + tools schema (`data/tools.json`)
  - runs LLM tool-calling loop
  - calls Sarvam STT/TTS
  - stores/retrieves memory in ChromaDB (`./chroma_db`)

**3) Web Search Microservice**
- 🔎 `search_service.py`:
  - separate Flask service
  - uses Playwright (headless browser) to fetch results
  - cached responses + basic rate limiting

This separation keeps the system **upgradeable**: you can swap search, LLM provider, STT/TTS provider, or UI without rewriting everything.

---

## 📁 Repository Structure

```text
.
├─ app.py                    # Flask web server (serves templates/index.html)
├─ templates/
│  └─ index.html             # Browser UI (record audio, show chat, play audio)
├─ frontend.py               # Optional Streamlit UI
├─ conversation_agent.py     # Core agent: STT/TTS + LLM + tools + memory
├─ search_service.py         # Web search microservice (Playwright)
├─ sarvam_tts.py             # Standalone Sarvam STT/TTS utilities + smoke flow
├─ sarvam_test.py            # Local mic → STT → translate → TTS (smoke test)
├─ groq_test.py              # Test calling Sarvam chat endpoint (legacy name)
├─ run_all.py                # Helper to run multiple services together
├─ system_prompt.txt         # System prompt / behavior spec for the assistant
├─ data/
│  ├─ personas.json          # Persona definitions (e.g., "swayam")
│  ├─ schemes.json           # Local welfare scheme catalog (sample dataset)
│  └─ tools.json             # Tool/function schema for tool calling
└─ chroma_db/                # Persistent vector store (memory)
```

---

## ✅ Prerequisites

- 🐍 **Python**: 3.10–3.12 recommended
- 🧩 **PortAudio** (for `pyaudio`, if you use mic-based tests)
- 🌐 **Playwright browsers** (for the web search microservice)

---

---

## 🚀 Setup (Local)

### 1) Create a virtual environment

**Windows (PowerShell)**
```bash
py -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install Python dependencies

```bash
pip install -r requirements.txt
```

> ⚠️ `frontend.py` uses Streamlit extras that are **not** currently listed in `requirements.txt`.
If you want the Streamlit UI, also install:
```bash
pip install streamlit streamlit-audio-recorder
```

### 3) Install Playwright browsers (for web search)

```bash
python -m playwright install chromium
```

### 4) PortAudio (only if you use mic tests)

- **Ubuntu/Debian**
  ```bash
  sudo apt-get update
  sudo apt-get install -y portaudio19-dev
  ```
- **macOS**
  ```bash
  brew install portaudio
  ```
- **Windows**
  - If `pip install pyaudio` fails, install a compatible wheel or use `pipwin`:
    ```bash
    pip install pipwin
    pipwin install pyaudio
    ```

---

## ▶️ Run the App

### Option A — Flask Web UI (recommended)

**Step 1: Start the search service (optional but recommended)**
```bash
python search_service.py
```
By default it runs on **127.0.0.1:5001**.

**Step 2: Start the main web app**
```bash
python app.py
```

**Step 3: Open**
- `http://127.0.0.1:5000`

**How it works**
- The browser records audio
- Sends audio to a backend endpoint (typically `/process_voice`)
- Backend returns:
  - detected user text
  - assistant text
  - Base64 audio (TTS)
- UI plays the audio reply

> 🧠 If you see placeholder lines like `...` in `app.py` / `templates/index.html`, those are incomplete sections that must be implemented/removed for a clean run.

---

### Option B — Streamlit UI (optional)

```bash
streamlit run frontend.py
```

---

## 🧪 Smoke Tests

### 1) Sarvam STT/TTS quick test
`sarvam_tts.py` contains a minimal flow that can detect language and generate speech.

```bash
python sarvam_tts.py
```

### 2) Microphone pipeline test (if enabled)
`sarvam_test.py` is intended for local mic capture → STT → translate → TTS.

```bash
python sarvam_test.py
```

---

## 🧠 Memory (ChromaDB)

- The agent uses **ChromaDB PersistentClient** with:
  - path: `./chroma_db`
  - collection: `conversation_memory`

**Notes**
- 🧹 If you want to reset memory, delete the `chroma_db/` folder.
- 🔒 Avoid storing personal/sensitive user information in embeddings.

---

## 🔎 Web Search Service

### Why it’s separate
- Keeps the main app lightweight
- Lets you replace search later (Bing → SerpAPI → custom crawler → RAG)

### Health check (basic)
Once `search_service.py` is running, the agent calls:
- `SEARCH_SERVICE_URL` (default: `http://127.0.0.1:5001/search`)

If the service is down, you’ll see:
- “Search service is not reachable. Start search_service.py and try again.”

---

## 🔒 Security Checklist (Minimum for Production)

If you plan to deploy this beyond localhost:

- ✅ **Never commit `.env`**
- ✅ **Rotate keys** if they were ever exposed
- ✅ Use a real web server:
  - `gunicorn` (Linux) / `waitress` (Windows)
  - reverse proxy with **Nginx/Caddy**
- ✅ Add **CORS policy** and **CSRF** protections where applicable
- ✅ Enforce **upload limits** for audio files (size, content-type)
- ✅ Add **request throttling** (per IP / per session)
- ✅ Separate secrets using a secret manager (Vault / AWS Secrets Manager / etc.)
- ✅ Add **structured logging** (no PII) + request IDs

---

## 🧯 Troubleshooting

### Playwright errors
- Run:
  ```bash
  python -m playwright install chromium
  ```
- Ensure you can run headless Chromium in your environment (some servers need extra libs).

### `pyaudio` install fails
- Install PortAudio first (see setup section), then retry `pip install pyaudio`.

### Search not working
- Confirm `search_service.py` is running on the port in `SEARCH_SERVICE_URL`.
- Try opening the search endpoint manually after starting the service.

### “...” (ellipsis) in source files
Some files contain literal `...` placeholder lines. Python/JS will not run with those in place.
Remove/replace them with real code before running in production.

---

## 🛣️ Roadmap Ideas

- 📦 Docker + docker-compose (app + search + optional vector DB)
- 🔐 Auth (admin dashboard + usage analytics)
- 📑 Better scheme dataset (state-wise filters, official links, document lists)
- 🧠 Retrieval-augmented generation (RAG) over official scheme PDFs
- 🗣️ Multi-turn conversation memory with user consent
- ✅ Test suite: `pytest` + integration tests for endpoints

---

## 📜 License
Add a license file if you plan to distribute this publicly.
#
