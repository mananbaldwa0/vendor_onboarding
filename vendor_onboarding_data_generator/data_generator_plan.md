# Vendor Onboarding — Data Generator Plan

> Purpose: Generate realistic, schema-valid fake vendor data for testing the onboarding backend.
> Phase 1 complete. Phase 2 will add OCR/AI test cases.
> Last updated: May 2026

---

## Goals

1. Generate **valid** vendor submissions that pass all backend validations end-to-end.
2. Generate **invalid** submissions that intentionally trigger specific validation errors.
3. Generate **edge-case** submissions (boundary values, optional fields missing, etc.).
4. Produce **fake documents** (PDFs/images) that pass file size/format checks.
5. Support **multi-round trail tests** — simulating a vendor fixing errors across multiple submissions.

---

## Tech Stack

| Tool | Purpose |
|---|---|
| Python 3.11 | Language |
| `faker` | Base fake data (names, addresses, emails) |
| `random` / `secrets` | Randomised valid identifiers |
| `reportlab` | Generate fake PDF documents with embedded text |
| `Pillow` | Generate fake image documents (JPG/PNG) |
| `httpx` | Hit live API endpoints during integration testing |

---

## Folder Structure

```
vendor_onboarding_data_generator/
├── data_generator_plan.md          ← this file
├── requirements.txt
├── generators/
│   ├── __init__.py
│   ├── company.py                  ← company identity fields
│   ├── legal.py                    ← PAN, GST, CIN, LLP, MSME, DIN, DPIN
│   ├── banking.py                  ← banking details
│   ├── compliance.py               ← IT/security compliance fields
│   ├── contact.py                  ← contact fields
│   └── documents.py                ← fake PDF/image generator
├── final_tests/
│   ├── generate_tests.py           ← generates all test dirs + docs
│   ├── run_tests.py                ← runs tests 01–10 against live API
│   ├── test_01_pass_pvt_ltd/
│   ├── test_02_pass_llp_no_gst/
│   ├── test_03_pass_partnership_msme/
│   ├── test_04_fix_cin_year/
│   ├── test_05_fix_free_email/
│   ├── test_06_fix_missing_dpa/
│   ├── test_07_fail_pan_type/
│   ├── test_08_fail_data_offshore/
│   ├── test_09_fail_no_cyber/
│   ├── test_10_phase2_preview/
│   └── test_11_trail_verify/       ← manual only, 3-round trail test
└── output/
    └── docs/
```

---

## Generator Modules

### `generators/company.py`

```python
{
  "company_name":       "Syntara Technologies Private Limited",
  "company_type":       "Private Limited",
  "incorporation_date": "2015-03-22",
  "registered_address": "Plot 14, Sector 5, MIDC Industrial Area",
  "city":               "Pune",
  "state":              "Maharashtra",
  "employee_count":     47,
  "annual_turnover":    "1-10 Cr",
  "website":            "https://syntara.io",
  "_meta": {
    "incorporation_year": 2015,
    "website_domain": "syntara.io"
  }
}
```

`company_type` seeded first — all other generators depend on it. `_meta` carries derived values used downstream (e.g. CIN year from `incorporation_year`).

---

### `generators/legal.py`

**PAN:**
```
Format: [A-Z]{5}[0-9]{4}[A-Z]
4th char encodes entity:
  C → Private Limited, Public Limited
  F → LLP, Partnership Firm
  P → Sole Proprietorship
```

**GST:**
```
Format: [state_code(2)][PAN(10)][entity_no(1)][Z][check(1)]
State code looked up from state→code map.
PAN embedded at chars 3–12 (0-indexed 2–11).
```

**CIN (Pvt Ltd / Public Ltd only):**
```
Format: [U/L][NIC 5-digit][state 2-char][year 4-digit][PTC/PLC][serial 6-digit]
Year from incorporation_date. Sits at index 8–11 (0-indexed) in the string.
Example: U72900MH2015PTC123456
```

**LLP number (LLP only):**
```
Format: AAA-1234
Field: llp_number
```

**DIN (Pvt Ltd / Public Ltd only):**
```
Format: 8 digits
Field: din
```

**DPIN (LLP only):**
```
Format: 8 digits
Field: dpin  ← separate from DIN, required for LLP
```

**MSME (optional, ~30% chance):**
```
Format: UDYAM-XX-00-0000000
Field: msme_number
Generated if employee_count ≤ 250 — no turnover restriction.
(MSME Medium category goes up to ~₹250 Cr turnover so >100 Cr bucket is still valid.)
```

**gst_registered boolean:**
```
True when GST number generated. False for no-GST scenarios.
Controls gst_cert doc requirement.
```

---

### `generators/banking.py`

```python
{
  "account_holder_name": "Syntara Technologies Pvt Ltd",
  "bank_name":           "HDFC Bank",
  "account_number":      "003601234567",
  "ifsc_code":           "HDFC0001234",   # [BANK_CODE]0[6 alphanum]
  "account_type":        "Current"
}
```

IFSC bank code prefix consistent with chosen bank (HDFC→HDFC, SBI→SBIN, etc.).

---

### `generators/compliance.py`

```python
{
  "service_nature":        "SaaS Platform",
  "processes_data":        True,
  "data_in_india":         True,
  "cloud_provider":        "AWS",
  "iso_certified":         True,
  "iso_cert_number":       "IS-2024-MH-00412",
  "iso_expiry_date":       "2026-11-30",
  "soc2_audited":          False,
  "cyber_insurance":       True,
  "cyber_coverage_crores": 5.0
}
```

- `processes_data = True` → `cyber_insurance` always `True`
- `iso_certified = True` → ISO cert fields populated, future expiry
- `data_in_india = True` for valid scenarios (False triggers RBI flag warning — not a hard block)
- `force_processes_data=False` kwarg available to generate compliance block without data processing

---

### `generators/contact.py`

```python
{
  "contact_name":  "Rahul Mehta",
  "contact_email": "rahul.mehta@syntara.io",
  "contact_phone": "+919876543210"
}
```

Email domain extracted from `website` field. Free domains (gmail/yahoo/hotmail/outlook/rediffmail) never used in valid scenarios.

---

### `generators/documents.py`

Generates fake PDF/image files with embedded text. Every file is between 10KB–10MB.

**PDF size fix:** reportlab plain text compresses to ~1.7KB (fails 10KB min). Fix: second page uses incompressible random-shaded rectangle grid → 172KB output.

| Document | Embedded Text | Format |
|---|---|---|
| PAN Card | PAN number | JPG |
| Cancelled Cheque | IFSC code + account number | JPG |
| GST Certificate | GST number + company name | PDF |
| Certificate of Incorporation | CIN number | PDF |
| LLP Agreement | LLP number | PDF |
| ISO 27001 Certificate | cert number + expiry date | PDF |
| Data Processing Agreement | company name | PDF |
| MSME Certificate | MSME number | PDF |
| Partnership Deed | company name | PDF |

---

## Final Tests — 11 Cases

### Automated (run_tests.py runs these)

| Test | Type | Rounds | What It Tests |
|---|---|---|---|
| test_01_pass_pvt_ltd | pass | 1 | Pvt Ltd, GST, ISO, processes_data → submitted |
| test_02_pass_llp_no_gst | pass | 1 | LLP, no GST, dpin+llp_number → submitted |
| test_03_pass_partnership_msme | pass | 1 | Partnership + MSME cert → submitted |
| test_04_fix_cin_year | fix | 2 | Round 1: corrupt CIN year → draft. Round 2: fix → submitted |
| test_05_fix_free_email | fix | 2 | Round 1: gmail.com → draft. Round 2: company domain → submitted |
| test_06_fix_missing_dpa | fix | 2 | Round 1: no DPA doc → draft. Round 2: DPA added → submitted |
| test_07_fail_pan_type | fail | 1 | PAN 4th char F for Pvt Ltd → always draft |
| test_08_fail_data_offshore | warn | 1 | data_in_india=False → WARNING only, still submits |
| test_09_fail_no_cyber | fail | 1 | processes_data=True + cyber_insurance=False → always draft |
| test_10_phase2_preview | phase2 | 1 | account_holder_name unrelated to company → Phase 1 passes, Phase 2 will flag |

**Test runner resets state before each test:** `DELETE /api/documents/all` + `DELETE /api/application/reset`.
Fix tests (04/05/06): full reset before round_1, docs-only delete before round_2 (keeps draft for upsert).

**Result: 13/13 rounds pass. Idempotent.**

### Manual Trail Test (test_11 — not in run_tests.py)

**test_11_trail_verify** — Sole Proprietorship, no GST, no ISO, no data processing, has MSME.

Purpose: verify the full round-trip flow with doc versioning across multiple submissions.

| Round | Expected Result | Errors | Docs to Upload |
|---|---|---|---|
| round_1 | draft | PAN 4th char C (needs P for Sole Prop) + Missing msme_cert | pan_card + cancelled_cheque (no msme_cert) |
| round_2 | draft | IFSC 5th char wrong (not 0) | msme_cert only (re-upload just the missing doc) |
| round_3 | submitted | none | no new docs (all 3 already linked from round_1+2) |

This test verifies:
- Partial doc uploads across rounds accumulate correctly
- Copy-forward logic works for doc scoping across rounds
- PAN type mismatch, IFSC corruption, and doc missing all caught correctly

---

## Validation Rules (as implemented in backend)

### MSME
- Format only: `UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}`
- No employee count restriction (removed — MSME Medium valid up to ₹250 Cr, ~250 employees is only micro/small ceiling)
- No turnover restriction

### Boolean fields
- `gst_registered`, `iso_certified`, `processes_data`, `data_in_india`, `cyber_insurance`, `soc2_audited`
- Backend uses `is None` check: `data.get("iso_certified") is None` → error
- `False` is NOT `None` → passes the check
- Generator always outputs explicit `True`/`False`, never `None` for these fields

### PAN 4th char → company type
| Char | Valid for |
|---|---|
| C | Private Limited, Public Limited |
| F | LLP, Partnership Firm |
| P | Sole Proprietorship |

### CIN year position
CIN year sits at **index 8–11 (0-indexed)** → `cin[8:12]`. Not 7-10.

---

## State Map Used in Generators

```python
STATE_GST_CODES = {
    "Maharashtra": "27", "Delhi": "07", "Karnataka": "29",
    "Tamil Nadu": "33", "Gujarat": "24", ... (all 28 states + 8 UTs)
}

STATE_ABBR = {
    "Maharashtra": "MH", "Delhi": "DL", "Karnataka": "KA", ...
}
```

State names in generator must exactly match state names in validation.py STATE_GST_CODES. Known mismatch: generator uses "Andaman and Nicobar Islands", validation uses "Andaman & Nicobar". Both sides handle their own list.

---

## Phase 2 — What Will Be Needed

When Phase 2 (OCR + AI) is built, new test cases will be needed:

| New Test Case | Purpose |
|---|---|
| `test_12_ocr_pan_mismatch` | PAN in image ≠ pan_number field |
| `test_13_ocr_ifsc_mismatch` | IFSC in cheque image ≠ ifsc_code field |
| `test_14_account_name_fuzzy` | account_holder_name unrelated to company_name (AI fuzzy catch) |
| `test_15_risk_score_high` | data_in_india=False + no ISO + no SOC2 → high risk score |

Generator already has `test_10_phase2_preview` where `account_holder_name` is intentionally unrelated — Phase 1 passes it, Phase 2 should flag it.

Documents for Phase 2 OCR testing must have the embedded text match (or intentionally mismatch) the form field values. The `generators/documents.py` already embeds real field values — for mismatch tests, the doc will need a corrupted value embedded instead.
