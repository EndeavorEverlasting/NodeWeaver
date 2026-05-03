# NodeWeaver - RAG Classifier API

## Overview

NodeWeaver is an intelligent Retrieval-Augmented Generation (RAG) classifier API designed for automatic task categorization and real-time topic detection. The system leverages semantic embeddings and weighted node convergence to classify text into categories like personal, work, academic, political, legal, and others. Built with a focus on productivity automation, NodeWeaver integrates seamlessly with AxTask and Google Sheets to provide intelligent task organization capabilities.

**Version: 1.0.3 - Learning & Classification Enhancement** — NodeWeaver features sophisticated learning mechanisms with classification correction and training data integration. The system can learn from misclassifications and adapt to domain-specific terminology, with enhanced political/legal category detection for better government meeting classification.

**Live Audio Topic Detection** — NodeWeaver features real-time audio processing capabilities, perfect for analyzing debates, meetings, YouTube videos, and any audio content. Users can upload audio files or use live microphone input to get instant topic classification as the content plays.

The system implements a sophisticated architecture where topics emerge from weighted node convergence using clustering algorithms, allowing for dynamic discovery of new patterns and categories in text data. This approach enables the system to adapt and learn from usage patterns while maintaining high classification accuracy.

## Recent Changes

### Task #3 - ML Dependency Fix & Full RAG Engine (Latest)
✓ Fixed `pyproject.toml` — removed 1100+ line `[tool.uv.sources]` block that erroneously mapped `sentence-transformers` and hundreds of unrelated packages to the pytorch-cpu index (which doesn't host them), making `uv sync` unsolvable on Linux
✓ Clean `pyproject.toml` — kept only minimal `[[tool.uv.index]]` for pytorch-cpu with `torch` mapped to it for Linux (CPU-only, avoids multi-GB CUDA downloads); all other packages resolve from PyPI
✓ Installed `sentence-transformers`, `scikit-learn`, `numpy`, `librosa` and their transitive deps via `uv sync`; `uv.lock` updated (95 packages, version-pinned)
✓ `app.py` updated — tries `RAGEngine` (full, sentence-transformers) at startup, falls back to `SimpleRAGEngine` only if import fails
✓ `services/embeddings.py` — forward-compatible `get_embedding_dimension()` call (fixes FutureWarning from sentence-transformers API rename)
✓ App starts with full RAG Engine: `INFO:app:Full RAG Engine initialized with sentence-transformers embeddings`

### Version 1.0.3 - Learning & Classification Enhancement
✓ Added `/api/v1/correct` endpoint — correct any misclassification; system stores the feedback as a training example
✓ Added `/api/v1/train` endpoint — provide labeled examples to reinforce any category
✓ New dedicated `legal` category with specialized keywords (court, judge, attorney, ordinance, compliance…)
✓ Enhanced `political` keywords: city council, zoning, municipal, civic, public hearing, ordinance, regulation
✓ Legal and political categories now carry 0.85 base confidence vs. 0.7 for generic categories
✓ Real-world fix: "Attend city council meeting about zoning changes" → political (0.9), legal (0.85), work (0.8)
✓ Keyword extraction logs learned terms so future enhancements can make the vocabulary dynamic
✓ Comprehensive learning documentation in LEARNING_MECHANISMS.md
✓ Post-merge setup script created at scripts/post-merge.sh for automated dependency sync after task merges

### AxTask HTTP Integration (Task #1 merge)
✓ `/api/v1/health` — structured JSON health check (no auth required); designed for AxTask polling
✓ API key middleware — `X-API-Key` header enforced on all `/api/v1/*` except `/health`; skipped in dev when `NODEWEAVER_API_KEY` is unset
✓ Native CORS support — `OPTIONS` preflight handled before auth; origins configurable via `NODEWEAVER_ALLOWED_ORIGINS`
✓ AxTask webhook callback — background-thread `POST` to `AXTASK_WEBHOOK_URL` on topic emergence; 5-second timeout, never blocks
✓ TypeScript HTTP client — `integration/nodeweaver-client.ts` with typed methods, retry/backoff, AbortController timeout
✓ Docker Compose overlay — `integration/docker-compose.nodeweaver.yml` for running NodeWeaver alongside AxTask locally
✓ Integration docs — `integration/README.md` with architecture diagram, env var tables, wiring guide, auth contract, webhook payload spec

### Version 1.0.2 - Multi-Classification Enhancement
✓ Multi-label classification — entries can have multiple topics/categories with individual confidence scores
✓ Many-to-many business rule between entries and topics
✓ `all_categories` array in every classify response with per-category confidence
✓ Automatic topic associations based on similarity scoring
✓ "Find a cake for birthday party" → personal (0.85) + shopping (0.75)

### Earlier Releases
✓ 1.0.1 — Flask extensions compatibility fix, correct `app.extensions` pattern
✓ 1.0.0 — Initial production release with full RAG pipeline, audio processing, topic emergence, web UI

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Application Layer
- **Flask Application** (`app.py`): `create_app()` factory with CORS middleware, API key auth, blueprint registration
- **Gunicorn** (`main.py`): Production WSGI entry point on port 5000
- **Blueprint Architecture**: `api/classifier.py`, `api/topics.py`, `api/audio.py`

### Security & Networking
- **API Key Auth**: `NODEWEAVER_API_KEY` env var; `X-API-Key` request header; dev-mode bypass when unset
- **CORS**: Native (no flask-cors); origins from `NODEWEAVER_ALLOWED_ORIGINS` (comma-separated, default `*`)
- **OPTIONS preflight**: Handled before auth fires

### Database Design
- **PostgreSQL**: Primary database with JSONB and array support
- **pgvector**: Vector similarity search (extension available; simple fallback active by default)
- **Models**: `Node`, `Topic`, `Document`, `ClassificationLog`, `NodeRelationship`
- **Vector Embeddings**: 384-dimensional vectors (sentence-transformers when available)
- **Topic Emergence**: DBSCAN clustering on node embeddings

### Core Services
- **SimpleRAGEngine** (`services/rag_engine_simple.py`): Active classification engine; keyword-based multi-label classifier with learning methods
- **SimpleEmbeddingService** (`services/embeddings_simple.py`): Text-to-vector conversion (rule-based fallback)
- **SimpleAudioProcessor** (`services/audio_processor_simple.py`): Audio transcription + classification
- **Full RAG Engine** (`services/rag_engine.py`): Sentence-transformers engine (requires ML deps; currently in fallback mode)

### Learning System
- `correct_classification(text, correct_category)` — finds prior log entry, creates corrective training document
- `add_training_data(text, category)` — stores high-confidence (0.95) labeled document; extracts keyword associations
- `_update_category_keywords(text, category)` — logs significant terms for future vocabulary updates
- Training documents flagged with `is_training_data: true` in `meta_data` JSON column

### Classification Categories
`personal`, `work`, `academic`, `political`, `legal`, `health`, `finance`, `entertainment`, `travel`, `shopping`, `technology`, `other`

| Category | Base Confidence | Notes |
|---|---|---|
| political | 0.85 | Municipal keywords: city council, zoning, ordinance, civic, municipal |
| legal | 0.85 | Court, judge, attorney, compliance, statute, jurisdiction |
| work | 0.9 | Meeting, project, deadline, office, colleague |
| personal, health, finance | 0.8 | Standard confidence |
| technology, entertainment, travel | 0.7 | Lower specificity |

### API Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/v1/health` | None | Health check for AxTask polling |
| POST | `/api/v1/classify` | Key | Single text classification |
| POST | `/api/v1/classify/batch` | Key | Up to 100 texts at once |
| POST | `/api/v1/train` | Key | Add labeled training example |
| POST | `/api/v1/correct` | Key | Correct a misclassification |
| GET | `/api/v1/categories` | Key | List available categories |
| GET | `/api/v1/topics` | Key | List topics |
| GET | `/api/v1/topics/<id>` | Key | Topic detail |
| POST | `/api/v1/topics/detect` | Key | Run clustering + fire webhook |
| POST | `/api/v1/topics/similar` | Key | Find topics similar to text |
| GET | `/api/v1/nodes` | Key | List knowledge-graph nodes |
| GET | `/api/v1/stats` | Key | Category/node counts |
| POST | `/api/v1/audio/upload` | Key | Upload audio for classification |
| GET | `/api/v1/version` | None | Version info |

### AxTask Integration Layer
- **TypeScript client**: `integration/nodeweaver-client.ts` — `classify`, `classifyBatch`, `getTopics`, `health` methods; retry with exponential backoff; typed errors
- **Python client**: `integration/axtask_client.py`
- **Google Apps Script**: `integration/google_apps_script.js`
- **Docker Compose overlay**: `integration/docker-compose.nodeweaver.yml`
- **Webhook**: Topic emergence fires background POST to `AXTASK_WEBHOOK_URL`

### Key Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | yes | PostgreSQL connection string |
| `SESSION_SECRET` | yes | Flask session secret |
| `NODEWEAVER_API_KEY` | recommended | Shared secret for `X-API-Key` auth; skipped in dev when unset |
| `NODEWEAVER_ALLOWED_ORIGINS` | no | Comma-separated CORS origins; default `*` |
| `AXTASK_WEBHOOK_URL` | no | URL to POST topic-emergence events to |

### Frontend Routes
- `/` — Main dashboard
- `/test` — Classification test interface
- `/docs` — API documentation
- `/live` — Live audio topic detection

### Important Files
- `app.py` — Flask app factory with auth/CORS middleware
- `main.py` — WSGI entry point
- `config.py` — All configuration constants and category definitions
- `models.py` — SQLAlchemy models
- `services/rag_engine_simple.py` — Active classification engine with learning methods
- `api/classifier.py` — classify, batch, train, correct endpoints
- `api/topics.py` — topics + webhook firing
- `scripts/post-merge.sh` — Post-merge dependency sync script
- `integration/README.md` — AxTask wiring guide
- `integration/nodeweaver-client.ts` — TypeScript HTTP client for AxTask
- `LEARNING_MECHANISMS.md` — Detailed learning system documentation
- `API_DOCUMENTATION.md` — Full API reference
- `VERSION.md` — Version history

## Known Limitations / Notes
- ML packages (sentence-transformers, numpy, scikit-learn) have a uv lock conflict and run in simple/fallback mode; classification uses keyword matching, not semantic embeddings
- Topic detection in simple mode returns existing DB topics rather than truly novel clusters; AxTask should de-duplicate webhook events by `topic_id`
- The "main" workflow (AxTask-specific) was removed; only "Start application" is active
