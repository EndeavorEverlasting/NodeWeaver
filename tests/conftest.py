"""
Test fixtures for NodeWeaver ↔ AxTask integration tests.

The root conftest.py has already set up sys.modules mocks and cleared
NODEWEAVER_API_KEY / AXTASK_WEBHOOK_URL before any project code runs.
"""

import os
import pytest
from unittest.mock import MagicMock, patch


def _build_app(extra_env=None):
    """
    Create a fresh Flask application for testing.

    `extra_env` is an optional dict of env-var overrides applied before
    create_app() so that middleware closures (e.g. api_key capture) pick
    them up correctly.
    """
    from app import create_app, db

    env_patch = extra_env or {}
    with patch.dict(os.environ, env_patch):
        with patch.object(db, "create_all"):
            app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="session")
def flask_app():
    """Session-scoped Flask app with no API key configured (open-access mode)."""
    return _build_app()


@pytest.fixture(scope="session")
def flask_app_with_key():
    """Session-scoped Flask app with NODEWEAVER_API_KEY='test-secret' configured."""
    return _build_app(extra_env={"NODEWEAVER_API_KEY": "test-secret"})


@pytest.fixture()
def client(flask_app):
    """Test client for the keyless app."""
    with flask_app.test_client() as c:
        yield c


@pytest.fixture()
def keyed_client(flask_app_with_key):
    """Test client for the API-key-protected app."""
    with flask_app_with_key.test_client() as c:
        yield c
