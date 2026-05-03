# NodeWeaver ↔ AxTask Integration

NodeWeaver runs as a **standalone HTTP service** that AxTask calls over the network.  
The two repos remain completely independent — no submodules, no shared histories.

---

## Architecture

```
AxTask (TypeScript/React/Node)
  └─ server/engines/dispatcher.ts
       └─ server/lib/nodeweaver-client.ts   ← copy from integration/
            └─ HTTP (X-API-Key)
                 └─ NodeWeaver (Python/Flask)
                      ├── POST /api/v1/classify
                      ├── POST /api/v1/classify/batch
                      ├── GET  /api/v1/topics
                      ├── POST /api/v1/topics/detect   ─── webhook ──► AxTask
                      └── GET  /api/v1/health
```

---

## Environment variables

### NodeWeaver side

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | yes | PostgreSQL connection string |
| `SESSION_SECRET` | yes | Flask session secret |
| `NODEWEAVER_API_KEY` | no* | Shared secret validated via `X-API-Key` header. When unset, auth is skipped (dev mode). |
| `NODEWEAVER_ALLOWED_ORIGINS` | no | Comma-separated CORS origins. Defaults to `*`. Example: `https://app.axtask.com,http://localhost:3000` |
| `AXTASK_WEBHOOK_URL` | no | Full URL NodeWeaver POSTs topic-emergence events to. Example: `https://api.axtask.com/webhooks/nodeweaver` |

*Strongly recommended in any non-local environment.

### AxTask side

| Variable | Required | Description |
|---|---|---|
| `NODEWEAVER_BASE_URL` | yes | NodeWeaver base URL. Example: `https://nodeweaver.example.com` |
| `NODEWEAVER_API_KEY` | yes* | Must match the value set on the NodeWeaver side. |

---

## Wiring the TypeScript client into AxTask

1. Copy `integration/nodeweaver-client.ts` to `server/lib/nodeweaver-client.ts` in the AxTask repo.

2. Set env vars (`.env.local` or your secrets manager):
   ```
   NODEWEAVER_BASE_URL=https://nodeweaver.example.com
   NODEWEAVER_API_KEY=your-shared-secret
   ```

3. Import and use in `server/engines/dispatcher.ts`:
   ```typescript
   import { getNodeWeaverClient } from '../lib/nodeweaver-client';

   const nw = getNodeWeaverClient();

   // Verify connectivity at startup
   const health = await nw.health();
   console.log('NodeWeaver status:', health.status);

   // Classify a task
   const result = await nw.classify({
     text: task.title + ' ' + (task.description ?? ''),
     metadata: { axtask_id: task.id },
   });
   task.category = result.predicted_category;
   task.classificationConfidence = result.confidence_score;
   ```

4. Handle the topic-emergence webhook in an AxTask route:
   ```typescript
   // POST /webhooks/nodeweaver
   app.post('/webhooks/nodeweaver', (req, res) => {
     const { event, data } = req.body;
     if (event === 'topic_emergence') {
       // data.topics contains the newly detected topics
     }
     res.sendStatus(200);
   });
   ```
   Set `AXTASK_WEBHOOK_URL=https://api.axtask.com/webhooks/nodeweaver` on the NodeWeaver side.

---

## Local Docker Compose

`integration/docker-compose.nodeweaver.yml` provides a `nodeweaver` service block you can merge into AxTask's local Compose profile:

```bash
# From the AxTask repo root, with docker-compose.nodeweaver.yml copied to services/nodeweaver/
docker compose \
  -f docker-compose.yml \
  -f services/nodeweaver/docker-compose.nodeweaver.yml \
  up
```

Required env vars for the compose file:

```
NODEWEAVER_REPO_PATH=/path/to/nodeweaver   # local checkout of the NodeWeaver repo
NODEWEAVER_API_KEY=your-shared-secret
NODEWEAVER_DATABASE_URL=postgresql://rag_user:rag_pass@nodeweaver-db:5432/nodeweaver
SESSION_SECRET=change-me
AXTASK_WEBHOOK_URL=http://axtask-api:3000/webhooks/nodeweaver   # optional
```

`NODEWEAVER_REPO_PATH` must point to the root of the NodeWeaver repository on your local filesystem. Docker Compose uses this to build the image from the correct source.

NodeWeaver will be reachable at `http://nodeweaver:5000` from other containers on the same Docker network, and at `http://localhost:5000` from the host.

---

## Auth contract

All `/api/v1/` endpoints **except** `/api/v1/health` require the header:

```
X-API-Key: <NODEWEAVER_API_KEY>
```

A missing or incorrect key returns:

```json
HTTP 401
{ "error": "Unauthorized", "message": "Missing or invalid X-API-Key header" }
```

When `NODEWEAVER_API_KEY` is not set on the NodeWeaver server, validation is skipped entirely (development convenience).

---

## Webhook payload

When topic emergence is detected (via `POST /api/v1/topics/detect`), NodeWeaver fires a background POST to `AXTASK_WEBHOOK_URL`:

```json
{
  "event": "topic_emergence",
  "source": "nodeweaver",
  "data": {
    "count": 2,
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

NodeWeaver does **not** retry webhook failures and does not block on the response.

> **Note on placeholder behavior:** When the default `SimpleRAGEngine` is active
> (i.e. the full ML stack is not installed), `POST /api/v1/topics/detect` returns
> existing database topics rather than genuinely new/emerging ones. As a result,
> AxTask may receive repeated `topic_emergence` webhook events for the same topics.
> Once the full RAG engine with sentence-transformers is available, detection
> produces only novel clusters. Until then, AxTask should treat the webhook as a
> best-effort signal and de-duplicate by `topic_id`.
