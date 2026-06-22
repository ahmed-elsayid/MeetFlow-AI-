from __future__ import annotations

import pytest

from app.models.enums import ChunkClassification
from app.models.schemas import (
    ClassifiedChunk,
    EmailDraft,
    ExtractedTask,
    NoteSection,
    ResearchBrief,
    TranscriptChunk,
)


@pytest.fixture
def sample_chunks() -> list[TranscriptChunk]:
    return [
        TranscriptChunk(
            meeting_id="test_mtg",
            speaker="Sarah",
            text="Let's move the Q3 deadline to September 15th",
            timestamp_start="00:12:34",
            timestamp_end="00:12:51",
            minute=12,
        ),
        TranscriptChunk(
            meeting_id="test_mtg",
            speaker="Mike",
            text="I'll take care of updating the roadmap document by Friday",
            timestamp_start="00:13:05",
            timestamp_end="00:13:18",
            minute=13,
        ),
        TranscriptChunk(
            meeting_id="test_mtg",
            speaker="Sarah",
            text="What's the latest on the Kubernetes migration costs?",
            timestamp_start="00:14:02",
            timestamp_end="00:14:11",
            minute=14,
        ),
        TranscriptChunk(
            meeting_id="test_mtg",
            speaker="Tom",
            text="Did anyone watch the game last night?",
            timestamp_start="00:15:00",
            timestamp_end="00:15:08",
            minute=15,
        ),
        TranscriptChunk(
            meeting_id="test_mtg",
            speaker="Lisa",
            text="We agreed to use React for the frontend migration",
            timestamp_start="00:16:00",
            timestamp_end="00:16:12",
            minute=16,
        ),
        TranscriptChunk(
            meeting_id="test_mtg",
            speaker="Mike",
            text="The performance benchmarks show a 40% improvement after the cache change",
            timestamp_start="00:17:00",
            timestamp_end="00:17:15",
            minute=17,
        ),
        TranscriptChunk(
            meeting_id="test_mtg",
            speaker="Sarah",
            text="Someone should look into the CI pipeline failures",
            timestamp_start="00:18:00",
            timestamp_end="00:18:10",
            minute=18,
        ),
        TranscriptChunk(
            meeting_id="test_mtg",
            speaker="Tom",
            text="Can you handle the database backup automation, Lisa?",
            timestamp_start="00:19:00",
            timestamp_end="00:19:12",
            minute=19,
        ),
    ]


@pytest.fixture
def classified_discussion() -> list[ClassifiedChunk]:
    chunk = TranscriptChunk(
        meeting_id="test_mtg",
        speaker="Mike",
        text="The performance benchmarks show a 40% improvement after the cache change",
        timestamp_start="00:17:00",
        timestamp_end="00:17:15",
        minute=17,
    )
    return [ClassifiedChunk(chunk=chunk, classification="discussion", confidence=0.9)]


@pytest.fixture
def classified_decision() -> list[ClassifiedChunk]:
    chunk = TranscriptChunk(
        meeting_id="test_mtg",
        speaker="Lisa",
        text="We agreed to use React for the frontend migration",
        timestamp_start="00:16:00",
        timestamp_end="00:16:12",
        minute=16,
    )
    return [ClassifiedChunk(chunk=chunk, classification="decision", confidence=0.95)]


@pytest.fixture
def classified_task() -> list[ClassifiedChunk]:
    chunk = TranscriptChunk(
        meeting_id="test_mtg",
        speaker="Mike",
        text="I'll take care of updating the roadmap document by Friday",
        timestamp_start="00:13:05",
        timestamp_end="00:13:18",
        minute=13,
    )
    return [ClassifiedChunk(chunk=chunk, classification="task_commitment", confidence=0.92)]


@pytest.fixture
def classified_ambiguous_task() -> list[ClassifiedChunk]:
    chunk = TranscriptChunk(
        meeting_id="test_mtg",
        speaker="Sarah",
        text="Someone should look into the CI pipeline failures",
        timestamp_start="00:18:00",
        timestamp_end="00:18:10",
        minute=18,
    )
    return [ClassifiedChunk(chunk=chunk, classification="task_commitment", confidence=0.85)]


@pytest.fixture
def classified_research() -> list[ClassifiedChunk]:
    chunk = TranscriptChunk(
        meeting_id="test_mtg",
        speaker="Sarah",
        text="What's the latest on the Kubernetes migration costs?",
        timestamp_start="00:14:02",
        timestamp_end="00:14:11",
        minute=14,
    )
    return [ClassifiedChunk(chunk=chunk, classification="research_trigger", confidence=0.88)]


@pytest.fixture
def sample_notes() -> list[NoteSection]:
    return [
        NoteSection(
            topic="Performance",
            points=["Mike reported 40% improvement from cache change"],
            is_decision=False,
        ),
        NoteSection(
            topic="Frontend Migration",
            points=["Team agreed to use React"],
            is_decision=True,
        ),
    ]


@pytest.fixture
def sample_tasks() -> list[ExtractedTask]:
    return [
        ExtractedTask(
            assignee="Mike",
            task_description="Update the roadmap document",
            deadline="2026-06-27",
            priority="medium",
        ),
        ExtractedTask(
            assignee="Lisa",
            task_description="Handle database backup automation",
            priority="medium",
        ),
    ]


@pytest.fixture
def sample_research() -> list[ResearchBrief]:
    return [
        ResearchBrief(
            query="What are the latest Kubernetes migration costs?",
            summary="Based on recent industry data, Kubernetes migration costs...",
            sources=["AWS pricing page", "CNCF survey 2025"],
            from_rag=False,
        ),
    ]


@pytest.fixture
def sample_meeting_state(
    sample_chunks, classified_discussion, sample_notes, sample_tasks, sample_research
):
    return {
        "meeting_id": "test_mtg",
        "chunks": sample_chunks,
        "classified": classified_discussion,
        "notes": sample_notes,
        "decisions": ["Use React for frontend migration"],
        "tasks": sample_tasks,
        "research": sample_research,
        "email_drafts": [],
        "pending_approvals": [],
        "is_meeting_active": False,
        "error_log": [],
    }
