// ─── Enums ──────────────────────────────────────────────────────────────────

export type ChunkClassification =
  | "decision"
  | "task_commitment"
  | "research_trigger"
  | "discussion"
  | "off_topic";

export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "edited"
  | "timed_out";

// ─── Core domain models ─────────────────────────────────────────────────────

export interface TranscriptChunk {
  meeting_id: string;
  speaker: string;
  text: string;
  timestamp_start: string;
  timestamp_end: string;
  minute: number;
  topic_cluster?: string | null;
  source_type?: string;
}

export interface ClassifiedChunk {
  chunk: TranscriptChunk;
  classification: ChunkClassification;
  confidence: number;
}

export interface NoteSection {
  topic: string;
  points: string[];
  is_decision: boolean;
}

export interface ExtractedTask {
  assignee: string;
  task_description: string;
  deadline?: string | null;
  priority: string;
  is_ambiguous: boolean;
  jira_ticket_url?: string | null;
}

export interface ResearchBrief {
  query: string;
  summary: string;
  sources: string[];
  from_rag: boolean;
}

export interface EmailDraft {
  variant: string;
  subject: string;
  body_html: string;
  recipients: string[];
}

export interface ApprovalRequest {
  request_id: string;
  action_type: string;
  payload: Record<string, unknown>;
  status: ApprovalStatus;
  requested_at: string;
  resolved_at?: string | null;
  resolved_by?: string | null;
}

// ─── API request/response shapes ────────────────────────────────────────────

export interface MeetingStartRequest {
  meeting_id: string;
  title?: string;
  participants?: string[];
}

export interface EndMeetingRequest {
  recipient_emails?: string[];
  stakeholder_emails?: string[];
}

export interface ChunkInput {
  meeting_id: string;
  speaker: string;
  text: string;
  timestamp_start: string;
  timestamp_end: string;
  minute: number;
}

export interface RAGQueryRequest {
  question: string;
  meeting_id?: string;
  speaker?: string;
  minute?: number;
}

export interface RAGQueryResult {
  text: string;
  metadata: Record<string, unknown>;
  distance: number;
}

export interface ApprovalResponse {
  request_id: string;
  status: ApprovalStatus;
  edited_payload?: Record<string, unknown>;
  resolved_by: string;
}

// ─── Health & Status ─────────────────────────────────────────────────────────

export interface HealthStatus {
  status: "ok" | "degraded";
  redis: boolean;
  chromadb: boolean;
}

export interface MeetingStatus {
  status: "active" | "ended" | "archived";
  chunks_processed: number;
  notes_sections: number;
  tasks_extracted: number;
  research_briefs: number;
  pending_approvals: number;
  errors: number;
  // Full content returned by the live status endpoint
  transcript?: TranscriptChunk[];
  notes?: NoteSection[];
  decisions?: string[];
  tasks?: ExtractedTask[];
  research?: ResearchBrief[];
  // archived state includes full state dict
  state?: Record<string, unknown>;
}

export interface MeetingEndSummary {
  meeting_id: string;
  total_chunks: number;
  notes_sections: number;
  decisions: string[];
  tasks: number;
  research_briefs: number;
  email_drafts: number;
  errors: string[];
}

// ─── Active meeting (frontend-managed) ───────────────────────────────────────

export interface ActiveMeeting {
  meeting_id: string;
  title: string;
  participants: string[];
  started_at: string;
  status: MeetingStatus | null;
}

// ─── HITL ─────────────────────────────────────────────────────────────────────

export interface HitlRequest {
  request_id: string;
  action_type: string;
  payload: string; // JSON string from SQLite
  status: ApprovalStatus;
  requested_at: string;
  resolved_at?: string | null;
  resolved_by?: string | null;
}

// ─── Audit log ───────────────────────────────────────────────────────────────

export interface AuditEvent {
  id: number;
  event_type: string;
  meeting_id?: string | null;
  request_id?: string | null;
  actor?: string | null;
  detail?: string | null;
  created_at: string;
}

// ─── Bot ─────────────────────────────────────────────────────────────────────

export type BotStatusValue = "not_started" | "running" | "stopped";

export interface BotStatus {
  status: BotStatusValue;
  pid: number | null;
  exit_code: number | null;
  recent_logs: string[];
}

export interface BotStartRequest {
  meeting_id: string;
  teams_url: string;
  display_name?: string;
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  source?: "rag" | "web" | "none";
  chunks?: RAGQueryResult[];
}

export interface ChatRequest {
  question: string;
  meeting_id?: string;
  history: { role: string; content: string }[];
}

export interface ChatResponse {
  answer: string;
  source: "rag" | "web" | "none";
  chunks: RAGQueryResult[];
}

// ─── UI helpers ──────────────────────────────────────────────────────────────

export type SidebarPage =
  | "dashboard"
  | "meetings"
  | "hitl"
  | "search"
  | "audit"
  | "settings";
