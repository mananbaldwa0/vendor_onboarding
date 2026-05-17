# Vendor Onboarding System

An end-to-end vendor onboarding platform with AI-powered risk scoring, OCR document validation, and an admin review dashboard.

**Live Demo:** https://vendor-onboarding-blue.vercel.app

**Engineering Scorecard:** https://mananbaldwa0.github.io/vendor_onboarding/manan_engineering_scorecard.html

---

## How It Works

1. Vendor registers with email → receives JWT token
2. Fills onboarding form (company info, bank details, compliance)
3. Uploads documents (PAN card, GST certificate, bank cancelled cheque, ISO cert, etc.)
4. Form submits → 3-layer validation runs:
   - **Layer 1** — Rule-based checks (field format, date logic, cross-field consistency)
   - **Layer 2** — OCR extraction (pdfplumber for PDFs, pytesseract for images) cross-checked against form fields
   - **Layer 3** — LLM risk scoring (Groq / LLaMA 3.3 70B) for fuzzy name matching, document readability, and compliance flags
5. Risk score computed → decision assigned (approved / human review / high risk / rejected)
6. Vendor receives an email notification with their application status
7. Admin dashboard shows all vendors, risk scores, flags, and LLM reasoning

---

## Test Cases

Three pre-built escalation scenarios in [`test_cases/`](./test_cases/).

| Case | Email |
|---|---|
| [Case 1](./test_cases/case_01_error_then_approved/) | anita@crescendotech.in |
| [Case 2](./test_cases/case_02_high_risk_approved/) | deepak@nexaflow.io |
| [Case 3](./test_cases/case_03_scammer_rejected/) | suresh@vortexglobal.tech |

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | React + Vite + Tailwind CSS |
| Backend | FastAPI + Python |
| Database | Supabase (PostgreSQL + Storage) |
| OCR | pdfplumber (PDFs) + pytesseract (images) |
| AI | Groq API (LLaMA 3.3 70B Versatile) |
| Email | Resend API |
| Frontend deploy | Vercel |
| Backend deploy | Render |
