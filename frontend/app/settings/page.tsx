"use client";

import { useState } from "react";
import { useAppStore } from "@/store";
import Card, { CardBody, CardHeader } from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Badge from "@/components/ui/Badge";
import Header from "@/components/layout/Header";
import { Settings, User, Server, CheckCircle2, Info } from "lucide-react";
import toast from "react-hot-toast";

export default function SettingsPage() {
  const { apiUrl, setApiUrl, resolvedBy, setResolvedBy } = useAppStore();
  const [apiUrlDraft, setApiUrlDraft] = useState(apiUrl);
  const [resolvedByDraft, setResolvedByDraft] = useState(resolvedBy);

  const saveApiUrl = () => {
    const trimmed = apiUrlDraft.trim().replace(/\/$/, "");
    setApiUrl(trimmed);
    toast.success("API URL saved");
  };

  const saveIdentity = () => {
    const trimmed = resolvedByDraft.trim();
    if (!trimmed) {
      toast.error("Identity cannot be empty");
      return;
    }
    setResolvedBy(trimmed);
    toast.success("Identity saved");
  };

  return (
    <div className="animate-fade-in">
      <Header title="Settings" subtitle="Connection and identity configuration" />

      <div className="px-8 py-6 max-w-2xl space-y-4">
        {/* API Connection */}
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-text flex items-center gap-2">
              <Server className="w-4 h-4 text-accent" />
              Backend API
            </h2>
          </CardHeader>
          <CardBody className="space-y-3">
            <Input
              label="API base URL"
              placeholder="http://localhost:8000"
              value={apiUrlDraft}
              onChange={(e) => setApiUrlDraft(e.target.value)}
              hint="Base URL of the FastAPI backend — no trailing slash"
            />
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                onClick={saveApiUrl}
                disabled={apiUrlDraft.trim() === apiUrl}
              >
                Save
              </Button>
              <span className="text-xs text-text-dim">
                Current: <span className="mono">{apiUrl}</span>
              </span>
            </div>
          </CardBody>
        </Card>

        {/* Identity */}
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-text flex items-center gap-2">
              <User className="w-4 h-4 text-primary-light" />
              Reviewer Identity
            </h2>
          </CardHeader>
          <CardBody className="space-y-3">
            <Input
              label="Resolved by"
              placeholder="alice@company.com"
              value={resolvedByDraft}
              onChange={(e) => setResolvedByDraft(e.target.value)}
              hint="Your name or email — recorded on HITL approvals and rejections"
            />
            <Button
              variant="primary"
              size="sm"
              icon={<CheckCircle2 className="w-3.5 h-3.5" />}
              onClick={saveIdentity}
              disabled={resolvedByDraft.trim() === resolvedBy || !resolvedByDraft.trim()}
            >
              Save
            </Button>
          </CardBody>
        </Card>

        {/* About */}
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-text flex items-center gap-2">
              <Info className="w-4 h-4 text-text-muted" />
              About MeetFlow AI
            </h2>
          </CardHeader>
          <CardBody>
            <div className="space-y-3 text-sm text-text-muted">
              <div className="flex items-center justify-between">
                <span>Frontend</span>
                <Badge variant="accent" size="sm">Next.js 15 · React 19</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span>State</span>
                <Badge variant="default" size="sm">Zustand v5 · TanStack Query v5</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span>Backend</span>
                <Badge variant="primary" size="sm">FastAPI · LangGraph · Azure OpenAI</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span>Vector DB</span>
                <Badge variant="success" size="sm">ChromaDB · text-embedding-3-small</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span>HITL persistence</span>
                <Badge variant="warning" size="sm">SQLite · Redis Streams</Badge>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
