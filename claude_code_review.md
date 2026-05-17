# Claude Code Project Review — Vendor Onboarding
> Generated: May 17, 2026 | Source: `~/.claude/history.jsonl` (354 prompts, 6 days)

---

## Prompt Volume by Day

| Date | Prompts | Phase |
|---|---|---|
| May 12 | 6 | Project setup |
| May 13 | 55 | Backend build |
| May 14 | 41 | Data generator + validation |
| May 15 | 26 | Bug fixes |
| May 16 | 72 | OCR pipeline + AI planning |
| May 17 | 154 | AI pipeline + scoring + admin + testing |
| **Total** | **354** | |

> **Token usage:** `history.jsonl` stores prompts only, not token counts. Find exact input/output tokens at console.anthropic.com → Usage. Today's session was the heaviest by far (154 prompts).

---

## Day-by-Day Timeline

---

### May 12 — Project Setup (6 prompts)
**Time:** 21:31–21:46

- Opened Claude Code for first time on this project
- Discussed virtual environment — where to place it (vendor_onboarding vs zamp)
- Decided: work inside `vendor_onboarding/` as the git root
- No code written, setup only

---

### May 13 — Backend + Frontend Build (55 prompts)
**Time:** 13:11–18:05

#### Backend (13:11–15:48)
- Loaded `phase1_claude_code_prompt.md` — full backend spec
- Built FastAPI backend: auth, vendor registration, application submit, draft save
- Set up Supabase schema (vendors, applications, documents tables)
- Connected Supabase keys + JWT secret in `.env`
- Debugged JWT token flow (token not changing, version returning 2 instead of 1)
- Clarified versioning logic: one application row per submission attempt, version increments on resubmit
- Discussed multi-service vendor scenario — kept single-form-per-vendor for demo

#### Frontend (16:09–17:08)
- Designed frontend plan, got approval, built it
- React form with all field groups
- API connection to backend
- Required field asterisks, save-as-draft button
- Logout button
- Realised status button was confusing — removed
- Docs upload integrated

#### Data Generator Planning (16:35–17:29)
- Loaded `data_generator_plan.md`
- Added missing fields, removed irrelevant ones
- Decided to accept docs (PDF/JPG) in form validation
- Added doc upload rules to validation

#### Documentation (17:17–17:57)
- Created `phase1_claude_code_prompt.md` (backend reference)
- Created `FRONTEND.md`
- Updated both after session changes

**Key decisions made:**
- Supabase for DB + storage
- JWT for auth (no OAuth for demo)
- Save-as-draft stores partial form, doesn't validate
- Version increments only on successful submit → failed submit stays draft

---

### May 14 — Data Generator + Validation Hardening (41 prompts)
**Time:** 17:22–21:01

#### Data Generator (17:22–18:44)
- Reviewed generator plan, updated fields
- Generated 10 test scenarios: 3 pass first go, 3 pass second go, 3 always fail, 1 edge case
- Removed email domains like gmail.com from valid company emails
- MSME turnover cap discussion (>10Cr allowed)

#### Validation Bug Fixes (18:58–20:22)
- Test 6: DB showing unexpected rows — investigated stale data from previous runs
- Small PDF passing validation — found size check was too loose, fixed
- Test 8: Showed "submitted" unexpectedly — traced to incorrect status flow
- 4 rows appearing for same vendor — traced to draft+submit combos creating extra rows

#### Document Versioning (20:32–21:01)
- Problem: `documents` table had no version concept — re-uploads clobbered old docs
- Solution: Added version column to documents, tied to application version
- New logic: on v2 submit, copy v1 docs as baseline, only replace docs explicitly re-uploaded
- Test 11 created for manual testing with multi-round validation errors

**Key decisions made:**
- Documents get version numbers matching application versions
- Draft does NOT validate — any partial save is allowed
- Submit validates fully; failure keeps status as draft
- Test 11 designed for manual walkthrough

---

### May 15 — Bug Fixes + UX (26 prompts)
**Time:** 00:49–23:59

#### Toggle Bugs (00:49–01:27)
- `processes_data`, `soc2_audited`, `cyber_insurance` toggles not persisting correctly on reload
- Investigated draft reload — values not populating from DB
- Fixed toggle state hydration from API response

#### Document Logic Bugs (01:00–01:18)
- Uploading same filename twice — only one row created (correct)
- Multiple uploads of different files — versioning tracked correctly
- Null doc rows on no-upload — confirmed not created

#### Employee/Turnover Validation (23:25–23:59)
- Removed arbitrary employee count cap (was 250, lifted)
- MSME turnover cap removed (>10Cr should be allowed)
- Discussed why blocking >100Cr turnover was wrong — removed

#### Draft + Doc Carry-Forward (23:55–00:04)
- V2 submit: docs not showing from V1 in form — user had to re-upload everything
- Identified: doc carry-forward from V1 to V2 was missing
- Discussed fix strategy

**Key decisions made:**
- Toggles must hydrate from DB on page load
- Employee count has no cap
- Doc carry-forward across versions is required

---

### May 16 — OCR Pipeline + AI Architecture (72 prompts)
**Time:** 00:04–22:43

#### Documentation Cleanup (00:04–00:42)
- Updated BACKEND.md, FRONTEND.md to reflect all changes
- Created `field_reference.html` — comprehensive table of all 36 fields, rules, doc types, AI checks
- Discussed copy logic bug in doc versioning (application_id null in doc rows on submit)

#### Doc Versioning Fix (00:59–01:54)
- Root cause: application_id not being populated in doc rows at submit time
- Fixed: on submit, query docs by vendor_id, assign current application_id

#### GitHub Push (01:56–02:18)
- Added `.gitignore`
- Pushed full project to GitHub

#### OCR Pipeline Design (14:53–16:47)
- Decided: trigger OCR after successful form submit as background task
- Rejected Claude API (no credits) → chose standard libraries
- Selected: `pdfplumber` for PDFs, `pytesseract` for images
- Discussed Tesseract installation on macOS
- Implemented `ocr_service.py`: download from Supabase → route by extension → extract → store in `documents.ocr_json`

#### OCR Output Review (16:58–17:12)
- Tested OCR on generated docs
- Found: IFSC code sometimes null even when present in text
- Found: account holder name missing from cheque
- Reviewed all doc types, identified extraction gaps
- Added `category` field to MSME extraction (useful for risk later)

#### Documentation Rename (17:20–17:40)
- Renamed `phase1_claude_code_prompt.md` → `BACKEND.md`
- Updated BACKEND.md, FRONTEND.md, data generator doc

#### AI Pipeline Architecture (20:33–22:43)
- Brainstormed risk factors: what to tell vendor vs what to keep internal
- Categorised: fixable (doc mismatches) vs unfixable (data offshore, new company)
- Decided: ISO expiry → tell vendor to resubmit updated cert; cross-version tracking
- Designed `ai_status` lifecycle: not_started → processing → done/failed
- Chose **Groq API + LLaMA 3.3 70B** (fast, cheap, structured JSON output)
- Wrote `AI.md` — full pipeline spec
- Started `ai_service.py` implementation
- Designed exact match checks (pre-computed in code, not LLM)
- Designed partial OCR handling (medium severity — more suspicious than failed)
- Added `ALLOWED_OCR_FIELDS` to strip raw_text from LLM input
- Added output format schema to system prompt to prevent hallucination

**Key decisions made:**
- OCR runs as background task after submit
- Standard libraries only (no paid AI for OCR)
- Groq LLaMA 70B for AI analysis
- Exact matches computed in code, fuzzy names left to LLM
- Partial OCR = medium severity (more suspicious than full failure)
- raw_text stripped before sending to LLM

---

### May 17 — AI Pipeline Completion + Full System (154 prompts)
**Time:** 00:01–20:33

#### AI Prompt Refinement (00:01–01:09)
- Debugged LLM misunderstanding of null/false/true — added plain-English context labels
- Added `exact_match_context` system: `verified` / `mismatch` / `partial_read` / `doc_ocr_failed` / `not_applicable`
- Removed `incorporation_date` from form, replaced with `company_age_years` (pre-computed)
- Added few-shot examples to system prompt (15 examples covering all scenarios)
- Tested with Ollama llama3.1:8b locally (API limit hit on Groq)
- Switched to local 8b temporarily — slower but functional
- Context window analysis: plenty of headroom for 70B model

#### Risk Scoring Design (01:34–02:53)
- Designed base score: high=10, medium=5, low=2, cap 100
- Cross-version delta: decay-weighted (weight = 0.5^(distance-1))
- Repeated notified factor → +5×weight; resolved → -3×weight
- Discussed auto-reject threshold — settled on 90 (not 76, not 85)
- Decision thresholds: 0-5=approved, 6-50=waiting/human_review, 51-75=human_review, 76-89=high_risk_review, ≥90=rejected
- Reasoning LLM: separate Groq call, plain English reviewer note, temperature=0.3
- Decided: scoring in code, reasoning in LLM

#### System Prompt Bug Fixes (00:45–01:13)
- `processes_data` false-positive: LLM fired soc2/iso flags when processes_data=false → fixed with IMPORTANT block
- Duplicate risk factors per doc → added deduplication rule
- `not_applicable` hallucination (ISO flags when cert not uploaded) → overrides rule added
- Mismatch not scored → both user_flag + risk_factor now required for every mismatch

#### Groq Switch + Documentation (03:02–03:41)
- Switched back to Groq (rate limit reset), removed Ollama as primary
- Cleaned BACKEND.md: removed AI section (belongs in AI.md only)
- Removed 10 stale test cases from data generator (based on old doc logic)
- Designed 3 escalation test cases for manual testing
- Updated FRONTEND.md, pushed to GitHub

#### Pipeline Bug Fixes (12:20–12:57)
- Found: AI pipeline using only current-version docs, not carrying forward docs from v1
- Fixed: two-pass dedup — Pass 1: newest doc with successful OCR per doc_type; Pass 2: add failed-OCR docs so they appear as "failed" not "not_applicable"
- Fixed: `_fetch` treating boolean `False` as missing (was using `if not val`, changed to `if val is None or val == ""`)
- Added: `iso_expiry_date` exact match with date normalization
- Added: `cancelled_watermark=false` flagging
- Added: `dpa_not_signed` risk factor (was missing, broke cross-version escalation)
- Added: presence-only checks for `partnership_deed` and `dpa` to surface OCR status

#### Email Flow (13:21–13:57)
- Implemented Resend API email to vendor on user_flags
- Atomic `email_sent_at` claim prevents double-send on retry
- Email suppressed if decision=rejected (no point emailing auto-rejected vendor)
- Updated `AI.md`, `BACKEND.md`, `requirements.txt`

#### Admin Dashboard (13:57–15:09)
- Built `/admin/login` with JWT auth (admin email gated)
- Built `/admin/dashboard` with vendor list, review details
- Documentation tab: full field reference rendered in UI
- Analytics tab: stub ("to be continued")
- Vendor status tab: skipped for demo

#### Field Reference + AI.md Consistency (14:27–15:09)
- Made field descriptions crisp (removed verbose explanations)
- Reviewed all fields for consistency between `field_reference.html`, `AI.md`, `ai_service.py`
- Found: ISO expiry date calculation redundant — left as known bug

#### Test Case Corrections (15:15–20:04)
- Generated 3 escalation cases: case01 (error→approved), case02 (human_review→high_risk→approved), case03 (scammer→rejected)
- Found and fixed meta.json bugs:
  - Case 01 V1: `pan_number_mismatch` missing from expected risk factors (base 10→20)
  - Case 01 V2: delta -3→-6 (two factors resolved not one)
  - Case 02/03 all versions: `service_turnover_mismatch` missing (base 62→67 throughout)
  - Case 02 V2: missing `expected_risk_factors` and `expected_user_flags` fields entirely
  - Case 02/03: CIN year 2023→2024 (layer 1 was blocking submission)
  - Case 02/03: ISO expiry changed to future date (layer 1 was blocking expired ISO)
  - Swapped `iso_cert_expired` → `iso_expiry_date_mismatch` in all test cases (doc shows old date, form declares future date)

#### Success Screen (19:36)
- Added submitted state to Form.jsx
- Shows green checkmark, "Application Submitted", "You will receive an email shortly"
- Button navigates to /status

#### Known Issues Documented (20:04–20:13)
- Added "Known Issues" section to AI.md
- LLM doc-level cascade: one field mismatch → LLM infers whole doc invalid → fires compliance flags that should be form-only
- Fix direction: pre-compute compliance checks in code, shrink LLM scope to fuzzy names + readability

---

## What Was Built — Full Feature List

### Backend (`vendor_onbording_backend/`)
- FastAPI app with Supabase + JWT auth
- Vendor registration + login
- Application submit (layer 1 rule-based validation, 36 fields)
- Save as draft (no validation)
- Document upload to Supabase Storage
- OCR pipeline: pdfplumber + pytesseract, background task, stores `ocr_json` per doc
- AI pipeline: exact matches → Groq LLaMA 3.3 70B → risk scoring → email
- Cross-version risk scoring with decay-weighted delta
- Resend email notification to vendor
- Admin router with JWT-gated login + dashboard data
- Reviews table: `user_flags`, `risk_factors`, `unreadable_docs`, `notified_factors`, `risk_score`, `decision`, `risk_reasoning`

### Frontend (`vendor_onboarding_frontend/`)
- React + Vite + Tailwind
- Vendor login + form (36 fields, 8 groups)
- Dynamic document requirements (based on company type, ISO, GST, etc.)
- Save as draft + auto-restore on reload
- Success screen on clean submission
- Status page
- Admin login + dashboard (vendor list, review details, documentation tab)

### Data Generator (`vendor_onboarding_data_generator/`)
- Generates synthetic vendor data + realistic docs (PAN, cheque, GST cert, incorporation, MSME, ISO, DPA, partnership deed)
- 3 escalation scenarios with full multi-version payloads and expected values

### Documentation
- `BACKEND.md` — full backend reference
- `FRONTEND.md` — frontend reference
- `AI.md` — AI pipeline spec with all risk factors, scoring, known issues
- `field_reference.html` — 36-field reference table with rules and AI checks

---

## Token Usage Note

`history.jsonl` tracks prompt text only, not token counts. To see actual token usage:

1. Go to **console.anthropic.com → Usage**
2. Filter by date: May 12–17, 2026
3. May 17 will be the heaviest day (~154 prompts, many with large context from .md file reads)
4. May 16 second heaviest (~72 prompts, OCR + AI architecture sessions)

Rough estimate of heavy sessions: any session reading `AI.md` (576 lines) + `ai_service.py` (891 lines) + system prompt in context = ~8,000–12,000 input tokens per turn.
