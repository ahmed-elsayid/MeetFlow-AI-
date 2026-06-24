# AI Meeting System for Microsoft Teams — MVP

> **Version:** MVP v2.0  
> **Scope:** Core system only. Enhancement phases planned separately.  
> **Stack:** Python 3.11+ · LangGraph · ChromaDB · Podman · LangSmith · Playwright

---

## 1. Problem Statement

Teams that meet frequently lose hours every week to manual work that should be automated. Someone takes notes, someone else forgets to, action items get mentioned out loud but never written down, and the recap email either arrives late or never arrives at all. When it does arrive, it misses context because the person writing it was also trying to participate.

The deeper problem is that meetings produce unstructured audio and structured decisions come out the other side — but there is nothing reliable bridging the two. Transcription tools give you a wall of text with no structure. Task trackers require manual entry. Recap bots send generic summaries with no awareness of what actually matters.

**What is missing:** A single system that joins a Microsoft Teams meeting, listens in real time, produces structured notes, extracts action items with owners and deadlines, pulls in background knowledge from uploaded documents and the web, asks a human before taking critical actions, and delivers tailored follow-up emails — all automatically, all traced for debugging, and all running inside a secure container.

**Who needs it:**

- Project managers spending 30–60 minutes per meeting on manual recaps
- Engineering leads losing track of verbal commitments across standups
- Cross-functional teams where absent stakeholders never get adequate context
- Organizations that need timestamped, searchable meeting records

**MVP success criteria:** A meeting ends and within two minutes every participant has a structured recap email, every action item exists as a ticket in Jira with the right owner, and the full timestamped transcript is searchable in the RAG store — with zero manual work from anyone on the call.

---

## 2. Features

### MVP Scope

| ID | Feature | What it does | MVP boundary |
|----|---------|-------------|--------------|
| F1 | Real-time transcription | Bot joins Teams call via Playwright, enables live captions, scrapes captions from the browser DOM using MutationObserver, streams transcript chunks to the orchestrator | Single meeting at a time. English only. |
| F2 | Structured note-taking | Separates discussion from decisions, groups by topic, writes to Notion or Google Docs live during the meeting | Auto-generated topic headings. No manual formatting. |
| F3 | Task extraction | Detects commitment language, extracts assignee + deadline + description, creates Jira tickets | Jira only in MVP. Trello and others in enhancement. |
| F4 | RAG with timestamps | Every transcript chunk stored with speaker, minute, timestamp metadata. Uploaded pre-meeting documents chunked and indexed. Queries filtered by time before vector search. | ChromaDB. Single collection per meeting. |
| F5 | Web search | Research agent searches the web when some topics or def. are vague based  | Tavily API. Results appear in recap only (no mid-meeting chat posting in MVP). |
| F6 | Follow-up emails | After the meeting, sends detailed recap to participants and brief summary to stakeholders | Two templates. SMTP or Graph API. |
| F7 | Multi-agent delegation | Orchestrator classifies utterances and routes to specialized agents running as LangGraph subagent nodes | 5 agents. Parallel dispatch. |
| F8 | Human-in-the-loop | Pauses before sending emails or creating ambiguous tasks. Sends approval request. Waits for approve/reject. | Teams adaptive card. Single approver. |
| F9 | LangSmith tracing | Every LLM call, tool invocation, and agent decision traced end-to-end | Project-level dashboard. Per-agent tags. |
| F10 | Podman containerization | Entire system runs in rootless Podman containers with compose file | Local dev + single-node production. |



### RAG Detail: Timestamped Retrieval

Every transcript chunk carries structured metadata:

```json
{
  "text": "Sarah mentioned the Q3 deadline is moving to September 15th",
  "metadata": {
    "meeting_id": "mtg_20260622_standup",
    "speaker": "Sarah",
    "timestamp_start": "00:12:34",
    "timestamp_end": "00:12:51",
    "minute": 12,
    "topic_cluster": "Q3 timeline",
    "source_type": "live_transcript"
  }
}
```

Uploaded documents use the same schema but with `source_type: "uploaded_document"` and null time fields.

**Two-stage retrieval:** When a query mentions a time reference ("what was said at minute 12?"), the pipeline first filters ChromaDB by the `minute` metadata field, then runs vector similarity only on the filtered subset. This makes time-based queries precise instead of random.

---

## 3. Agents

### Orchestrator

The central coordinator. Receives every transcript chunk, classifies it, and routes to the correct agent. Never does work directly.

| | |
|---|---|
| **Inputs** | Raw transcript chunks (text + speaker + timestamp) from the audio pipeline |
| **Outputs** | Classified chunks dispatched to agents. Final compiled summary at meeting end. |
| **Tools** | Utterance classifier prompt, LangGraph state manager, agent dispatcher |
| **Classification labels** | `decision` · `task_commitment` · `research_trigger` · `discussion` · `off_topic` |
| **Key rule** | Maintains a running meeting context object that all agents can read. At meeting end, collects all agent outputs and compiles the unified package for the email agent. |

### Note-taking Agent

Converts raw transcript into structured, readable notes in real time.

| | |
|---|---|
| **Inputs** | Chunks classified as `discussion` or `decision` |
| **Outputs** | Formatted notes pushed incrementally to Notion API or Google Docs API |
| **Tools** | Notion/Docs API client, summarization prompt, topic clustering |
| **Key rule** | Groups related points under auto-generated topic headings. Maintains a separate "Decisions" section. Notes are complete by the time the call ends — no post-processing. |

### Task Extraction Agent

Detects action items from natural conversation and creates trackable tickets.

| | |
|---|---|
| **Inputs** | Chunks classified as `task_commitment` |
| **Outputs** | Jira tickets with assignee, description, deadline, priority |
| **Tools** | Jira REST API client, NER for person names, date parser |
| **Detection patterns** | "I will…", "I'll take care of…", "Let's get this done by…", "Can you handle…", "Action item:…" |
| **Key rule** | Extracts `{assignee, task_description, deadline, priority}`. When ownership is ambiguous ("someone should look into this"), flags the task for human review instead of guessing. |

### Research Agent

Fetches background information when unfamiliar topics surface in conversation.

| | |
|---|---|
| **Inputs** | Chunks classified as `research_trigger` |
| **Outputs** | Research briefs (3–5 sentences) added to meeting context for the final recap |
| **Tools** | RAG query (ChromaDB), web search (Tavily API), document summarizer |
| **Key rule** | Checks RAG first (uploaded docs + past transcripts). Falls back to web search only when RAG confidence is low. Results are injected into the orchestrator's context, not sent mid-meeting in MVP. |

### Email Automation Agent

Drafts and sends follow-up emails after the meeting ends.

| | |
|---|---|
| **Inputs** | Compiled summary from orchestrator (notes + tasks + decisions + research) |
| **Outputs** | Two email variants sent via SMTP or Microsoft Graph Mail API |
| **Templates** | **Participant email:** full summary, assigned tasks, decisions, links to notes. **Stakeholder email:** brief executive summary, decisions only, no task list. |
| **Key rule** | Always routes through human-in-the-loop before sending. The approver sees a preview and can approve, edit, or reject. |

### Human-in-the-Loop Gate (Middleware)

Not a standalone agent. A reusable middleware any agent can invoke to pause and request human approval.

| | |
|---|---|
| **Trigger points** | Before sending any email (email agent). Before creating ambiguous tasks (task agent). |
| **Mechanism** | Sends Teams adaptive card with approve / reject / edit buttons. Waits for response. |
| **Timeout** | Configurable. Default 10 minutes. Escalates if no response. |
| **Audit** | Logs who approved what, when, for every gated action. |

---


## 5. Architecture

### Technology Stack

| Layer | MVP Technology |
|-------|---------------|
| Language | Python 3.11+ |
| API framework | FastAPI |
| Orchestration | LangGraph (stateful multi-agent graph) |
| LLM | Claude (Anthropic API) — primary. OpenAI GPT-4o — fallback. |
| Real-time transcription | Browser caption scraping via Playwright MutationObserver |
| Meeting joining | Playwright + Groq vision (fallback) |
| Embeddings | OpenAI text-embedding-3-small |
| Vector database | ChromaDB (containerized) |
| Web search | Tavily API |
| Task management | Jira REST API |
| Note storage | Notion API |
| Email | Microsoft Graph Mail API |
| Teams integration | Playwright browser automation (join + captions) |
| Tracing | LangSmith |
| Containerization | Podman + podman-compose |
| Message passing | LangGraph channels (in-process). Redis Streams if scaling needed. |

### Container Layout (podman-compose)

```
┌─────────────────────────────────────────────────┐
│                 Podman Host                      │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐             │
│  │  app          │  │  chromadb     │             │
│  │  FastAPI +    │  │  Vector DB    │             │
│  │  LangGraph    │◄─►  Port 8000   │             │
│  │  Port 8080    │  │              │             │
│  └──────────────┘  └──────────────┘             │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐             │
│  │  worker       │  │  redis        │             │
│  │  Background   │  │  Message      │             │
│  │  agent tasks  │  │  queue        │             │
│  └──────────────┘  └──────────────┘             │
│                                                  │
│  Volumes: chromadb_data, app_logs                │
└─────────────────────────────────────────────────┘
```


## 5. System Flow



### Phase 2 — Live Meeting

```
Teams meeting starts
         │
         ▼
Bot joins via Playwright browser automation
  (vision-guided with Groq fallback)
         │
         ▼
Bot enables live captions in Teams UI
         │
         ▼
MutationObserver scrapes captions from DOM in real time
  - Speaker name extracted from span[data-tid="author"]
  - Caption text finalized via terminal punctuation detection
  - Duplicates filtered by stripped-text comparison
         │
         ▼
Finalized caption segments emitted as they appear
  {speaker, text, timestamp_start, timestamp_end, minute, meeting_id}
         │
         ▼
┌──────────────────────────────────────────────────────┐
│                   ORCHESTRATOR                        │
│                                                      │
│  Classifies each chunk:                              │
│    → discussion       ──► Note-taking agent           │
│    → decision         ──► Note-taking agent           │
│    → task_commitment  ──► Task extraction agent        │
│    → research_trigger ──► Research agent               │
│    → off_topic        ──► Discarded                   │
│                                                      │
│  All dispatches are parallel (LangGraph fan-out)     │
│  Running context object updated after each chunk     │
│  LangSmith traces every classification + dispatch    │
└──────────────────────────────────────────────────────┘
         │                    │                   │
         ▼                    ▼                   ▼
   ┌───────────┐      ┌────────────┐      ┌────────────┐
   │ Note-taker │      │ Task agent  │      │ Researcher │
   │ → Notion   │      │ → Jira      │      │ → RAG      │
   │   (live)   │      │ (or HITL    │      │ → Tavily   │
   │            │      │  if vague)  │      │            │
   └───────────┘      └────────────┘      └────────────┘
```

Each chunk is also embedded and stored in ChromaDB in parallel with the agent dispatch, building the searchable meeting archive as the meeting runs.

### Phase 3 — Post-meeting

```
Meeting-end signal received (bot detects call ended)
         │
         ▼
Orchestrator collects outputs from all agents:
  - Structured notes (from note-taker)
  - Task list with ticket URLs (from task agent)
  - Research briefs (from researcher)
         │
         ▼
Orchestrator compiles unified summary object
         │
         ▼
Email agent drafts two email variants:
  - Participant: full notes + tasks + decisions + research
  - Stakeholder: executive brief + decisions only
         │
         ▼
Human-in-the-loop gate fires:
  Approver receives Teams adaptive card with email preview
         │
         ├── Approve → Emails sent via Graph Mail / SMTP
         ├── Edit    → Email agent revises, re-submits
         └── Reject  → Emails discarded, logged
         │
         ▼
Full transcript + metadata stored in ChromaDB
Meeting archived. System ready for next meeting.
```

### RAG Query Flow (Anytime)

```
User query: "What did Sarah say at minute 12?"
         │
         ▼
Query parser (LLM): extracts {speaker: "Sarah", minute: 12}
         │
         ▼
Step 1 — Metadata filter:
  ChromaDB WHERE minute=12 AND speaker="Sarah"
  (narrows from thousands of chunks to ~5-10)
         │
         ▼
Step 2 — Vector similarity:
  Cosine search on filtered subset only
  Returns top-k ranked by relevance
         │
         ▼
Step 3 — LLM synthesis:
  Retrieved chunks → coherent answer with citations
         │
         ▼
Response: "At minute 12, Sarah said the Q3 deadline
is moving to September 15th due to the vendor delay
discussed earlier in the meeting."
```

--

