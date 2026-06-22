from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("app.services.redis_queue.get_redis") as mock_redis, \
         patch("app.services.redis_queue.ensure_stream_group", new_callable=AsyncMock), \
         patch("app.api.routes_meeting.live_graph") as mock_live_graph, \
         patch("app.api.routes_meeting.post_meeting_graph") as mock_post_graph, \
         patch("app.services.redis_queue.store_meeting_state", new_callable=AsyncMock), \
         patch("app.services.redis_queue.get_meeting_state", new_callable=AsyncMock):

        mock_r = AsyncMock()
        mock_r.ping = AsyncMock()
        mock_redis.return_value = mock_r

        mock_live_graph.ainvoke = AsyncMock(return_value={
            "meeting_id": "test_mtg",
            "chunks": [],
            "classified": [],
            "notes": [],
            "decisions": [],
            "tasks": [],
            "research": [],
            "email_drafts": [],
            "pending_approvals": [],
            "is_meeting_active": True,
            "error_log": [],
        })

        mock_post_graph.ainvoke = AsyncMock(return_value={
            "meeting_id": "test_mtg",
            "chunks": [],
            "classified": [],
            "notes": [],
            "decisions": [],
            "tasks": [],
            "research": [],
            "email_drafts": [],
            "pending_approvals": [],
            "is_meeting_active": False,
            "error_log": [],
        })

        from app.main import app
        yield TestClient(app)


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["name"] == "AI Meeting System"


def test_start_meeting(client):
    resp = client.post("/meeting/start", json={
        "meeting_id": "e2e_test",
        "title": "E2E Test Meeting",
        "participants": ["alice@example.com"],
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "started"


def test_start_duplicate_meeting(client):
    client.post("/meeting/start", json={"meeting_id": "dup_test"})
    resp = client.post("/meeting/start", json={"meeting_id": "dup_test"})
    assert resp.status_code == 400


def test_process_chunk(client):
    client.post("/meeting/start", json={"meeting_id": "chunk_test"})

    resp = client.post("/meeting/chunk", json={
        "meeting_id": "chunk_test",
        "speaker": "Sarah",
        "text": "Let's move the deadline to September",
        "timestamp_start": "00:12:34",
        "timestamp_end": "00:12:51",
        "minute": 12,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"


def test_chunk_without_meeting(client):
    resp = client.post("/meeting/chunk", json={
        "meeting_id": "nonexistent",
        "speaker": "X",
        "text": "test",
        "timestamp_start": "00:00:00",
        "timestamp_end": "00:00:05",
        "minute": 0,
    })
    assert resp.status_code == 404


def test_meeting_status(client):
    client.post("/meeting/start", json={"meeting_id": "status_test"})

    resp = client.get("/meeting/status_test/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_end_meeting(client):
    client.post("/meeting/start", json={"meeting_id": "end_test"})

    resp = client.post("/meeting/end_test/end")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ended"
