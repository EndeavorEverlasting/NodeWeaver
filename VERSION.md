# NodeWeaver Version History

## Version 1.0.3 (2025-08-05) - Learning & Classification Enhancement

### Learning Mechanisms
- **Classification Correction** (`POST /api/v1/correct`): Correct any misclassification after the fact. The system finds the original log entry, stores a corrective training document at 0.95 confidence, and records both the original and corrected categories for pattern analysis.
- **Training Data Integration** (`POST /api/v1/train`): Supply labeled examples for any category. Each example is stored as a high-confidence document and keywords are extracted for future vocabulary improvement.
- **Keyword Learning** (`_update_category_keywords`): Significant words (length > 3, alphabetic) from training text are extracted and logged. These associations are the foundation for a future dynamic keyword database.
- **Corrective Feedback Loop**: Every correction feeds back into the document store, so retrieval-based similarity queries will gradually favor corrected patterns.

### Enhanced Category Detection
- **New `legal` category**: Keywords — `legal`, `law`, `court`, `judge`, `lawyer`, `attorney`, `lawsuit`, `contract`, `regulation`, `compliance`, `zoning`, `ordinance`, `municipal law`, `jurisdiction`, `statute`. Base confidence: **0.85**.
- **Expanded `political` keywords**: Added `city council`, `council`, `zoning`, `municipal`, `civic`, `public hearing`, `ordinance`, `regulation`. Base confidence raised to **0.85** (was 0.7).
- **Nuanced government meeting classification**: Before this release the system had no way to distinguish a city council zoning meeting from a generic work meeting. The expanded keyword sets give the system enough signal to prioritize political/legal over work.

### Real-World Before/After
| Text | Before 1.0.3 | After 1.0.3 |
|---|---|---|
| "Attend city council meeting about zoning changes" | work (0.8) | **political (0.9)**, legal (0.85), work (0.8) |
| "Review municipal ordinance for compliance" | work (0.8) | **legal (0.85)**, political (0.85) |

### AxTask HTTP Integration (merged alongside 1.0.3)
- **`GET /api/v1/health`**: Structured health check — `{ status, service, version, api_version, components: { database, embedding_model }, timestamp }`. No auth required. Designed for AxTask connectivity polling.
- **API key middleware**: `before_request` hook validates `X-API-Key` header on all `/api/v1/*` routes except `/health`. Skipped transparently in dev mode when `NODEWEAVER_API_KEY` is unset.
- **Native CORS**: `OPTIONS` preflight handled before auth fires. Origins configured via `NODEWEAVER_ALLOWED_ORIGINS` (comma-separated, default `*`).
- **AxTask webhook**: `POST /api/v1/topics/detect` fires a background-thread HTTP POST to `AXTASK_WEBHOOK_URL` on topic emergence. 5-second timeout, errors swallowed — NodeWeaver never blocks on the callback.
- **TypeScript HTTP client** (`integration/nodeweaver-client.ts`): Zero-dependency (native `fetch`, Node 18+). Typed methods: `classify`, `classifyBatch`, `getTopics`, `health`. Retry with exponential backoff. `AbortController` timeout. Typed error hierarchy: `NodeWeaverError`, `NodeWeaverAuthError`, `NodeWeaverTimeoutError`. Singleton factory.
- **Docker Compose overlay** (`integration/docker-compose.nodeweaver.yml`): `nodeweaver` + `nodeweaver-db` services. Build context via `NODEWEAVER_REPO_PATH` env var.
- **Integration docs** (`integration/README.md`): Architecture diagram, env var tables for both sides, AxTask wiring guide, auth contract, webhook payload spec, Docker Compose instructions.
- **Post-merge setup script** (`scripts/post-merge.sh`): Runs `uv sync` and verifies DB tables after every task merge. Registered in `.replit` with 60-second timeout.

### Technical Details
- `correct_classification()` uses `ClassificationLog.log_id` (not `.timestamp`, which doesn't exist on the model) for ordering
- Training documents stored with `meta_data.is_training_data = true` and `confidence_score = 0.95`
- `datetime` import added to `services/rag_engine_simple.py` for timestamp metadata
- `legal` added to `Config.DEFAULT_CATEGORIES` in `config.py`
- All version strings updated: `config.py`, `pyproject.toml`, `API_DOCUMENTATION.md`, `replit.md`

---

## Version 1.0.2 (2025-08-04) - Multi-Classification Enhancement

### Major Features
- **Multi-label Classification**: Every classify response now includes `all_categories` — an array of every matching category with its individual confidence score, not just the top one.
- **Many-to-Many Business Rule**: Entries relate to multiple topics; topics relate to multiple entries. The `topic_associations` field in classify responses carries the matched topic IDs.
- **Automatic Topic Associations**: After classification, documents are linked to existing topics whose similarity score exceeds the threshold.

### Changed Business Rules
- `predicted_category` / `confidence_score` remain at the top level for backward compatibility — they always reflect the highest-confidence match.
- `all_categories` is the new canonical field for multi-label consumers.

### Technical Updates
- `_predict_categories_multi()` replaces the old single-category predictor
- Keyword matching scores all categories in a single pass; confidence = `min(0.9, base + (matches − 1) × 0.05)`
- `topic_associations` stored in `Document.topic_ids` (ARRAY column)

### Example Results
| Input | Primary | All Categories |
|---|---|---|
| "Find a cake for birthday party" | personal (0.85) | personal, shopping (0.75) |
| "Schedule meeting and buy cake for office party" | work (0.9) | work, personal, finance, shopping |

---

## Version 1.0.1 (2025-08-04) - Bug Fix Release

### Bug Fixes
- **Flask Extensions Compatibility**: Moved RAG engine from `app.rag_engine` attribute to `app.extensions['rag_engine']` — fixes `AttributeError` on Flask >= 2.3 which freezes `__dict__` after init
- **LSP Type Errors**: Resolved type-checker complaints across `app.py` and blueprint files

---

## Version 1.0.0 (2025-08-04) - Initial Production Release

### Core Features
- Complete RAG classification system with keyword + embedding pipeline
- Real-time audio processing (file upload + live microphone)
- Topic emergence detection via DBSCAN clustering on node embeddings
- AxTask Python client and Google Apps Script integration
- Bootstrap dark-theme web UI with test interface and live audio dashboard
- Docker + docker-compose setup with PostgreSQL and pgvector

### API Endpoints at Launch
- `POST /api/v1/classify` — single text, returns category + confidence
- `POST /api/v1/classify/batch` — up to 100 texts
- `GET /api/v1/topics` — list topics with filtering
- `POST /api/v1/topics/detect` — run clustering detection
- `POST /api/v1/audio/upload` — audio file → transcription + classification
- `GET /api/v1/stats` — category and node counts

---

## Upgrade Notes

### From 1.0.2 → 1.0.3
- No breaking changes. New endpoints (`/train`, `/correct`, `/health`) are purely additive.
- Set `NODEWEAVER_API_KEY` in production — auth is now enforced by default.
- Set `NODEWEAVER_ALLOWED_ORIGINS` to your AxTask domain in production (default `*` is fine for dev).
- If using Docker Compose with AxTask, see `integration/README.md` for the overlay instructions.

### From 1.0.1 → 1.0.2
- `predicted_category` / `confidence_score` unchanged — backward compatible.
- New `all_categories` array in classify responses; consume it to get multi-label results.

### From 1.0.0 → 1.0.1
- No API changes. Internal Flask extension access pattern updated.

---

## Release Cadence
- **Major** (x.0.0): Breaking API changes or major architectural shifts
- **Minor** (1.x.0): New endpoints or capabilities, backward compatible
- **Patch** (1.0.x): Bug fixes and documentation updates
