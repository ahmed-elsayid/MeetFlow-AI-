"use client";

import { useHealth } from "@/hooks/useHealth";
import { usePendingHitl } from "@/hooks/useHitl";
import { useAppStore } from "@/store";
import Card, { CardBody, CardHeader } from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Skeleton, { SkeletonCard } from "@/components/ui/Skeleton";
import Header from "@/components/layout/Header";
import Button from "@/components/ui/Button";
import {
  Activity,
  CheckCircle2,
  XCircle,
  Database,
  Wifi,
  Video,
  ShieldCheck,
  Clock,
  ArrowRight,
} from "lucide-react";
import { formatRelative } from "@/lib/utils";
import Link from "next/link";

function HealthIndicator({
  label,
  ok,
  icon: Icon,
}: {
  label: string;
  ok: boolean | undefined;
  icon: React.ElementType;
}) {
  return (
    <div className="flex items-center justify-between py-2.5">
      <div className="flex items-center gap-2.5 text-sm text-text-muted">
        <Icon className="w-4 h-4" />
        {label}
      </div>
      {ok === undefined ? (
        <Skeleton className="h-5 w-16 rounded-full" />
      ) : ok ? (
        <Badge variant="success" dot>Online</Badge>
      ) : (
        <Badge variant="danger" dot>Offline</Badge>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
  color = "primary",
}: {
  label: string;
  value: number | string;
  icon: React.ElementType;
  color?: string;
}) {
  const colorMap: Record<string, string> = {
    primary: "bg-primary-muted text-primary-light",
    success: "bg-success-muted text-success-light",
    warning: "bg-warning-muted text-warning-light",
    danger: "bg-danger-muted text-danger-light",
    accent: "bg-accent-muted text-accent",
  };
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-text-muted">{label}</p>
          <p className="text-2xl font-bold text-text mt-1">{value}</p>
        </div>
        <div className={`p-3 rounded-xl ${colorMap[color]}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: health, isLoading: healthLoading } = useHealth();
  const { data: hitlData } = usePendingHitl();
  const activeMeetings = useAppStore((s) => s.activeMeetings);

  return (
    <div className="animate-fade-in">
      <Header
        title="Dashboard"
        subtitle="System overview and real-time status"
      />

      <div className="px-8 py-6 space-y-6 max-w-6xl">
        {/* Stats row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Active Meetings"
            value={activeMeetings.filter((m) => m.status?.status === "active").length}
            icon={Video}
            color="primary"
          />
          <StatCard
            label="Pending Approvals"
            value={hitlData?.count ?? 0}
            icon={ShieldCheck}
            color={hitlData && hitlData.count > 0 ? "warning" : "success"}
          />
          <StatCard
            label="Tracked Meetings"
            value={activeMeetings.length}
            icon={Activity}
            color="accent"
          />
          <StatCard
            label="System Status"
            value={health?.status === "ok" ? "Healthy" : health ? "Degraded" : "—"}
            icon={health?.status === "ok" ? CheckCircle2 : XCircle}
            color={health?.status === "ok" ? "success" : "warning"}
          />
        </div>

        {/* Two-column */}
        <div className="grid lg:grid-cols-2 gap-4">
          {/* Health */}
          <Card>
            <CardHeader>
              <h2 className="text-sm font-semibold text-text">Service Health</h2>
            </CardHeader>
            <CardBody>
              {healthLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-8" />
                  <Skeleton className="h-8" />
                  <Skeleton className="h-8" />
                </div>
              ) : (
                <div className="divide-y divide-border/50">
                  <HealthIndicator label="FastAPI Backend" ok={!!health} icon={Wifi} />
                  <HealthIndicator label="Redis" ok={health?.redis} icon={Activity} />
                  <HealthIndicator label="ChromaDB" ok={health?.chromadb} icon={Database} />
                </div>
              )}
            </CardBody>
          </Card>

          {/* Pending HITL */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-text">Pending Approvals</h2>
                <Link href="/hitl">
                  <Button variant="ghost" size="sm" icon={<ArrowRight className="w-3.5 h-3.5" />}>
                    View all
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardBody className="space-y-2">
              {hitlData?.items.length === 0 ? (
                <div className="text-center py-6">
                  <CheckCircle2 className="w-8 h-8 text-success mx-auto mb-2" />
                  <p className="text-sm text-text-muted">No pending approvals</p>
                </div>
              ) : (
                hitlData?.items.slice(0, 4).map((item) => (
                  <div
                    key={item.request_id}
                    className="flex items-center justify-between p-2.5 rounded-lg bg-bg-elevated border border-border"
                  >
                    <div className="min-w-0">
                      <p className="text-sm text-text font-medium truncate">
                        {item.action_type}
                      </p>
                      <p className="text-xs text-text-dim flex items-center gap-1 mt-0.5">
                        <Clock className="w-3 h-3" />
                        {formatRelative(item.requested_at)}
                      </p>
                    </div>
                    <Badge variant="warning" dot>Pending</Badge>
                  </div>
                ))
              )}
            </CardBody>
          </Card>
        </div>

        {/* Recent meetings */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-text">Recent Meetings</h2>
              <Link href="/meetings">
                <Button variant="ghost" size="sm" icon={<ArrowRight className="w-3.5 h-3.5" />}>
                  All meetings
                </Button>
              </Link>
            </div>
          </CardHeader>
          <CardBody>
            {activeMeetings.length === 0 ? (
              <div className="text-center py-8">
                <Video className="w-10 h-10 text-text-dim mx-auto mb-3" />
                <p className="text-sm text-text-muted">No meetings tracked yet</p>
                <p className="text-xs text-text-dim mt-1">
                  Start a meeting to begin tracking
                </p>
                <Link href="/meetings" className="mt-4 inline-block">
                  <Button variant="primary" size="sm">Start a meeting</Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {activeMeetings.slice(0, 5).map((m) => (
                  <Link
                    key={m.meeting_id}
                    href={`/meetings/${m.meeting_id}`}
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-bg-elevated border border-transparent hover:border-border transition-all group"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-primary-muted flex items-center justify-center shrink-0">
                        <Video className="w-4 h-4 text-primary-light" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-text truncate">
                          {m.title || m.meeting_id}
                        </p>
                        <p className="text-xs text-text-dim">
                          {formatRelative(m.started_at)} · {m.participants.length} participant{m.participants.length !== 1 ? "s" : ""}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Badge
                        variant={
                          m.status?.status === "active" ? "success" :
                          m.status?.status === "ended" ? "dim" : "primary"
                        }
                        dot
                      >
                        {m.status?.status ?? "—"}
                      </Badge>
                      <ArrowRight className="w-3.5 h-3.5 text-text-dim opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
