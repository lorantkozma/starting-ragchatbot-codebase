"""Tests for the FastAPI HTTP layer.

These exercise an in-test app (see `conftest.test_app`) that mirrors
`backend/app.py` but skips the static-file mount and document ingestion,
both of which require paths that don't exist under pytest. The route bodies
under test are the same logic as production.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------


class TestQueryEndpoint:
    def test_returns_answer_sources_and_session_id(self, client, sample_query_answer, sample_sources):
        resp = client.post("/api/query", json={"query": "What is computer use?"})

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["answer"] == sample_query_answer
        assert body["sources"] == sample_sources
        assert body["session_id"] == "session_test_1"

    def test_creates_session_when_not_provided(self, client, mock_rag_system):
        client.post("/api/query", json={"query": "hello"})

        mock_rag_system.session_manager.create_session.assert_called_once()
        # The auto-created session id must be passed through to `query`.
        args, _ = mock_rag_system.query.call_args
        assert args[1] == "session_test_1"

    def test_reuses_provided_session_id(self, client, mock_rag_system):
        client.post("/api/query", json={"query": "hello", "session_id": "session_existing"})

        mock_rag_system.session_manager.create_session.assert_not_called()
        args, _ = mock_rag_system.query.call_args
        assert args == ("hello", "session_existing")

    def test_missing_query_returns_422(self, client):
        # `query` is required by the pydantic request model.
        resp = client.post("/api/query", json={})
        assert resp.status_code == 422

    def test_rag_exception_returns_500(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("vector store unreachable")

        resp = client.post("/api/query", json={"query": "anything"})

        assert resp.status_code == 500
        assert "vector store unreachable" in resp.json()["detail"]

    def test_empty_sources_serializes_as_empty_list(self, client, mock_rag_system, sample_query_answer):
        mock_rag_system.query.return_value = (sample_query_answer, [])

        body = client.post("/api/query", json={"query": "small talk"}).json()

        assert body["sources"] == []
        assert body["answer"] == sample_query_answer


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------


class TestCoursesEndpoint:
    def test_returns_total_and_titles(self, client, sample_course_titles):
        resp = client.get("/api/courses")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_courses"] == len(sample_course_titles)
        assert body["course_titles"] == sample_course_titles

    def test_empty_catalog(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }

        body = client.get("/api/courses").json()

        assert body == {"total_courses": 0, "course_titles": []}

    def test_analytics_exception_returns_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("chroma down")

        resp = client.get("/api/courses")

        assert resp.status_code == 500
        assert "chroma down" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


class TestRootEndpoint:
    def test_root_returns_ok(self, client):
        resp = client.get("/")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"


# ---------------------------------------------------------------------------
# Cross-cutting concerns
# ---------------------------------------------------------------------------


class TestContentTypeAndShape:
    @pytest.mark.parametrize("path", ["/api/courses", "/"])
    def test_get_endpoints_return_json(self, client, path):
        resp = client.get(path)
        assert resp.headers["content-type"].startswith("application/json")

    def test_query_post_returns_json(self, client):
        resp = client.post("/api/query", json={"query": "x"})
        assert resp.headers["content-type"].startswith("application/json")
