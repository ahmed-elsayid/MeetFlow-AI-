from enum import Enum


class ChunkClassification(str, Enum):
    DECISION = "decision"
    TASK_COMMITMENT = "task_commitment"
    RESEARCH_TRIGGER = "research_trigger"
    DISCUSSION = "discussion"
    OFF_TOPIC = "off_topic"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    TIMED_OUT = "timed_out"
