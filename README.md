# MeetFlow AI

An AI-powered meeting assistant for Microsoft Teams that automatically joins live meetings using a headless browser, captures real-time captions, and understands each speaker's messages. It intelligently routes conversations to specialized AI agents that generate meeting notes, extract action items, perform relevant research, and draft follow-up emails. Every suggested action is reviewed and approved by a human before it is executed, ensuring accuracy and control.


---

## Architecture

```
Teams Meeting
     │
     ▼
┌─────────────────────────────────┐
│  Playwright Bot  (bot/)         │
│  MutationObserver caption scrape│
│  ─→ POST /meeting/chunk         │
└─────────────┬───────────────────┘
              │ Redis Streams
              ▼
┌─────────────────────────────────────────────────────┐
│  FastAPI Backend  (app/)                            │
│                                                     │
│  ┌─── Live LangGraph ──────────────────────────┐   │
│  │ classify → route                            │   │
│  │   ↙          ↓          ↘                   │   │
│  │ Notetaker  TaskExtractor  Researcher        │   │
│  │ → Notion   → Jira (MCP)  → RAG + Tavily    │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─── Post-meeting LangGraph ──────────────────┐   │
│  │ Notetaker → EmailDrafter → HITL Gate        │   │
│  │                            ↕  (approve/edit)│   │
│  │                         → EmailSender       │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  Next.js 15 Dashboard (frontend/)│
│  Live transcript · HITL panel   │
│  Notes · Tasks · Research       │
└─────────────────────────────────┘
```

**5 AI agents:** Orchestrator (classifier + router), Note-taker, Task Extractor, Researcher, Email Drafter  
**HITL middleware:** Every email and ambiguous task requires explicit human approval before it fires. Reviewers can edit the draft in the UI before approving.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + Uvicorn |
| AI orchestration | LangGraph (stateful multi-agent graph) |
| LLM | Azure OpenAI (GPT-4.1-mini) |
| Embeddings | Azure OpenAI (text-embedding-3-small) |
| Vector DB | ChromaDB (persistent) |
| Message queue | Redis Streams |
| Browser bot | Playwright + MutationObserver |
| Task management | Jira REST API via MCP stdio |
| Notes | Notion API |
| Email | SMTP (Gmail app password) |
| Web search | Tavily API |
| Tracing | LangSmith |
| HITL persistence | SQLite (`meetflow.db`) |
| Frontend | Next.js 15 · TypeScript · Tailwind CSS · Zustand v5 · TanStack Query v5 |
| Containers | Docker + docker compose |

---

## Project Structure

```
MeetFlow-AI/
├── app/                        # FastAPI backend
│   ├── main.py                 # App entry point, CORS, lifespan hooks
│   ├── config.py               # Pydantic Settings — loads root .env
│   ├── api/
│   │   ├── routes_meeting.py   # /meeting/* — start, chunk, end, status
│   │   ├── routes_bot.py       # /bot/* — spawn/stop/status Playwright bot
│   │   ├── routes_approval.py  # /approval/respond — HITL webhook
│   │   ├── routes_hitl.py      # /hitl/* — list, inspect requests
│   │   ├── routes_rag.py       # /rag/* — query, upload
│   │   └── routes_health.py    # /health
│   ├── graph/
│   │   ├── builder.py          # LangGraph wiring (live + post-meeting)
│   │   ├── orchestrator.py     # Chunk classifier (LLM → JSON label)
│   │   ├── state.py            # MeetingState TypedDict with add-reducers
│   │   └── nodes/              # One file per agent node
│   ├── hitl/
│   │   ├── gate.py             # hitl_gate() · wait_for_approval() · record_approval()
│   │   └── adaptive_cards.py   # Teams adaptive card templates
│   ├── models/                 # Pydantic schemas + enums
│   ├── persistence/            # SQLite (HITL store, audit log, checkpoints)
│   ├── services/               # External API clients (email, RAG, Redis, Jira, Notion)
│   └── worker/
│       └── consumer.py         # Redis Streams consumer → live graph
│
├── bot/                        # Playwright Teams bot (independent package)
│   ├── main.py                 # CLI entry point (--url, --display-name, --output-dir)
│   ├── pipeline.py             # Caption queue consumer → disk + HTTP forward
│   ├── bot/joiner.py           # Vision-guided Teams meeting joiner
│   ├── captions/captions.py    # MutationObserver caption scraper
│   ├── output/writer.py        # JSON + TXT transcript writer
│   ├── Dockerfile              # Playwright image (Xvfb + Chromium)
│   ├── pyproject.toml          # Bot's own Python deps
│   └── tests/
│
├── frontend/                   # Next.js 15 dashboard
│   ├── app/
│   │   ├── page.tsx            # Dashboard / home
│   │   ├── meetings/           # Meeting list + detail with live transcript
│   │   ├── hitl/page.tsx       # HITL approval queue (with inline editor)
│   │   ├── search/page.tsx     # RAG search
│   │   ├── audit/page.tsx      # Audit log
│   │   └── settings/page.tsx   # API URL + reviewer identity
│   ├── components/             # Shared UI component library
│   ├── hooks/                  # TanStack Query hooks
│   ├── services/api.ts         # Axios client + typed API methods
│   ├── store/                  # Zustand global state
│   ├── types/index.ts          # Shared TypeScript types
│   └── Dockerfile              # Multi-stage Next.js production image
│
├── prompts/                    # LLM prompt templates
├── tests/                      # Backend test suite (pytest)
├── notebooks/                  # Exploration notebooks
├── Dockerfile                  # Backend image (app + worker)
├── docker-compose.yml          # Full stack (redis · app · worker · bot · frontend)
├── .env.example                # All required environment variables
└── pyproject.toml              # Backend Python project + deps
```

---

## Quick Start

### Prerequisites

- Python 3.11+ and `uv` (`pip install uv`)
- Node.js 18+ and npm
- Docker (for Redis; optional for full stack)
- A Chromium-capable machine for the bot (headless, handled by Playwright)

### 1 — Clone and configure

```bash
git clone <repo-url>
cd MeetFlow-AI

cp .env.example .env
# Fill in: Azure OpenAI, Jira, Notion, SMTP, Tavily, LangSmith
```

### 2 — Run locally (recommended for development)

Open four terminals in the project root:

```bash
# Terminal 1 — Redis
docker run --rm -p 6379:6379 redis:7-alpine

# Terminal 2 — Backend API
uv sync
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# Terminal 3 — LangGraph Worker (Redis Streams consumer)
python -m app.worker.consumer

# Terminal 4 — Frontend
cd frontend
npm install
cp .env.local.example .env.local   # or: echo "NEXT_PUBLIC_API_URL=http://localhost:8080" > .env.local
npm run dev
```

Open **http://localhost:3000**.

### 3 — Run with Docker Compose

```bash
# Build and start all services
docker compose up --build

# Also start the Teams bot (optional — needs a meeting URL)
docker compose --profile bot up --build
```

| Service | Port | Notes |
|---|---|---|
| `redis` | 6379 | Message broker |
| `app` | 8080 | FastAPI backend |
| `worker` | — | Runs inside same image as `app` |
| `frontend` | 3000 | Next.js dashboard |
| `bot` | — | Only with `--profile bot` |

---

## Bot — Playwright Caption Scraper

The bot joins a Teams meeting in a headless browser and streams captions into the pipeline — no audio capture required.

### Install Playwright browsers (one-time)

```bash
playwright install chromium
# or from the bot directory:
cd bot && uv sync && uv run playwright install chromium
```

### Starting a meeting

**Via the dashboard:** Paste a Teams link in **Meetings → New Meeting → Teams meeting link** and click **Start & join Teams**. The dashboard spawns the bot and streams its logs live.

**Via CLI:**

```bash
python bot/main.py --url "https://teams.microsoft.com/l/meetup-join/..."
# Optional flags:
#   --display-name "MeetFlow AI"
#   --output-dir ./my_output
```

### How caption scraping works

1. Playwright opens a headless Chromium browser and navigates to the Teams URL
2. The joiner clicks through the lobby: guest join, name entry, audio/video bypass
3. The bot enables **Live captions** from the meeting "More" menu
4. A `MutationObserver` injected into the page watches `div[data-tid="closed-caption-renderer-wrapper"]` for new nodes
5. Each new node is read for speaker (`span[data-tid="author"]`) and text
6. Finalized captions are deduped by a terminal-punctuation heuristic and pushed to an `asyncio.Queue`
7. `pipeline.py` drains the queue and `POST /meeting/chunk` to the backend for each segment

> **Note:** Scraping relies on Teams' internal DOM structure. Microsoft may update selectors without notice. The bot pins `User-Agent: Chrome/125` to reduce UI variability.

---

## AI Pipeline

### Live graph (per caption chunk)

```
chunk → classify (LLM → label) → route
  ├─ decision / discussion  → notetaker   (accumulates → Notion on meeting end)
  ├─ task_commitment        → task_extractor → Jira ticket via MCP
  ├─ research_trigger       → researcher  → RAG similarity + Tavily web search
  └─ off_topic              → (discarded)
```

### Post-meeting graph (on `POST /meeting/{id}/end`)

```
notetaker (full-meeting summary + Notion write)
  → email_drafter (participant recap + stakeholder briefing)
    → email_sender → HITL gate → SMTP send
```

### HITL approval flow

1. An approval request is written to SQLite + published to Redis with a timeout
2. The frontend HITL panel (`/hitl`) shows it as pending with full context
3. Reviewer can **Approve**, **Reject**, or **Edit** — the email subject and body are editable inline before approving
4. `POST /approval/respond` stores the decision (with optional `edited_payload`) in Redis
5. `wait_for_approval()` in `app/hitl/gate.py` unblocks and returns `(status, edited_payload)`
6. The email sender uses the edited draft if `status == EDITED`

---

## API Reference

### Meeting lifecycle

```
POST /meeting/start
     {"meeting_id": "standup-20260626", "title": "Daily Standup", "participants": ["alice@co.com"]}

POST /meeting/chunk
     {"meeting_id": "standup-20260626", "speaker": "Alice", "text": "Ship docs by Friday",
      "timestamp_start": "00:05:12", "timestamp_end": "00:05:18", "minute": 5}

POST /meeting/{id}/end
     {"recipient_emails": ["alice@co.com"], "stakeholder_emails": ["cto@co.com"]}

GET  /meeting/{id}/status      → transcript[], notes[], tasks[], research[], decisions[]
```

### Bot control

```
POST /bot/start
     {"meeting_id": "standup-20260626", "teams_url": "https://teams.microsoft.com/...", "display_name": "MeetFlow AI"}

GET  /bot/status/{meeting_id}  → {status, pid, exit_code, recent_logs[]}

POST /bot/stop/{meeting_id}
```

### HITL

```
GET  /hitl/pending
GET  /hitl/all?limit=50

POST /approval/respond
     {"request_id": "uuid", "status": "approved|rejected|edited",
      "resolved_by": "alice", "edited_payload": {"draft": {...}}}
```

### RAG

```
POST /rag/query
     {"question": "What did Alice say about the deadline?", "meeting_id": "standup-20260626"}

POST /rag/upload
     {"meeting_id": "standup-20260626", "text": "Agenda: ...", "source_name": "agenda.pdf"}
```

### Health

```
GET /health   → {"status": "ok", "redis": true, "chromadb": true}
```

---

## External Service Setup

### Azure OpenAI (required)

1. Create deployments in Azure AI Foundry for a chat model and an embeddings model
2. Set in `.env`:
   - `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT_NAME`
   - `AZURE_OPENAI_EMBEDDING_ENDPOINT`, `AZURE_OPENAI_EMBEDDING_API_KEY`, `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`

### Jira (optional — task creation)

1. Generate an API token at https://id.atlassian.com/manage-profile/security/api-tokens
2. Set `JIRA_BASE_URL` (e.g. `https://your-org.atlassian.net`), `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`

### Notion (optional — meeting notes)

1. Create an integration at https://www.notion.so/my-integrations
2. Share a Notion database with the integration
3. Set `NOTION_API_KEY` and `NOTION_DATABASE_ID`

### Email via SMTP (required for follow-up emails)

1. For Gmail: enable 2FA → Settings → App Passwords → generate a 16-character password
2. Set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER=you@gmail.com`, `SMTP_PASSWORD=<16-char-app-password>`

### Tavily (optional — web search)

1. Sign up at https://tavily.com and grab a free API key
2. Set `TAVILY_API_KEY`

### LangSmith (optional — LLM tracing)

1. Sign up at https://smith.langchain.com
2. Set `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`, `LANGCHAIN_TRACING_V2=true`

---

## Testing

```bash
# Backend
uv sync
pytest tests/ -v

# Frontend type-check
cd frontend && npx tsc --noEmit

# Bot
cd bot && uv run pytest tests/ -v
```

---

## Known Limitations

- **English only** — Teams Live Captions default to English
- **One bot per meeting** — each `POST /bot/start` spawns a separate process; parallel meetings need separate calls
- **DOM brittleness** — Teams may update caption DOM selectors without notice; the bot pins `User-Agent: Chrome/125` to limit variability
- **No audio recording** — captions only; no Whisper or audio file
- **Jira requires a real URL** — task creation silently skips if `JIRA_BASE_URL` is a placeholder
- **Notion OAuth** — the first Notion write requires `notion_token.txt` to be present (created by the OAuth flow in `app/services/notion_client.py`)
- **Windows bot subprocess** — the bot is spawned via `subprocess.Popen` (not `asyncio.create_subprocess_exec`) because Windows `SelectorEventLoop` does not support subprocess creation