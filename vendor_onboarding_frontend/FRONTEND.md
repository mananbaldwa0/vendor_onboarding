# Vendor Onboarding — Frontend Reference
> Phase 1 complete. Last updated: May 2026

---

## Stack

- React 18 + Vite
- Tailwind CSS
- React Router v6

---

## Run

```bash
cd vendor_onboarding_frontend
npm install
npm run dev
# Opens at http://localhost:3000
```

Backend must also be running at port 8000 (Vite proxies `/api` → `localhost:8000`). Two terminals needed.

---

## Pages

| Route | File | Description |
|---|---|---|
| `/` | `Login.jsx` | Email input → POST /api/auth/login → stores token |
| `/form` | `Form.jsx` | 8-group vendor form with docs upload, draft + submit |
| `/status` | `Status.jsx` | Shows latest submission status, version, submitted_at |

Protected routes (`/form`, `/status`) redirect to `/` if no token in localStorage.

---

## Auth Flow

1. Vendor enters email on login page
2. Backend returns JWT token + vendor_id
3. Token stored in `localStorage`
4. All API calls send `Authorization: Bearer <token>`
5. Logout clears localStorage → redirects to `/`

---

## Form — 8 Groups + Documents

| Group | Fields | Conditional Logic |
|---|---|---|
| 1 — Company Identity | company_name, company_type, incorporation_date, registered_address, city, state, employee_count, annual_turnover, website | — |
| 2 — PAN | pan_number | — |
| 3 — GST | gst_registered (toggle), gst_number | gst_number shown only if gst_registered = true |
| 4 — Director / Company IDs | signatory_name, din, cin_number, dpin, llp_number, msme_number | din+cin shown for Private/Public Ltd; dpin+llp shown for LLP; msme always optional |
| 5 — Banking | account_holder_name, bank_name, account_number, ifsc_code, account_type | — |
| 6 — ISO 27001 | iso_certified (toggle), iso_cert_number, iso_expiry_date, soc2_audited | cert fields shown only if iso_certified = true |
| 7 — Data & Compliance | service_nature, processes_data, data_in_india, cloud_provider, cyber_insurance, cyber_coverage_crores | cyber_coverage shown only if cyber_insurance = true |
| 8 — Contact | contact_name, contact_email, contact_phone | — |
| Documents | Dynamic upload list | Pan Card + Cancelled Cheque always; others conditional on form values |

### Boolean Toggle Initialization — Critical

All boolean fields must initialize to `false` (not `null`/`undefined`) in `useState`. If a boolean is `undefined`, `JSON.stringify` omits it entirely → backend sees `None` → triggers "Specify..." error even when user didn't touch the toggle.

```javascript
const [form, setForm] = useState({
  gst_registered: false,
  iso_certified: false,
  soc2_audited: false,
  processes_data: false,
  cyber_insurance: false,
  data_in_india: true,   // default true — India is the expected/common case
})
```

### Draft Load — Merge Not Replace

When loading an existing draft, merge with defaults instead of replacing:
```javascript
// WRONG — wipes boolean defaults, any missing key becomes undefined
setForm(formData)

// CORRECT — keeps defaults for any field not present in draft
setForm(f => ({ ...f, ...formData }))
```
Null values from DB are filtered before merge, so `false` defaults survive.

---

## Documents Upload

Documents section appears after Group 8. List updates dynamically as user fills the form.

| Document | Shown When |
|---|---|
| PAN Card | Always |
| Cancelled Cheque | Always |
| GST Certificate | `gst_registered = true` |
| Certificate of Incorporation | company_type = Private/Public Limited |
| LLP Agreement | company_type = LLP |
| Partnership Deed | company_type = Partnership Firm |
| ISO 27001 Certificate | `iso_certified = true` |
| Data Processing Agreement (DPA) | `processes_data = true` |
| MSME Certificate | `msme_number` field not empty |

Upload behavior:
- File selected → immediately uploads via POST /api/documents/upload
- Shows "Uploading..." → "✓ Uploaded" on success with filename shown below label
- Shows error on failure (file too small, wrong format, etc.)
- "Replace" button shown if already uploaded
- Accepted: `.pdf`, `.jpg`, `.jpeg`, `.png`

### Docs Pre-Populated on Page Load

On form mount, `GET /api/documents/` is called. Any already-uploaded docs (from this session or any previous version) pre-populate as `{ status: 'done', fileName }`. User sees "✓ Uploaded" immediately without re-uploading.

```javascript
useEffect(() => {
  getStatus().then(async status => {
    const uploadedDocs = await getDocuments().catch(() => [])
    if (uploadedDocs.length > 0) {
      const docState = {}
      for (const d of uploadedDocs) {
        docState[d.doc_type] = { status: 'done', fileName: d.file_name }
      }
      setDocs(docState)
    }
    // then load form data from draft if exists...
  })
}, [])
```

---

## Form Submission Flow

**Save as Draft** (left button):
- Calls POST /api/application/draft
- No validation runs
- Updates existing draft in-place (no new version)
- Button shows "✓ Draft Saved" for 3 seconds then resets

**Submit Application** (right button):
- Calls POST /api/application/submit
- Backend runs full rule-based validation
- If errors → red error box shown inline. No navigation.
- If clean → navigates to `/status`

---

## Validation Errors Display

Errors returned from backend shown as bulleted red list below the documents section:

```
Fix these errors before submitting:
• Company name is required (min 3 characters)
• PAN 4th character 'X' does not match company type 'LLP'
• Missing required document: PAN Card
```

No client-side validation — all checks run server-side.

---

## Status Page

Shows:
- Application ID
- Version number
- Status badge (color-coded: draft=yellow, submitted=blue, approved=green, rejected=red, pending=orange)
- Submitted at timestamp
- "Resubmit / Update" button → navigates to `/form`
- "No application yet" state with Start Application button
- Logout button

---

## API Calls (`src/api.js`)

| Function | Endpoint | Auth | Notes |
|---|---|---|---|
| `login(email)` | POST /api/auth/login | No | Returns token + vendor_id |
| `submitApplication(data)` | POST /api/application/submit | Bearer | Returns errors[] if validation fails |
| `saveDraft(data)` | POST /api/application/draft | Bearer | No validation; updates in-place |
| `getStatus()` | GET /api/application/status | Bearer | Returns latest version |
| `getApplication(id)` | GET /api/application/{id} | Bearer | Returns full application row |
| `getDocuments()` | GET /api/documents/ | Bearer | Returns all doc rows for vendor |
| `uploadDocument(file, docType)` | POST /api/documents/upload | Bearer | multipart/form-data |

---

## Reusable Components

| Component | File | Props | Notes |
|---|---|---|---|
| `GroupCard` | `components/GroupCard.jsx` | `icon`, `title`, `count`, `children` | Section wrapper with emoji icon + field count |
| `Field` | inline in Form.jsx | `label`, `required`, `hint`, `children` | Shows red `*` if required |
| `Input` | inline in Form.jsx | `value`, `onChange`, `type`, `placeholder` | Controlled input |
| `Select` | inline in Form.jsx | `value`, `onChange`, `options`, `placeholder` | Dropdown |
| `Toggle` | inline in Form.jsx | `value`, `onChange` | Boolean switch, uses `!!value` coercion |

---

## File Structure

```
vendor_onboarding_frontend/
├── package.json
├── vite.config.js       — proxy /api → localhost:8000
├── tailwind.config.js
├── FRONTEND.md          — this file
└── src/
    ├── main.jsx
    ├── App.jsx           — routes + auth guard
    ├── api.js            — all fetch calls
    ├── index.css
    ├── pages/
    │   ├── Login.jsx
    │   ├── Form.jsx      — 8 groups + documents + draft + submit
    │   └── Status.jsx
    └── components/
        └── GroupCard.jsx
```

---

## Phase 1 Status — COMPLETE

All pages built and working against live backend:
- `/` Login with email → JWT stored in localStorage
- `/form` 8-group form + document uploads + draft + submit + pre-filled from existing draft/docs
- `/status` Shows latest application status + version + resubmit button

Tested with 11 test cases (10 automated + 1 manual 3-round trail test).

---

## What Is Not Built Yet (Phase 2+)

| Feature | Planned Phase |
|---|---|
| Show OCR verification result per document | Phase 2 — backend OCR is done, frontend display pending |
| Show AI risk score on status page | Phase 2 |
| Client-side field validation (regex on frontend) | Backlog |
| OTP auth on login (replace direct email login) | Phase 3 |
| Admin dashboard | Phase 4 |
