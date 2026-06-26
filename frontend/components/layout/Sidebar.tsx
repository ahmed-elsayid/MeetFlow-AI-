"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Video,
  ShieldCheck,
  ScrollText,
  Search,
  Settings,
  Zap,
  Circle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store";
import { useHealth } from "@/hooks/useHealth";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/meetings", label: "Meetings", icon: Video },
  { href: "/hitl", label: "HITL Panel", icon: ShieldCheck, badge: true },
  { href: "/search", label: "RAG Search", icon: Search },
  { href: "/audit", label: "Audit Log", icon: ScrollText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const pendingHitlCount = useAppStore((s) => s.pendingHitlCount);
  const health = useAppStore((s) => s.health);
  useHealth(); // keep health synced

  return (
    <aside className="w-60 shrink-0 flex flex-col bg-bg-surface border-r border-border h-screen sticky top-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shadow-lg shadow-primary/30">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-bold text-text leading-tight">MeetFlow</p>
            <p className="text-xs text-text-dim leading-tight">AI Assistant</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {nav.map(({ href, label, icon: Icon, badge }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150",
                active
                  ? "bg-primary-muted text-primary-light font-medium"
                  : "text-text-muted hover:text-text hover:bg-bg-elevated"
              )}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="flex-1">{label}</span>
              {badge && pendingHitlCount > 0 && (
                <span className="min-w-[18px] h-[18px] rounded-full bg-danger text-white text-[10px] font-bold flex items-center justify-center px-1">
                  {pendingHitlCount}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* System status */}
      <div className="px-4 py-4 border-t border-border">
        <div className="flex items-center gap-2 text-xs text-text-dim">
          <Circle
            className={cn(
              "w-2 h-2 fill-current",
              health?.status === "ok" ? "text-success" : "text-warning"
            )}
          />
          <span>
            {health
              ? health.status === "ok"
                ? "All systems normal"
                : "Degraded"
              : "Connecting…"}
          </span>
        </div>
      </div>
    </aside>
  );
}
