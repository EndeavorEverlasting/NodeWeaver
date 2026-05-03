# NodeWeaver API Documentation

**Version:** 1.0.3  
**Base URL:** `http://localhost:5000/api/v1`  
**Content-Type:** `application/json`

---

## Authentication

All `/api/v1/` endpoints **except** `/api/v1/health` require the following header when `NODEWEAVER_API_KEY` is set on the server:

```
X-API-Key: <your-api-key>
```

When the env var is **not set** (development mode), authentication is skipped automatically.

**Unauthorized response (HTTP 401):**
```json
{
  "error": "Unauthorized",
  "message": "Missing or invalid X-API-Key header"
}
```

---

## CORS

Origins listed in `NODEWEAVER_ALLOWED_ORIGINS` (comma-separated) receive CORS headers. Defaults to `*` when the env var is unset. Preflight `OPTIONS` requests are always permitted before authentication fires.

---

## Classification Pipeline

NodeWeaver uses a three-layer classification pipeline for every `/api/v1/classify` call. Each layer only runs if the previous layer did not produce a confident enough result.

| Layer | Name | Description |
|---|---|---|
| 1 | `nodeweaver_rag` | Internal keyword + topic scoring (existing RAG engine) |
| 2 | `rag_augmented` | Re-scores using augmented context from similar topics |
| 3 | `universal_classifier` | HuggingFace zero-shot model as final fallback |

### Pipeline environment variables

| Variable | Default | Description |
|---|---|---|
| `NW_L1_CONFIDENCE_THRESHOLD` | `0.7` | Minimum confidence for Layer 1 result to be accepted |
| `NW_L2_CONFIDENCE_THRESHOLD` | `0.55` | Minimum confidence for Layer 2 result to be accepted |
| `NW_ZS_MODEL` | `cross-encoder/nli-deberta-v3-small` | HuggingFace model used by Layer 3. Validated at startup — an informative warning is logged if the model cannot be fetched. |
| `NW_ZS_PRELOAD` | `false` | Set to `true` (or `1` / `yes`) to eagerly download and load the zero-shot model at startup instead of waiting for the first ambiguous request. A clear log message is emitted when preloading begins and when it completes (or fails). |

By default, Layer 3 loads lazily on the first request that reaches it and is then cached in memory. Setting `NW_ZS_PRELOAD=true` eliminates the first-call latency spike and makes model-fetch failures immediately visible in startup logs. If the model or `transformers` library is unavailable, NodeWeaver logs a warning and returns the best result from Layers 1–2 instead of crashing.

---

## Rate Limiting

- Maximum **100 requests per minute per IP** (configurable via `RATE_LIMIT_PER_MINUTE` env var)
- Batch processing limited to 100 texts per request
- Audio files limited to 10 MB per upload

When the limit is exceeded the server responds with **HTTP 429** and a `Retry-After` header indicating how many seconds to wait before retrying:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 42
Content-Type: application/json

{
  "error": "Too Many Requests",
  "message": "Rate limit exceeded. Maximum 100 requests per minute per IP.",
  "retry_after": 42
}
```

| HTTP Status | Meaning |
|---|---|
| 429 | Rate limit exceeded — check `Retry-After` header |

---

## Endpoints

### Health

#### `GET /api/v1/health`

Structured health check for AxTask connectivity polling. **No authentication required.**

```http
GET /api/v1/health
```

**Response (200 — healthy):**
```json
{
  "status": "healthy",
  "service": "nodeweaver",
  "version": "1.0.3",
  "api_version": "v1",
  "components": {
    "database": "healthy",
    "embedding_model": "ready",
    "rag_engine": "full",
    "zero_shot_model": "ready"
  },
  "timestamp": "2025-08-04T19:30:52Z"
}
```

**Response (503 — degraded):**
```json
{
  "status": "degraded",
  "service": "nodeweaver",
  "version": "1.0.3",
  "api_version": "v1",
  "components": {
    "database": "unhealthy",
    "embedding_model": "ready",
    "rag_engine": "full",
    "zero_shot_model": "loading"
  },
  "timestamp": "2025-08-04T19:30:52Z"
}
```

The `zero_shot_model` field reports one of three values:

| Value | Meaning |
|---|---|
| `loading` | Model has not yet been loaded (lazy mode) or is actively downloading (preload in progress) |
| `ready` | Model is loaded in memory and ready to classify |
| `unavailable` | Model failed to load — Layer 3 is disabled for this session |

---

### Text Classification

#### `POST /api/v1/classify`

Classify a single text input.

```http
POST /api/v1/classify
X-API-Key: <api-key>
Content-Type: application/json
```

**Request body:**
```json
{
  "text": "I need to finish my research paper by tomorrow",
  "metadata": { "axtask_id": "task-123", "source": "axtask" }
}
```

**Response:**
```json
{
  "predicted_category": "academic",
  "confidence_score": 0.89,
  "classification_source": "nodeweaver_rag",
  "layer_debug": {
    "layer1": { "category": "academic", "confidence": 0.89 }
  },
  "similar_topics": [
    { "label": "education", "similarity": 0.76 }
  ],
  "similar_nodes": [],
  "processing_time": 0.042,
  "log_id": 17
}
```

| Field | Type | Description |
|---|---|---|
| `predicted_category` | string | Winning category label |
| `confidence_score` | float | Confidence of the winning layer |
| `classification_source` | string | Layer that produced the result: `nodeweaver_rag`, `rag_augmented`, or `universal_classifier` |
| `layer_debug` | object | Per-layer category and confidence for debugging |

---

#### `POST /api/v1/classify/batch`

Classify up to 100 texts in one call.

```http
POST /api/v1/classify/batch
X-API-Key: <api-key>
Content-Type: application/json
```

**Request body:**
```json
{
  "texts": [
    "Meeting with client at 2pm",
    "Buy groceries on the way home",
    "Submit assignment before deadline"
  ]
}
```

**Response:**
```json
{
  "results": [
    { "predicted_category": "work",     "confidence_score": 0.92, "similar_topics": [], "similar_nodes": [], "processing_time": 0.031 },
    { "predicted_category": "personal", "confidence_score": 0.87, "similar_topics": [], "similar_nodes": [], "processing_time": 0.028 },
    { "predicted_category": "academic", "confidence_score": 0.91, "similar_topics": [], "similar_nodes": [], "processing_time": 0.029 }
  ],
  "batch_size": 3,
  "processing_time": 0.11
}
```

---

#### `POST /api/v1/train`

Add a single training example.

```http
POST /api/v1/train
X-API-Key: <api-key>
Content-Type: application/json
```

**Request body:**
```json
{ "text": "Finish quarterly report", "category": "work", "metadata": {} }
```

---

#### `POST /api/v1/correct`

Correct a misclassification.

```http
POST /api/v1/correct
X-API-Key: <api-key>
Content-Type: application/json
```

**Request body:**
```json
{ "text": "Buy milk", "correct_category": "personal" }
```

---

#### `GET /api/v1/categories`

List available classification categories.

```http
GET /api/v1/categories
X-API-Key: <api-key>
```

**Response:**
```json
{ "categories": ["personal","work","academic","political","legal","health","finance","entertainment","travel","shopping","technology","other"], "total": 12 }
```

---

### Topic Management

#### `GET /api/v1/topics`

List topics with optional filtering.

```http
GET /api/v1/topics?category=work&page=1&per_page=20
X-API-Key: <api-key>
```

**Query parameters:** `category`, `min_weight` (float), `min_coherence` (float), `page`, `per_page` (max 100).

---

#### `GET /api/v1/topics/<topic_id>`

Get details for a specific topic.

```http
GET /api/v1/topics/42
X-API-Key: <api-key>
```

---

#### `POST /api/v1/topics/detect`

Trigger clustering-based topic detection. Fires an async webhook to `AXTASK_WEBHOOK_URL` when new topics emerge.

```http
POST /api/v1/topics/detect
X-API-Key: <api-key>
Content-Type: application/json
```

**Response:**
```json
{
  "message": "Topic detection completed",
  "emerging_topics": 2,
  "topics": [...]
}
```

---

#### `POST /api/v1/topics/similar`

Find topics similar to a given text.

```http
POST /api/v1/topics/similar
X-API-Key: <api-key>
Content-Type: application/json
```

**Request body:**
```json
{ "text": "machine learning project", "limit": 10, "threshold": 0.5 }
```

---

#### `GET /api/v1/nodes`

List knowledge-graph nodes.

```http
GET /api/v1/nodes?category=work&search=meeting
X-API-Key: <api-key>
```

---

#### `GET /api/v1/stats`

System statistics (topic / node counts by category).

```http
GET /api/v1/stats
X-API-Key: <api-key>
```

---

### Audio Processing

#### `POST /api/v1/audio/upload`

Upload an audio file for transcription + classification.

```http
POST /api/v1/audio/upload
X-API-Key: <api-key>
Content-Type: multipart/form-data
```

Supported formats: WAV, MP3, M4A, FLAC. Maximum size: 10 MB.

---

## Webhook — topic emergence

When `AXTASK_WEBHOOK_URL` is set, NodeWeaver fires a background `POST` to that URL after each topic-detection run that produces new topics:

```json
{
  "event": "topic_emergence",
  "source": "nodeweaver",
  "data": {
    "count": 1,
    "topics": [
      {
        "topic_id": 42,
        "label": "Work: project deadline",
        "category": "work",
        "total_weight": 12.5,
        "coherence_score": 0.84
      }
    ]
  }
}
```

NodeWeaver uses a 5-second timeout and swallows all errors — it never blocks on the callback.

---

## Error responses

```json
{
  "error": "Classification failed",
  "details": "..."
}
```

| HTTP Status | Meaning |
|---|---|
| 400 | Validation error — check request body |
| 401 | Missing or invalid `X-API-Key` |
| 404 | Endpoint not found |
| 429 | Rate limit exceeded — check `Retry-After` header |
| 500 | Internal server error |
| 503 | Service degraded (database unreachable) |

---

## SDK / Integration

See `integration/README.md` for the full AxTask wiring guide and the TypeScript client (`integration/nodeweaver-client.ts`).
