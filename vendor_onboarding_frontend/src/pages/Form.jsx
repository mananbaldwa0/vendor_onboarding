import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { submitApplication, saveDraft, uploadDocument, getStatus, getApplication, getDocuments } from '../api'
import GroupCard from '../components/GroupCard'

const INDIAN_STATES = [
  'Andhra Pradesh','Arunachal Pradesh','Assam','Bihar','Chhattisgarh','Goa','Gujarat',
  'Haryana','Himachal Pradesh','Jharkhand','Karnataka','Kerala','Madhya Pradesh',
  'Maharashtra','Manipur','Meghalaya','Mizoram','Nagaland','Odisha','Punjab','Rajasthan',
  'Sikkim','Tamil Nadu','Telangana','Tripura','Uttar Pradesh','Uttarakhand','West Bengal',
  'Delhi','Jammu & Kashmir','Ladakh','Puducherry','Chandigarh','Andaman & Nicobar',
  'Dadra & Nagar Haveli','Daman & Diu','Lakshadweep'
]

const COMPANY_TYPES = ['Private Limited','Public Limited','LLP','Partnership Firm','Sole Proprietorship']
const TURNOVER_OPTIONS = ['<1 Cr','1-10 Cr','10-100 Cr','>100 Cr']
const ACCOUNT_TYPES = ['Current','Savings']
const SERVICE_TYPES = ['Core Banking Software','Cybersecurity Tool','Cloud Infrastructure','SaaS Platform','Data Analytics','HR/ERP Software','Network/Hardware','Other']
const CLOUD_PROVIDERS = ['AWS','Azure','GCP','Private Cloud','On-Premise','Hybrid','Not Applicable']

function Field({ label, children, hint, required }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
    </div>
  )
}

function Input({ value, onChange, type = 'text', placeholder }) {
  return (
    <input
      type={type}
      value={value || ''}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
    />
  )
}

function Select({ value, onChange, options, placeholder = 'Select...' }) {
  return (
    <select
      value={value || ''}
      onChange={e => onChange(e.target.value)}
      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
    >
      <option value="">{placeholder}</option>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  )
}

function Toggle({ value, onChange, label }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${value ? 'bg-indigo-600' : 'bg-gray-300'}`}
    >
      <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${value ? 'translate-x-6' : 'translate-x-1'}`} />
    </button>
  )
}

const NON_FORM_FIELDS = new Set(['id', 'vendor_id', 'status', 'version', 'submitted_at', 'created_at'])

export default function Form() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    gst_registered: false,
    iso_certified: false,
    soc2_audited: false,
    processes_data: false,
    cyber_insurance: false,
    data_in_india: true,
  })
  const [loading, setLoading] = useState(false)
  const [draftLoading, setDraftLoading] = useState(false)
  const [draftSaved, setDraftSaved] = useState(false)
  const [error, setError] = useState('')
  const [validationErrors, setValidationErrors] = useState([])
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    getStatus()
      .then(async status => {
        const uploadedDocs = await getDocuments().catch(() => [])
        if (uploadedDocs.length > 0) {
          const docState = {}
          for (const d of uploadedDocs) {
            docState[d.doc_type] = { status: 'done', fileName: d.file_name }
          }
          setDocs(docState)
        }
        if (!status?.application_id) return
        const app = await getApplication(status.application_id)
        const formData = {}
        for (const [k, v] of Object.entries(app)) {
          if (!NON_FORM_FIELDS.has(k) && v !== null && v !== undefined) {
            formData[k] = v
          }
        }
        setForm(f => ({ ...f, ...formData }))
      })
      .catch(() => {})
  }, [])

  function handleLogout() {
    localStorage.clear()
    navigate('/')
  }

  function set(key) {
    return val => setForm(f => ({ ...f, [key]: val }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    setValidationErrors([])
    try {
      const payload = { ...form }
      Object.keys(payload).forEach(k => { if (payload[k] === '') payload[k] = null })
      const result = await submitApplication(payload)
      if (result.errors && result.errors.length > 0) {
        setValidationErrors(result.errors)
      } else {
        setSubmitted(true)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleDraft() {
    setDraftLoading(true)
    setDraftSaved(false)
    setError('')
    try {
      const payload = { ...form }
      Object.keys(payload).forEach(k => { if (payload[k] === '') payload[k] = null })
      await saveDraft(payload)
      setDraftSaved(true)
      setTimeout(() => setDraftSaved(false), 3000)
    } catch (err) {
      setError(err.message)
    } finally {
      setDraftLoading(false)
    }
  }

  const showDIN = ['Private Limited', 'Public Limited'].includes(form.company_type)
  const showDPIN = form.company_type === 'LLP'

  // document upload state: { doc_type: { file, status: 'idle'|'uploading'|'done'|'error', error } }
  const [docs, setDocs] = useState({})

  function setDocState(docType, patch) {
    setDocs(d => ({ ...d, [docType]: { ...d[docType], ...patch } }))
  }

  async function handleFileChange(docType, file) {
    if (!file) return
    setDocState(docType, { file, status: 'uploading', error: null })
    try {
      await uploadDocument(file, docType)
      setDocState(docType, { status: 'done', fileName: file.name })
    } catch (err) {
      setDocState(docType, { status: 'error', error: err.message })
    }
  }

  function requiredDocs() {
    const list = [
      { key: 'pan_card', label: 'PAN Card', always: true },
      { key: 'cancelled_cheque', label: 'Cancelled Cheque', always: true },
      { key: 'gst_cert', label: 'GST Certificate', show: form.gst_registered },
      { key: 'incorporation', label: 'Certificate of Incorporation', show: showDIN },
      { key: 'llp_agreement', label: 'LLP Agreement', show: showDPIN },
      { key: 'partnership_deed', label: 'Partnership Deed', show: form.company_type === 'Partnership Firm' },
      { key: 'iso_cert', label: 'ISO 27001 Certificate', show: form.iso_certified },
      { key: 'dpa', label: 'Data Processing Agreement (DPA)', show: form.processes_data },
      { key: 'msme_cert', label: 'MSME Certificate', show: !!form.msme_number },
    ]
    return list.filter(d => d.always || d.show)
  }

  if (submitted) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-5">
            <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Application Submitted</h2>
          <p className="text-sm text-gray-500 mb-1">Your application is under review.</p>
          <p className="text-sm text-gray-500 mb-8">You will receive an email shortly with the status of your submission.</p>
          <button
            onClick={() => navigate('/status')}
            className="w-full bg-indigo-600 text-white rounded-lg py-3 text-sm font-semibold hover:bg-indigo-700 transition"
          >
            View Application Status
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Vendor Onboarding Form</h1>
            <p className="text-sm text-gray-500 mt-1">Fill all sections and submit. You can resubmit if needed.</p>
          </div>
          <button onClick={handleLogout} className="text-sm text-gray-400 hover:text-gray-600 mt-1">Logout</button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">

          {/* GROUP 1 */}
          <GroupCard icon="🏢" title="Company Identity" count="9 fields">
            <Field label="Legal Company Name" required>
              <Input value={form.company_name} onChange={set('company_name')} placeholder="As registered with MCA" />
            </Field>
            <Field label="Company Type" required>
              <Select value={form.company_type} onChange={set('company_type')} options={COMPANY_TYPES} />
            </Field>
            <Field label="Date of Incorporation" required>
              <Input type="date" value={form.incorporation_date} onChange={set('incorporation_date')} />
            </Field>
            <Field label="Registered Address" required>
              <Input value={form.registered_address} onChange={set('registered_address')} placeholder="Full address as per certificate" />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="City" required>
                <Input value={form.city} onChange={set('city')} placeholder="e.g. Mumbai" />
              </Field>
              <Field label="State" required>
                <Select value={form.state} onChange={set('state')} options={INDIAN_STATES} />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Employee Count" required>
                <Input type="number" value={form.employee_count} onChange={v => set('employee_count')(v ? parseInt(v) : null)} placeholder="Total on payroll" />
              </Field>
              <Field label="Annual Turnover (Last FY)" required>
                <Select value={form.annual_turnover} onChange={set('annual_turnover')} options={TURNOVER_OPTIONS} />
              </Field>
            </div>
            <Field label="Company Website" hint="Optional">
              <Input value={form.website} onChange={set('website')} placeholder="https://yourcompany.com" />
            </Field>
          </GroupCard>

          {/* GROUP 2 */}
          <GroupCard icon="🪪" title="PAN Card" count="1 field">
            <Field label="PAN Number" hint="Format: AAAAA0000A" required>
              <Input value={form.pan_number} onChange={set('pan_number')} placeholder="ABCDE1234F" />
            </Field>
          </GroupCard>

          {/* GROUP 3 */}
          <GroupCard icon="🧾" title="GST" count="2 fields">
            <Field label="GST Registered?" required>
              <div className="flex items-center gap-3">
                <Toggle value={!!form.gst_registered} onChange={set('gst_registered')} />
                <span className="text-sm text-gray-600">{form.gst_registered ? 'Yes' : 'No'}</span>
              </div>
            </Field>
            {form.gst_registered && (
              <Field label="GST Number" hint="15-character GST registration number" required>
                <Input value={form.gst_number} onChange={set('gst_number')} placeholder="22AAAAA0000A1Z5" />
              </Field>
            )}
          </GroupCard>

          {/* GROUP 4 */}
          <GroupCard icon="👤" title="Director / Company IDs" count="6 fields">
            <Field label="Authorized Signatory Name" required>
              <Input value={form.signatory_name} onChange={set('signatory_name')} placeholder="Full legal name" />
            </Field>
            {showDIN && (
              <>
                <Field label="DIN (Director Identification No.)" hint="8-digit MCA number" required>
                  <Input value={form.din} onChange={set('din')} placeholder="12345678" />
                </Field>
                <Field label="CIN (Company Identification No.)" hint="21-character MCA number e.g. U72900MH2015PTC123456" required>
                  <Input value={form.cin_number} onChange={set('cin_number')} placeholder="U72900MH2015PTC123456" />
                </Field>
              </>
            )}
            {showDPIN && (
              <>
                <Field label="DPIN (Designated Partner Identification No.)" hint="8-digit MCA number for LLP partners" required>
                  <Input value={form.dpin} onChange={set('dpin')} placeholder="12345678" />
                </Field>
                <Field label="LLP Identification No." hint="Format: AAA-1234" required>
                  <Input value={form.llp_number} onChange={set('llp_number')} placeholder="AAA-1234" />
                </Field>
              </>
            )}
            {!showDIN && !showDPIN && (
              <p className="text-xs text-gray-400">Select company type above to see relevant ID fields.</p>
            )}
            <Field label="MSME Registration No." hint="Optional — format: UDYAM-XX-00-0000000">
              <Input value={form.msme_number} onChange={set('msme_number')} placeholder="UDYAM-MH-00-0000000" />
            </Field>
          </GroupCard>

          {/* GROUP 5 */}
          <GroupCard icon="🏦" title="Banking Details" count="5 fields">
            <Field label="Account Holder Name" required>
              <Input value={form.account_holder_name} onChange={set('account_holder_name')} placeholder="Name as on bank account" />
            </Field>
            <Field label="Bank Name" required>
              <Input value={form.bank_name} onChange={set('bank_name')} placeholder="e.g. HDFC Bank" />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Account Number" required>
                <Input value={form.account_number} onChange={set('account_number')} placeholder="9–18 digit account no." />
              </Field>
              <Field label="IFSC Code" required>
                <Input value={form.ifsc_code} onChange={set('ifsc_code')} placeholder="HDFC0001234" />
              </Field>
            </div>
            <Field label="Account Type" required>
              <Select value={form.account_type} onChange={set('account_type')} options={ACCOUNT_TYPES} />
            </Field>
          </GroupCard>

          {/* GROUP 6 */}
          <GroupCard icon="🔐" title="ISO 27001 Certification" count="4 fields">
            <Field label="ISO 27001 Certified?" required>
              <div className="flex items-center gap-3">
                <Toggle value={!!form.iso_certified} onChange={set('iso_certified')} />
                <span className="text-sm text-gray-600">{form.iso_certified ? 'Yes' : 'No'}</span>
              </div>
            </Field>
            {form.iso_certified && (
              <>
                <Field label="Certificate Number" required>
                  <Input value={form.iso_cert_number} onChange={set('iso_cert_number')} placeholder="Cert number on ISO document" />
                </Field>
                <Field label="Certificate Expiry Date" required>
                  <Input type="date" value={form.iso_expiry_date} onChange={set('iso_expiry_date')} />
                </Field>
              </>
            )}
            <Field label="SOC 2 Type II Audited?">
              <div className="flex items-center gap-3">
                <Toggle value={!!form.soc2_audited} onChange={set('soc2_audited')} />
                <span className="text-sm text-gray-600">{form.soc2_audited ? 'Yes' : 'No'}</span>
              </div>
            </Field>
          </GroupCard>

          {/* GROUP 7 */}
          <GroupCard icon="🛡️" title="Data & Compliance" count="6 fields">
            <Field label="Nature of IT Service" required>
              <Select value={form.service_nature} onChange={set('service_nature')} options={SERVICE_TYPES} />
            </Field>
            <Field label="Does service process bank/customer data?" required>
              <div className="flex items-center gap-3">
                <Toggle value={!!form.processes_data} onChange={set('processes_data')} />
                <span className="text-sm text-gray-600">{form.processes_data ? 'Yes' : 'No'}</span>
              </div>
            </Field>
            <Field label="Is data stored within India?" required>
              <div className="flex items-center gap-3">
                <Toggle value={!!form.data_in_india} onChange={set('data_in_india')} />
                <span className="text-sm text-gray-600">{form.data_in_india ? 'Yes' : 'No'}</span>
              </div>
            </Field>
            <Field label="Cloud Provider" required>
              <Select value={form.cloud_provider} onChange={set('cloud_provider')} options={CLOUD_PROVIDERS} />
            </Field>
            <Field label="Cyber Insurance Policy?" required={!!form.processes_data}>
              <div className="flex items-center gap-3">
                <Toggle value={!!form.cyber_insurance} onChange={set('cyber_insurance')} />
                <span className="text-sm text-gray-600">{form.cyber_insurance ? 'Yes' : 'No'}</span>
              </div>
            </Field>
            {form.cyber_insurance && (
              <Field label="Cyber Insurance Coverage (₹ Crores)" required>
                <Input type="number" value={form.cyber_coverage_crores} onChange={v => set('cyber_coverage_crores')(v ? parseFloat(v) : null)} placeholder="Coverage amount in crores" />
              </Field>
            )}
          </GroupCard>

          {/* GROUP 8 */}
          <GroupCard icon="📞" title="Primary Contact" count="3 fields">
            <Field label="Contact Name" required>
              <Input value={form.contact_name} onChange={set('contact_name')} placeholder="Full name" />
            </Field>
            <Field label="Official Email" hint="Must use company domain — no Gmail/Yahoo etc." required>
              <Input type="email" value={form.contact_email} onChange={set('contact_email')} placeholder="you@company.com" />
            </Field>
            <Field label="Phone Number" hint="Include country code" required>
              <Input value={form.contact_phone} onChange={set('contact_phone')} placeholder="+91XXXXXXXXXX" />
            </Field>
          </GroupCard>

          {/* DOCUMENTS */}
          <GroupCard icon="📎" title="Documents" count={`${requiredDocs().length} required`}>
            <p className="text-xs text-gray-400 -mt-1">Upload changes dynamically based on your form answers above.</p>
            {requiredDocs().map(doc => {
              const state = docs[doc.key] || {}
              return (
                <div key={doc.key} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-700">{doc.label}</p>
                    {state.fileName && state.status === 'done' && <p className="text-xs text-gray-400 mt-0.5 truncate max-w-xs">{state.fileName}</p>}
                    {state.error && <p className="text-xs text-red-500 mt-0.5">{state.error}</p>}
                  </div>
                  <div className="flex items-center gap-2">
                    {state.status === 'done' && <span className="text-green-600 text-xs font-semibold">✓ Uploaded</span>}
                    {state.status === 'uploading' && <span className="text-gray-400 text-xs">Uploading...</span>}
                    <label className="cursor-pointer bg-white border border-gray-300 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 transition">
                      {state.status === 'done' ? 'Replace' : 'Choose File'}
                      <input
                        type="file"
                        accept=".pdf,.jpg,.jpeg,.png"
                        className="hidden"
                        onChange={e => handleFileChange(doc.key, e.target.files[0])}
                      />
                    </label>
                  </div>
                </div>
              )
            })}
          </GroupCard>

          {validationErrors.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-2xl px-5 py-4">
              <p className="text-sm font-semibold text-red-700 mb-2">Fix these errors before submitting:</p>
              <ul className="space-y-1">
                {validationErrors.map((e, i) => (
                  <li key={i} className="text-sm text-red-600 flex gap-2">
                    <span className="mt-0.5 shrink-0">•</span>{e}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="flex gap-3 pb-10">
            <button
              type="button"
              onClick={handleDraft}
              disabled={draftLoading}
              className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-3 text-sm font-medium hover:bg-gray-50 disabled:opacity-50 transition"
            >
              {draftLoading ? 'Saving...' : draftSaved ? '✓ Draft Saved' : 'Save as Draft'}
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-indigo-600 text-white rounded-lg py-3 text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition"
            >
              {loading ? 'Submitting...' : 'Submit Application'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
