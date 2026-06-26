import type { CSSProperties } from "react";
import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
  lines?: number;
  style?: CSSProperties;
}

export default function Skeleton({ className, style }: SkeletonProps) {
  return (
    <div
      className={cn("bg-bg-elevated animate-pulse rounded-md", className)}
      style={style}
    />
  );
}

export function SkeletonCard({ lines = 3 }: SkeletonProps) {
  return (
    <div className="rounded-xl border border-border bg-bg-surface p-5 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className="h-3" style={{ width: `${70 + i * 10}%` } as React.CSSProperties} />
      ))}
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 p-3">
      <Skeleton className="h-8 w-8 rounded-full" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3 w-1/3" />
        <Skeleton className="h-2.5 w-1/2" />
      </div>
      <Skeleton className="h-6 w-16 rounded-full" />
    </div>
  );
}
