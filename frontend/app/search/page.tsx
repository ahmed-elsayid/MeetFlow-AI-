"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ragApi } from "@/services/api";
import { useAppStore } from "@/store";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Header from "@/components/layout/Header";
import { Bot, Database, Globe, Loader2, Send, Upload, ChevronDown } from "lucide-react";
import toast from "react-hot-toast";
import type { ChatMessage, RAGQueryResult } from "@/types";

// ─── Source badge ─────────────────────────────────────────────────────────────

function SourceBadge({ source }: { source?: string }) {
  if (source === "rag")
    return <Badge variant="primary" size="sm"><Database className="w-3 h-3" /> Meeting transcript</Badge>;
  if (source === "web")
    return <Badge variant="accent" size="sm"><Globe className="w-3 h-3" /> Web search</Badge>;
  return null;
}

// ─── Chunk collapsible ────────────────────────────────────────────────────────

function ChunkList({ chunks }: { chunks: RAGQueryResult[] }) {
  const [open, setOpen] = useState(false);
  if (!chunks.length) return null;
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-text-dim hover:text-text transition-colors"
      >
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} />
        {chunks.length} source{chunks.length !== 1 ? "s" : ""}
      </button>
      {open && (
        <div className="mt-2 space-y-1.5 pl-2 border-l border-border">
          {chunks.map((c, i) => {
            const meta = c.metadata as Record<string, string | number | undefined>;
            return (
              <div key={i} className="text-xs text-text-dim bg-bg-elevated rounded-lg px-2.5 py-1.5">
                {meta.speaker && <span className="text-primary-light font-medium">{String(meta.speaker)}</span>}
                {meta.timestamp_start && <span className="ml-1 opacity-60">{String(meta.timestamp_start)}</span>}
                <p className="mt-0.5 text-text-muted">{c.text}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Message bubble ───────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      {/* Avatar */}
      <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-bold mt-0.5 ${
        isUser ? "bg-primary-muted text-primary-light" : "bg-bg-elevated border border-border text-text-muted"
      }`}>
        {isUser ? "U" : <Bot className="w-3.5 h-3.5" />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[75%] ${isUser ? "items-end" : "items-start"} flex flex-col gap-1`}>
        <div className={`px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
          isUser
            ? "bg-primary text-white rounded-tr-sm"
            : "bg-bg-elevated border border-border text-text rounded-tl-sm"
        }`}>
          {msg.content}
        </div>
        {!isUser && (
          <div className="flex items-center gap-2 pl-1">
            <SourceBadge source={msg.source} />
            {msg.chunks && <ChunkList chunks={msg.chunks} />}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const activeMeetings = useAppStore((s) => s.activeMeetings);
  const [meetingId, setMeetingId] = useState("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "Hello! Select a meeting and ask me anything — I'll search the transcript first, then the web if needed.",
    },
  ]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const { mutate: sendMessage, isPending } = useMutation({
    mutationFn: (question: string) =>
      ragApi.chat({
        question,
        meeting_id: meetingId.trim() || undefined,
        history: messages
          .filter((m) => m.role !== "assistant" || messages.indexOf(m) !== 0)
          .map((m) => ({ role: m.role, content: m.content })),
      }),
    onSuccess: (data, question) => {
      setMessages((prev) => [
        ...prev,
        { role: "user", content: question },
        { role: "assistant", content: data.answer, source: data.source, chunks: data.chunks },
      ]);
    },
    onError: (e: Error) => {
      toast.error(e.message);
    },
  });

  const handleSend = () => {
    const q = input.trim();
    if (!q || isPending) return;
    setInput("");
    sendMessage(q);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="animate-fade-in flex flex-col h-[calc(100vh-0px)]">
      <Header
        title="Meeting Chat"
        subtitle="Ask questions — answers come from the transcript or web search"
      />

      {/* Meeting selector */}
      <div className="px-8 py-3 border-b border-border flex items-center gap-3">
        <span className="text-xs text-text-muted shrink-0">Meeting:</span>
        {activeMeetings.length > 0 ? (
          <select
            className="h-8 px-2.5 text-xs rounded-lg border border-border bg-bg-elevated text-text focus:outline-none focus:border-primary"
            value={meetingId}
            onChange={(e) => setMeetingId(e.target.value)}
          >
            <option value="">All meetings</option>
            {activeMeetings.map((m) => (
              <option key={m.meeting_id} value={m.meeting_id}>
                {m.title || m.meeting_id}
              </option>
            ))}
          </select>
        ) : (
          <input
            className="h-8 px-2.5 text-xs rounded-lg border border-border bg-bg-elevated text-text focus:outline-none focus:border-primary w-48 placeholder:text-text-dim"
            placeholder="meeting-id (optional)"
            value={meetingId}
            onChange={(e) => setMeetingId(e.target.value)}
          />
        )}
        {meetingId && (
          <Badge variant="primary" size="sm">
            <Database className="w-3 h-3" /> {meetingId}
          </Badge>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto"
          onClick={() => {
            setMessages([{
              role: "assistant",
              content: "Conversation cleared. Ask me anything!",
            }]);
          }}
        >
          Clear chat
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-5">
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}

        {isPending && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-bg-elevated border border-border flex items-center justify-center shrink-0">
              <Bot className="w-3.5 h-3.5 text-text-muted" />
            </div>
            <div className="px-3.5 py-2.5 rounded-2xl rounded-tl-sm bg-bg-elevated border border-border">
              <Loader2 className="w-4 h-4 animate-spin text-text-dim" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-8 py-4 border-t border-border">
        <div className="flex gap-2 items-end max-w-4xl mx-auto">
          <textarea
            ref={textareaRef}
            className="flex-1 min-h-[40px] max-h-32 px-3.5 py-2.5 text-sm rounded-xl border border-border bg-bg-elevated text-text focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 placeholder:text-text-dim resize-none"
            placeholder="Ask about the meeting… (Enter to send, Shift+Enter for newline)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <Button
            variant="primary"
            size="sm"
            loading={isPending}
            icon={<Send className="w-3.5 h-3.5" />}
            onClick={handleSend}
            disabled={!input.trim()}
            className="shrink-0"
          >
            Send
          </Button>
        </div>
        <p className="text-center text-xs text-text-dim mt-2">
          <Database className="w-3 h-3 inline mr-1" />RAG from transcript ·
          <Globe className="w-3 h-3 inline mx-1" />falls back to web search
        </p>
      </div>

      {/* Upload panel (collapsible) */}
      <UploadPanel />
    </div>
  );
}

// ─── Upload panel ─────────────────────────────────────────────────────────────

function UploadPanel() {
  const [open, setOpen] = useState(false);
  const [meetingId, setMeetingId] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [text, setText] = useState("");
  const { mutate: upload, isPending } = useMutation({
    mutationFn: () => ragApi.upload(meetingId, text, sourceName),
    onSuccess: () => {
      toast.success("Document uploaded and embedded");
      setText("");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="border-t border-border px-8">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 py-3 text-xs text-text-dim hover:text-text transition-colors w-full"
      >
        <Upload className="w-3.5 h-3.5" />
        Upload document to knowledge base
        <ChevronDown className={`w-3.5 h-3.5 ml-auto transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="pb-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">Meeting ID</label>
              <input
                className="w-full h-8 px-2.5 text-xs rounded-lg border border-border bg-bg-elevated text-text focus:outline-none focus:border-primary placeholder:text-text-dim"
                placeholder="quarterly-review-q4"
                value={meetingId}
                onChange={(e) => setMeetingId(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1">Source name</label>
              <input
                className="w-full h-8 px-2.5 text-xs rounded-lg border border-border bg-bg-elevated text-text focus:outline-none focus:border-primary placeholder:text-text-dim"
                placeholder="agenda.pdf"
                value={sourceName}
                onChange={(e) => setSourceName(e.target.value)}
              />
            </div>
          </div>
          <textarea
            className="w-full px-3 py-2 text-xs rounded-lg border border-border bg-bg-elevated text-text focus:outline-none focus:border-primary placeholder:text-text-dim resize-none"
            placeholder="Paste document content here…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
          />
          <Button
            variant="primary"
            size="sm"
            loading={isPending}
            icon={<Upload className="w-3 h-3" />}
            onClick={() => upload()}
            disabled={!meetingId || !text || !sourceName}
          >
            Embed & store
          </Button>
        </div>
      )}
    </div>
  );
}
