# NodeWeaver Learning Mechanisms

_Version 1.0.3 — Added corrective feedback loop, training data integration, and enhanced category vocabulary_

---

## Why Learning Matters

A keyword-based classifier is only as good as its keyword lists. When a user sees "Attend city council meeting about zoning changes" classified as **work**, that's technically correct but shallow — the meeting is a civic/government obligation, which is better captured by **political** and **legal**. Learning mechanisms let the system grow beyond its initial vocabulary in two ways:

1. **Proactive training** — you feed it labeled examples you already know are right.
2. **Reactive correction** — you tell it when it gets something wrong, and it remembers.

---

## How the System Classifies (Background)

Before diving into learning, it helps to know how classification works:

1. The input text is lowercased and scanned against a keyword dictionary for each category.
2. Each keyword match increments that category's score. Confidence = `min(0.9, base_confidence + (matches − 1) × 0.05)`.
3. All categories above zero matches are returned as `all_categories`, sorted by confidence. The highest becomes `predicted_category`.
4. Categories with a higher `base_confidence` win ties — that's why `political` (0.85) now beats `work` (0.9 cap but 0.8 for one keyword match) for civic meeting text that hits the political keyword set multiple times.

---

## Category Vocabulary

### Political — base confidence 0.85

Keywords that trigger this category include:

> political, government, policy, vote, election, senator, congress, politics, law, **city council**, **council**, **zoning**, **municipal**, **civic**, **public hearing**, **ordinance**, **regulation**

The bold words were added in v1.0.3 specifically to handle government and civic meetings that were previously slipping through as generic `work`.

### Legal — base confidence 0.85 (new in v1.0.3)

> legal, law, court, judge, lawyer, attorney, lawsuit, contract, regulation, compliance, **zoning**, **ordinance**, municipal law, jurisdiction, statute

Zoning and ordinance appear in both `political` and `legal` because a zoning hearing is simultaneously a civic act and a legal proceeding — the multi-label system correctly assigns both.

### Work — base confidence 0.9 cap, but 0.8 for a single keyword match

> meeting, project, deadline, office, work, job, business, report, presentation, client, task, colleague, conference, schedule

`work` still appears in multi-label results for civic meetings (because "meeting" is a work keyword), but it no longer wins the primary classification when competing against multiple political/legal keyword hits.

---

## API: Reactive Correction

Use this when the system returned the wrong primary category.

```
POST /api/v1/correct
Content-Type: application/json
X-API-Key: <your-key>

{
  "text": "Attend city council meeting about zoning changes",
  "correct_category": "political",
  "metadata": {
    "note": "Government meetings are civic/political, not generic work"
  }
}
```

**Response:**
```json
{
  "success": true,
  "text": "Attend city council meeting about zoning changes",
  "correct_category": "political",
  "message": "Classification corrected to: political"
}
```

**What happens internally:**

1. The system queries `ClassificationLog` for the most recent entry with this exact text.
2. It records the original predicted category alongside the corrected one in correction metadata.
3. It calls `add_training_data()` with the correct category — creating a new `Document` row with `confidence_score = 0.95` and `meta_data.is_correction = true`.
4. It extracts significant words from the text (length > 3, alphabetic) and logs them as candidate keywords for the corrected category.

**If the text hasn't been classified before**, the endpoint returns HTTP 404 with `"success": false`. In that case, use `/api/v1/train` instead.

---

## API: Proactive Training

Use this to pre-teach the system before it even encounters similar text in production.

```
POST /api/v1/train
Content-Type: application/json
X-API-Key: <your-key>

{
  "text": "Review municipal ordinance 2024-05 for zoning compliance",
  "category": "legal",
  "metadata": {
    "source": "city_legal_team",
    "validated_by": "attorney"
  }
}
```

**Response:**
```json
{
  "success": true,
  "document_id": 42,
  "text": "Review municipal ordinance 2024-05 for zoning compliance",
  "category": "legal",
  "message": "Training data added for category: legal"
}
```

**What happens internally:**

1. A `Document` row is created with `confidence_score = 0.95`, `predicted_category = "legal"`, and `meta_data.is_training_data = true`.
2. The document's embedding is generated and stored (enables future vector-similarity retrieval once the full ML stack is active).
3. `_update_category_keywords()` extracts words like `["review", "municipal", "ordinance", "zoning", "compliance"]` and logs them — these can feed a future dynamic keyword updater.
4. The document participates in the `similar_topics` lookup for future classifications.

---

## Learning Storage Schema

Every training and correction document is stored in the `documents` table with this metadata structure:

```json
{
  "is_training_data": true,
  "user_corrected_category": "political",
  "training_timestamp": "2025-08-05T00:30:00",

  "original_category": "work",
  "corrected_category": "political",
  "correction_timestamp": "2025-08-05T00:30:00",
  "is_correction": true
}
```

Fields present on training-only documents (not corrections): `is_training_data`, `training_timestamp`.  
Fields added by corrections: `original_category`, `corrected_category`, `correction_timestamp`, `is_correction`.

---

## Real-World Example: Government Meeting

### Before v1.0.3

```
Input: "Attend city council meeting about zoning changes"

all_categories:
  - work  →  0.8  (1 keyword match: "meeting")
```

The text hit "meeting" in the work keyword list. Nothing else matched. Primary = work.

### After v1.0.3 (keyword expansion alone)

```
Input: "Attend city council meeting about zoning changes"

all_categories:
  - political  →  0.9   (3 keyword matches: "city council", "council", "zoning")
  - legal      →  0.85  (1 keyword match: "zoning")
  - work       →  0.8   (1 keyword match: "meeting")
```

Primary = political. Work is still included (legitimately — attending a meeting is work-adjacent), but it is no longer the top classification.

### After a correction is submitted

If a user submits `POST /api/v1/correct` with `correct_category: "political"`:
- A document is stored representing the text as strongly political.
- When `/api/v1/topics/detect` next runs, this document participates in clustering, potentially creating or reinforcing a "Political Meetings" topic node.
- Future texts that are similar to this one will retrieve it as a neighbor, nudging classification confidence further toward political.

---

## Improving the System Further

### Things you can do right now

| Action | Endpoint | Effect |
|---|---|---|
| Correct a bad classification | `POST /api/v1/correct` | Creates a corrective training document |
| Add a known-good example | `POST /api/v1/train` | Creates a positive training document |
| Trigger topic clustering | `POST /api/v1/topics/detect` | Groups training documents into topic nodes |

### What makes a good training example

- **Specific**: "Review the zoning variance application for Lot 42-B" is better than "legal stuff".
- **Representative**: Use phrasing that actually appears in real tasks, not textbook definitions.
- **Diverse**: Cover different phrasings of the same concept — "city council hearing", "municipal board meeting", "public comment period" all belong to the same cluster.
- **Consistent**: Use the same category name every time for the same concept (`"legal"` not `"Legal"` or `"law"`).

### Roadmap: Planned learning improvements

1. **Dynamic keyword database**: Currently, extracted keywords are logged. The next step is writing them back to the category keyword lists so every new training example immediately widens the detection net.
2. **Vector-space similarity**: Once sentence-transformers is available, the system will retrieve training documents by semantic embedding distance rather than keyword overlap. This will handle paraphrases and synonyms automatically.
3. **Confidence calibration**: Track the distribution of corrected vs. uncorrected classifications per category to automatically adjust base_confidence values.
4. **Batch correction import**: Accept a CSV or JSON array of `{ text, category }` pairs for bulk training.

---

## API Reference Summary

| Endpoint | Method | Auth | Key Request Fields | Key Response Fields |
|---|---|---|---|---|
| `/api/v1/classify` | POST | Key | `text`, `metadata` | `predicted_category`, `confidence_score`, `all_categories` |
| `/api/v1/correct` | POST | Key | `text`, `correct_category`, `metadata` | `success`, `message` |
| `/api/v1/train` | POST | Key | `text`, `category`, `metadata` | `success`, `document_id`, `message` |

All three endpoints accept an optional `metadata` object for tracking context (user IDs, source systems, validation status, etc.).
