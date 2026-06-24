# AI Meeting System for Microsoft Teams — MVP

An AI-powered meeting assistant that joins Microsoft Teams calls, scrapes real-time captions from the browser DOM, classifies utterances, and routes them to specialized agents for note-taking, task extraction, research, and follow-up emails.

## Architecture

```
Teams Meeting → Playwright Bot → Browser Caption Scraping → Transcript Chunks
                                                              ↓
                                                       Orchestrator (Claude)
                                                       ↙    ↓      ↘
                                               Note-taker  Task    Researcher
                                               → Notion    Agent   → RAG/Tavily
                                                           → Jira
                                                              ↓
                                                       Email Drafter
                                                       → HITL Gate → Send
```

**5 Agents:** Orchestrator (classifier + router), Note-taker, Task Extractor, Research, Email Drafter  
**HITL Middleware:** Human-in-the-loop approval via Teams adaptive cards before sending emails or creating ambiguous tasks

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| API | FastAPI |
| Orchestration | LangGraph (stateful multi-agent graph) |
| LLM | Claude (Anthropic) |
| Real-time transcription | Browser caption scraping (Playwright MutationObserver) |
| Meeting joining | Playwright + Groq vision (fallback) |
| Embeddings | OpenAI text-embedding-3-small |
| Vector DB | ChromaDB |
| Web search | Tavily API |
| Tasks | Jira REST API |
| Notes | Notion API |
| Email | Microsoft Graph Mail API / SMTP |
| Teams | Playwright browser automation |
| Tracing | LangSmith |
| Containers | Podman + podman-compose |
| Queue | Redis Streams |

## Quick Start

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 2. Run with Podman

```bash
podman-compose up --build
```

This starts 4 containers:
- **app** (port 8080) — FastAPI + LangGraph
- **chromadb** (port 8000) — Vector database
- **worker** — Background agent task processor
- **redis** (port 6379) — Message queue

### 3. Run locally (development)

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8080
```

## API Endpoints

### Meeting Lifecycle

```bash
# Start a meeting
POST /meeting/start
{"meeting_id": "standup_20260622", "title": "Daily Standup", "participants": ["a@co.com"]}

# Send transcript chunks (from browser caption scraper)
POST /meeting/chunk
{"meeting_id": "standup_20260622", "speaker": "Sarah", "text": "I'll update the docs by Friday.", "timestamp_start": "00:12:34", "timestamp_end": "00:12:51", "minute": 12}

# End meeting (triggers email drafting)
POST /meeting/{id}/end

# Check meeting status
GET /meeting/{id}/status
```

### RAG Queries

```bash
# Query past meetings
POST /rag/query
{"question": "What did Sarah say at minute 12?", "meeting_id": "standup_20260622", "speaker": "Sarah", "minute": 12}

# Upload pre-meeting documents
POST /rag/upload
{"meeting_id": "standup_20260622", "text": "Agenda: ...", "source_name": "agenda"}
```

### HITL Approval

```bash
# Respond to approval request (webhook from Teams)
POST /approval/respond
{"request_id": "uuid", "status": "approved", "resolved_by": "admin"}
```

### Health Check

```bash
GET /health
# Returns: {"status": "ok", "redis": true, "chromadb": true}
```

## External Service Setup

### Jira
1. Create an API token at https://id.atlassian.com/manage-profile/security/api-tokens
2. Set `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY` in `.env`

### Notion
1. Create an integration at https://www.notion.so/my-integrations
2. Share a database with the integration
3. Set `NOTION_API_KEY` and `NOTION_DATABASE_ID` in `.env`

### Microsoft Graph (Teams + Email)
1. Register an app in Azure AD
2. Grant `Mail.Send`, `TeamworkActivity.Send` permissions
3. Set `MS_GRAPH_CLIENT_ID`, `MS_GRAPH_CLIENT_SECRET`, `MS_GRAPH_TENANT_ID` in `.env`

### LangSmith
1. Get an API key at https://smith.langchain.com
2. Set `LANGCHAIN_API_KEY` and `LANGCHAIN_PROJECT` in `.env`

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Project Structure

```
app/
├── main.py              # FastAPI entry point
├── config.py            # Settings (pydantic-settings)
├── models/              # Shared Pydantic schemas + enums
├── graph/
│   ├── orchestrator.py  # Chunk classifier
│   ├── builder.py       # LangGraph StateGraph wiring
│   └── nodes/           # Agent node implementations
├── services/            # External API clients
├── hitl/                # Human-in-the-loop middleware
├── api/                 # FastAPI route handlers
└── worker/              # Redis stream consumer
prompts/                 # LLM prompt templates
tests/                   # Test suite
```
