from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from app.models.schemas import (
    ApprovalRequest,
    ClassifiedChunk,
    EmailDraft,
    ExtractedTask,
    NoteSection,
    ResearchBrief,
    TranscriptChunk,
)


class MeetingState(TypedDict):
    meeting_id: str
    chunks: Annotated[list[TranscriptChunk], add]
    classified: Annotated[list[ClassifiedChunk], add]
    notes: Annotated[list[NoteSection], add]
    decisions: Annotated[list[str], add]
    tasks: Annotated[list[ExtractedTask], add]
    research: Annotated[list[ResearchBrief], add]
    email_drafts: Annotated[list[EmailDraft], add]
    pending_approvals: Annotated[list[ApprovalRequest], add]
    is_meeting_active: bool
    error_log: Annotated[list[str], add]
