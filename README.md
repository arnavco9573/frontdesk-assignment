# FrontDesk — LiveKit Agents demo

A local starter workspace that demonstrates a voice AI receptionist built with LiveKit Agents (Python), a small FastAPI backend, and a Next.js frontend supervisor. This repo ties together a voice agent, a backend help-request workflow, and a simple supervisor UI to show how an agent can escalate questions to a human and learn via embeddings.

## Why this project is useful

- Provides an end-to-end example of building a voice AI assistant using LiveKit Agents for Python.
- Demonstrates real-world features: speech-to-text (STT), text-to-speech (TTS), LLM integration, and a supervisor escalation flow backed by Firestore.
- Includes embeddings-based RAG: resolved supervisor answers are embedded and stored in a knowledge base for retrieval-augmented responses.

## Key features

- Voice agent and session orchestration (see `agent-starter-python/`).
- Backend API for creating and resolving help requests, and for indexing resolved answers into `knowledge_base` (see `backend-api/`).
- Simple Next.js supervisor UI to view/resolve help requests (see `frontend-supervisor/`).

## Contents

- `agent-starter-python/` — Python LiveKit Agents example (agent code, tests, example Dockerfile). See `agent-starter-python/AGENTS.md` for agent-specific docs.
- `backend-api/` — FastAPI backend that stores help requests in Firestore and saves embeddings to the knowledge base.
- `frontend-supervisor/` — Next.js app with a minimal supervisor UI and Firebase integration.
- `service-account.json` — (local) Firebase service account used by the backend/agent. Keep this secret; do not commit to public repos.
- `.github/prompts/create-readme.prompt.md` — authoring prompt used to generate this README.

## Quick start (developer)

Prerequisites

- Python 3.11+ (the project includes a small helper tool called `uv` used to run the agent; a separate venv is not required for the agent when using `uv`).
- Node.js 18+ and pnpm/npm for the frontend.
- A LiveKit Cloud instance (or self-hosted LiveKit) with API key/secret.
- A Google API key for embeddings (if you want embeddings functionality) and Firebase project + service account JSON for Firestore.

Important environment variables

Set these before running the services. You can copy `.env.example` files shipped in subprojects and create a local `.env.local`.

- `LIVEKIT_URL` — e.g. `wss://assignment-XXXX.livekit.cloud`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `GOOGLE_API_KEY` — for embeddings (used by `backend-api` and the agent).
- `FIREBASE_SERVICE_ACCOUNT` or place `service-account.json` at the repository root for local dev.

Run the backend (FastAPI)

Open a terminal, activate the backend venv if present, then:

```bat
cd backend-api
# create/activate venv (Windows, adjust if using global env)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Run the agent (LiveKit Agents)

This starter uses the repository's `uv` helper for the agent (no manual venv activation is required when using `uv`). To set up and run the agent use the following Windows cmd steps:

```bat
cd agent-starter-python
uv sync
uv pip install google-generativeai numpy
# Place your Firebase service account JSON at the repo root (or inside agent-starter-python) as `service-account.json`.
# Create a `.env.local` in `agent-starter-python` and add the following values:
# LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and GOOGLE_API_KEY

# Run the agent in console mode:
uv run python src\agent.py console
```

Notes

- If you prefer to run inside a venv, you can still create one and install `requirements.txt`, but the `uv` helper is the intended dev workflow for the agent in this repo.

Notes

- The agent expects `LIVEKIT_*` env vars to be present. Use `.env.local` or export them in your shell before running.
- If the agent fails to connect to STT/TTS endpoints and you see websocket 401 errors, double-check `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, and system clock.

Run the supervisor frontend (Next.js)

```bat
cd frontend-supervisor
npm install
npm run dev
# Frontend runs at http://localhost:3000 by default
```

## How the help-request flow works

1. The agent receives a user question it cannot answer.
2. The agent POSTs `POST http://127.0.0.1:8000/api/help-requests` with the query and conversation history.
3. The backend stores the request in Firestore and returns a `requestId`.
4. A human supervisor resolves the request via the supervisor UI (or the `/api/help-requests/{id}/resolve` endpoint).
5. The backend stores the supervisor answer and (optionally) creates an embedding to add the Q/A to `knowledge_base` for future retrieval.

## Where to get help

- Project docs: `agent-starter-python/AGENTS.md`.
- LiveKit documentation: https://docs.livekit.io/ (for LiveKit Agents details).
- Open an issue in this repository if you find a bug or need help.

## Who maintains this project

This repository was scaffolded from the LiveKit Agents starter projects. Update the maintainers list in this README to reflect actual owners.

Maintainers

- (Update this section) Primary maintainer: repository owner — please add contact handle or email.

Contribution guidelines

- Please open issues and pull requests.
- For contribution workflow, tests and CI, follow the repository's existing patterns (see `.github/workflows/` and `agent-starter-python/AGENTS.md`).

## Security

- Do not commit `service-account.json` or any secrets to source control.
- Rotate LiveKit API secrets and Google keys if they are exposed.

## Next steps / suggested improvements

- Add a `CONTRIBUTING.md` that documents the development flow and how to run tests locally.
- Add CI secrets to GitHub (see `.github/workflows/tests.yml`).
- Harden the agent with better retry/backoff and improve error handling for websocket auth failures.

---

Files changed/created

- `README.md` — this file: high-level project overview and bootstrap steps.

If you'd like, I can also:
- Add more detailed developer setup scripts (PowerShell/cmd) for Windows.
- Create a `CONTRIBUTING.md` and short `SUPPORT.md`.

Please tell me if you want the README focused on a particular subproject (agent, backend, or frontend) or if you want a shorter quickstart version.
