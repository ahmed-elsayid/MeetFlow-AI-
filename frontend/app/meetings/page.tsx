"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useStartMeeting, useDeleteMeeting, useUploadTranscript } from "@/hooks/useMeeting";
import { useStartBot } from "@/hooks/useBot";
import { useAppStore } from "@/store";
import Card, { CardBody } from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Modal from "@/components/ui/Modal";
import Header from "@/components/layout/Header";
import { Plus, Video, Bot, Users, Clock, ChevronRight, Link2, Trash2, Upload } from "lucide-react";
import { formatRelative } from "@/lib/utils";
import Link from "next/link";
import toast from "react-hot-toast";

function StartMeetingModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [meetingId, setMeetingId] = useState("");
  const [title, setTitle] = useState("");
  const [participantsRaw, setParticipantsRaw] = useState("");
  const [teamsUrl, setTeamsUrl] = useState("");
  const router = useRouter();
  const { mutate: startMeeting, isPending: startingMeeting } = useStartMeeting();
  const { mutate: startBot, isPending: startingBot } = useStartBot();

  const isPending = startingMeeting || startingBot;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!meetingId.trim()) return;

    const participants = participantsRaw
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);

    startMeeting(
      { meeting_id: meetingId.trim(), title: title.trim(), participants },
      {
        onSuccess: (data) => {
          const id = data.meeting_id;

          if (teamsUrl.trim()) {
            startBot(
              { meeting_id: id, teams_url: teamsUrl.trim() },
              {
                onSuccess: () => {
                  toast.success(`Meeting started — bot joining Teams`);
                  onClose();
                  router.push(`/meetings/${id}`);
                },
                onError: (err) => {
                  toast.error(`Meeting created but bot failed to start: ${err.message}`);
                  onClose();
                  router.push(`/meetings/${id}`);
                },
              }
            );
          } else {
            toast.success(`Meeting "${id}" started`);
            onClose();
            router.push(`/meetings/${id}`);
          }
        },
        onError: (err) => toast.error(err.message),
      }
    );
  };

  return (
    <Modal open={open} onClose={onClose} title="Start New Meeting" size="md">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Meeting ID *"
          placeholder="quarterly-review-q4"
          value={meetingId}
          onChange={(e) => setMeetingId(e.target.value)}
          hint="Unique identifier — no spaces"
          required
        />
        <Input
          label="Title"
          placeholder="Q4 Quarterly Review"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <Input
          label="Participants (emails, comma-separated)"
          placeholder="alice@co.com, bob@co.com"
          value={participantsRaw}
          onChange={(e) => setParticipantsRaw(e.target.value)}
        />

        {/* Teams link — key new field */}
        <div className="space-y-1.5 pt-1 border-t border-border">
          <div className="flex items-center gap-1.5 mb-1">
            <Bot className="w-3.5 h-3.5 text-primary-light" />
            <span className="text-xs font-semibold text-text">Bot (optional)</span>
          </div>
          <Input
            label="Teams meeting link"
            placeholder="https://teams.microsoft.com/l/meetup-join/..."
            value={teamsUrl}
            onChange={(e) => setTeamsUrl(e.target.value)}
            hint="Paste the link — the bot will join and start capturing captions automatically"
          />
          {teamsUrl && (
            <p className="text-xs text-primary-light flex items-center gap-1">
              <Link2 className="w-3 h-3" />
              Bot will join Teams and stream the transcript into the pipeline
            </p>
          )}
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={isPending}
            icon={teamsUrl ? <Bot className="w-4 h-4" /> : <Video className="w-4 h-4" />}
          >
            {teamsUrl ? "Start & join Teams" : "Start meeting"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function UploadTranscriptModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [meetingId, setMeetingId] = useState("");
  const [title, setTitle] = useState("");
  const [recipientEmails, setRecipientEmails] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const router = useRouter();
  const { mutate: upload, isPending } = useUploadTranscript();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!meetingId.trim() || !file) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("meeting_id", meetingId.trim());
    formData.append("title", title.trim());
    formData.append("recipient_emails", recipientEmails.trim());

    upload(formData, {
      onSuccess: (data) => {
        toast.success(
          `Parsed ${data.chunks_parsed} lines — analysis running in background`
        );
        onClose();
        router.push(`/meetings/${data.meeting_id}`);
      },
      onError: (err: Error) => toast.error(err.message),
    });
  };

  return (
    <Modal open={open} onClose={onClose} title="Upload Transcript File" size="md">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Meeting ID *"
          placeholder="project-kickoff-june"
          value={meetingId}
          onChange={(e) => setMeetingId(e.target.value)}
          hint="Unique identifier for this transcript"
          required
        />
        <Input
          label="Title"
          placeholder="Project Kickoff — June 2026"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <Input
          label="Recipient emails (comma-separated)"
          placeholder="alice@co.com, bob@co.com"
          value={recipientEmails}
          onChange={(e) => setRecipientEmails(e.target.value)}
          hint="Leave blank to skip email sending"
        />

        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-text-muted">
            Transcript file (.txt) *
          </label>
          <div className="relative flex items-center gap-3 px-3 py-2.5 rounded-lg border border-border bg-bg-elevated cursor-pointer hover:border-primary transition-colors">
            <Upload className="w-4 h-4 text-text-dim shrink-0" />
            <span className="text-sm text-text-dim truncate flex-1">
              {file ? file.name : "Click to choose a .txt file"}
            </span>
            <input
              type="file"
              accept=".txt,text/plain"
              className="absolute inset-0 opacity-0 cursor-pointer"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
            />
          </div>
          <p className="text-xs text-text-dim">
            Expected format per line:{" "}
            <span className="font-mono">[H:MM:SS] Speaker Name: text</span>
          </p>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={isPending}
            icon={<Upload className="w-4 h-4" />}
            disabled={!meetingId.trim() || !file}
          >
            Upload & process
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default function MeetingsPage() {
  const [showModal, setShowModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const activeMeetings = useAppStore((s) => s.activeMeetings);
  const { mutate: deleteMeeting, isPending: deleting } = useDeleteMeeting();

  return (
    <div className="animate-fade-in">
      <Header
        title="Meetings"
        subtitle={`${activeMeetings.length} meeting${activeMeetings.length !== 1 ? "s" : ""} tracked`}
        actions={
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              icon={<Upload className="w-4 h-4" />}
              onClick={() => setShowUploadModal(true)}
            >
              Upload transcript
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<Plus className="w-4 h-4" />}
              onClick={() => setShowModal(true)}
            >
              New meeting
            </Button>
          </div>
        }
      />

      <div className="px-8 py-6 max-w-4xl">
        {activeMeetings.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-16 h-16 rounded-2xl bg-primary-muted flex items-center justify-center mb-4">
              <Video className="w-7 h-7 text-primary-light" />
            </div>
            <h3 className="text-lg font-semibold text-text mb-2">No meetings yet</h3>
            <p className="text-sm text-text-muted max-w-sm mb-6">
              Start a meeting to begin real-time AI analysis, note-taking, and task extraction.
            </p>
            <Button
              variant="primary"
              icon={<Plus className="w-4 h-4" />}
              onClick={() => setShowModal(true)}
            >
              Start first meeting
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {activeMeetings.map((meeting) => (
              <div key={meeting.meeting_id} className="relative group">
                <Link href={`/meetings/${meeting.meeting_id}`}>
                  <Card hover className="p-0">
                    <div className="p-4 flex items-center gap-4">
                      <div className="w-10 h-10 rounded-xl bg-primary-muted flex items-center justify-center shrink-0">
                        <Video className="w-5 h-5 text-primary-light" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold text-text truncate">
                            {meeting.title || meeting.meeting_id}
                          </p>
                          <Badge
                            variant={
                              meeting.status?.status === "active" ? "success" :
                              meeting.status?.status === "ended" ? "dim" : "primary"
                            }
                            dot
                            size="sm"
                          >
                            {meeting.status?.status ?? "starting"}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-3 mt-1">
                          <span className="text-xs text-text-dim flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatRelative(meeting.started_at)}
                          </span>
                          <span className="text-xs text-text-dim flex items-center gap-1">
                            <Users className="w-3 h-3" />
                            {meeting.participants.length} participant{meeting.participants.length !== 1 ? "s" : ""}
                          </span>
                          {meeting.status && (
                            <>
                              <span className="text-xs text-text-dim">
                                {meeting.status.chunks_processed} chunks
                              </span>
                              <span className="text-xs text-text-dim">
                                {meeting.status.tasks_extracted} tasks
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-text-dim shrink-0" />
                    </div>
                  </Card>
                </Link>
                {/* Delete button — appears on hover */}
                <button
                  className="absolute top-3 right-10 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg hover:bg-danger/10 text-danger-light"
                  onClick={(e) => { e.preventDefault(); setConfirmDeleteId(meeting.meeting_id); }}
                  title="Delete meeting"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete confirmation modal — outside ternary so it always renders */}
      <Modal
        open={!!confirmDeleteId}
        onClose={() => setConfirmDeleteId(null)}
        title="Delete meeting?"
        size="sm"
      >
        <p className="text-sm text-text-muted mb-4">
          Removes all state, embeddings, and HITL records for{" "}
          <span className="font-mono text-text">{confirmDeleteId}</span>. Cannot be undone.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirmDeleteId(null)}>Cancel</Button>
          <Button
            variant="danger"
            loading={deleting}
            icon={<Trash2 className="w-4 h-4" />}
            onClick={() => {
              if (!confirmDeleteId) return;
              deleteMeeting(confirmDeleteId, {
                onSuccess: () => { toast.success("Meeting deleted"); setConfirmDeleteId(null); },
                onError: (e) => toast.error(e.message),
              });
            }}
          >
            Delete
          </Button>
        </div>
      </Modal>

      <StartMeetingModal open={showModal} onClose={() => setShowModal(false)} />
      <UploadTranscriptModal open={showUploadModal} onClose={() => setShowUploadModal(false)} />
    </div>
  );
}
