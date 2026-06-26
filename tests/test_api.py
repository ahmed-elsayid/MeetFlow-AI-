from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


def _make_live_result(meeting_id="test_mtg"):
    return {
        "meeting_id": meeting_id,
        "chunks": [],
        "classified": [],
        "notes": [],
        "decisions": [],
        "action_items": [],
        "tasks": [],
        "research": [],
        "email_drafts": [],
        "pending_approvals": [],
        "is_meeting_active": True,
        "recipient_emails": [],
        "stakeholder_emails": [],
        "error_log": [],
        "transcript": "",
    }


def _make_post_result(meeting_id="test_mtg"):
    return {**_make_live_result(meeting_id), "is_meeting_active": False}


def _client():
    """Return a context manager that yields a patched TestClient."""
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        with patch("app.services.redis_queue.get_redis") as mock_redis, \
             patch("app.services.redis_queue.ensure_stream_group", new_callable=AsyncMock), \
             patch("app.api.routes_meeting.live_graph") as mock_live_graph, \
             patch("app.api.routes_meeting.post_meeting_graph") as mock_post_graph, \
             patch("app.api.routes_meeting.get_rag_service") as mock_rag_svc, \
             patch("app.services.redis_queue.store_meeting_state", new_callable=AsyncMock), \
             patch("app.services.redis_queue.get_meeting_state", new_callable=AsyncMock):

            mock_r = AsyncMock()
            mock_r.ping = AsyncMock()
            mock_redis.return_value = mock_r

            mock_rag = MagicMock()
            mock_rag.embed_and_store = AsyncMock()
            mock_rag_svc.return_value = mock_rag

            mock_live_graph.ainvoke = AsyncMock(return_value=_make_live_result())
            mock_post_graph.ainvoke = AsyncMock(return_value=_make_post_result())

            from app.main import app
            from fastapi.testclient import TestClient
            with TestClient(app) as c:
                yield c

    return _ctx()


def test_root():
    with _client() as c:
        resp = c.get("/")
        assert resp.status_code == 200
        assert resp.json()["name"] == "AI Meeting System"


def test_start_meeting():
    with _client() as c:
        resp = c.post("/meeting/start", json={
            "meeting_id": "e2e_test",
            "title": "E2E Test Meeting",
            "participants": ["alice@example.com"],
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"


def test_start_duplicate_meeting():
    with _client() as c:
        c.post("/meeting/start", json={"meeting_id": "dup_test"})
        resp = c.post("/meeting/start", json={"meeting_id": "dup_test"})
        assert resp.status_code == 400


def test_process_chunk():
    with _client() as c:
        c.post("/meeting/start", json={"meeting_id": "chunk_test"})

        resp = c.post("/meeting/chunk", json={
            "meeting_id": "chunk_test",
            "speaker": "Sarah",
            "text": "Let's move the deadline to September",
            "timestamp_start": "00:12:34",
            "timestamp_end": "00:12:51",
            "minute": 12,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"


def test_chunk_without_meeting():
    with _client() as c:
        resp = c.post("/meeting/chunk", json={
            "meeting_id": "nonexistent",
            "speaker": "X",
            "text": "test",
            "timestamp_start": "00:00:00",
            "timestamp_end": "00:00:05",
            "minute": 0,
        })
        assert resp.status_code == 404


def test_meeting_status():
    with _client() as c:
        c.post("/meeting/start", json={"meeting_id": "status_test"})
        resp = c.get("/meeting/status_test/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"


def test_end_meeting():
    with _client() as c:
        c.post("/meeting/start", json={"meeting_id": "end_test"})
        resp = c.post("/meeting/end_test/end", json={
            "recipient_emails": ["alice@example.com"],
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ended"


def test_chunk_embedding_called():
    """embed_and_store must be called for each incoming chunk."""
    with _client() as c, \
         patch("app.api.routes_meeting.get_rag_service") as mock_rag_svc:

        mock_rag = MagicMock()
        mock_rag.embed_and_store = AsyncMock()
        mock_rag_svc.return_value = mock_rag

        c.post("/meeting/start", json={"meeting_id": "embed_test"})
        c.post("/meeting/chunk", json={
            "meeting_id": "embed_test",
            "speaker": "Alice",
            "text": "Some utterance",
            "timestamp_start": "00:01:00",
            "timestamp_end": "00:01:05",
            "minute": 1,
        })
        mock_rag.embed_and_store.assert_called_once()
