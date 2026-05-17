# AI Check Pipeline — Implementation Reference
> Runs after OCR pipeline completes on every clean submit.
> Last updated: May 2026

---

## Purpose

The AI pipeline is the third validation layer that runs after a vendor submits. It catches things rule-based validation and simple OCR cannot:
- Document content doesn't match what the vendor typed in the form
- Documents are obscured, morphed, or belong to a different entity
- Risk signals like low insurance coverage, offshore data storage, suspicious employee/turnover ratios

---

## Full Validation Flow (All Three Layers)

```
VENDOR FILLS FORM + UPLOADS DOCS
           │
           ▼
┌─────────────────────────────────────────────┐
│  LAYER 1 — RULE-BASED VALIDATION            │
│  Runs at: POST /api/application/submit       │
│  Runs on: form fields only (what vendor typed│
│                                             │
│  Checks:                                    │
│  • Required fields present                  │
│  • Regex format (PAN, GST, CIN, IFSC...)    │
│  • Cross-field logic (PAN char vs type,     │
│    GST state code vs state, CIN year vs     │
│    incorporation year)                      │
│  • Required documents uploaded              │
│  • No free email domains                    │
│                                             │
│  Result: PASS → status=submitted            │
│          FAIL → status=draft, errors[]      │
│                returned to vendor           │
└─────────────────────────────────────────────┘
           │ PASS only
           ▼
┌─────────────────────────────────────────────┐
│  LAYER 2 — OCR PIPELINE                     │
│  Runs at: background task after clean submit │
│  Runs on: uploaded document files           │
│                                             │
│  For each doc:                              │
│  • Download from Supabase Storage           │
│  • Route by extension: PDF → pdfplumber     │
│                        JPG/PNG → pytesseract│
│  • Extract structured fields                │
│  • Store in documents.ocr_json              │
│  • Set documents.ocr_status                 │
│                                             │
│  ocr_status values:                         │
│  not_started → processing → done/failed     │
│                                             │
│  Result: ocr_json populated per doc row     │
└─────────────────────────────────────────────┘
           │ always (even if some docs failed)
           ▼
┌─────────────────────────────────────────────┐
│  LAYER 3 — AI PIPELINE                      │
│  Runs at: end of OCR pipeline (chained)     │
│  Runs on: form fields + OCR results         │
│                                             │
│  Steps:                                     │
│  1. Pre-compute exact matches in code       │
│  2. Flag detection LLM (Ollama/Groq)        │
│     → user_flags, risk_factors,             │
│       unreadable_docs                       │
│  3. Risk scoring in code (pure math)        │
│     → risk_score, decision,                 │
│       notified_factors                      │
│  4. Reasoning LLM (Haiku/Ollama)            │
│     → risk_reasoning (plain English note)   │
│  5. Store all in reviews table              │
│  6. (Future) Email vendor user_flags        │
│                                             │
│  ai_status values:                          │
│  not_started → processing → done/failed     │
│                                             │
│  Result: reviews row fully populated        │
└─────────────────────────────────────────────┘
```

---

## Why Three Layers

| Layer | Catches | Can't catch |
|---|---|---|
| Rule-based | Wrong format, missing fields, missing docs | Doc content vs form mismatch |
| OCR | Extracts what's actually in the document | Whether it matches the form |
| AI | Mismatches, fuzzy names, risk signals, partial reads | Already caught by layers 1-2 |

**Key insight:** Layer 1 trusts the vendor's input. Layer 3 verifies it against the actual documents.

Example: Vendor types `gst_number = 27AABCT1234M1Z5` (Maharashtra, valid format). Layer 1 passes it. But if the uploaded GST certificate has a different PAN embedded — layers 1 and 2 miss this. Layer 3 catches it via `ocr_gstin_pan_matches_form_pan`.

---

## Model

**Active: Groq API — LLaMA 3.3 70B Versatile**
- Fast inference (~300 tokens/sec on Groq)
- Cheap ($0.59/1M input tokens)
- Flag detection uses `response_format: json_object` (structured JSON)
- Reasoning uses plain text (temperature 0.3)
- Env var: `GROQ_API_KEY`
- Free tier: 100K tokens/day (~40 calls/day at current prompt size)
- Both `_call_llm` and `_call_reasoning_llm` use Groq

**Fallback: Ollama local — llama3.1:8b (commented out in code)**
- Runs on `http://localhost:11434`
- No rate limits, free, instant switch
- Quality noticeably worse — misses conditional rules, hallucinates more
- Use only for structural/flow testing, not prompt quality validation
- Switch in `services/ai_service.py` — comment/uncomment two blocks in `_call_llm` and `_call_reasoning_llm`

---

## Database Schema

```sql
CREATE TABLE reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id UUID REFERENCES applications(id) UNIQUE,
  vendor_id UUID REFERENCES vendors(id),
  user_flags JSONB,
  risk_factors JSONB,
  unreadable_docs JSONB,
  ai_status TEXT DEFAULT 'not_started',
  created_at TIMESTAMP DEFAULT NOW()
);
```

`UNIQUE` on `application_id` — one review per submission. Retry on failure updates existing row, no duplicate.

**ai_status lifecycle:** `not_started → processing → done / failed`

---

## AI Pipeline Flow (`services/ai_service.py`)

```
run_ai_pipeline(app_id, vendor_id)
    │
    ├─ upsert reviews row: ai_status = 'processing'
    │
    ├─ fetch application row (all 31 form fields)
    │
    ├─ fetch latest doc per doc_type across ALL vendor versions (not just current app_id)
    │    → SELECT doc_type, ocr_json, ocr_status ORDER BY uploaded_at DESC, dedupe by doc_type
    │    → if vendor re-uploaded doc in v2 → picks v2 (newer). if not re-uploaded → picks v1.
    │    → only includes docs where ocr_json IS NOT NULL (OCR has run)
    │
    ├─ _build_ocr_summary()
    │    → flat dict: { doc_type: { status, ...extracted_fields } }
    │    → strips raw_text to keep prompt small
    │
    ├─ _compute_exact_matches()
    │    → returns flat dict of true/false/"partial"/null per check
    │    → see "Exact Matches" section below
    │
    ├─ _call_llm(form, ocr_summary, exact_matches)
    │    → _compute_exact_match_context() converts raw values → labeled strings
    │    → _compute_company_age_years() pre-computes age, removes incorporation_date
    │    → sends { today, form, ocr, exact_match_context } to flag detection LLM
    │    → temperature=0.1 (Groq) / 0.0 (Ollama)
    │    → returns user_flags, risk_factors, unreadable_docs
    │
    ├─ upsert reviews row: ai_status = 'done'
    │    user_flags, risk_factors, unreadable_docs stored
    │
    └─ compute_risk_score_and_store()
         ├─ _compute_notified_factors() → which risk_factors had a user_flag
         ├─ _base_score() → weighted sum of current risk_factors (capped 100)
         ├─ fetch prior reviews for this vendor (with their notified_factors)
         ├─ _cross_version_delta() → decay-weighted escalation/resolution
         ├─ _decision() → approved/waiting_for_response/human_review/high_risk_review/rejected
         ├─ _call_reasoning_llm() → plain English note for reviewer (Haiku/Ollama)
         └─ upsert reviews row: risk_score, decision, notified_factors, risk_reasoning
```

On any exception → `ai_status = 'failed'`, error stored in `risk_factors`.

---

## Exact Match Values — Four States (Internal)

`_compute_exact_matches()` returns raw values. These are NOT sent directly to LLM.

| Value | Meaning |
|---|---|
| `true` | Confirmed match |
| `false` | Confirmed mismatch |
| `"partial"` | Doc OCR succeeded but this specific field is null |
| `null` | Whole doc OCR failed, OR doc not required for this vendor |

**Why `"partial"` is a double flag:** OCR reading a doc but missing a specific field is suspicious — could be obscured, damaged, or edited. Different from a fully unreadable doc. Vendor must re-upload AND reviewer is notified as fraud signal.

---

## Exact Match Context Labels (What LLM Sees)

`_compute_exact_match_context()` converts raw values → plain-English strings. This is what the LLM receives in `exact_match_context`. Purpose: LLM was hallucinating on raw null/true/false — labeled strings tell it exactly WHY and what to do.

| Label | When | LLM Action |
|---|---|---|
| `"verified"` | value = true | Skip. No flag. |
| `"mismatch — value extracted from {doc_type} does not match form"` | value = false | `user_flags` high severity |
| `"partial_read — {doc_type} OCR succeeded but this field is null; possible obscured or edited document"` | value = "partial" | `user_flags` medium + `risk_factors` medium |
| `"doc_ocr_failed — {doc_type} could not be read at all"` | value = null + doc failed | `unreadable_docs` + `risk_factors` low |
| `"not_applicable — {doc_type} was not required for this vendor"` | value = null + doc not in ocr | Skip entirely. No flag, no risk factor. |

**Key rule:** `not_applicable` overrides everything — even if `form.iso_expiry_date` is in the past, if `iso_cert_number` is `not_applicable`, no ISO flags are fired.

---

## Exact Matches (Pre-Computed in Code)

All computed in `_compute_exact_matches()`. Results sent to LLM — LLM generates the message, not the code.

### Form Field vs OCR Extracted Value

| Key | Form Field | OCR Field | Doc |
|---|---|---|---|
| `pan_number` | `pan_number` | `pan_number` | pan_card |
| `ifsc_code` | `ifsc_code` | `ifsc_code` | cancelled_cheque |
| `account_number` | `account_number` | `account_number` | cancelled_cheque |
| `gst_number` | `gst_number` | `gstin` | gst_cert |
| `cin_number` | `cin_number` | `cin_number` | incorporation |
| `llp_number` | `llp_number` | `llp_number` | llp_agreement |
| `msme_number` | `msme_number` | `udyam_number` | msme_cert |
| `iso_cert_number` | `iso_cert_number` | `cert_number` | iso_cert |

### OCR Cross-Checks (Derived from Doc Content)

Rule-based at submit checks vendor-typed fields only. These check the actual document content against form fields — catches wrong entity's document uploaded.

| Key | Logic | What It Catches |
|---|---|---|
| `ocr_gstin_state_matches_form_state` | GST cert chars[0:2] vs `STATE_GST_CODES[form.state]` | Wrong state's GST cert uploaded |
| `ocr_gstin_pan_matches_form_pan` | GST cert chars[2:12] vs form `pan_number` | GST cert belongs to different entity |
| `ocr_pan_4th_char_matches_company_type` | PAN card char[3] vs allowed chars for `company_type` | PAN card is for wrong entity type |

---

## What LLM Receives

`incorporation_date` is removed from form. Replaced with `company_age_years` (pre-computed int).

Raw `exact_matches` (true/false/"partial"/null) are NOT sent to LLM. They are converted to `exact_match_context` — plain-English labeled strings that explain WHY each value is what it is. See "Exact Match Context Labels" section below.

`today` (ISO date string) is added to user content so LLM can evaluate date comparisons like iso_expiry_date in the past.

```json
{
  "today": "2026-05-17",
  "form": {
    "company_name": "Test Corp Private Limited",
    "company_type": "Private Limited",
    "pan_number": "AABCT1234M",
    "state": "Maharashtra",
    "annual_turnover": "1-10 Cr",
    "employee_count": 450,
    "iso_certified": true,
    "iso_expiry_date": "2024-03-01",
    "processes_data": true,
    "soc2_audited": false,
    "data_in_india": false,
    "cyber_insurance": true,
    "cyber_coverage_crores": 1.0,
    "company_age_years": 2,
    "...all fields except incorporation_date..."
  },
  "ocr": {
    "pan_card":         { "status": "done", "pan_number": "AABCT1234M", "name_on_card": "TEST CORP PVT LTD" },
    "cancelled_cheque": { "status": "done", "ifsc_code": "HDFC0001234", "account_number": "003601234567", "account_holder_name": "Test Corp" },
    "gst_cert":         { "status": "done", "gstin": "27AABCT1234M1Z5", "legal_name": "Test Corp Private Limited" },
    "incorporation":    { "status": "failed" },
    "dpa":              { "status": "done", "is_signed": false }
  },
  "exact_match_context": {
    "pan_number":      "verified",
    "ifsc_code":       "verified",
    "account_number":  "verified",
    "gst_number":      "verified",
    "cin_number":      "doc_ocr_failed — incorporation could not be read at all",
    "llp_number":      "not_applicable — llp_agreement was not required for this vendor",
    "msme_number":     "not_applicable — msme_cert was not required for this vendor",
    "iso_cert_number": "partial_read — iso_cert OCR succeeded but this field is null; possible obscured or edited document",
    "ocr_gstin_state_matches_form_state":   "verified",
    "ocr_gstin_pan_matches_form_pan":        "verified",
    "ocr_pan_4th_char_matches_company_type": "verified"
  }
}
```

---

## LLM Output Schema

The system prompt gives LLM the exact output format to follow. All three keys must always be present even if empty array. No extra keys allowed.

```json
{
  "user_flags": [
    {
      "field": "<form field name or doc_type this flag relates to>",
      "severity": "<exactly one of: high, medium, low>",
      "message": "<clear message written to the vendor explaining what to fix>"
    }
  ],
  "risk_factors": [
    {
      "factor": "<short snake_case identifier e.g. iso_cert_expired, data_offshore>",
      "severity": "<exactly one of: high, medium, low>",
      "note": "<internal note for reviewer — NOT shown to vendor>"
    }
  ],
  "unreadable_docs": [
    {
      "doc_type": "<doc_type exactly as received e.g. pan_card, gst_cert>",
      "message": "<message written to the vendor asking to re-upload>"
    }
  ]
}
```

**Example output:**
```json
{
  "user_flags": [
    {
      "field": "dpa",
      "severity": "high",
      "message": "Data Processing Agreement is not signed. Please upload a signed copy."
    },
    {
      "field": "iso_cert",
      "severity": "high",
      "message": "ISO certificate expired on 2024-03-01. Please upload the renewed certificate."
    },
    {
      "field": "iso_cert_number",
      "severity": "medium",
      "message": "ISO certificate could not be fully read — certificate number field is missing. Please re-upload a clear, unedited copy."
    }
  ],
  "risk_factors": [
    {
      "factor": "iso_cert_expired",
      "severity": "high",
      "note": "ISO certificate expired March 2024. Vendor processes data but has no valid ISO cert."
    },
    {
      "factor": "partial_ocr_iso_cert",
      "severity": "medium",
      "note": "ISO certificate OCR read partially — cert_number field missing. Possible obscured or edited document."
    },
    {
      "factor": "data_offshore",
      "severity": "high",
      "note": "data_in_india=false. Vendor stores data outside India — RBI compliance risk."
    },
    {
      "factor": "processes_data_no_soc2",
      "severity": "medium",
      "note": "Vendor processes data but is not SOC2 audited."
    },
    {
      "factor": "employee_turnover_mismatch",
      "severity": "high",
      "note": "450 employees with 1-10 Cr turnover is inconsistent. Possible misrepresentation."
    },
    {
      "factor": "low_cyber_coverage",
      "severity": "medium",
      "note": "Cyber coverage of ₹1Cr is low for a data processor with 1-10 Cr turnover."
    },
    {
      "factor": "new_company",
      "severity": "low",
      "note": "Company incorporated June 2023 — less than 2 years old."
    }
  ],
  "unreadable_docs": [
    {
      "doc_type": "incorporation",
      "message": "Certificate of incorporation could not be read. Please re-upload a clear, unedited copy."
    }
  ]
}
```

### Output Constraints (enforced via system prompt)

| Constraint | Detail |
|---|---|
| All 3 keys always present | Even if no flags found — use empty array `[]` |
| `severity` values | Exactly one of: `high`, `medium`, `low` — no other strings |
| `factor` format | `snake_case` short identifier — e.g. `iso_cert_expired`, `data_offshore` |
| `partial` factor naming | Always `partial_ocr_<doc_type>` — e.g. `partial_ocr_gst_cert` |
| `doc_type` in unreadable_docs | Must match exact doc_type string from input — e.g. `pan_card`, `gst_cert` |
| No text outside JSON | System prompt explicitly says no markdown, no explanation, no ```json blocks |

### Severity Guide

| Severity | Meaning |
|---|---|
| `high` | Serious mismatch, compliance gap, or fraud signal |
| `medium` | Notable concern for reviewer |
| `low` | Informational, minor signal |

### Backend Impact of Output Format

None. `_call_llm()` does `json.loads(raw)` and stores all three keys as JSONB in `reviews` table. JSONB accepts any valid JSON — no DB schema change needed. No endpoint currently reads from `reviews` so format changes are fully contained in the prompt.

---

## All Checks the LLM Performs

### User Flags (shown to vendor)

| Check | Type | Trigger |
|---|---|---|
| PAN number mismatch | Exact → false | pan_number key |
| IFSC mismatch | Exact → false | ifsc_code key |
| Account number mismatch | Exact → false | account_number key |
| GST number mismatch | Exact → false | gst_number key |
| CIN number mismatch | Exact → false | cin_number key |
| LLP number mismatch | Exact → false | llp_number key |
| MSME number mismatch | Exact → false | msme_number key |
| ISO cert number mismatch | Exact → false | iso_cert_number key |
| Wrong entity GST cert (state) | Cross-check → false | ocr_gstin_state_matches_form_state |
| Wrong entity GST cert (PAN) | Cross-check → false | ocr_gstin_pan_matches_form_pan |
| Wrong PAN entity type | Cross-check → false | ocr_pan_4th_char_matches_company_type |
| Name on PAN card vs company_name | Fuzzy → LLM judges | ocr.pan_card.name_on_card vs form.company_name |
| Account holder vs company_name | Fuzzy → LLM judges | ocr.cancelled_cheque.account_holder_name vs form.account_holder_name |
| Company name on GST cert | Fuzzy → LLM judges | ocr.gst_cert.legal_name vs form.company_name |
| Company name suffix vs type | LLM judges | "Pvt Ltd" in name but type = LLP |
| DPA not signed | Direct OCR field | ocr.dpa.is_signed = false |
| ISO cert expired | Date comparison | form.iso_expiry_date < today |
| Partial read on any doc | partial value | Any exact_matches key = "partial" |
| Whole doc unreadable | null value (failed) | Any exact_matches key = null + doc ocr_status = failed |

### Risk Factors (internal, reviewer only)

| Factor | Signal |
|---|---|
| ISO cert expired | Vendor must renew; did they fix it in next version? |
| Partial OCR on any doc | Possible obscured or morphed document |
| `data_in_india = false` | RBI compliance risk |
| `processes_data = true` + `soc2_audited = false` | Security gap |
| `processes_data = true` + `iso_certified = false` | Security gap |
| Employee count vs turnover mismatch | Possible misrepresentation |
| Low cyber coverage relative to turnover | Underinsured for data processor |
| Company < 2 years old | New entity, limited track record |
| Service nature vs turnover implausible | "Core Banking Software" + `<1 Cr` = suspicious |
| Account holder name partial fuzzy match | Borderline name similarity |
| AI pipeline itself failed | Stored as risk_factor so reviewer knows check didn't run |

---

## Partial Read Handling

When `exact_matches` key = `"partial"` (doc OCR succeeded but specific field is null):

**LLM does two things:**
1. `user_flags` — "Document uploaded for {doc_type} could not be fully read. Please re-upload a clear, unedited copy."
2. `risk_factors` — "Partial OCR on {doc_type} — {field} missing. Possible obscured, damaged, or edited document."

**Why both:** Vendor may have uploaded legitimately poor quality scan (user flag fixes it). But partial reads are also a fraud vector — someone editing a document to remove a specific value. Reviewer needs to know regardless of whether vendor re-uploads.

---

## Folder Structure

```
services/
├── ocr_service.py       — OCR pipeline, calls run_ai_pipeline() at end
├── ai_service.py        — AI pipeline: exact checks + Groq call + reviews upsert
└── ocr_extractors/
    ├── pdf_extractor.py
    └── image_extractor.py
```

---

## Environment Variables

```
GROQ_API_KEY=gsk_...
```

---

## System Prompt Design — Key Decisions

### Why context labels instead of raw values
Initial approach sent `exact_matches: { "pan_number": true, "cin_number": null }` to LLM. LLM couldn't tell whether `null` meant doc failed or doc not applicable — hallucinated flags for not-uploaded docs. Switched to `exact_match_context` with labeled strings. LLM now knows exactly WHY each value is what it is.

### Why few-shot examples (10 total)
LLM without examples missed subtle patterns:
- Fuzzy name mismatch (Rajesh Kumar Mehta vs Silverline IT Solutions) — needed example 6
- not_applicable being skipped — needed examples 5, 7, 8, 9
- Deduplication of risk factors for same doc — needed example 10

### Bug fixes applied to system prompt (v2)
1. **processes_data false-positive**: LLM fired `processes_data_no_soc2`/`no_iso` even when `processes_data=false`. Fix: added explicit IMPORTANT block — "ONLY fire if form.processes_data IS EXACTLY true". Added example 9.
2. **Duplicate risk factors**: LLM created two risk factors for same doc (e.g. `partial_ocr_incorporation` + `ocr_failed_incorporation`). Fix: added deduplication rule — "at most ONE risk factor per doc_type". Added example 10.
3. **not_applicable hallucination**: LLM saw `form.iso_expiry_date` in past and fired ISO flags even when `iso_cert_number` = `not_applicable`. Fix: added explicit override rule — "not_applicable overrides form fields". Added examples 8 and 9.

### Bug fixes applied to system prompt (v3)
4. **company_age_years=null in test runner**: `_call_llm` was overwriting pre-computed `company_age_years` from test input with None when `incorporation_date` was already stripped. Fix: only compute if `company_age_years` not already in form dict.
5. **Invented risk factors (data_offshore when data_in_india=true)**: LLM invented risk factor names not in the allowed list. Fix: added "ONLY create risk_factors for conditions explicitly listed" + explicit guard on `data_in_india` condition + example 11.
6. **iso_cert_expired missing from user_flags**: LLM had no `today` date in prompt so couldn't evaluate "in the past". Fix: added `today` field to user content JSON. Also clarified rule must fire BOTH user_flag + risk_factor. Added example 12.
7. **Duplicate user_flags for same field (gst_number)**: Both `gst_number` mismatch and `ocr_gstin_pan_matches_form_pan` mismatch firing as separate user_flags for `gst_number`. Fix: if both fire, merge into one user_flag; cross-check only adds a `gst_cert_entity_mismatch` risk_factor. Clarified in cross-check section.
8. **processes_data_no_iso false-positive on expired cert**: LLM inferred "not ISO certified" from expired cert even when `form.iso_certified=true`. Fix: added explicit rule — processes_data_no_iso checks form.iso_certified field ONLY, not expiry date.

### Why temperature=0.1
Need deterministic structured output — lower temperature reduces variation. Not 0 because occasional creative phrasing in messages is acceptable; only the structure needs to be consistent.

### Why `response_format: json_object`
Groq enforces JSON-only output. Without it, LLM sometimes wraps with ```json ``` blocks or adds explanation text. With it, `json.loads()` in `_call_llm()` is safe.

---

## Risk Scoring Pipeline

Runs immediately after the AI flag detection pipeline writes `risk_factors`. Pure code — no LLM involved.

---

### New columns on reviews table

```sql
ALTER TABLE reviews
  ADD COLUMN risk_score       INTEGER,
  ADD COLUMN decision         TEXT,
  ADD COLUMN notified_factors JSONB,
  ADD COLUMN risk_reasoning   TEXT;
```

---

### Phase 1 — Base score (current version only)

Read `risk_factors` JSONB column from current reviews row. Weighted sum:

| Severity | Points |
|---|---|
| high | 10 |
| medium | 5 |
| low | 2 |

Sum all factors → cap at 100. This is the base score.

---

### Phase 2 — Cross-version adjustment with decay

Fetch all prior reviews rows for same vendor ordered by version descending. For each prior version compute influence weight using exponential decay:

```
weight = 0.5 ^ distance
```

- v-1 (immediate previous) → weight = 1.0
- v-2 → weight = 0.5
- v-3 → weight = 0.25
- and so on

For each prior version's `risk_factors`:
- Factor **still present** in current version → `+5 × weight` (vendor ignored it — escalation)
- Factor **gone** in current version → `-3 × weight` (vendor fixed it — positive signal)

Sum all deltas → round → add to base score → clamp 0–100.

**Why decay:** v1 flags matter less than v2 flags when computing v3 score. Old unfixed issues are less suspicious than recently introduced ones. Recent behaviour is stronger signal.

---

### Decision thresholds

| Score | Decision | Meaning |
|---|---|---|
| 0–5 | approved | Zero/trivial flags. Reviewer glances at signing. |
| 6–50, user_flags non-empty | waiting_for_response | Vendor was notified. Awaiting v2. |
| 6–50, user_flags empty | human_review | Internal risks only. No email sent. Human must review. |
| 51–75 | human_review | Serious flags. Reviewer reads carefully. |
| 76–89 | high_risk_review | Multiple serious flags. Senior reviewer urgently. |
| 90–100 | rejected | Extreme fraud/risk signals. Auto-reject. |

**v1 auto-approve logic:** score 0–5 means zero meaningful flags (only `low` severity at most). Any `medium` or `high` flag pushes score above 5 → human_review minimum.

**`rejected`** also sets `applications.status = rejected`.

---

### notified_factors — what it is and why

`notified_factors` = list of risk_factor names that had a corresponding `user_flag` in the same version. Stored per reviews row.

**Why:** Cross-version escalation only applies to factors the vendor was explicitly told about. If `data_offshore` fires but vendor was never emailed about it, penalising them for "not fixing" it is unfair. Only notified factors escalate.

Mapping is hardcoded in `RISK_FACTOR_TO_FLAG_FIELD` in `ai_service.py`. Internal-only factors (`data_offshore`, `processes_data_no_soc2`, `employee_turnover_mismatch`, etc.) are not in the map — never escalate.

---

### Cross-version decay formula

```
weight = 0.5 ^ (distance - 1)

v-1 (most recent prior)  → weight 1.0
v-2                      → weight 0.5
v-3                      → weight 0.25
```

For each prior version:
- Notified factor still present in current → `+5 × weight`
- Notified factor resolved in current → `-3 × weight`

Sum all deltas → round → add to base → clamp 0–100.

---

### Reasoning LLM — `_call_reasoning_llm()`

Runs after scoring. Produces `risk_reasoning` — plain English note for human reviewer.

**Input (built by `build_reasoning_input()`):**
```json
{
  "vendor_id": "...",
  "versions": [
    {
      "version": 1,
      "risk_factors": [...],
      "notified_factors": [...],
      "risk_score": 42,
      "decision": "waiting_for_response"
    }
  ]
}
```

**Model:** Groq (LLaMA 3.3 70B) — active. Ollama 8B — commented fallback.

**Why not Ollama 8B for reasoning:** 8B hallucinates facts (says score increased when it decreased), misses cross-version escalation narrative, gives generic notes. Groq 70B correctly identifies patterns like "vendor ignored two explicit requests across two cycles" and gives actionable reviewer recommendations.

**Temperature:** 0.3 — slightly higher than flag detection (0.1) because reasoning benefits from natural language variation. Structure not required here.

**Output:** Plain text, 3–5 sentences. No JSON. Stored in `reviews.risk_reasoning`.

**Score/decision not repeated** — reviewer already sees those fields. LLM focuses on WHY and WHAT NEXT.

**Switch to Ollama fallback:** Comment Groq block, uncomment Ollama block in `_call_reasoning_llm()`.

---

### Flow (chained into `run_ai_pipeline()`)

```
run_ai_pipeline()
    │
    ├─ [existing] LLM writes user_flags + risk_factors + unreadable_docs
    │
    └─ _compute_risk_score_and_store()
         ├─ Phase 1: base score from current risk_factors
         ├─ Phase 2: cross-version decay adjustment from prior reviews
         ├─ Compute decision
         ├─ Write risk_score + decision to reviews row
         └─ If auto_reject → set applications.status = rejected
```

---

## Status

**AI Flag Detection Pipeline — COMPLETE**
- `services/ai_service.py` — exact matches, context labels, Groq LLM call, reviews upsert
- `ocr_service.py` chains `run_ai_pipeline()` at end of OCR loop
- 7 test cases in `ai_test_runner.py`, results in `ai_test_output.json`
- Groq (llama-3.3-70b-versatile) active. Ollama (llama3.1:8b) commented in as fallback.

**Risk Scoring + Reasoning — COMPLETE**
- `compute_risk_score_and_store()` — base score, cross-version delta, decision, notified_factors
- `_call_reasoning_llm()` — Groq (active) / Ollama 8B (fallback) plain English reviewer note
- `risk_test_runner.py` — 5 test cases, all passing, reasoning output verified

**Pending SQL (run on Supabase):**
```sql
-- reviews table (if not created yet)
CREATE TABLE reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id UUID REFERENCES applications(id) UNIQUE,
  vendor_id UUID REFERENCES vendors(id),
  user_flags JSONB,
  risk_factors JSONB,
  unreadable_docs JSONB,
  ai_status TEXT DEFAULT 'not_started',
  created_at TIMESTAMP DEFAULT NOW()
);

-- new columns (add if table already exists)
ALTER TABLE reviews
  ADD COLUMN risk_score       INTEGER,
  ADD COLUMN decision         TEXT,
  ADD COLUMN notified_factors JSONB,
  ADD COLUMN risk_reasoning   TEXT;
```

**To switch reasoning LLM to Haiku:**
1. Add `ANTHROPIC_API_KEY` to `.env`
2. `pip install anthropic`
3. Uncomment Anthropic block in `_call_reasoning_llm()`, comment Ollama block
