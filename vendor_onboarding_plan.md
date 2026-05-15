# IT Vendor Onboarding — Backend Plan (Phase 1)
> Form Submission + Basic Validation Only. AI Review is Phase 2.

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Language | Python 3.11 | Claude Code knows it best |
| Framework | FastAPI | Fast, auto-generates API docs |
| Database | Supabase (PostgreSQL) | Free, hosted, no setup pain |
| File Storage | Supabase Storage | Stores uploaded documents |
| Email | Resend.com | Dead simple, free tier |
| OCR (PDF) | pdfplumber | Extracts text from PDFs |
| OCR (Images) | pytesseract | Extracts text from JPG/PNG |
| Auth | JWT tokens + OTP via email | Simple, no password needed |
| Deployment | Render.com | Free tier, supports FastAPI |

---

## User Flow

```
Vendor visits site
      ↓
[LOGIN PAGE] — enters email → backend returns JWT token directly (no OTP — Phase 3)
      ↓
Token saved in localStorage
      ↓
[FORM PAGE] — fills all fields, uploads documents
      ↓
Save as Draft (anytime) → POST /api/application/draft → always saves, no validation
      ↓
Hits Submit → backend runs all validations
      ↓
    PASS → status = "submitted" → stored in applications table
    FAIL → status = "draft"    → stored in applications table (vendor keeps progress)
             errors[] returned in response → shown inline on form
```

---

## ALL FORM FIELDS — Definitions & Validation Rules

### SECTION 1 — Company Information

| # | Field | Definition | Validation Rule |
|---|---|---|---|
| 1 | Legal Company Name | Full name as registered with MCA/ROC. This must exactly match the name on PAN card, GST certificate, and bank account. | Required. Min 3 chars. |
| 2 | Company Type | Legal structure of the entity. Determines which documents are needed. | Required. One of: `Private Limited`, `LLP`, `Public Limited`, `Partnership Firm`, `Sole Proprietorship` |
| 3 | Date of Incorporation | Date the company was officially registered. Used to verify years in business and cross-check CIN (CIN contains year of incorporation). | Required. Must be a past date. Must not be before 1900. |
| 4 | Registered Address | Full address as per incorporation certificate. Street, building, locality. | Required. Min 10 chars. |
| 5 | City | City of the registered office. | Required. |
| 6 | State | Indian state of registered office. **Critical** — first 2 digits of GST number are the state code and must match this. | Required. Dropdown of all 28 states + 8 UTs. |
| 7 | Employee Count | Total number of employees currently on payroll. Used to cross-check MSME eligibility and turnover range. | Required. Numeric. Min 1. |
| 8 | Annual Turnover (Last FY) | Revenue range for the last completed financial year (April–March). | Required. Options: `<1 Cr`, `1–10 Cr`, `10–100 Cr`, `>100 Cr` |
| 9 | Company Website | Official company website. Contact email domain must match this domain. | Optional. Must be valid URL if provided. |

---

### SECTION 2 — Legal & Tax Details

| # | Field | Definition | Validation Rule |
|---|---|---|---|
| 10 | PAN Number | Permanent Account Number issued by Income Tax dept. Format: 5 uppercase letters + 4 digits + 1 uppercase letter. 4th character indicates entity type: C = Company, F = Firm, P = Individual, etc. | Required. Regex: `[A-Z]{5}[0-9]{4}[A-Z]{1}` |
| 11 | GST Number | 15-character Goods & Services Tax registration number. Structure: `[State Code (2 digits)] + [PAN (10 chars)] + [Entity No. (1)] + [Z] + [Check digit]`. PAN embedded (chars 3–12) must match the PAN field above. | Required (unless GST exempt). Regex: `[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z][Z][0-9A-Z]`. State code must match State field. PAN portion must match PAN field. |
| 12 | CIN Number | Company Identification Number — only for Private Limited and Public Limited companies. Format: `[U/L][5-digit NIC code][2-char state][4-digit year][PTC/PLC/LLC][6-digit serial]`. Year in CIN must match incorporation year. | Required for Pvt Ltd / Public Ltd. Regex: `[UL][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}` |
| 13 | LLP Identification No. | Identification number assigned by MCA to Limited Liability Partnerships. Format: `AAA-1234`. | Required only if Company Type = LLP. |
| 14 | MSME Registration No. | Udyam Registration Number if the company is MSME registered. Format: `UDYAM-XX-00-0000000`. If provided, employee count and turnover must be within MSME limits. | Optional. If provided, Regex: `UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}` |
| 15 | Authorized Signatory Name (`signatory_name`) | Full name of the person authorized to sign vendor agreements on behalf of the company. | Required. |
| 16 | DIN (Director Identification No.) | 8-digit number issued by MCA to company directors. Only applicable for companies (Pvt Ltd / Public Ltd), not LLP partners. | Required for Pvt Ltd / Public Ltd. Regex: `[0-9]{8}` |
| 16b | DPIN (Designated Partner Identification No.) | 8-digit number issued by MCA to LLP designated partners. Equivalent of DIN for LLP. | Required for LLP. Regex: `[0-9]{8}` |

---

### SECTION 3 — Banking Details

| # | Field | Definition | Validation Rule |
|---|---|---|---|
| 17 | Account Holder Name | Name registered on the bank account. **Must exactly match Legal Company Name** — even minor differences (like "Pvt" vs "Private") are flagged. | Required. Cross-checked against Legal Company Name. |
| 18 | Bank Name | Name of the bank where the account is held. | Required. Dropdown of RBI-registered banks. |
| 19 | Account Number | Bank account number. Indian accounts are typically 9–18 digits. Must be numeric only. | Required. Regex: `[0-9]{9,18}` |
| 20 | IFSC Code | 11-character Indian Financial System Code. Structure: `[4-char bank code][0][6-char branch code]`. 5th character is always 0. | Required. Regex: `[A-Z]{4}0[A-Z0-9]{6}` |
| 21 | Account Type | Type of bank account. Companies typically use Current accounts. | Required. Options: `Current`, `Savings` |

---

### SECTION 4 — IT & Security Compliance

| # | Field | Definition | Validation Rule |
|---|---|---|---|
| 22 | Nature of IT Service | What the vendor provides. Helps assess the level of risk and compliance needed. | Required. Options: `Core Banking Software`, `Cybersecurity Tool`, `Cloud Infrastructure`, `SaaS Platform`, `Data Analytics`, `HR/ERP Software`, `Network/Hardware`, `Other` |
| 23 | Does service process bank/customer data? | Whether the vendor's system will handle any sensitive bank data (customer PII, transactions, account info). If Yes — triggers DPA and cyber insurance requirements. | Required. Yes / No |
| 24 | Is data stored within India? | RBI mandates that all payment and financial data of Indian customers must be stored only within India (data localization). If No — application is auto-flagged. | Required. Yes / No. If No → flag for review. |
| 25 | Cloud Provider | Infrastructure where the vendor's service runs. | Required. Options: `AWS`, `Azure`, `GCP`, `Private Cloud`, `On-Premise`, `Hybrid`, `Not Applicable` |
| 26 | ISO 27001 Certified? | Whether the vendor holds an active ISO 27001 (Information Security Management) certification. Banks strongly prefer or require this. | Required. Yes / No |
| 27 | ISO 27001 Certificate Number | The certificate number on the ISO 27001 document. | Required if ISO = Yes. |
| 28 | ISO 27001 Expiry Date | Expiry date of the ISO 27001 certificate. Must be a future date — expired certs are flagged as Pending. | Required if ISO = Yes. Must be future date. |
| 29 | SOC 2 Type II Audited? | Whether the vendor has completed a SOC 2 Type II audit (common for US/global SaaS). A credibility signal — not mandatory but adds weight. | Optional. Yes / No |
| 30 | Cyber Insurance Policy? | Whether the vendor holds an active cyber insurance policy. **Required if data processing = Yes.** | Required if data processing = Yes. |
| 31 | Cyber Insurance Coverage (INR Crores) | Value of cyber insurance coverage. Minimum acceptable level depends on service criticality. | Required if cyber insurance = Yes. Numeric. |

---

### SECTION 5 — Primary Contact

| # | Field | Definition | Validation Rule |
|---|---|---|---|
| 32 | Contact Name | Full name of the primary point of contact for this onboarding. | Required. |
| 33 | Official Email | Work email of the contact. **Must use the company's domain** — no Gmail, Yahoo, Hotmail, or other free email providers. Domain should match company website if provided. | Required. Regex: valid email. Domain must not be in `[gmail.com, yahoo.com, hotmail.com, outlook.com, rediffmail.com]`. |
| 34 | Phone Number | Contact phone number with country code. Country code must be consistent with the registered state/country. | Required. Must include `+` and country code. Regex: `\+[0-9]{1,3}[0-9]{7,12}` |

---

## DOCUMENTS — Required, Alternatives & How They Are Read

### How Document Reading Works

Every uploaded file goes through this pipeline:

```
Upload (PDF / JPG / PNG / JPEG)
      ↓
Format check — only PDF/JPG/PNG/JPEG accepted
      ↓
Size check — minimum 10KB (not empty), maximum 10MB
      ↓
OCR Extraction:
  PDF  → pdfplumber extracts text
  Image → pytesseract extracts text
      ↓
Pattern Match — look for expected identifier in extracted text
      ↓
  FOUND   → document marked as valid
  NOT FOUND → document flagged → email vendor to re-upload correct document
```

---

### Document List

| Doc | Required When | What We Extract & Check | Primary Format | Alternative Accepted |
|---|---|---|---|---|
| **PAN Card** | Always | Look for PAN pattern `[A-Z]{5}[0-9]{4}[A-Z]` in text. Must match the PAN number entered in the form. | PDF or JPG/PNG of PAN card | PAN Allotment Letter from Income Tax Dept (also contains PAN number) |
| **GST Registration Certificate** | Always (unless GST exempt) | Look for 15-char GST pattern in text. Must match the GST number entered. | PDF from GST portal | GST Provisional Certificate (issued when registration is pending) OR GST Exemption Declaration Letter on company letterhead if GST exempt |
| **Certificate of Incorporation** | Pvt Ltd / Public Ltd | Look for "Corporate Identification Number" or CIN pattern in text. Must match CIN entered. | PDF from MCA | MOA + AOA (Memorandum and Articles of Association) together as alternative |
| **LLP Agreement** | LLP type | Look for "LLP Identification Number" or "LLP-IN" in text. | PDF | LLP Incorporation Certificate from MCA |
| **Partnership Deed** | Partnership Firm | Look for firm name + "partnership" in text. | PDF | Notarized partnership agreement |
| **Cancelled Cheque** | Always | Look for IFSC pattern `[A-Z]{4}0[A-Z0-9]{6}` in text. IFSC must match the one entered. Account number may also appear. | Scanned JPG/PNG or PDF | Bank Statement (first page showing account number + bank name) OR Bank letterhead letter confirming account details |
| **ISO 27001 Certificate** | If ISO = Yes | Look for "ISO/IEC 27001" and certificate number in text. Expiry date extracted and compared. | PDF | SOC 2 Type II Audit Report (accepted as equivalent) |
| **Data Processing Agreement (DPA)** | If data processing = Yes | Look for "Data Processing Agreement" or "DPA" in text. Basic presence check only. | PDF | Signed Undertaking Letter on company letterhead stating data processing compliance intent (treated as Pending, not Approved — full DPA still needed) |
| **MSME Certificate** | If MSME No. provided | Look for "Udyam Registration" and MSME registration number in text. | PDF from Udyam portal | Udyog Aadhaar certificate (older format, accepted) |

---

## Database Schema

### Table: `vendors`
```
id              UUID PRIMARY KEY
email           TEXT UNIQUE NOT NULL
otp             VARCHAR(6)         -- Phase 3: OTP auth not yet implemented
otp_expires_at  TIMESTAMP          -- Phase 3
session_token   TEXT
created_at      TIMESTAMP DEFAULT NOW()
```

### Table: `applications`
```
id                    UUID PRIMARY KEY
vendor_id             UUID REFERENCES vendors(id)
version               INTEGER NOT NULL DEFAULT 1   -- increments on new submission cycle
status                TEXT  -- 'draft' | 'submitted'  (incomplete/under_review/approved/rejected = Phase 2+)

-- Section 1: Company Info
company_name          TEXT
company_type          TEXT
incorporation_date    DATE
registered_address    TEXT
city                  TEXT
state                 TEXT
employee_count        INTEGER
annual_turnover       TEXT
website               TEXT

-- Section 2: Legal & Tax
pan_number            VARCHAR(10)
gst_number            VARCHAR(15)
cin_number            VARCHAR(21)
llp_number            TEXT
msme_number           TEXT
signatory_name        TEXT           -- was director_name in original plan
din                   VARCHAR(8)     -- for Private/Public Ltd
dpin                  VARCHAR(8)     -- for LLP

-- Section 3: Banking
account_holder_name   TEXT
bank_name             TEXT
account_number        TEXT
ifsc_code             VARCHAR(11)
account_type          TEXT

-- Section 4: IT & Security
service_nature        TEXT
processes_data        BOOLEAN
data_in_india         BOOLEAN
cloud_provider        TEXT
iso_certified         BOOLEAN
iso_cert_number       TEXT
iso_expiry_date       DATE
soc2_audited          BOOLEAN
cyber_insurance       BOOLEAN
cyber_coverage_crores DECIMAL

-- Section 5: Contact
contact_name          TEXT
contact_email         TEXT
contact_phone         TEXT

-- Metadata
validation_errors     JSONB
submitted_at          TIMESTAMP
created_at            TIMESTAMP DEFAULT NOW()
updated_at            TIMESTAMP DEFAULT NOW()
```

### Table: `documents`
```
id                  UUID PRIMARY KEY
vendor_id           UUID REFERENCES vendors(id)    -- scoped by vendor (not application)
application_id      UUID REFERENCES applications(id)  -- optional; set when doc linked to app
doc_type            TEXT   -- 'pan_card', 'gst_cert', 'incorporation', etc.
file_name           TEXT
file_url            TEXT   -- Supabase public storage URL
uploaded_at         TIMESTAMP DEFAULT NOW()
-- NOT YET: file_size_kb, is_valid, extracted_text, validation_message (Phase 2 / OCR)
```

> **Note:** Documents queried by `vendor_id` only at submit time. All docs uploaded by vendor are visible to submission validation regardless of which application they belong to. This is the current design — Phase 2 will tighten scoping.

---

## API Endpoints

### Auth
```
POST /api/auth/login
  Body: { email }
  Action: Find or create vendor by email, return JWT (no OTP — Phase 3 upgrade)
  Returns: { token, vendor_id }
  Note: OTP flow (POST /auth/start + /auth/verify) planned for Phase 3
```

### Document Upload
```
POST /api/documents/upload
  Auth: Bearer token required
  Body: multipart/form-data { file, doc_type, application_id? }
  Action: Format check (.pdf/.jpg/.jpeg/.png) → size check (10KB–10MB) → upload to Supabase Storage → upsert documents row
  Returns: { doc_id, file_url, doc_type }
  Note: No OCR/extraction yet (Phase 2). Upload succeeds or fails on format+size only.

DELETE /api/documents/all
  Auth: Bearer token required
  Action: Delete all documents for this vendor (used by test runner)
  Returns: { deleted: true, vendor_id }
```

### Application
```
POST /api/application/submit
  Auth: Bearer token required
  Body: All form fields as JSON
  Action:
    1. Fetch all uploaded doc_types for vendor (by vendor_id)
    2. Run all validation rules (format + cross-field + conditional + docs present)
    3a. If errors → save/update as draft → return { status: "draft", errors[] }
    3b. If clean  → save as submitted → return { status: "submitted", version }
  Returns: { application_id, status, version, errors[] }

POST /api/application/draft
  Auth: Bearer token required
  Body: Any partial form fields as JSON
  Action: Save/update draft unconditionally (no validation)
  Returns: { application_id, status: "draft", version }

GET /api/application/status
  Auth: Bearer token required
  Returns: { application_id, status, submitted_at, version }

GET /api/application/{id}
  Auth: Bearer token required
  Returns: Full application row

DELETE /api/application/reset
  Auth: Bearer token required
  Action: Delete all applications for this vendor (used by test runner)
  Returns: { deleted: true, vendor_id }
```

### Upsert Logic (applications)
```
Submit called →
  1. Existing draft row?     → update in-place (same id, same version)
  2. No draft, has submitted? → insert new row, version = latest + 1  (Phase 2 resubmit)
  3. Nothing exists          → insert new row, version = 1
```

---

## Validation Rules — All in One Place

### Regex Validators
```python
PAN        = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
GST        = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z][Z][0-9A-Z]$'
CIN        = r'^[UL][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$'
IFSC       = r'^[A-Z]{4}0[A-Z0-9]{6}$'
DIN        = r'^[0-9]{8}$'
ACCOUNT_NO = r'^[0-9]{9,18}$'
PHONE      = r'^\+[0-9]{1,3}[0-9]{7,12}$'
MSME       = r'^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$'
```

### Cross-Field Validators
```
1. GST state code (chars 0-1) must match State dropdown selection
2. PAN (chars 2-11 of GST) must match PAN field
3. CIN year (chars 8-11, 0-indexed) must match year in Date of Incorporation  ← was 7-10, corrected
4. Account Holder Name vs Company Name — Phase 2 AI fuzzy check (not Phase 1 rule)
5. Contact email domain must not be free provider (gmail, yahoo, etc.)
6. If data_in_india = False → WARNING FLAG only (not a hard block). Submits with flag. RBI review applies.
7. If processes_data = Yes → DPA doc must be uploaded + cyber_insurance = Yes
8. If iso_certified = Yes → cert number + expiry date required + ISO doc uploaded
9. If msme_number provided → msme_cert doc must be uploaded
10. ISO expiry date must be in the future
11. Incorporation date must be in the past
12. PAN 4th char: C = Pvt/Public Ltd, F = LLP + Partnership Firm, P = Sole Proprietorship
```

### Email Triggers
```
NOT YET IMPLEMENTED — Phase 3
Planned:
1. OTP Email          → on POST /auth/start
2. Confirmation Email → on successful submission (status = submitted)
3. Error Email        → on failed validation (status = draft, errors returned inline to frontend)
```

---

## Actual Folder Structure (Built)

```
vendor_onbording_backend/
├── main.py                    # FastAPI app, CORS, router registration
├── .env                       # SUPABASE_URL, SUPABASE_KEY, JWT_SECRET
├── routers/
│   ├── auth.py                # POST /api/auth/login
│   ├── documents.py           # POST /api/documents/upload, DELETE /api/documents/all
│   └── application.py        # POST /submit, POST /draft, GET /status, DELETE /reset, GET /{id}
├── models/
│   └── schemas.py             # Pydantic: ApplicationSubmit, ApplicationResponse, StatusResponse, DocumentResponse
├── services/
│   ├── supabase_client.py     # Supabase client singleton
│   ├── jwt_service.py         # encode_token / decode_token
│   └── validation.py          # All Phase 1 rules (format + cross-field + conditional + docs)
└── validation_rules.md        # Human-readable rule reference
```

> **Not yet built:** `ocr.py` (Phase 2), `email.py` (Phase 3), `storage.py` (inline in documents.py)

---

## Phase Status

### Phase 1 — COMPLETE
- Rule-based form validation (format + cross-field + conditional + docs present)
- Draft/submit flow with upsert logic
- Document upload (format + size check, stored in Supabase Storage)
- 10 final test cases generated + run against live API, 13/13 passing
- Data generator: 5 generators (company, legal, banking, compliance, contact, documents)

### Phase 2 — NEXT
- OCR extraction: pdfplumber (PDF) + pytesseract (images)
- Extract and cross-verify: PAN from PAN card, GSTIN from GST cert, IFSC from cheque, etc.
- AI fuzzy checks: account_holder_name vs company_name, email domain vs website
- status: `under_review` while AI processes; `approved` / `pending` / `rejected` after
- Tighten doc scoping: link docs to application_id at submit time

### Phase 3 — PLANNED
- OTP email auth (replace direct login)
- Confirmation + error emails via Resend
- Admin dashboard

## Known Limitations / Open Issues

1. **Doc scoping**: Documents queried by `vendor_id` only — all docs ever uploaded visible to any submission. Fix in Phase 2: scope to docs uploaded since last submit or link by session.
2. **RBI flag not persisted**: `data_in_india=False` logs warning but no `rbi_flag` column in DB yet.
3. **No diff check**: Re-submitting identical data creates new version. Guard needed before Phase 2.
