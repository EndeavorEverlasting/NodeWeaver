"""
Root-level pytest configuration.

This file is loaded by pytest BEFORE any test module or sub-conftest is
imported.  We use it to:

  1. Set test environment variables (SQLite, dummy session secret).
  2. Inject lightweight mock objects into sys.modules so that the heavy ML
     services (sentence-transformers, audio processors, etc.) are never
     actually imported and no real database connection is attempted.

Any fixture shared across multiple test files belongs in tests/conftest.py.
"""

import os
import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. Environment – must happen before any project module is imported
# ---------------------------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SESSION_SECRET", "pytest-secret-key")
# Ensure no accidental API-key or webhook leaks from the real environment
os.environ.pop("NODEWEAVER_API_KEY", None)
os.environ.pop("AXTASK_WEBHOOK_URL", None)

# ---------------------------------------------------------------------------
# 2. Mock sys.modules for services that load ML models or require a GPU
# ---------------------------------------------------------------------------

_mock_rag_instance = MagicMock()
_mock_rag_instance.embedding_service = None   # health check: "embedding_model" → "ready"
_mock_rag_instance.detect_emerging_topics.return_value = []

_mock_rag_module = MagicMock()
_mock_rag_module.SimpleRAGEngine.return_value = _mock_rag_instance
sys.modules.setdefault("services.rag_engine_simple", _mock_rag_module)

_mock_pipeline_instance = MagicMock()
_mock_pipeline_module = MagicMock()
_mock_pipeline_module.ClassificationPipeline.return_value = _mock_pipeline_instance
sys.modules.setdefault("services.classification_pipeline", _mock_pipeline_module)

_mock_audio_module = MagicMock()
sys.modules.setdefault("services.audio_processor_simple", _mock_audio_module)

# Expose the shared mock instances so test fixtures can configure them
_MOCK_RAG_INSTANCE = _mock_rag_instance
_MOCK_PIPELINE_INSTANCE = _mock_pipeline_instance
