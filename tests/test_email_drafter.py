from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.graph.nodes.email_drafter import email_drafter_node


@pytest.mark.asyncio
@patch("app.graph.nodes.email_drafter.llm")
async def test_drafts_both_email_variants(mock_llm, sample_meeting_state):
    participant_response = AsyncMock()
    participant_response.content = json.dumps({
        "subject": "Meeting Recap: Q3 Planning",
        "body_html": "<html><body><h1>Meeting Recap</h1><p>Notes here</p></body></html>",
    })

    stakeholder_response = AsyncMock()
    stakeholder_response.content = json.dumps({
        "subject": "Meeting Brief: Q3 Planning",
        "body_html": "<html><body><h1>Executive Summary</h1><p>Decisions here</p></body></html>",
    })

    mock_llm.ainvoke = AsyncMock(side_effect=[participant_response, stakeholder_response])

    result = await email_drafter_node(sample_meeting_state)

    assert len(result["email_drafts"]) == 2
    variants = {d.variant for d in result["email_drafts"]}
    assert variants == {"participant", "stakeholder"}


@pytest.mark.asyncio
@patch("app.graph.nodes.email_drafter.llm")
async def test_handles_llm_json_error(mock_llm, sample_meeting_state):
    bad_response = AsyncMock()
    bad_response.content = "This is not valid JSON but a nice email body"

    mock_llm.ainvoke = AsyncMock(return_value=bad_response)

    result = await email_drafter_node(sample_meeting_state)

    assert len(result["email_drafts"]) == 2
    assert "test_mtg" in result["email_drafts"][0].subject
