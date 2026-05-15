# Backend — Implementation Reference
> Single source of truth. Phase 1 complete.
> Last updated: May 2026

---

## What This Backend Does

A FastAPI server that:
1. Lets a vendor log in with just their email (no password, no OTP yet)
2. Accepts their onboarding form data and stores it in Supabase
3. Accepts document uploads (PDFs/images) and stores them in Supabase Storage
4. Runs rule-based validation on every submit (regex, cross-field, required doc checks)
5. Upserts draft in-place until clean — new version only after a successful submit
6. Supports in-place draft saves (no version bump, no validation)
7. Returns current application status and version to the vendor

---

## Stack

| Layer | Tool | Purpose |
|---|---|---|
| Language | Python 3.11+ | — |
| Framework | FastAPI | REST API + auto /docs UI |
| Database | Supabase (PostgreSQL) | Stores vendors, applications, documents |
| File Storage | Supabase Storage | Stores uploaded PDFs/images |
| Auth | PyJWT | Signs and verifies JWT tokens |
| File Upload | python-multipart | Handles multipart/form-data |
| Models | Pydantic | Request/response type validation |
| Env Config | python-dotenv | Loads .env file |

---

## Database Schema

Three tables. Run this SQL once on Supabase SQL Editor to create them.

```sql
-- One row per vendor email. Created on first login.
CREATE TABLE vendors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

-- One row per submission. Same vendor can have many rows (versioned).
-- status: 'draft' | 'submitted' | 'approved' | 'pending' | 'rejected'
-- version: increments per vendor (1, 2, 3...) — never resets
CREATE TABLE applications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vendor_id UUID REFERENCES vendors(id),
  status TEXT DEFAULT 'draft',
  version INTEGER NOT NULL DEFAULT 1,

  -- Group 1: Company Identity
  company_name TEXT,
  company_type TEXT,
  incorporation_date DATE,
  registered_address TEXT,
  city TEXT,
  state TEXT,
  employee_count INTEGER,
  annual_turnover TEXT,
  website TEXT,

  -- Group 2: PAN
  pan_number TEXT,

  -- Group 3: GST
  gst_registered BOOLEAN,
  gst_number TEXT,

  -- Group 4: Director / Company IDs
  signatory_name TEXT,
  din TEXT,
  dpin TEXT,
  cin_number TEXT,
  llp_number TEXT,
  msme_number TEXT,

  -- Group 5: Banking
  account_holder_name TEXT,
  bank_name TEXT,
  account_number TEXT,
  ifsc_code TEXT,
  account_type TEXT,

  -- Group 6: ISO Certification
  iso_certified BOOLEAN,
  iso_cert_number TEXT,
  iso_expiry_date DATE,
  soc2_audited BOOLEAN,

  -- Group 7: Data & Compliance
  service_nature TEXT,
  processes_data BOOLEAN,
  data_in_india BOOLEAN,
  cloud_provider TEXT,
  cyber_insurance BOOLEAN,
  cyber_coverage_crores DECIMAL,

  -- Group 8: Contact
  contact_name TEXT,
  contact_email TEXT,
  contact_phone TEXT,

  submitted_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

-- One row per uploaded document.
-- application_id is NULL when doc is "floating" (uploaded but not yet linked to a submission).
-- Docs get linked to application_id at submit/draft time via _link_docs().
-- vendor_id stored on every doc row — used for isolation and copy-forward logic.
CREATE TABLE documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id UUID REFERENCES applications(id),  -- NULL until submit/draft links it
  vendor_id UUID REFERENCES vendors(id),
  doc_type TEXT,
  file_name TEXT,
  file_url TEXT,
  uploaded_at TIMESTAMP DEFAULT NOW()
);
```

**If tables already exist** (add new columns without recreating):
```sql
ALTER TABLE applications
  ADD COLUMN IF NOT EXISTS city TEXT,
  ADD COLUMN IF NOT EXISTS cin_number TEXT,
  ADD COLUMN IF NOT EXISTS llp_number TEXT,
  ADD COLUMN IF NOT EXISTS msme_number TEXT,
  ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS vendor_id UUID REFERENCES vendors(id);
```

**Storage bucket:** create `vendor-docs` in Supabase Storage → public: OFF.
Files stored at path: `{vendor_id}/{doc_type}/{filename}`

---

## Auth Design

- No password. No OTP yet (planned Phase 3).
- Vendor enters email → backend finds or creates vendor row → returns JWT token.
- Token is signed with `JWT_SECRET` env var using HS256 algorithm.
- Token expiry: 7 days.
- Token payload: `{ "vendor_id": "uuid", "email": "..." }`
- All protected endpoints require: `Authorization: Bearer <token>` header.

---

## Submission Model — Upsert Draft, Append on New Cycle

`POST /submit` behavior (implemented in `_upsert_application()` in `routers/application.py`):

```
1. Existing draft row?      → update in-place (same id, same version). No new row.
2. No draft, has submitted? → insert new row, version = latest + 1  (resubmit cycle)
3. Nothing exists           → insert new row, version = 1
```

```
First submit (errors)  → version 1 draft  (id: AAA) ← updated in-place on each retry
First submit (clean)   → version 1 submitted (id: AAA)
Resubmit after submit  → version 2 draft (id: BBB) ← new row
```

**Draft saves** (`POST /draft`) follow the same upsert logic. No version bump. If no draft exists, inserts one.

**Why this design:** vendor doesn't lose progress if one field is wrong. Draft updated in-place until clean submit. New version only on fresh cycle after successful submit.

---

## Document Lifecycle — Floating → Linked

Documents float with `application_id = NULL` after upload. They get linked to an application when the vendor submits or saves a draft.

### Upload (upsert in-place)
```
Upload pan_card (1st time)   → INSERT row (vendor_id, doc_type, file_url, application_id=NULL)
Upload pan_card (again)      → UPDATE existing NULL row in-place (new file_url, same id)
```
One row per `(vendor_id, doc_type)` per version cycle. Re-uploading same type never creates a second row.

### Linking (on submit or draft save)
`_link_docs(sb, vendor_id, app_id)`:
```
UPDATE documents SET application_id = app_id
WHERE vendor_id = vendor_id AND application_id IS NULL
```
All floating docs get stamped with the application's ID.

### Doc validation scope
`_get_uploaded_doc_types(sb, vendor_id)`:
- Queries ALL doc rows for this vendor regardless of `application_id`
- Returns every `doc_type` ever uploaded across all versions

**Why:** Validation only asks "has this vendor ever uploaded this doc type?" — not "which version?". Computationally simple (one query, no version filtering). Acceptable for demo scale.

**Result per version:**
| Scenario | Validation sees |
|---|---|
| V1 docs linked to v1_app_id | Found — query ignores application_id |
| New docs uploaded (NULL) before v2 submit | Found |
| V1 docs + new v2 docs | All found — union across all rows |

`_link_docs` still runs on every submit/draft for audit trail — stamps NULL docs to current app_id. Docs from previous versions stay linked to their original app_id (no mutation).

---

## Validation — Rule-Based (Phase 1)

Runs on every `POST /submit`. Draft saves skip validation entirely.

If errors found → upsert as `status: "draft"`, errors returned to frontend.
If clean → upsert as `status: "submitted"`.

**Important:** `model_dump(mode="json", exclude_none=True)` is used before validation. This means:
- Fields the vendor left blank → `None` → excluded from dict → `data.get("field")` returns `None` → triggers "required" error
- Boolean `False` is NOT `None` → stays in dict → `data.get("iso_certified") is None` returns `False` → no "Specify..." error

### Validation Engine: `services/validation.py`

**Regex patterns:**
| Pattern | Format |
|---|---|
| `RE_PAN` | `^[A-Z]{5}[0-9]{4}[A-Z]{1}$` |
| `RE_GST` | `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$` |
| `RE_CIN` | `^[UL][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$` |
| `RE_LLP` | `^[A-Z]{3}-[0-9]{4}$` |
| `RE_DIN` | `^[0-9]{8}$` |
| `RE_ACCOUNT` | `^[0-9]{9,18}$` |
| `RE_IFSC` | `^[A-Z]{4}0[A-Z0-9]{6}$` |
| `RE_PHONE` | `^\+[0-9]{1,3}[0-9]{7,12}$` |
| `RE_MSME` | `^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$` |
| `RE_URL` | `^https?://[^\s]+\.[^\s]+$` |

**Allowed values:**
- `company_type`: Private Limited, Public Limited, LLP, Partnership Firm, Sole Proprietorship
- `annual_turnover`: `<1 Cr`, `1-10 Cr`, `10-100 Cr`, `>100 Cr`
- `account_type`: Current, Savings
- `service_nature`: Core Banking Software, Cybersecurity Tool, Cloud Infrastructure, SaaS Platform, Data Analytics, HR/ERP Software, Network/Hardware, Other
- `cloud_provider`: AWS, Azure, GCP, Private Cloud, On-Premise, Hybrid, Not Applicable

**PAN 4th character → company type:**
| Char | Valid for |
|---|---|
| C | Private Limited, Public Limited |
| F | LLP, Partnership Firm |
| P | Sole Proprietorship |

**Cross-field checks:**
| Check | Fields |
|---|---|
| PAN 4th char vs company type | `pan_number`, `company_type` |
| GST state code (chars 1–2) vs state | `gst_number`, `state` |
| GST embedded PAN (chars 3–12) vs PAN | `gst_number`, `pan_number` |
| CIN year (chars 9–12, 0-indexed 8–11) vs incorporation year | `cin_number`, `incorporation_date` |
| Cyber insurance required if data processing | `processes_data`, `cyber_insurance` |
| ISO fields required if ISO certified | `iso_certified`, `iso_cert_number`, `iso_expiry_date` |
| MSME number format only | `msme_number` — no employee count or turnover restriction |
| DIN + CIN required for Pvt/Public Ltd | `company_type`, `din`, `cin_number` |
| DPIN + LLP number required for LLP | `company_type`, `dpin`, `llp_number` |

**Required documents per submission:**
| `doc_type` | Required When |
|---|---|
| `pan_card` | Always |
| `cancelled_cheque` | Always |
| `gst_cert` | `gst_registered = true` |
| `incorporation` | `company_type` in Pvt/Public Ltd |
| `llp_agreement` | `company_type = LLP` |
| `partnership_deed` | `company_type = Partnership Firm` |
| `iso_cert` | `iso_certified = true` |
| `dpa` | `processes_data = true` |
| `msme_cert` | `msme_number` provided |

Free email domains blocked for `contact_email`: gmail.com, yahoo.com, hotmail.com, outlook.com, rediffmail.com, yahoo.in, ymail.com.

---

## API Endpoints

### `POST /api/auth/login`
Creates or finds vendor by email. Returns JWT token.
```json
Request:  { "email": "vendor@company.com" }
Response: { "token": "eyJ...", "vendor_id": "uuid" }
```

---

### `POST /api/documents/upload`
Uploads file to Supabase Storage, upserts doc row.
- Auth: Bearer token required
- Body: `multipart/form-data` — fields: `file`, `doc_type`, `application_id` (optional, unused now)
- Validates: extension (.pdf/.jpg/.jpeg/.png), min size 10KB, max size 10MB
- Upsert: if NULL row of same `(vendor_id, doc_type)` exists → update in-place; else insert
```json
Response: { "doc_id": "uuid", "file_url": "https://...", "doc_type": "pan_card" }
```

---

### `GET /api/documents/`
Returns all doc rows for this vendor (floating + linked to any version).
- Auth: Bearer token required
- Used by frontend on page load to pre-populate "✓ Uploaded" state
```json
Response: [
  { "doc_type": "pan_card", "file_name": "pan.jpg", "file_url": "https://..." },
  { "doc_type": "cancelled_cheque", "file_name": "cheque.jpg", "file_url": "https://..." }
]
```

---

### `POST /api/application/submit`
Runs full validation. Upserts using draft-in-place logic.
- Auth: Bearer token required
- Body: JSON with any/all form fields
- Doc validation checks ALL vendor docs ever uploaded (no version filter)
- If errors → status = `draft`, errors returned (all correct fields still saved)
- If clean → status = `submitted`
```json
Response (clean):  { "application_id": "uuid", "status": "submitted", "version": 2, "errors": [] }
Response (errors): { "application_id": "uuid", "status": "draft",     "version": 2, "errors": ["PAN ..."] }
```

---

### `POST /api/application/draft`
Saves form data in-place without validation.
- Auth: Bearer token required
- Body: JSON with any/all form fields
```json
Response: { "application_id": "uuid", "status": "draft", "version": 1 }
```

---

### `GET /api/application/status`
Returns latest submission for this vendor (highest version number).
- Auth: Bearer token required
```json
Response: { "application_id": "uuid", "status": "submitted", "submitted_at": "...", "version": 2 }
// If no submissions yet:
Response: { "application": null }
```

---

### `GET /api/application/{id}`
Returns a specific application row by UUID.
- Auth: Bearer token required
```json
Response: { full application row as JSON }
```

---

### `DELETE /api/documents/all`
Deletes all documents for this vendor from documents table.
- Auth: Bearer token required
- Use case: test runner cleanup before each test run

---

### `DELETE /api/application/reset`
Deletes all applications for this vendor.
- Auth: Bearer token required
- Use case: test runner cleanup before each test run

---

## Key Functions in `routers/application.py`

```python
def _upsert_application(sb, vendor_id, data) -> tuple[str, int]:
    # draft exists → update in-place
    # no draft + submitted → insert new, version = latest + 1
    # nothing → insert new, version = 1

def _link_docs(sb, vendor_id, app_id):
    # SET application_id = app_id WHERE vendor_id = vendor_id AND application_id IS NULL
    # Stamps floating docs to current app. Previous versions' docs untouched.

def _get_uploaded_doc_types(sb, vendor_id) -> list[str]:
    # SELECT doc_type FROM documents WHERE vendor_id = vendor_id
    # Returns all doc_types ever uploaded — no application_id filter.
    # Simple. Demo-scale. Computationally heavier than version-scoped query but no edge cases.
```

---

## Environment Variables

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=sb_secret_...
JWT_SECRET=any_long_random_string
```

Note: Supabase new UI renamed keys — "Publishable key" = old anon, "Secret key" = old service_role. Use Secret key here.

---

## Folder Structure

```
vendor_onbording_backend/
├── main.py
├── requirements.txt
├── .env
├── .env.example
├── phase1_claude_code_prompt.md  ← this file
├── validation_rules.md
├── routers/
│   ├── auth.py              — POST /api/auth/login
│   ├── documents.py         — POST /upload, GET /, DELETE /all
│   └── application.py       — POST /submit, POST /draft, GET /status, GET /{id}, DELETE /reset
├── services/
│   ├── supabase_client.py
│   ├── jwt_service.py
│   └── validation.py
└── models/
    └── schemas.py
```

---

## Run Locally

```bash
cd vendor_onbording_backend
source ../zamp_venv/bin/activate
uvicorn main:app --reload --port 8000
# API docs at: http://localhost:8000/docs
```

---

## Known Gotchas

| Issue | Fix |
|---|---|
| `supabase_url is required` | .env must have no spaces: `SUPABASE_URL=https://xxx...` |
| `date is not JSON serializable` | Use `model_dump(mode="json", exclude_none=True)` — converts `date` to ISO string |
| `Invalid token` 401 | JWT_SECRET changed after login — re-login to get fresh token |
| Frontend ECONNREFUSED | Backend not running — need two terminals (backend + frontend) |
| `False` value triggers "Specify..." error | `model_dump(exclude_none=True)` keeps `False`; only `None` excluded. If frontend sends `null`, Pydantic sets `None` → excluded → backend sees missing field → error. Fix: initialize all boolean form fields to `false` not `null`. |
| Supabase `.is_()` syntax | Use `.is_("application_id", "null")` for NULL checks in Python client |
| Supabase OR query | `.or_(f"application_id.eq.{draft_id},application_id.is.null")` |

---

## Phase 1 Status — COMPLETE

All endpoints built and tested. 11 test cases pass (10 automated + 1 manual trail test).

## What Is NOT Built Yet (Phase 2)

| Feature | Notes |
|---|---|
| OCR — extract text from uploaded documents | Use pytesseract or Google Vision API. Extract PAN from pan_card image, IFSC from cheque, etc. |
| AI field matching — compare OCR output to form fields | e.g. PAN extracted from image must match pan_number field. Flag mismatches. |
| AI fuzzy name check — account_holder_name vs company_name | Levenshtein / fuzzy match. Phase 1 passes this through unchecked. |
| Risk score (0–100) per submission | Weighted sum of flags: offshore data, no ISO, no SOC2, free email, etc. |
| Reviews table | One row per submission: `{ application_id, risk_score, flags[], verdict, reviewer_note }` |
| OTP email verification on login | Phase 3 |
| Admin dashboard | Phase 4 |
| GET /history — all versions for a vendor | Backlog |
