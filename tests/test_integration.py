"""
End-to-end tests confirming NodeWeaver ↔ AxTask integration contracts.

Covered scenarios (all run without a live database or ML service):

1. GET /api/v1/health  — returns the expected JSON shape
2. API key auth        — missing X-API-Key returns 401 when NODEWEAVER_API_KEY is set
3. CORS preflight      — OPTIONS request carries Access-Control-* headers
4. Webhook             — POST /api/v1/topics/detect fires the webhook when
                         AXTASK_WEBHOOK_URL is configured and fails gracefully
                         when the remote endpoint is unreachable
"""

import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _json(response):
    """Decode a Flask test-client response as JSON."""
    return json.loads(response.data)


# ---------------------------------------------------------------------------
# 1. Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """GET /api/v1/health must return the documented JSON shape."""

    def test_health_returns_200_or_503(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code in (200, 503)

    def test_health_json_shape(self, client):
        response = client.get("/api/v1/health")
        body = _json(response)

        assert "status" in body, "Missing 'status' field"
        assert body["status"] in ("healthy", "degraded"), (
            f"Unexpected status value: {body['status']!r}"
        )
        assert "service" in body, "Missing 'service' field"
        assert body["service"] == "nodeweaver", (
            f"Expected service='nodeweaver', got {body['service']!r}"
        )
        assert "version" in body, "Missing 'version' field"
        assert "api_version" in body, "Missing 'api_version' field"
        assert "components" in body, "Missing 'components' field"
        assert "database" in body["components"], "Missing components.database"
        assert "embedding_model" in body["components"], "Missing components.embedding_model"
        assert "timestamp" in body, "Missing 'timestamp' field"

    def test_health_no_auth_required(self, keyed_client):
        """Health must be reachable even when an API key is configured."""
        response = keyed_client.get("/api/v1/health")
        assert response.status_code in (200, 503), (
            "Health endpoint should not return 401 even with NODEWEAVER_API_KEY set"
        )

    def test_health_database_component_values(self, client):
        body = _json(client.get("/api/v1/health"))
        assert body["components"]["database"] in ("healthy", "unhealthy")
        assert body["components"]["embedding_model"] in ("ready", "unavailable")


# ---------------------------------------------------------------------------
# 2. API key authentication
# ---------------------------------------------------------------------------

class TestApiKeyAuth:
    """
    Requests to protected /api/v1/* routes (excluding /health) require the
    X-API-Key header when NODEWEAVER_API_KEY is set on the server.

    The `keyed_client` fixture creates a fresh Flask app built after
    NODEWEAVER_API_KEY='test-secret' is placed in the environment so the
    before_request closure captures the correct key value.
    """

    def test_missing_api_key_returns_401(self, keyed_client):
        """Omitting X-API-Key must yield HTTP 401."""
        response = keyed_client.post(
            "/api/v1/classify",
            json={"text": "schedule a meeting"},
        )
        assert response.status_code == 401, (
            f"Expected 401 without X-API-Key, got {response.status_code}"
        )
        body = _json(response)
        assert "error" in body, "401 response must contain an 'error' field"

    def test_missing_api_key_error_message(self, keyed_client):
        """The 401 body must describe the problem."""
        body = _json(
            keyed_client.post("/api/v1/classify", json={"text": "test"})
        )
        assert body.get("error") == "Unauthorized"

    def test_wrong_api_key_returns_401(self, keyed_client):
        """A wrong key must also yield 401."""
        response = keyed_client.post(
            "/api/v1/classify",
            json={"text": "hello"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401

    def test_correct_api_key_is_accepted(self, keyed_client, flask_app_with_key):
        """Supplying the correct X-API-Key must not produce a 401."""
        # Give the mocked pipeline a return value so the endpoint won't error
        pipeline = flask_app_with_key.extensions.get("classification_pipeline")
        if pipeline is not None:
            pipeline.classify.return_value = {
                "predicted_category": "work",
                "confidence_score": 0.9,
                "similar_topics": [],
                "similar_nodes": [],
            }

        with patch("api.classifier.db") as mock_db:
            mock_db.session.add = MagicMock()
            mock_db.session.commit = MagicMock()
            response = keyed_client.post(
                "/api/v1/classify",
                json={"text": "schedule a meeting"},
                headers={"X-API-Key": "test-secret"},
            )

        assert response.status_code != 401, (
            "A correct X-API-Key should not trigger a 401"
        )

    def test_health_exempt_from_auth(self, keyed_client):
        """/api/v1/health must return 200/503, never 401."""
        response = keyed_client.get("/api/v1/health")
        assert response.status_code != 401


# ---------------------------------------------------------------------------
# 3. CORS preflight
# ---------------------------------------------------------------------------

class TestCORSPreflight:
    """OPTIONS preflight requests must carry the required CORS response headers."""

    PREFLIGHT_HEADERS = {
        "Origin": "https://axtask.example.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "X-API-Key, Content-Type",
    }

    def test_options_returns_200(self, client):
        response = client.options("/api/v1/health", headers=self.PREFLIGHT_HEADERS)
        assert response.status_code == 200, (
            f"OPTIONS preflight should return 200, got {response.status_code}"
        )

    def test_cors_allow_origin_header_present(self, client):
        """Access-Control-Allow-Origin must be set on preflight responses."""
        response = client.options("/api/v1/health", headers=self.PREFLIGHT_HEADERS)
        assert "Access-Control-Allow-Origin" in response.headers, (
            "Missing Access-Control-Allow-Origin on OPTIONS response"
        )

    def test_cors_allow_methods_header_present(self, client):
        response = client.options("/api/v1/health", headers=self.PREFLIGHT_HEADERS)
        assert "Access-Control-Allow-Methods" in response.headers, (
            "Missing Access-Control-Allow-Methods on OPTIONS response"
        )

    def test_cors_allow_headers_contains_x_api_key(self, client):
        response = client.options("/api/v1/health", headers=self.PREFLIGHT_HEADERS)
        allow_headers = response.headers.get("Access-Control-Allow-Headers", "")
        assert "X-API-Key" in allow_headers, (
            f"X-API-Key must be listed in Access-Control-Allow-Headers, got: {allow_headers!r}"
        )

    def test_cors_wildcard_origin_when_default_config(self, client, flask_app):
        """With NODEWEAVER_ALLOWED_ORIGINS='*' (default) the header must be '*'."""
        if flask_app.config.get("ALLOWED_ORIGINS") == ["*"]:
            response = client.options("/api/v1/health", headers=self.PREFLIGHT_HEADERS)
            origin_header = response.headers.get("Access-Control-Allow-Origin", "")
            assert origin_header == "*", (
                f"Expected wildcard CORS origin, got {origin_header!r}"
            )

    def test_cors_headers_on_normal_requests(self, client):
        """after_request hook must add CORS headers to non-OPTIONS responses too."""
        response = client.get("/api/v1/health")
        assert "Access-Control-Allow-Origin" in response.headers, (
            "CORS headers missing on regular GET response"
        )

    def test_preflight_does_not_require_api_key(self, keyed_client):
        """OPTIONS preflight must be answered without auth even on protected routes."""
        response = keyed_client.options(
            "/api/v1/classify", headers=self.PREFLIGHT_HEADERS
        )
        assert response.status_code != 401, (
            "Preflight OPTIONS must not require X-API-Key"
        )


# ---------------------------------------------------------------------------
# 4. Webhook — tested via the /api/v1/topics/detect endpoint
# ---------------------------------------------------------------------------

class TestWebhook:
    """
    The /api/v1/topics/detect route calls _fire_webhook when topics are found.
    Tests confirm the webhook fires (with the right payload) and fails gracefully.
    """

    # Shared fixture helper: configure the mock rag_engine so detect_topics
    # returns at least one topic, which triggers _fire_webhook.
    _FAKE_TOPIC = {
        "topic_id": 1,
        "label": "Test Topic",
        "category": "work",
        "total_weight": 1.0,
        "coherence_score": 0.9,
        "origin_node_ids": [],
        "metadata": {},
        "created_at": None,
    }

    def _set_fake_topics(self, flask_app):
        rag = flask_app.extensions.get("rag_engine")
        if rag is not None:
            rag.detect_emerging_topics.return_value = [self._FAKE_TOPIC]

    def _reset_topics(self, flask_app):
        rag = flask_app.extensions.get("rag_engine")
        if rag is not None:
            rag.detect_emerging_topics.return_value = []

    def test_webhook_fires_on_topic_detection(self, client, flask_app):
        """POST /api/v1/topics/detect fires the webhook when topics emerge."""
        import urllib.request as _urlreq

        self._set_fake_topics(flask_app)
        posted = []

        def fake_urlopen(req, timeout=None):
            posted.append({
                "url": req.full_url,
                "method": req.method,
                "body": json.loads(req.data.decode()),
            })
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.status = 200
            return resp

        with patch.dict(os.environ, {"AXTASK_WEBHOOK_URL": "http://axtask.local/hook"}):
            with patch.object(_urlreq, "urlopen", side_effect=fake_urlopen):
                response = client.post("/api/v1/topics/detect")
                time.sleep(0.3)  # let the daemon thread deliver

        self._reset_topics(flask_app)

        assert response.status_code == 200
        assert len(posted) == 1, f"Expected 1 webhook POST, got {len(posted)}"
        call = posted[0]
        assert call["url"] == "http://axtask.local/hook"
        assert call["method"] == "POST"
        assert call["body"]["event"] == "topic_emergence"
        assert call["body"]["source"] == "nodeweaver"
        assert "data" in call["body"]

    def test_webhook_payload_structure(self, client, flask_app):
        """Webhook payload must carry event, source, and data keys."""
        import urllib.request as _urlreq

        self._set_fake_topics(flask_app)
        captured = []

        def capture(req, timeout=None):
            captured.append(json.loads(req.data.decode()))
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.status = 200
            return resp

        with patch.dict(os.environ, {"AXTASK_WEBHOOK_URL": "http://axtask.local/hook"}):
            with patch.object(_urlreq, "urlopen", side_effect=capture):
                client.post("/api/v1/topics/detect")
                time.sleep(0.3)

        self._reset_topics(flask_app)

        assert len(captured) == 1
        payload = captured[0]
        for key in ("event", "source", "data"):
            assert key in payload, f"Webhook payload missing '{key}' key"
        assert payload["source"] == "nodeweaver"

    def test_webhook_skipped_when_url_not_set(self, client, flask_app):
        """When AXTASK_WEBHOOK_URL is absent no HTTP request must be made."""
        import urllib.request as _urlreq

        self._set_fake_topics(flask_app)

        env_without = {
            k: v for k, v in os.environ.items() if k != "AXTASK_WEBHOOK_URL"
        }
        with patch.dict(os.environ, env_without, clear=True):
            with patch.object(_urlreq, "urlopen") as mock_urlopen:
                client.post("/api/v1/topics/detect")
                time.sleep(0.2)
                mock_urlopen.assert_not_called()

        self._reset_topics(flask_app)

    def test_webhook_fails_gracefully_on_network_error(self, client, flask_app):
        """A network failure must not propagate — NodeWeaver must stay healthy."""
        import urllib.error
        import urllib.request as _urlreq

        self._set_fake_topics(flask_app)

        def boom(req, timeout=None):
            raise urllib.error.URLError("connection refused")

        with patch.dict(os.environ, {"AXTASK_WEBHOOK_URL": "http://unreachable.example/hook"}):
            with patch.object(_urlreq, "urlopen", side_effect=boom):
                # The endpoint itself must still return 200
                try:
                    response = client.post("/api/v1/topics/detect")
                    time.sleep(0.3)
                except Exception as exc:
                    pytest.fail(f"topics/detect raised on webhook failure: {exc}")

        self._reset_topics(flask_app)

        assert response.status_code == 200, (
            "topics/detect must return 200 even when the webhook endpoint is down"
        )
