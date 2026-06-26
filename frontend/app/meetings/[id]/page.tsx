"use client";

import { use, useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  useMeetingStatus,
  useSendChunk,
  useEndMeeting,
  useDeleteMeeting,
} from "@/hooks/useMeeting";
import { useBotStatus, useStartBot, useStopBot } from "@/hooks/useBot";
import { useAppStore } from "@/store";
import Card, { CardBody, CardHeader } from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Input, { Textarea } from "@/components/ui/Input";
import Modal from "@/components/ui/Modal";
import Header from "@/components/layout/Header";
import Skeleton from "@/components/ui/Skeleton";
import {
  Send,
  StopCircle,
  Activity,
  FileText,
  Cpu,
  Search,
  CheckSquare,
  AlertTriangle,
  Users,
  Loader2,
  MessageSquare,
  BookOpen,
  FlaskConical,
  Bot,
  Terminal,
  Link2,
  Square,
  Trash2,
} from "lucide-react";
import toast from "react-hot-toast";
import type { TranscriptChunk, NoteSection, ExtractedTask, ResearchBrief } from "@/types";

// ─── Stat pill ──────────────────────────────────────────────────────────────

function StatPill({ label, value, icon: Icon }: { label: string; value: number; icon: React.ElementType }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-bg-elevated border border-border">
      <Icon className="w-3.5 h-3.5 text-text-muted" />
      <span className="text-xs text-text-muted">{label}</span>
      <span className="text-sm font-semibold text-text ml-auto">{value}</span>
    </div>
  );
}

// ─── Speaker colour map (stable across re-renders) ───────────────────────────

const SPEAKER_COLORS = [
  "text-primary-light",
  "text-accent",
  "text-success-light",
  "text-warning-light",
  "text-danger-light",
];

function useSpeakerColor() {
  const mapRef = useRef<Record<string, number>>({});
  const idxRef = useRef(0);
  return useCallback((speaker: string) => {
    if (!(speaker in mapRef.current)) {
      mapRef.current[speaker] = idxRef.current++ % SPEAKER_COLORS.length;
    }
    return SPEAKER_COLORS[mapRef.current[speaker]];
  }, []);
}

// ─── Single transcript line ───────────────────────────────────────────────────

function ChunkLine({ chunk, color }: { chunk: TranscriptChunk; color: string }) {
  return (
    <div className="flex gap-2 text-sm animate-fade-in">
      <span className="text-xs text-text-dim mono shrink-0 pt-0.5 w-14">
        {chunk.timestamp_start}
      </span>
      <div className="flex-1 min-w-0">
        <span className={`font-semibold text-xs ${color}`}>{chunk.speaker}</span>
        <span className="text-text-muted ml-1">{chunk.text}</span>
      </div>
    </div>
  );
}

// ─── Live transcript feed (SSE-powered when active) ──────────────────────────

function TranscriptFeed({
  meetingId,
  isActive,
  fallbackChunks,
}: {
  meetingId: string;
  isActive: boolean;
  fallbackChunks: TranscriptChunk[];
}) {
  const [liveChunks, setLiveChunks] = useState<TranscriptChunk[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const getColor = useSpeakerColor();

  // Seed local list from polling data on first load
  useEffect(() => {
    if (fallbackChunks.length > liveChunks.length) {
      setLiveChunks(fallbackChunks);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fallbackChunks.length]);

  // SSE connection while meeting is active
  useEffect(() => {
    if (!isActive) return;
    const apiUrl =
      (typeof window !== "undefined" && (window as Window & { __meetflowApiUrl?: string }).__meetflowApiUrl) ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8080";

    const es = new EventSource(`${apiUrl}/meeting/${meetingId}/stream`);

    es.onmessage = (event) => {
      if (event.data === "[DONE]") {
        es.close();
        return;
      }
      try {
        const chunk: TranscriptChunk = JSON.parse(event.data);
        setLiveChunks((prev) => {
          // Deduplicate by timestamp_start + speaker
          const key = `${chunk.speaker}|${chunk.timestamp_start}`;
          const exists = prev.some(
            (c) => `${c.speaker}|${c.timestamp_start}` === key
          );
          return exists ? prev : [...prev, chunk];
        });
      } catch {
        // ignore parse errors
      }
    };

    return () => es.close();
  }, [meetingId, isActive]);

  // Auto-scroll on new lines
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [liveChunks.length]);

  const chunks = isActive ? liveChunks : fallbackChunks;

  if (chunks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-text-dim">
        <MessageSquare className="w-8 h-8 mb-2" />
        <p className="text-sm">No transcript yet — join Teams via the Bot tab or inject manually</p>
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1">
      {chunks.map((chunk, i) => (
        <ChunkLine key={i} chunk={chunk} color={getColor(chunk.speaker)} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

// ─── Notes panel ─────────────────────────────────────────────────────────────

function NotesPanel({ notes, decisions }: { notes: NoteSection[]; decisions: string[] }) {
  if (notes.length === 0 && decisions.length === 0) {
    return (
      <div className="text-center py-8 text-text-dim">
        <BookOpen className="w-7 h-7 mx-auto mb-2" />
        <p className="text-sm">Notes will appear as the meeting progresses</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 max-h-72 overflow-y-auto pr-1">
      {decisions.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-warning-light uppercase tracking-wider mb-1.5">
            Decisions
          </p>
          <ul className="space-y-1">
            {decisions.map((d, i) => (
              <li key={i} className="text-sm text-text-muted flex gap-2">
                <span className="text-warning-light shrink-0">•</span>
                {d}
              </li>
            ))}
          </ul>
        </div>
      )}
      {notes.map((section, i) => (
        <div key={i}>
          <p className="text-xs font-semibold text-primary-light uppercase tracking-wider mb-1.5">
            {section.topic}
            {section.is_decision && (
              <Badge variant="warning" size="sm" className="ml-2">decision</Badge>
            )}
          </p>
          <ul className="space-y-1">
            {section.points.map((p, j) => (
              <li key={j} className="text-sm text-text-muted flex gap-2">
                <span className="text-text-dim shrink-0">•</span>
                {p}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

// ─── Tasks panel ─────────────────────────────────────────────────────────────

function TasksPanel({ tasks }: { tasks: ExtractedTask[] }) {
  if (tasks.length === 0) {
    return (
      <div className="text-center py-8 text-text-dim">
        <CheckSquare className="w-7 h-7 mx-auto mb-2" />
        <p className="text-sm">No tasks extracted yet</p>
      </div>
    );
  }

  const priorityColor: Record<string, string> = {
    highest: "danger", high: "warning", medium: "accent", low: "success", lowest: "dim",
  };

  return (
    <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
      {tasks.map((task, i) => (
        <div key={i} className="p-3 rounded-lg bg-bg-base border border-border">
          <div className="flex items-center justify-between gap-2 mb-1">
            <p className="text-sm text-text font-medium truncate">{task.task_description}</p>
            <Badge
              variant={(priorityColor[task.priority?.toLowerCase()] as "danger" | "warning" | "accent" | "success" | "dim") ?? "default"}
              size="sm"
            >
              {task.priority}
            </Badge>
          </div>
          <div className="flex items-center gap-3 text-xs text-text-dim">
            <span>👤 {task.assignee || "Unassigned"}</span>
            {task.deadline && <span>📅 {task.deadline}</span>}
            {task.jira_ticket_url && (
              <a
                href={task.jira_ticket_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline"
              >
                Jira ↗
              </a>
            )}
            {task.is_ambiguous && <Badge variant="warning" size="sm">ambiguous</Badge>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Research panel ───────────────────────────────────────────────────────────

function ResearchPanel({ research }: { research: ResearchBrief[] }) {
  if (research.length === 0) {
    return (
      <div className="text-center py-8 text-text-dim">
        <FlaskConical className="w-7 h-7 mx-auto mb-2" />
        <p className="text-sm">No research briefs yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
      {research.map((brief, i) => (
        <div key={i} className="p-3 rounded-lg bg-bg-base border border-border">
          <p className="text-xs font-semibold text-accent mb-1">{brief.query}</p>
          <p className="text-sm text-text-muted">{brief.summary}</p>
          {brief.sources.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {brief.sources.map((src, j) => (
                <span key={j} className="text-xs text-text-dim mono bg-bg-elevated px-1.5 py-0.5 rounded">
                  {src.length > 40 ? src.slice(0, 40) + "…" : src}
                </span>
              ))}
            </div>
          )}
          <Badge variant={brief.from_rag ? "primary" : "accent"} size="sm" className="mt-2">
            {brief.from_rag ? "from transcript" : "web search"}
          </Badge>
        </div>
      ))}
    </div>
  );
}

// ─── Chunk sender ─────────────────────────────────────────────────────────────

function SendChunkPanel({ meetingId }: { meetingId: string }) {
  const [speaker, setSpeaker] = useState("");
  const [text, setText] = useState("");
  const [timestampStart, setTimestampStart] = useState("00:00:00");
  const [minute, setMinute] = useState(0);
  const [lastClass, setLastClass] = useState<string | null>(null);
  const { mutate: sendChunk, isPending } = useSendChunk();

  const classColor = (c: string) =>
    ({ decision: "success", task_commitment: "primary", research_trigger: "accent", off_topic: "dim" }[c] ?? "default");

  const handleSend = () => {
    if (!speaker.trim() || !text.trim()) {
      toast.error("Speaker and text are required");
      return;
    }
    sendChunk(
      { meeting_id: meetingId, speaker: speaker.trim(), text: text.trim(), timestamp_start: timestampStart, timestamp_end: timestampStart, minute },
      {
        onSuccess: (r) => {
          setLastClass(r.classification);
          setText("");
          setMinute((m) => m + 1);
          toast.success(`Classified: ${r.classification}`);
        },
        onError: (e) => toast.error(e.message),
      }
    );
  };

  return (
    <Card>
      <CardHeader>
        <h2 className="text-sm font-semibold text-text">Send Transcript Chunk</h2>
        <p className="text-xs text-text-dim mt-0.5">Inject a chunk — the live graph will classify and process it</p>
      </CardHeader>
      <CardBody className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Input label="Speaker" placeholder="Alice" value={speaker} onChange={(e) => setSpeaker(e.target.value)} />
          <Input label="Timestamp" placeholder="00:05:22" value={timestampStart} onChange={(e) => setTimestampStart(e.target.value)} />
        </div>
        <Textarea
          label="Transcript text"
          placeholder="Type or paste a meeting utterance…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          onKeyDown={(e) => { if (e.key === "Enter" && e.ctrlKey) handleSend(); }}
        />
        <div className="flex items-center justify-between">
          {lastClass && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-text-dim">Last:</span>
              <Badge variant={classColor(lastClass) as "success" | "primary" | "accent" | "dim" | "default"} size="sm">
                {lastClass}
              </Badge>
            </div>
          )}
          <Button
            variant="primary"
            size="sm"
            loading={isPending}
            icon={<Send className="w-3.5 h-3.5" />}
            onClick={handleSend}
            className="ml-auto"
          >
            Send (Ctrl+Enter)
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Bot control panel ────────────────────────────────────────────────────────

function BotControlPanel({ meetingId }: { meetingId: string }) {
  const [teamsUrl, setTeamsUrl] = useState("");
  const [displayName, setDisplayName] = useState("MeetFlow AI");
  const logsRef = useRef<HTMLDivElement>(null);

  const { data: botStatus } = useBotStatus(meetingId);
  const { mutate: startBot, isPending: starting } = useStartBot();
  const { mutate: stopBot, isPending: stopping } = useStopBot();

  const isRunning = botStatus?.status === "running";
  const isStopped = botStatus?.status === "stopped";
  const logs = botStatus?.recent_logs ?? [];

  // Auto-scroll logs to bottom
  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [logs.length]);

  const handleStart = () => {
    if (!teamsUrl.trim()) {
      toast.error("Paste a Teams meeting link first");
      return;
    }
    startBot(
      { meeting_id: meetingId, teams_url: teamsUrl.trim(), display_name: displayName.trim() || "MeetFlow AI" },
      {
        onSuccess: () => toast.success("Bot is joining the meeting…"),
        onError: (e) => toast.error(e.message),
      }
    );
  };

  const handleStop = () => {
    stopBot(meetingId, {
      onSuccess: () => toast.success("Bot stopped"),
      onError: (e) => toast.error(e.message),
    });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-primary-light" />
            <h2 className="text-sm font-semibold text-text">Teams Bot</h2>
          </div>
          {botStatus && (
            <Badge
              variant={isRunning ? "success" : isStopped ? "dim" : "default"}
              dot
              size="sm"
            >
              {isRunning ? "running" : isStopped ? `exited (${botStatus.exit_code})` : "not started"}
            </Badge>
          )}
        </div>
        <p className="text-xs text-text-dim mt-0.5">
          {isRunning
            ? "Bot is in the meeting — captions are streaming into the pipeline"
            : "Paste a Teams link and the bot will join and capture live captions"}
        </p>
      </CardHeader>

      <CardBody className="space-y-3">
        {!isRunning && (
          <>
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">
                Teams meeting link *
              </label>
              <input
                className="w-full h-9 px-3 text-sm rounded-lg border bg-bg-elevated border-border text-text focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 placeholder:text-text-dim"
                placeholder="https://teams.microsoft.com/l/meetup-join/…"
                value={teamsUrl}
                onChange={(e) => setTeamsUrl(e.target.value)}
              />
            </div>
            <Input
              label="Display name in meeting"
              placeholder="MeetFlow AI"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
            <Button
              variant="primary"
              size="sm"
              loading={starting}
              icon={<Link2 className="w-3.5 h-3.5" />}
              onClick={handleStart}
              className="w-full justify-center"
            >
              Join Teams meeting
            </Button>
          </>
        )}

        {isRunning && (
          <Button
            variant="danger"
            size="sm"
            loading={stopping}
            icon={<Square className="w-3.5 h-3.5" />}
            onClick={handleStop}
            className="w-full justify-center"
          >
            Stop bot
          </Button>
        )}

        {/* Log terminal */}
        {logs.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-1.5">
              <Terminal className="w-3 h-3 text-text-dim" />
              <span className="text-xs text-text-dim">Bot log</span>
            </div>
            <div
              ref={logsRef}
              className="bg-bg-base border border-border rounded-lg p-2.5 h-48 overflow-y-auto font-mono text-[10px] leading-4 space-y-0.5"
            >
              {logs.map((line, i) => {
                const isError = /error|exception|traceback|failed/i.test(line);
                const isWarn = /warning|warn/i.test(line);
                const isGood = /caption|chunk|transcript|sent|connected|joined/i.test(line);
                return (
                  <div
                    key={i}
                    className={
                      isError ? "text-danger-light" :
                      isWarn ? "text-warning-light" :
                      isGood ? "text-success-light" :
                      "text-text-dim"
                    }
                  >
                    {line}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {botStatus?.status === "not_started" && (
          <p className="text-xs text-text-dim text-center py-2">
            No bot started yet for this meeting
          </p>
        )}
      </CardBody>
    </Card>
  );
}

// ─── End meeting modal ────────────────────────────────────────────────────────

function EndMeetingModal({ meetingId, open, onClose }: { meetingId: string; open: boolean; onClose: () => void }) {
  const [recipientEmails, setRecipientEmails] = useState("");
  const [stakeholderEmails, setStakeholderEmails] = useState("");
  const { mutate: endMeeting, isPending } = useEndMeeting();
  const router = useRouter();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const recipients = recipientEmails.split(",").map((s) => s.trim()).filter(Boolean);
    const stakeholders = stakeholderEmails.split(",").map((s) => s.trim()).filter(Boolean);
    endMeeting(
      { meetingId, req: { recipient_emails: recipients, stakeholder_emails: stakeholders.length ? stakeholders : recipients } },
      {
        onSuccess: (data) => {
          toast.success(`Meeting ended · ${data.summary.notes_sections} note sections · ${data.summary.tasks} tasks`);
          onClose();
          router.push("/meetings");
        },
        onError: (e) => toast.error(e.message),
      }
    );
  };

  return (
    <Modal open={open} onClose={onClose} title="End Meeting" size="md">
      <p className="text-sm text-text-muted mb-4">
        Triggers the post-meeting graph: final notes → Notion write → email drafts with HITL approval.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Recipient emails (comma-separated)" placeholder="alice@co.com, bob@co.com" value={recipientEmails} onChange={(e) => setRecipientEmails(e.target.value)} />
        <Input label="Stakeholder emails (optional)" placeholder="cto@co.com" value={stakeholderEmails} onChange={(e) => setStakeholderEmails(e.target.value)} />
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="danger" loading={isPending} icon={<StopCircle className="w-4 h-4" />}>
            End & process
          </Button>
        </div>
      </form>
    </Modal>
  );
}

// ─── Right-panel tab ─────────────────────────────────────────────────────────

type RightTab = "bot" | "manual";

// ─── Tab bar ─────────────────────────────────────────────────────────────────

type Tab = "transcript" | "notes" | "tasks" | "research";
const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "transcript", label: "Transcript", icon: MessageSquare },
  { id: "notes", label: "Notes", icon: BookOpen },
  { id: "tasks", label: "Tasks", icon: CheckSquare },
  { id: "research", label: "Research", icon: FlaskConical },
];

// ─── Page ────────────────────────────────────────────────────────────────────

export default function MeetingDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [showEndModal, setShowEndModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("transcript");
  const [rightTab, setRightTab] = useState<RightTab>("bot");

  const meeting = useAppStore((s) => s.activeMeetings.find((m) => m.meeting_id === id));
  const { data: status, isLoading } = useMeetingStatus(id);
  const { data: botStatus } = useBotStatus(id);
  const { mutate: deleteMeeting, isPending: deleting } = useDeleteMeeting();

  const isActive = status?.status === "active" || (!status && !!meeting);

  const transcript = status?.transcript ?? [];
  const notes = status?.notes ?? [];
  const decisions = status?.decisions ?? [];
  const tasks = status?.tasks ?? [];
  const research = status?.research ?? [];

  const handleDelete = () => {
    deleteMeeting(id, {
      onSuccess: () => {
        toast.success(`Meeting "${id}" deleted`);
        router.push("/meetings");
      },
      onError: (e) => toast.error(e.message),
    });
  };

  return (
    <div className="animate-fade-in">
      <Header
        title={meeting?.title || id}
        subtitle={`Meeting ID: ${id}`}
        actions={
          <div className="flex items-center gap-2">
            {isActive ? (
              <Button variant="danger" size="sm" icon={<StopCircle className="w-4 h-4" />} onClick={() => setShowEndModal(true)}>
                End meeting
              </Button>
            ) : (
              <Badge variant="dim" dot>Ended</Badge>
            )}
            <Button
              variant="ghost"
              size="sm"
              icon={<Trash2 className="w-3.5 h-3.5 text-danger-light" />}
              onClick={() => setShowDeleteConfirm(true)}
            >
              Delete
            </Button>
          </div>
        }
      />

      {/* Delete confirm modal */}
      <Modal open={showDeleteConfirm} onClose={() => setShowDeleteConfirm(false)} title="Delete meeting?" size="sm">
        <p className="text-sm text-text-muted mb-4">
          This will remove the meeting state from Redis, all transcript embeddings from ChromaDB, and all HITL records. This cannot be undone.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setShowDeleteConfirm(false)}>Cancel</Button>
          <Button variant="danger" loading={deleting} icon={<Trash2 className="w-4 h-4" />} onClick={handleDelete}>
            Delete
          </Button>
        </div>
      </Modal>

      <div className="px-8 py-6 space-y-4 max-w-6xl">
        {/* Stats */}
        {isLoading ? (
          <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}
          </div>
        ) : status ? (
          <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
            <StatPill label="Chunks" value={status.chunks_processed} icon={Activity} />
            <StatPill label="Notes" value={status.notes_sections} icon={FileText} />
            <StatPill label="Tasks" value={status.tasks_extracted} icon={CheckSquare} />
            <StatPill label="Research" value={status.research_briefs} icon={Search} />
            <StatPill label="Approvals" value={status.pending_approvals} icon={Cpu} />
            <StatPill label="Errors" value={status.errors} icon={AlertTriangle} />
          </div>
        ) : null}

        {/* Live indicator */}
        {isActive && (
          <div className="flex items-center gap-2 text-sm text-success-light px-3 py-2 rounded-lg bg-success-muted border border-success/20">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Meeting is live — status refreshes every 4s
          </div>
        )}

        {/* Participants */}
        {meeting && meeting.participants.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap text-xs text-text-dim">
            <Users className="w-3.5 h-3.5" />
            {meeting.participants.map((p) => (
              <span key={p} className="px-2 py-0.5 rounded-full bg-bg-elevated border border-border text-text-muted">
                {p}
              </span>
            ))}
          </div>
        )}

        {/* Main two-column layout */}
        <div className="grid lg:grid-cols-[1fr_400px] gap-4">
          {/* Left — tabbed live content */}
          <Card>
            {/* Tab bar */}
            <div className="flex items-center gap-0.5 px-3 pt-3 pb-0 border-b border-border">
              {TABS.map(({ id: tabId, label, icon: Icon }) => {
                const count =
                  tabId === "transcript" ? transcript.length :
                  tabId === "notes" ? notes.length + decisions.length :
                  tabId === "tasks" ? tasks.length :
                  research.length;
                return (
                  <button
                    key={tabId}
                    onClick={() => setActiveTab(tabId)}
                    className={`flex items-center gap-1.5 px-3 py-2 text-xs rounded-t-lg transition-colors border-b-2 -mb-px ${
                      activeTab === tabId
                        ? "border-primary text-primary-light font-medium bg-primary-muted/30"
                        : "border-transparent text-text-muted hover:text-text"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {label}
                    {count > 0 && (
                      <span className="min-w-[16px] h-4 rounded-full bg-bg-elevated border border-border text-[10px] flex items-center justify-center px-1">
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            <CardBody>
              {activeTab === "transcript" && (
                <TranscriptFeed
                  meetingId={id}
                  isActive={isActive}
                  fallbackChunks={transcript}
                />
              )}
              {activeTab === "notes" && <NotesPanel notes={notes} decisions={decisions} />}
              {activeTab === "tasks" && <TasksPanel tasks={tasks} />}
              {activeTab === "research" && <ResearchPanel research={research} />}
            </CardBody>
          </Card>

          {/* Right — Bot control + Manual injection tabs */}
          {isActive ? (
            <div className="space-y-2">
              {/* Tab switcher */}
              <div className="flex items-center gap-1 p-1 bg-bg-elevated border border-border rounded-xl w-fit">
                <button
                  onClick={() => setRightTab("bot")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg transition-colors ${
                    rightTab === "bot"
                      ? "bg-bg-overlay text-text font-medium"
                      : "text-text-muted hover:text-text"
                  }`}
                >
                  <Bot className="w-3.5 h-3.5" />
                  Bot
                  {botStatus?.status === "running" && (
                    <span className="w-1.5 h-1.5 rounded-full bg-success shrink-0" />
                  )}
                </button>
                <button
                  onClick={() => setRightTab("manual")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg transition-colors ${
                    rightTab === "manual"
                      ? "bg-bg-overlay text-text font-medium"
                      : "text-text-muted hover:text-text"
                  }`}
                >
                  <Send className="w-3.5 h-3.5" />
                  Manual
                </button>
              </div>

              {rightTab === "bot" ? (
                <BotControlPanel meetingId={id} />
              ) : (
                <SendChunkPanel meetingId={id} />
              )}
            </div>
          ) : (
            <Card>
              <CardBody>
                <p className="text-sm text-text-dim text-center py-8">Meeting has ended</p>
              </CardBody>
            </Card>
          )}
        </div>
      </div>

      <EndMeetingModal meetingId={id} open={showEndModal} onClose={() => setShowEndModal(false)} />
    </div>
  );
}
