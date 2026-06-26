"use client";

import { useState, useEffect } from "react";
import { useAllHitl, useRespondHitl } from "@/hooks/useHitl";
import { useAppStore } from "@/store";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Modal from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Input";
import Header from "@/components/layout/Header";
import { SkeletonRow } from "@/components/ui/Skeleton";
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Clock,
  Eye,
  RefreshCw,
  Pencil,
  Mail,
} from "lucide-react";
import { formatDate, formatRelative } from "@/lib/utils";
import toast from "react-hot-toast";
import type { HitlRequest } from "@/types";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, "warning" | "success" | "danger" | "accent" | "dim"> = {
    pending: "warning",
    approved: "success",
    rejected: "danger",
    edited: "accent",
    timed_out: "dim",
  };
  return (
    <Badge variant={map[status] ?? "default"} dot size="sm">
      {status.replace("_", " ")}
    </Badge>
  );
}

function parsePayload(raw: string): Record<string, unknown> | null {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

// ─── Inspect modal with editing ───────────────────────────────────────────────

function InspectModal({
  item,
  onClose,
  resolvedBy,
}: {
  item: HitlRequest;
  onClose: () => void;
  resolvedBy: string;
}) {
  const { mutate: respond, isPending } = useRespondHitl();
  const payload = parsePayload(item.payload);
  const isEmail = item.action_type === "email_send";
  const draft = isEmail ? (payload?.draft as Record<string, unknown> | undefined) : undefined;

  // Editing state
  const [editing, setEditing] = useState(false);
  const [editedSubject, setEditedSubject] = useState((draft?.subject as string) ?? "");
  const [editedBody, setEditedBody] = useState((draft?.body_html as string) ?? "");

  useEffect(() => {
    setEditedSubject((draft?.subject as string) ?? "");
    setEditedBody((draft?.body_html as string) ?? "");
    setEditing(false);
  }, [item.request_id]);

  const hasEdits =
    editing &&
    (editedSubject !== (draft?.subject ?? "") || editedBody !== (draft?.body_html ?? ""));

  const respondWith = (status: "approved" | "rejected" | "edited") => {
    const editedPayload =
      status === "edited" && payload
        ? { ...payload, draft: { ...(payload.draft as object), subject: editedSubject, body_html: editedBody } }
        : undefined;

    respond(
      { request_id: item.request_id, status, resolved_by: resolvedBy, edited_payload: editedPayload },
      {
        onSuccess: () => {
          toast.success(status === "rejected" ? "Rejected" : status === "edited" ? "Approved with edits" : "Approved");
          onClose();
        },
        onError: (e) => toast.error(e.message),
      }
    );
  };

  const isPending_ = item.status === "pending";

  return (
    <Modal open onClose={onClose} title={`${item.action_type}`} size="lg">
      <div className="space-y-4">
        {/* Meta */}
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-xs text-text-dim">Request ID</p>
            <p className="mono text-xs text-text mt-0.5 break-all">{item.request_id}</p>
          </div>
          <div>
            <p className="text-xs text-text-dim">Status</p>
            <div className="mt-0.5"><StatusBadge status={item.status} /></div>
          </div>
          <div>
            <p className="text-xs text-text-dim">Requested</p>
            <p className="text-xs text-text mt-0.5">{formatDate(item.requested_at)}</p>
          </div>
          <div>
            <p className="text-xs text-text-dim">Resolved by</p>
            <p className="text-xs text-text mt-0.5">{item.resolved_by ?? "—"}</p>
          </div>
        </div>

        {/* Email draft editor (email_send actions) */}
        {isEmail && draft && (
          <div className="rounded-xl border border-border bg-bg-base p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-accent" />
                <span className="text-sm font-semibold text-text">Email draft</span>
              </div>
              {isPending_ && (
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Pencil className="w-3.5 h-3.5" />}
                  onClick={() => setEditing(!editing)}
                >
                  {editing ? "Cancel edit" : "Edit before approving"}
                </Button>
              )}
            </div>

            <div>
              <p className="text-xs text-text-dim mb-1">To</p>
              <div className="flex flex-wrap gap-1">
                {((draft.recipients as string[]) ?? []).map((r) => (
                  <span key={r} className="text-xs mono px-2 py-0.5 rounded-full bg-bg-elevated border border-border text-text-muted">
                    {r}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs text-text-dim mb-1">Subject</p>
              {editing ? (
                <input
                  className="w-full h-8 px-3 text-sm rounded-lg border bg-bg-elevated border-border text-text focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30"
                  value={editedSubject}
                  onChange={(e) => setEditedSubject(e.target.value)}
                />
              ) : (
                <p className="text-sm text-text">{draft.subject as string}</p>
              )}
            </div>

            <div>
              <p className="text-xs text-text-dim mb-1">Body</p>
              {editing ? (
                <Textarea
                  value={editedBody}
                  onChange={(e) => setEditedBody(e.target.value)}
                  rows={8}
                  className="mono text-xs"
                />
              ) : (
                <pre className="text-xs text-text-muted mono bg-bg-elevated border border-border rounded-lg p-3 whitespace-pre-wrap overflow-auto max-h-48">
                  {draft.body_html as string}
                </pre>
              )}
            </div>
          </div>
        )}

        {/* Raw payload for non-email actions */}
        {!isEmail && (
          <div>
            <p className="text-xs text-text-dim mb-1.5">Payload</p>
            <pre className="text-xs text-text-muted mono overflow-auto max-h-64 whitespace-pre-wrap bg-bg-base rounded-lg p-3 border border-border">
              {payload ? JSON.stringify(payload, null, 2) : item.payload}
            </pre>
          </div>
        )}

        {/* Action buttons */}
        {isPending_ && (
          <div className="flex gap-2 justify-end pt-2 border-t border-border">
            <Button
              variant="danger"
              size="sm"
              icon={<XCircle className="w-3.5 h-3.5" />}
              loading={isPending}
              onClick={() => respondWith("rejected")}
            >
              Reject
            </Button>
            {hasEdits ? (
              <Button
                variant="accent"
                size="sm"
                icon={<Pencil className="w-3.5 h-3.5" />}
                loading={isPending}
                onClick={() => respondWith("edited")}
              >
                Approve with edits
              </Button>
            ) : (
              <Button
                variant="success"
                size="sm"
                icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                loading={isPending}
                onClick={() => respondWith("approved")}
              >
                Approve
              </Button>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}

// ─── Row ─────────────────────────────────────────────────────────────────────

function RequestRow({
  item,
  onInspect,
  onApprove,
  onReject,
}: {
  item: HitlRequest;
  onInspect: (item: HitlRequest) => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}) {
  const isPending = item.status === "pending";

  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border/50 last:border-0 hover:bg-bg-elevated/50 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-sm font-medium text-text">{item.action_type}</p>
          <StatusBadge status={item.status} />
        </div>
        <div className="flex items-center gap-3 mt-0.5">
          <p className="text-xs text-text-dim mono truncate max-w-[160px]">{item.request_id}</p>
          <span className="text-xs text-text-dim flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatRelative(item.requested_at)}
          </span>
          {item.resolved_by && (
            <span className="text-xs text-text-dim">by {item.resolved_by}</span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-1.5 shrink-0">
        <Button variant="ghost" size="sm" icon={<Eye className="w-3.5 h-3.5" />} onClick={() => onInspect(item)}>
          Inspect
        </Button>
        {isPending && (
          <>
            <Button variant="success" size="sm" icon={<CheckCircle2 className="w-3.5 h-3.5" />} onClick={() => onApprove(item.request_id)}>
              Approve
            </Button>
            <Button variant="danger" size="sm" icon={<XCircle className="w-3.5 h-3.5" />} onClick={() => onReject(item.request_id)}>
              Reject
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HitlPage() {
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [inspecting, setInspecting] = useState<HitlRequest | null>(null);
  const resolvedBy = useAppStore((s) => s.resolvedBy);

  const { data, isLoading, refetch } = useAllHitl(100);
  const { mutate: respond } = useRespondHitl();

  const items = data?.items ?? [];
  const filtered = filterStatus === "all" ? items : items.filter((i) => i.status === filterStatus);
  const pendingCount = items.filter((i) => i.status === "pending").length;

  const quickApprove = (requestId: string) =>
    respond(
      { request_id: requestId, status: "approved", resolved_by: resolvedBy },
      { onSuccess: () => toast.success("Approved"), onError: (e) => toast.error(e.message) }
    );

  const quickReject = (requestId: string) =>
    respond(
      { request_id: requestId, status: "rejected", resolved_by: resolvedBy },
      { onSuccess: () => toast.success("Rejected"), onError: (e) => toast.error(e.message) }
    );

  const statusTabs = ["all", "pending", "approved", "rejected", "edited", "timed_out"];

  return (
    <div className="animate-fade-in">
      <Header
        title="HITL Panel"
        subtitle="Human-in-the-loop approval queue"
        actions={
          <Button variant="ghost" size="sm" icon={<RefreshCw className="w-3.5 h-3.5" />} onClick={() => refetch()}>
            Refresh
          </Button>
        }
      />

      <div className="px-8 py-6 max-w-5xl space-y-4">
        {/* Summary */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-warning-muted border border-warning/30">
            <ShieldCheck className="w-4 h-4 text-warning-light" />
            <span className="text-sm font-semibold text-warning-light">{pendingCount} pending</span>
          </div>
          <p className="text-sm text-text-muted">{items.length} total requests</p>
          {pendingCount > 0 && (
            <p className="text-xs text-text-dim">
              Click <strong>Inspect</strong> to view and optionally edit the payload before approving
            </p>
          )}
        </div>

        {/* Filter tabs */}
        <div className="flex items-center gap-1 p-1 bg-bg-elevated border border-border rounded-xl w-fit flex-wrap">
          {statusTabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setFilterStatus(tab)}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors capitalize ${
                filterStatus === tab
                  ? "bg-bg-overlay text-text font-medium"
                  : "text-text-muted hover:text-text"
              }`}
            >
              {tab.replace("_", " ")}
              {tab === "pending" && pendingCount > 0 && (
                <span className="ml-1.5 min-w-[16px] h-4 rounded-full bg-warning text-bg-base text-[10px] font-bold inline-flex items-center justify-center px-1">
                  {pendingCount}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* List */}
        <Card>
          {isLoading ? (
            <div className="divide-y divide-border/50">
              {Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} />)}
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12">
              <CheckCircle2 className="w-10 h-10 text-success mx-auto mb-3" />
              <p className="text-sm text-text-muted">No requests in this filter</p>
            </div>
          ) : (
            <div>
              {filtered.map((item) => (
                <RequestRow
                  key={item.request_id}
                  item={item}
                  onInspect={setInspecting}
                  onApprove={quickApprove}
                  onReject={quickReject}
                />
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Inspect / edit modal */}
      {inspecting && (
        <InspectModal
          item={inspecting}
          resolvedBy={resolvedBy}
          onClose={() => setInspecting(null)}
        />
      )}
    </div>
  );
}
