"use client";

import { useState, useMemo } from "react";
import { useAuditEvents } from "@/hooks/useAudit";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Header from "@/components/layout/Header";
import Skeleton, { SkeletonRow } from "@/components/ui/Skeleton";
import { ScrollText, Search, RefreshCw, ChevronRight } from "lucide-react";
import { formatDate, truncate } from "@/lib/utils";
import type { AuditEvent } from "@/types";

function eventTypeColor(
  t: string
): "success" | "warning" | "danger" | "primary" | "accent" | "default" {
  if (t.includes("resolved") || t.includes("approved")) return "success";
  if (t.includes("rejected")) return "danger";
  if (t.includes("opened") || t.includes("pending")) return "warning";
  if (t.includes("hitl")) return "primary";
  if (t.includes("chunk")) return "accent";
  return "default";
}

function EventRow({ event, onClick }: { event: AuditEvent; onClick: () => void }) {
  return (
    <div
      className="flex items-center gap-3 px-4 py-2.5 border-b border-border/50 last:border-0 hover:bg-bg-elevated/40 cursor-pointer transition-colors group"
      onClick={onClick}
    >
      <div className="w-1.5 h-1.5 rounded-full bg-text-dim shrink-0" />
      <div className="flex-1 min-w-0 grid grid-cols-[140px_120px_1fr_80px] gap-2 items-center">
        <Badge variant={eventTypeColor(event.event_type)} size="sm">
          {event.event_type.replace(/_/g, " ")}
        </Badge>
        <p className="text-xs text-text-dim mono truncate">
          {event.meeting_id ?? event.request_id ?? "—"}
        </p>
        <p className="text-xs text-text-muted truncate">
          {event.detail ? truncate(event.detail, 80) : "—"}
        </p>
        <p className="text-xs text-text-dim text-right">
          {formatDate(event.created_at)}
        </p>
      </div>
      <ChevronRight className="w-3.5 h-3.5 text-text-dim opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
    </div>
  );
}

export default function AuditPage() {
  const [search, setSearch] = useState("");
  const [meetingFilter, setMeetingFilter] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null);

  const { data, isLoading, refetch } = useAuditEvents(
    meetingFilter.trim() || undefined,
    200
  );

  const filtered = useMemo(() => {
    if (!data?.events) return [];
    const q = search.toLowerCase();
    if (!q) return data.events;
    return data.events.filter(
      (e) =>
        e.event_type.toLowerCase().includes(q) ||
        (e.meeting_id ?? "").toLowerCase().includes(q) ||
        (e.request_id ?? "").toLowerCase().includes(q) ||
        (e.detail ?? "").toLowerCase().includes(q) ||
        (e.actor ?? "").toLowerCase().includes(q)
    );
  }, [data, search]);

  return (
    <div className="animate-fade-in">
      <Header
        title="Audit Log"
        subtitle="System events and HITL activity"
        actions={
          <Button
            variant="ghost"
            size="sm"
            icon={<RefreshCw className="w-3.5 h-3.5" />}
            onClick={() => refetch()}
          >
            Refresh
          </Button>
        }
      />

      <div className="px-8 py-6 max-w-5xl space-y-4">
        {/* Filters */}
        <div className="flex items-end gap-3">
          <Input
            label="Search events"
            placeholder="hitl_opened, email, meeting-id…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            icon={<Search className="w-4 h-4" />}
          />
          <Input
            label="Filter by meeting"
            placeholder="quarterly-review-q4"
            value={meetingFilter}
            onChange={(e) => setMeetingFilter(e.target.value)}
          />
        </div>

        {/* Stats */}
        <div className="flex items-center gap-2">
          <ScrollText className="w-4 h-4 text-text-dim" />
          <span className="text-sm text-text-muted">
            {filtered.length} event{filtered.length !== 1 ? "s" : ""}
            {search && " matching"}
          </span>
        </div>

        {/* Table */}
        <Card>
          {/* Header row */}
          <div className="grid grid-cols-[140px_120px_1fr_80px] gap-2 px-4 py-2 border-b border-border bg-bg-base/50">
            <span className="text-xs font-medium text-text-dim uppercase tracking-wider">Event</span>
            <span className="text-xs font-medium text-text-dim uppercase tracking-wider">Reference</span>
            <span className="text-xs font-medium text-text-dim uppercase tracking-wider">Detail</span>
            <span className="text-xs font-medium text-text-dim uppercase tracking-wider text-right">Time</span>
          </div>

          {isLoading ? (
            <div>
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonRow key={i} />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12">
              <ScrollText className="w-8 h-8 text-text-dim mx-auto mb-2" />
              <p className="text-sm text-text-muted">No events found</p>
            </div>
          ) : (
            <div>
              {filtered.map((event) => (
                <EventRow
                  key={event.id}
                  event={event}
                  onClick={() => setSelectedEvent(event)}
                />
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Event detail panel (simple bottom drawer) */}
      {selectedEvent && (
        <div
          className="fixed inset-0 z-40 flex items-end"
          onClick={() => setSelectedEvent(null)}
        >
          <div className="absolute inset-0 bg-black/40" />
          <div
            className="relative w-full bg-bg-elevated border-t border-border rounded-t-2xl p-6 max-h-[60vh] overflow-y-auto animate-slide-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-text">
                Event #{selectedEvent.id} — {selectedEvent.event_type}
              </h3>
              <Button variant="ghost" size="sm" onClick={() => setSelectedEvent(null)}>
                Close
              </Button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-xs text-text-dim">Meeting ID</p>
                <p className="text-text mono text-xs mt-0.5">
                  {selectedEvent.meeting_id ?? "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-text-dim">Request ID</p>
                <p className="text-text mono text-xs mt-0.5">
                  {selectedEvent.request_id ?? "—"}
                </p>
              </div>
              <div>
                <p className="text-xs text-text-dim">Actor</p>
                <p className="text-text text-xs mt-0.5">{selectedEvent.actor ?? "—"}</p>
              </div>
              <div>
                <p className="text-xs text-text-dim">Timestamp</p>
                <p className="text-text text-xs mt-0.5">
                  {formatDate(selectedEvent.created_at)}
                </p>
              </div>
            </div>
            {selectedEvent.detail && (
              <div className="mt-4">
                <p className="text-xs text-text-dim mb-1.5">Detail</p>
                <pre className="text-xs text-text-muted mono bg-bg-base border border-border rounded-lg p-3 whitespace-pre-wrap overflow-auto max-h-48">
                  {(() => {
                    try {
                      return JSON.stringify(JSON.parse(selectedEvent.detail!), null, 2);
                    } catch {
                      return selectedEvent.detail;
                    }
                  })()}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
