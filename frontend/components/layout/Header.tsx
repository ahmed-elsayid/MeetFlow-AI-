"use client";

import { RefreshCw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import Button from "@/components/ui/Button";

interface HeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export default function Header({ title, subtitle, actions }: HeaderProps) {
  const qc = useQueryClient();
  return (
    <header className="flex items-center justify-between px-8 py-5 border-b border-border bg-bg-base sticky top-0 z-10">
      <div>
        <h1 className="text-lg font-semibold text-text">{title}</h1>
        {subtitle && (
          <p className="text-sm text-text-muted mt-0.5">{subtitle}</p>
        )}
      </div>
      <div className="flex items-center gap-2">
        {actions}
        <Button
          variant="ghost"
          size="sm"
          icon={<RefreshCw className="w-3.5 h-3.5" />}
          onClick={() => qc.invalidateQueries()}
          title="Refresh all data"
        />
      </div>
    </header>
  );
}
