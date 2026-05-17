# AI Check Pipeline — Implementation Reference
> Runs after OCR pipeline completes on every clean submit.
> Last updated: May 2026 (bug fixes + new checks)

---

## Purpose

The AI pipeline is the third validation layer that runs after a vendor submits. It catches things rule-based validation and simple OCR cannot:
- Document content doesn't match what the vendor typed in the form
- Documents are obscured, morphed, or belong to a different entity
- Risk signals like low insurance coverage, offshore data storage, suspicious employee/turnover ratios
- Cross-version escalation when vendor ignores flagged issues across resubmissions

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
│  2. Call Groq LLaMA 3.3 70B                 │
│  3. LLM judges fuzzy names + risk factors   │
│     + partial reads                         │
│  4. Store flags + risk_factors in reviews   │
│  5. Compute risk score (base + cross-version│
│     delta); determine decision              │
│  6. Email vendor if user_flags non-empty    │
│                                             │
│  ai_status values:                          │
│  not_started → processing → done/failed     │
│                                             │
│  Result: reviews row with score + decision  │
└─────────────────────────────────────────────┘
```

---

## Why Three Layers

| Layer | Catches | Can't catch |
|---|---|---|
| Rule-based | Wrong format, missing fields, missing docs | Doc content vs form mismatch |
| OCR | Extracts what's actually in the document | Whether it matches the form |
| AI | Mismatches, fuzzy names, risk signals, partial reads, cross-version escalation | Already caught by layers 1-2 |

**Key insight:** Layer 1 trusts the vendor's input. Layer 3 verifies it against the actual documents.

---

## Model

**Groq API — LLaMA 3.3 70B Versatile**
- Fast inference (~300 tokens/sec on Groq)
- Cheap ($0.59/1M input tokens)
- Structured JSON output via `response_format: json_object`
- Env var: `GROQ_API_KEY`

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
  notified_factors JSONB,
  ai_status TEXT DEFAULT 'not_started',
  risk_score INTEGER,
  decision TEXT,
  risk_reasoning TEXT,
  email_sent_at TIMESTAMPTZ,
  created_at TIMESTAMP DEFAULT NOW()
);
```

`UNIQUE` on `application_id` — one review per submission. Retry on failure updates existing row, no duplicate.

`email_sent_at` — set atomically before sending email. Prevents double-send if pipeline is triggered twice.

**ai_status lifecycle:** `not_started → processing → done / failed`

---

## AI Pipeline Flow (`services/ai_service.py`)

```
run_ai_pipeline(app_id, vendor_id)
    │
    ├─ upsert reviews row: ai_status = 'processing'
    │
    ├─ fetch application row (all 36 form fields)
    │
    ├─ fetch latest doc per doc_type across ALL vendor versions
    │    → query all vendor docs ORDER BY uploaded_at DESC
    │    → two-pass dedupe by doc_type in Python:
    │       Pass 1: pick newest doc with ocr_json != null (successful OCR)
    │       Pass 2: for doc_types with no successful OCR, pick newest doc with ocr_status="failed"
    │    → ensures OCR-failed docs enter ocr_summary as {status: "failed"} — not silently skipped
    │    → if vendor re-uploaded in v2 → picks v2; else falls back to v1
    │
    ├─ build OCR summary
    │    → flat dict: { doc_type: { status, ...extracted_fields } }
    │    → strips raw_text to keep prompt small
    │
    ├─ compute exact matches
    │    → returns flat dict of true/false/"partial"/null per check
    │    → see "Exact Matches" section below
    │
    ├─ call flag detection LLM (Groq LLaMA 3.3 70B)
    │    → converts raw match values → plain-English context labels
    │    → pre-computes company_age_years, removes incorporation_date
    │    → sends { today, form, ocr, exact_match_context } to Groq
    │    → temperature=0.1, response_format=json_object
    │    → returns user_flags, risk_factors, unreadable_docs
    │
    ├─ upsert reviews row: ai_status = 'done'
    │    user_flags, risk_factors, unreadable_docs stored
    │
    ├─ compute risk score + store
    │    → base score: weighted sum of risk_factors (high=10, med=5, low=2, cap 100)
    │    → cross-version delta: decay-weighted escalation/resolution from prior versions
    │    → decision: approved / waiting_for_response / human_review / high_risk_review / rejected
    │    → call reasoning LLM (Groq) → plain English reviewer note
    │    → store risk_score, decision, notified_factors, risk_reasoning
    │    → if rejected → set applications.status = rejected
    │
    └─ send vendor email (Resend)
         → only if user_flags non-empty AND decision != rejected
         → atomic email_sent_at claim prevents double-send on retry
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

`_compute_exact_match_context()` converts raw values → plain-English strings. LLM receives these in `exact_match_context`.

| Label | When | LLM Action |
|---|---|---|
| `"verified"` | value = true | Skip. No flag. |
| `"mismatch — ..."` | value = false | `user_flags` high + `risk_factors` high (`<field>_mismatch`) |
| `"partial_read — ..."` | value = "partial" | `user_flags` medium + `risk_factors` medium |
| `"doc_ocr_failed — ..."` | value = null + doc failed | `unreadable_docs` + `user_flags` medium (one per doc) + `risk_factors` low |
| `"not_applicable — ..."` | value = null + doc not in ocr | Skip entirely. No flag, no risk factor. |

**Key rule:** `not_applicable` overrides everything — even if `form.iso_expiry_date` is in the past, if `iso_cert_number` is `not_applicable`, no ISO flags are fired.

**Mismatch → both user_flag and risk_factor:** Every exact mismatch means the doc shows a different value than what the vendor declared. This is both a vendor action item (fix the doc) and a risk signal (scored and tracked across versions). `incorporation_date` mismatch is medium severity because date format differences are common.

---

## Exact Matches (Pre-Computed in Code)

All computed in `_compute_exact_matches()`.

### Form Field vs OCR Extracted Value

| Key | Form Field | OCR Field | Doc | Severity if Mismatch |
|---|---|---|---|---|
| `pan_number` | `pan_number` | `pan_number` | pan_card | high |
| `ifsc_code` | `ifsc_code` | `ifsc_code` | cancelled_cheque | high |
| `account_number` | `account_number` | `account_number` | cancelled_cheque | high |
| `gst_number` | `gst_number` | `gstin` | gst_cert | high |
| `cin_number` | `cin_number` | `cin_number` | incorporation | high |
| `incorporation_date` | `incorporation_date` | `incorporation_date` | incorporation | medium |
| `llp_number` | `llp_number` | `llp_number` | llp_agreement | high |
| `msme_number` | `msme_number` | `udyam_number` | msme_cert | high |
| `iso_cert_number` | `iso_cert_number` | `cert_number` | iso_cert | high |
| `iso_expiry_date` | `iso_expiry_date` | `expiry_date` | iso_cert | medium |

`iso_expiry_date` comparison normalizes formats (YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY) before comparing.

### Presence-Only Checks (OCR Status Tracking — No Form Comparison)

These keys exist in `exact_match_context` solely to surface OCR status for docs that have no numeric/date field to compare against. The LLM uses them only to detect `partial_read` and `doc_ocr_failed` — actual field value checks are done directly from `ocr` by the LLM.

| Key | Doc | Representative Field | Purpose |
|---|---|---|---|
| `dpa_is_signed` | dpa | `is_signed` | Get DPA OCR status into context; LLM checks `ocr.dpa.is_signed` directly |
| `partnership_firm_name` | partnership_deed | `firm_name` | Get partnership_deed OCR status into context; LLM does fuzzy name check from `ocr` |

**Return values:** `True` = field present (any value); `"partial"` = doc done but field missing; `None` = doc failed or not uploaded. Never returns `False` — no form comparison.

`incorporation_date` comparison normalizes formats (YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY) before comparing.

### OCR Cross-Checks (Derived from Doc Content)


These check doc content against form fields — catches wrong entity's document uploaded.

| Key | Logic | What It Catches | Severity if Mismatch |
|---|---|---|---|
| `ocr_gstin_state_matches_form_state` | GST cert chars[0:2] vs `STATE_GST_CODES[form.state]` | Wrong state's GST cert | high |
| `ocr_gstin_pan_matches_form_pan` | GST cert chars[2:12] vs form `pan_number` | GST cert for different entity | high |
| `ocr_pan_4th_char_matches_company_type` | PAN card char[3] vs allowed chars for `company_type` | PAN for wrong entity type | high |

---

## What LLM Receives

`incorporation_date` is removed from form before LLM call. Replaced with `company_age_years` (pre-computed int). Raw `exact_matches` are converted to `exact_match_context` labeled strings.

```json
{
  "form": { "...all fields except incorporation_date...", "company_age_years": 2 },
  "ocr": {
    "pan_card":         { "status": "done", "pan_number": "AABCT1234M", "name_on_card": "TEST CORP PVT LTD" },
    "cancelled_cheque": { "status": "done", "ifsc_code": "HDFC0001234", "account_number": "003601234567", "account_holder_name": "Test Corp" },
    "gst_cert":         { "status": "done", "gstin": "27AABCT1234M1Z5", "legal_name": "Test Corp Private Limited" },
    "incorporation":    { "status": "failed" },
    "dpa":              { "status": "done", "is_signed": false }
  },
  "exact_match_context": {
    "pan_number":         "verified",
    "ifsc_code":          "verified",
    "account_number":     "verified",
    "gst_number":         "verified",
    "cin_number":         "doc_ocr_failed — incorporation could not be read at all",
    "incorporation_date": "doc_ocr_failed — incorporation could not be read at all",
    "llp_number":         "not_applicable — llp_agreement was not required for this vendor",
    "msme_number":        "not_applicable — msme_cert was not required for this vendor",
    "iso_cert_number":    "partial_read — iso_cert OCR succeeded but this field is null",
    "ocr_gstin_state_matches_form_state":   "verified",
    "ocr_gstin_pan_matches_form_pan":       "verified",
    "ocr_pan_4th_char_matches_company_type":"verified"
  }
}
```

---

## LLM Output Schema

```json
{
  "user_flags": [
    { "field": "<form field or doc identifier>", "severity": "high|medium|low", "message": "<message to vendor>" }
  ],
  "risk_factors": [
    { "factor": "<snake_case identifier>", "severity": "high|medium|low", "note": "<internal reviewer note>" }
  ],
  "unreadable_docs": [
    { "doc_type": "<doc_type>", "message": "<message to vendor>" }
  ]
}
```

---

## All Possible Risk Factors

Every risk factor has a fixed severity range. LLM chooses within range for fuzzy name checks; all others are fixed.

### Exact Mismatch Risk Factors (all fixed high, except dates)

| Risk | Plain English | Severity | Escalates Cross-Version |
|---|---|---|---|
| `pan_number_mismatch` | PAN number on card doesn't match form | high | yes |
| `ifsc_code_mismatch` | IFSC code on cheque doesn't match form | high | yes |
| `account_number_mismatch` | Account number on cheque doesn't match form | high | yes |
| `gst_number_mismatch` | GSTIN on GST certificate doesn't match form | high | yes |
| `cin_number_mismatch` | CIN on incorporation cert doesn't match form | high | yes |
| `incorporation_date_mismatch` | Incorporation date on cert doesn't match form | medium | yes |
| `llp_number_mismatch` | LLP number on agreement doesn't match form | high | yes |
| `msme_number_mismatch` | MSME/Udyam number on cert doesn't match form | high | yes |
| `iso_cert_number_mismatch` | ISO certificate number on cert doesn't match form | high | yes |
| `iso_expiry_date_mismatch` | ISO expiry date on cert doesn't match form | medium | yes |

### OCR Cross-Check Mismatch Risk Factors

| Risk | Plain English | Severity | Escalates Cross-Version |
|---|---|---|---|
| `gst_cert_state_mismatch` | State code in GST cert doesn't match vendor's declared state | high | yes |
| `gst_cert_entity_mismatch` | PAN embedded inside GST cert doesn't match vendor's PAN | high | yes |
| `pan_entity_type_mismatch` | PAN card entity type character doesn't match declared company type | high | yes |

### Partial OCR Risk Factors (field missing inside readable doc)

| Risk | Plain English | Severity | Escalates Cross-Version |
|---|---|---|---|
| `partial_ocr_pan_card` | PAN card was read but PAN number field is missing | medium | yes |
| `partial_ocr_cancelled_cheque` | Cancelled cheque was read but key field is missing | medium | yes |
| `partial_ocr_gst_cert` | GST certificate was read but GSTIN field is missing | medium | yes |
| `partial_ocr_incorporation` | Incorporation cert was read but key field is missing | medium | yes |
| `partial_ocr_llp_agreement` | LLP agreement was read but LLP number is missing | medium | yes |
| `partial_ocr_msme_cert` | MSME cert was read but Udyam number is missing | medium | yes |
| `partial_ocr_iso_cert` | ISO cert was read but certificate number is missing | medium | yes |
| `partial_ocr_dpa` | DPA was read but is_signed field is missing | medium | yes |
| `partial_ocr_partnership_deed` | Partnership deed was read but firm_name field is missing | medium | yes |

### OCR Failed Risk Factors (whole doc unreadable)

| Risk | Plain English | Severity | Escalates Cross-Version |
|---|---|---|---|
| `ocr_failed_pan_card` | PAN card could not be read at all | low | yes (via user_flags + unreadable_docs) |
| `ocr_failed_cancelled_cheque` | Cancelled cheque could not be read at all | low | yes (via user_flags + unreadable_docs) |
| `ocr_failed_gst_cert` | GST certificate could not be read at all | low | yes (via user_flags + unreadable_docs) |
| `ocr_failed_incorporation` | Incorporation cert could not be read at all | low | yes (via user_flags + unreadable_docs) |
| `ocr_failed_llp_agreement` | LLP agreement could not be read at all | low | yes (via user_flags + unreadable_docs) |
| `ocr_failed_msme_cert` | MSME certificate could not be read at all | low | yes (via user_flags + unreadable_docs) |
| `ocr_failed_iso_cert` | ISO certificate could not be read at all | low | yes (via user_flags + unreadable_docs) |
| `ocr_failed_dpa` | Data Processing Agreement could not be read at all | low | yes (via user_flags + unreadable_docs) |
| `ocr_failed_partnership_deed` | Partnership deed could not be read at all | low | yes (via user_flags + unreadable_docs) |

### Fuzzy Name Mismatch Risk Factors (LLM judges severity)

LLM compares extracted name from each doc against `form.company_name`:
- **no_issue** → same entity (abbreviations, "Pvt Ltd" = "Private Limited") → skip entirely
- **low** → minor variation (word order, initials) → risk_factor only, no user_flag, no cross-version escalation
- **medium** → different but possibly related name (trading name, subsidiary) → both user_flag + risk_factor
- **high** → completely different entity → both user_flag + risk_factor

| Risk | Doc Checked | Severity Range | Escalates Cross-Version |
|---|---|---|---|
| `pan_name_mismatch` | Name on PAN card vs company name | low/medium/high | medium/high only |
| `account_holder_name_mismatch` | Account holder on cancelled cheque vs company name | low/medium/high | medium/high only |
| `gst_legal_name_mismatch` | Legal name on GST cert vs company name | low/medium/high | medium/high only |
| `incorporation_name_mismatch` | Company name on incorporation cert vs company name | low/medium/high | medium/high only |
| `llp_name_mismatch` | LLP name on agreement vs company name | low/medium/high | medium/high only |
| `iso_name_mismatch` | Company name on ISO cert vs company name | low/medium/high | medium/high only |
| `msme_name_mismatch` | Enterprise name on MSME cert vs company name | low/medium/high | medium/high only |
| `partnership_name_mismatch` | Firm name on partnership deed vs company name | low/medium/high | medium/high only |

### Document Validity Risk Factors

| Risk | Plain English | Severity | Escalates Cross-Version |
|---|---|---|---|
| `dpa_not_signed` | DPA was uploaded and read but is_signed = false | medium | yes |
| `cancelled_cheque_no_watermark` | Cancelled cheque does not have a "CANCELLED" watermark | low | yes |

### Compliance & Business Risk Factors (form fields only, internal)

These never create user_flags and never escalate cross-version — vendor cannot fix them by resubmitting.

| Risk | Plain English | Severity |
|---|---|---|
| `iso_cert_expired` | ISO certificate expiry date is in the past | high |
| `data_offshore` | Vendor declared data is stored outside India | high |
| `employee_turnover_mismatch` | Employee count is implausible relative to declared turnover | high |
| `processes_data_no_soc2` | Vendor processes data but is not SOC2 audited | medium |
| `processes_data_no_iso` | Vendor processes data but is not ISO certified | medium |
| `low_cyber_coverage` | Vendor processes data but cyber insurance coverage is low for their turnover | medium |
| `service_turnover_mismatch` | Service nature is implausible relative to declared turnover | medium |
| `new_company` | Company is less than 2 years old | low |
| `ai_check_failed` | AI pipeline itself threw an error — check did not run | low |

---

## Fuzzy Name Check Design

LLM receives all extracted name fields in `ocr` and compares each against `form.company_name`:

| Doc | OCR Field | Factor Name | OCR fail detection |
|---|---|---|---|
| pan_card | `name_on_card` | `pan_name_mismatch` | via `pan_number` exact match |
| cancelled_cheque | `account_holder_name` | `account_holder_name_mismatch` | via `ifsc_code`/`account_number` exact match |
| gst_cert | `legal_name` | `gst_legal_name_mismatch` | via `gst_number` exact match |
| incorporation | `company_name` | `incorporation_name_mismatch` | via `cin_number` exact match |
| llp_agreement | `company_name` | `llp_name_mismatch` | via `llp_number` exact match |
| iso_cert | `company_name` | `iso_name_mismatch` | via `iso_cert_number` exact match |
| msme_cert | `enterprise_name` | `msme_name_mismatch` | via `msme_number` exact match |
| partnership_deed | `firm_name` | `partnership_name_mismatch` | via `partnership_firm_name` presence check |
| dpa | `is_signed` (value check) | `dpa_not_signed` | via `dpa_is_signed` presence check |

**Why presence-only checks for `partnership_deed` and `dpa`:** These docs have no numeric/date field to cross-compare against the form. Without a presence-only entry in `exact_match_context`, a failed OCR on them would be invisible to the pipeline — they'd appear as "not_applicable" instead of "doc_ocr_failed". The presence checks fix this: they bring OCR status into context so the LLM can add them to `unreadable_docs` when needed.

---

## Risk Scoring

### Base Score

```
base_score = Σ(severity_weight for each risk_factor)
  high   = 10 points
  medium = 5 points
  low    = 2 points
  cap    = 100
```

### Cross-Version Delta

Tracks whether vendor acted on issues they were notified about.

**Notified factors** = risk_factors whose corresponding user_flag field was in this version's `user_flags`. For `ocr_failed_*` factors — vendor is notified via both `user_flags` (medium severity) and `unreadable_docs`; both paths are counted.

```
For each prior version (oldest to newest):
  weight = 0.5 ^ (distance - 1)   # most recent prior = distance 1 = weight 1.0

  repeated notified factor → +5 × weight   (vendor was told, didn't fix)
  resolved notified factor → -3 × weight   (vendor fixed it)

delta = round(Σ all version contributions)
final_score = clamp(base_score + delta, 0, 100)
```

### Decision Thresholds

| Score | Decision | Meaning |
|---|---|---|
| 0–5 | `approved` | Clean or trivial signals only |
| 6–50 | `waiting_for_response` (if user_flags present) or `human_review` | Minor issues sent to vendor |
| 51–75 | `human_review` | Reviewer must assess manually |
| 76–89 | `high_risk_review` | Serious risk — reviewer escalation |
| ≥ 90 | `rejected` | Auto-rejected — too many unresolved high-risk signals |

**Note:** Thresholds are under review — with many more risk factors now contributing to score, calibration may need adjustment.

---

## OCR Failure and Partial Read Handling

**OCR failed** (whole doc unreadable, `ocr_status = "failed"`):

1. `unreadable_docs` — doc_type + message asking vendor to re-upload
2. `user_flags` — one entry per doc, field=doc_type, severity:medium (vendor explicitly flagged)
3. `risk_factors` — `ocr_failed_<doc_type>` severity:low

All three fire. Vendor is emailed and sees the flag. Risk factor is low because unreadable docs are common with poor scan quality — not inherently suspicious.

**Partial read** (doc OCR done but specific field null):

1. `user_flags` — vendor asked to re-upload clear unedited copy (medium severity)
2. `risk_factors` — `partial_ocr_<doc_type>` (medium severity) — internal fraud signal

Both fire. Vendor may have uploaded legitimately poor quality scan. But partial reads are also a fraud vector — someone editing a doc to remove a specific field. Reviewer sees this regardless of whether vendor re-uploads. Medium severity (higher than failed) because a doc that reads partially is more suspicious than one that's completely unreadable.

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

### Why mismatch generates both user_flag AND risk_factor
Early design only created user_flags for exact mismatches. This meant a vendor repeatedly submitting wrong PAN had score 0 — no escalation possible. Every mismatch is both a vendor action item (fix it) and a risk signal (score it, track it). User flags are a subset of risk. Not scoring them broke cross-version escalation entirely.

### Why fuzzy names use low/medium/high instead of a binary flag
Abbreviations ("Pvt Ltd" vs "Private Limited") are common and not suspicious. But "Rajesh Kumar Mehta" on a company bank cheque is high severity. LLM is the right tool for this judgment call — code cannot reasonably detect this spectrum. Low severity fires risk_factor only (internal signal) without notifying vendor. Medium/high notifies vendor and escalates cross-version.

### Why unreadable_docs count as notified_factors
`ocr_failed_*` risk_factors are in `RISK_FACTOR_TO_FLAG_FIELD` so cross-version delta can fire on them. But unreadable docs create `unreadable_docs` entries (not `user_flags`). The vendor IS emailed about unreadable docs. `_compute_notified_factors` uses `DOC_TYPE_TO_NOTIFIED_FIELD` to include `unreadable_docs` in the notified set — so if vendor re-uploads the same unreadable doc and it fails again, delta fires correctly.

### Bug fixes applied to system prompt
1. **processes_data false-positive**: LLM fired `processes_data_no_soc2`/`no_iso` even when `processes_data=false`. Fix: explicit IMPORTANT block.
2. **Duplicate risk factors**: LLM created two risk factors for same doc. Fix: deduplication rule.
3. **not_applicable hallucination**: LLM saw `form.iso_expiry_date` in past and fired ISO flags even when doc not uploaded. Fix: not_applicable overrides form fields rule.
4. **Mismatch not scored**: Exact mismatches only created user_flags, no risk_factors. Fix: mismatch now creates both.
5. **Cross-checks missing risk_factors**: `gst_cert_state_mismatch` and `pan_entity_type_mismatch` only created user_flags. Fix: both now create risk_factors too.
6. **Incorporation date not verified**: OCR extracted `incorporation_date` from cert but it was never cross-checked against form. Fix: added `incorporation_date` to exact matches with date format normalization.
7. **dpa.is_signed missing risk_factor**: Only created user_flag, cross-version escalation broken. Fix: now fires both user_flag + `dpa_not_signed` risk_factor.

### Bug fixes applied to pipeline code (`ai_service.py`)
1. **OCR-failed docs silently treated as not_applicable**: Filter `ocr_json is not None` excluded docs where OCR failed (`ocr_json=null`). All their exact match checks returned null → `"not_applicable"` → LLM skipped. Vendor never told to re-upload. Fix: two-pass dedup — Pass 1 picks successful OCR, Pass 2 adds failed-status docs for doc_types with no successful OCR.
2. **`partnership_deed` and `dpa` invisible on OCR fail**: Neither doc had any exact match field, so even after the two-pass fix they'd have no entry in `exact_match_context`. Fix: presence-only checks `dpa_is_signed` and `partnership_firm_name` added — they surface OCR status without conflicting with LLM's value-level checks.
3. **`_fetch` treats `False` as missing**: `if not val` evaluated boolean `False` as "partial". Fix: changed to `if val is None or val == ""`.
4. **`iso_expiry_date` never cross-checked**: OCR extracted `iso_cert.expiry_date` but never compared to `form.iso_expiry_date`. Vendor could submit wrong expiry undetected. Fix: added `iso_expiry_date` to exact matches with date normalization (medium severity — date format differences common).
5. **`cancelled_watermark` never checked**: OCR extracted `cancelled_cheque.cancelled_watermark` but nothing acted on it. Fix: system prompt now fires user_flag + `cancelled_cheque_no_watermark` risk_factor when false.

### Why temperature=0.1
Need deterministic structured output. Lower temperature reduces variation. Not 0 because occasional creative phrasing in messages is acceptable; only the structure needs to be consistent.

---

## Known Issues (Pending Fix)

### LLM Doc-Level Cascade on Field Mismatch

**Problem:** When one field in a doc mismatches (e.g. `iso_expiry_date_mismatch`), the LLM infers the whole document is invalid and cascades into compliance risk factors that are supposed to be gated on form fields only. Observed example: `iso_expiry_date_mismatch` fired → LLM also fired `processes_data_no_iso` despite `form.iso_certified = true`. The system prompt rule *"check iso_certified field only"* does not hold when LLM has OCR evidence that contradicts the form.

**Root cause:** Compliance risk factors (`processes_data_no_soc2`, `processes_data_no_iso`, `iso_cert_expired`, etc.) are designed as form-only checks. But LLM receives full OCR context and uses it to second-guess form booleans when it sees mismatches or expired dates in docs.

**Fix direction (not yet implemented):**
- Exact match checks already handle all field-level doc verification independently of LLM.
- Compliance/form-only risk factors should be pre-computed in code (like exact matches) and injected as `compliance_context` — not left to LLM judgment.
- LLM scope should be limited to: fuzzy name checks, doc readability, mismatch messaging. Not compliance decisions.
- This eliminates the one-wrong-field → whole-doc-condemned cascade entirely.

**Workaround until fix:** System prompt rules exist (`ONLY fire processes_data_no_iso if iso_certified IS EXACTLY true`) but are unreliable when OCR evidence contradicts the form.

---

## Status

**AI Pipeline — COMPLETE (May 2026 bug fix pass)**

Built:
- `services/ai_service.py` — full pipeline: exact matches, partial detection, OCR cross-checks, fuzzy name scoring, Groq LLM call, cross-version scoring, reviews upsert
- `groq` added to `requirements.txt`
- `ocr_service.py` chains `run_ai_pipeline()` at end of OCR loop
- `GROQ_API_KEY` added to `.env`
- Cross-version risk scoring with decay-weighted delta — complete
- Email notification to vendor on flags — complete

Bug fix pass (May 2026):
- OCR-failed docs no longer silently skipped (two-pass dedup)
- `partnership_deed` and `dpa` OCR failures now surface correctly (presence-only checks)
- `_fetch` no longer treats boolean `False` as missing
- `iso_expiry_date` exact match added (cross-checks form vs cert)
- `cancelled_watermark=false` now flagged
- `dpa_not_signed` risk factor added (was missing, broke cross-version escalation)
