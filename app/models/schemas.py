from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .enums import ApprovalStatus


class TranscriptChunk(BaseModel):
    meeting_id: str
    speaker: str
    text: str
    timestamp_start: str
    timestamp_end: str
    minute: int
    topic_cluster: Optional[str] = None
    source_type: str = "live_transcript"


class ClassifiedChunk(BaseModel):
    chunk: TranscriptChunk
    classification: str
    confidence: float


class ExtractedTask(BaseModel):
    assignee: str
    task_description: str
    deadline: Optional[str] = None
    priority: str = "medium"
    is_ambiguous: bool = False
    jira_ticket_url: Optional[str] = None


class NoteSection(BaseModel):
    topic: str
    points: list[str]
    is_decision: bool = False


class StructuredNotes(BaseModel):
    meeting_id: str
    sections: list[NoteSection]
    decisions: list[str]


class ResearchBrief(BaseModel):
    query: str
    summary: str
    sources: list[str]
    from_rag: bool


class EmailDraft(BaseModel):
    variant: str
    subject: str
    body_html: str
    recipients: list[str]


class ApprovalRequest(BaseModel):
    request_id: str
    action_type: str
    payload: dict
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None


class MeetingSummary(BaseModel):
    meeting_id: str
    notes: StructuredNotes
    tasks: list[ExtractedTask]
    research: list[ResearchBrief]
    participant_email: Optional[EmailDraft] = None
    stakeholder_email: Optional[EmailDraft] = None


class MeetingStartRequest(BaseModel):
    meeting_id: str
    title: str = ""
    participants: list[str] = Field(default_factory=list)


class EndMeetingRequest(BaseModel):
    recipient_emails: list[str] = Field(default_factory=list)
    stakeholder_emails: list[str] = Field(default_factory=list)


class ChunkInput(BaseModel):
    meeting_id: str
    speaker: str
    text: str
    timestamp_start: str
    timestamp_end: str
    minute: int


class RAGQueryRequest(BaseModel):
    question: str
    meeting_id: Optional[str] = None
    speaker: Optional[str] = None
    minute: Optional[int] = None


class RAGUploadRequest(BaseModel):
    meeting_id: str
    text: str
    source_name: str


class ApprovalResponse(BaseModel):
    request_id: str
    status: ApprovalStatus
    edited_payload: Optional[dict] = None
    resolved_by: str = "unknown"
