import axios, { AxiosError, AxiosInstance } from "axios";
import type {
  ApprovalResponse,
  BotStartRequest,
  BotStatus,
  ChatRequest,
  ChatResponse,
  ChunkInput,
  EndMeetingRequest,
  HealthStatus,
  HitlRequest,
  MeetingEndSummary,
  MeetingStartRequest,
  MeetingStatus,
  RAGQueryRequest,
  RAGQueryResult,
  AuditEvent,
} from "@/types";

// ─── Axios instance ──────────────────────────────────────────────────────────

const DEFAULT_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

const client: AxiosInstance = axios.create({
  baseURL: DEFAULT_BASE_URL,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

// Request interceptor — pick up dynamic API URL from Zustand store + log in dev
client.interceptors.request.use((config) => {
  // Dynamically read base URL so Settings page changes take effect without reload
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { useAppStore } = require("@/store");
    const storeUrl: string = useAppStore.getState().apiUrl;
    if (storeUrl) config.baseURL = storeUrl;
  } catch {
    // store not yet hydrated (SSR) — use default
  }
  if (process.env.NODE_ENV === "development") {
    console.debug(`→ ${config.method?.toUpperCase()} ${config.url}`);
  }
  return config;
});

// Response interceptor — normalise errors
client.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    const msg =
      (err.response?.data as { detail?: string })?.detail ||
      err.message ||
      "Unknown error";
    return Promise.reject(new Error(msg));
  }
);

// ─── Health ──────────────────────────────────────────────────────────────────

export const healthApi = {
  check: async (): Promise<HealthStatus> => {
    const { data } = await client.get<HealthStatus>("/health");
    return data;
  },
};

// ─── Meetings ────────────────────────────────────────────────────────────────

export const meetingApi = {
  start: async (req: MeetingStartRequest) => {
    const { data } = await client.post<{ status: string; meeting_id: string }>(
      "/meeting/start",
      req
    );
    return data;
  },

  sendChunk: async (chunk: ChunkInput) => {
    const { data } = await client.post<{
      status: string;
      classification: string;
      notes_count: number;
      tasks_count: number;
    }>("/meeting/chunk", chunk);
    return data;
  },

  end: async (
    meetingId: string,
    req: EndMeetingRequest
  ): Promise<{ status: string; summary: MeetingEndSummary }> => {
    const { data } = await client.post(
      `/meeting/${meetingId}/end`,
      req
    );
    return data;
  },

  getStatus: async (meetingId: string): Promise<MeetingStatus> => {
    const { data } = await client.get<MeetingStatus>(
      `/meeting/${meetingId}/status`
    );
    return data;
  },

  delete: async (meetingId: string): Promise<{ status: string; meeting_id: string }> => {
    const { data } = await client.delete(`/meeting/${meetingId}`);
    return data;
  },

  uploadTranscript: async (formData: FormData) => {
    const { data } = await client.post<{
      status: string;
      meeting_id: string;
      chunks_parsed: number;
      chunks_embedded: number;
      message: string;
    }>("/meeting/upload-transcript", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60_000,
    });
    return data;
  },
};

// ─── RAG ─────────────────────────────────────────────────────────────────────

export const ragApi = {
  query: async (req: RAGQueryRequest): Promise<RAGQueryResult[]> => {
    const { data } = await client.post<{
      results: RAGQueryResult[];
      count: number;
    }>("/rag/query", req);
    return data.results;
  },

  chat: async (req: ChatRequest): Promise<ChatResponse> => {
    const { data } = await client.post<ChatResponse>("/rag/chat", req);
    return data;
  },

  upload: async (meetingId: string, text: string, sourceName: string) => {
    const { data } = await client.post<{ status: string; meeting_id: string }>(
      "/rag/upload",
      { meeting_id: meetingId, text, source_name: sourceName }
    );
    return data;
  },
};

// ─── HITL & Approval ─────────────────────────────────────────────────────────

export const hitlApi = {
  listPending: async (): Promise<{ items: HitlRequest[]; count: number }> => {
    const { data } = await client.get("/hitl/pending");
    return data;
  },

  listAll: async (
    limit = 50
  ): Promise<{ items: HitlRequest[]; count: number }> => {
    const { data } = await client.get("/hitl/all", { params: { limit } });
    return data;
  },

  getRequest: async (requestId: string): Promise<HitlRequest> => {
    const { data } = await client.get<HitlRequest>(`/hitl/${requestId}`);
    return data;
  },

  respond: async (resp: ApprovalResponse) => {
    const { data } = await client.post<{ status: string; request_id: string }>(
      "/approval/respond",
      resp
    );
    return data;
  },
};

// ─── Audit ────────────────────────────────────────────────────────────────────

export const auditApi = {
  getEvents: async (
    meetingId?: string,
    limit = 100
  ): Promise<{ events: AuditEvent[]; count: number }> => {
    const { data } = await client.get("/hitl/audit/events", {
      params: { ...(meetingId ? { meeting_id: meetingId } : {}), limit },
    });
    return data;
  },
};

// ─── Bot ─────────────────────────────────────────────────────────────────────

export const botApi = {
  start: async (
    req: BotStartRequest
  ): Promise<{ status: string; pid: number; meeting_id: string }> => {
    const { data } = await client.post("/bot/start", req);
    return data;
  },

  getStatus: async (meetingId: string): Promise<BotStatus> => {
    const { data } = await client.get<BotStatus>(`/bot/status/${meetingId}`);
    return data;
  },

  stop: async (meetingId: string): Promise<{ status: string }> => {
    const { data } = await client.post(`/bot/stop/${meetingId}`);
    return data;
  },
};

export default client;
