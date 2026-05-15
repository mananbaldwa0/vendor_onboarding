# Claude Code Prompt — Change Submission Model to Append-Only

## Context

The current `POST /api/application/submit` endpoint updates the existing application row in-place
for a vendor. This means resubmissions overwrite prior data and there is no audit trail.

We want to change this to an **append-only model**:
- While a vendor is filling the form, their progress is saved as a single `draft` row (updates in place — this is fine).
- The moment they hit **Submit**, a **new row is always inserted**, regardless of prior submissions.
- Each submission row gets an incrementing `version` number (1, 2, 3...).
- All read endpoints (`GET /status`, `GET /{id}`) return the **latest version** (highest `version` for that `vendor_id`).

This preserves a full audit trail of every submission attempt, which is required for fintech/banking compliance.

---

## Schema Change Required

Add one column to the `applications` table in Supabase:

```sql
ALTER TABLE applications ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
```

No other schema changes are needed. The existing `status` ENUM already includes `'draft'` which is used for the in-progress save flow.

---

## Code Changes Required

### 1. `routers/application.py` — `POST /submit` endpoint

**Current behaviour:** checks if a row exists for `vendor_id`, updates it if yes, inserts if no.

**New behaviour:**

```
On POST /submit:
  1. Find the current latest version for this vendor (SELECT MAX(version) WHERE vendor_id = ?)
  2. new_version = latest_version + 1  (or 1 if no prior rows exist)
  3. Always INSERT a new row with:
       - vendor_id
       - version = new_version
       - status = "submitted"
       - submitted_at = now()
       - all form fields from request body
  4. Return { application_id, status, version }
```

**Exception — Draft auto-save (if you add a separate `POST /draft` endpoint later):**
Draft saves should UPDATE the existing draft row in place (do not version drafts).
This prompt does not require you to build the draft endpoint — just leave a TODO comment for it.

---

### 2. `routers/application.py` — `GET /status` endpoint

**Current behaviour:** returns the single row for `vendor_id`.

**New behaviour:** returns the row with the **highest `version`** for `vendor_id`.

```python
# Use order_by + limit instead of a plain .eq() fetch
result = sb.table("applications") \
    .select("id, status, submitted_at, version") \
    .eq("vendor_id", vendor_id) \
    .order("version", desc=True) \
    .limit(1) \
    .execute()
```

---

### 3. `routers/application.py` — `GET /{app_id}` endpoint

No change needed — this already fetches by `id` (UUID), which uniquely identifies a specific submission row. Keep it as-is.

---

### 4. `models/schemas.py` — Response models

Add `version: int` to `ApplicationResponse` and `StatusResponse` so callers know which version they are seeing:

```python
class ApplicationResponse(BaseModel):
    application_id: str
    status: str
    version: int          # ← add this

class StatusResponse(BaseModel):
    application_id: Optional[str] = None
    status: Optional[str] = None
    submitted_at: Optional[datetime] = None
    version: Optional[int] = None   # ← add this
```

---

## What NOT to Change

- Do not touch `routers/auth.py` — login flow is unaffected.
- Do not touch `routers/documents.py` — document upload is unaffected.
- Do not touch `services/` — JWT and Supabase client are unaffected.
- Do not add a new `GET /history` endpoint in this task — leave a TODO comment for it.

---

## Acceptance Criteria

1. Two sequential `POST /submit` calls from the same vendor create **two separate rows** in `applications`, with `version = 1` and `version = 2` respectively.
2. `GET /status` returns the row with `version = 2` (the latest).
3. `GET /{app_id}` with the UUID of the first submission still returns `version = 1` correctly.
4. The `version` field appears in both `ApplicationResponse` and `StatusResponse`.
5. No existing endpoints are broken.
