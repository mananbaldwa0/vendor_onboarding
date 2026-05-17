import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminGetVendors } from '../../api'
import { FIELD_GROUPS, DOCUMENT_DOCS } from '../../data/fieldDocs'

// ─── Constants ────────────────────────────────────────────────────────────────

const DECISION_CONFIG = {
  approved:             { color: 'bg-green-100 text-green-700',   label: 'Approved' },
  waiting_for_response: { color: 'bg-yellow-100 text-yellow-700', label: 'Waiting for Response' },
  human_review:         { color: 'bg-orange-100 text-orange-700', label: 'Human Review' },
  high_risk_review:     { color: 'bg-red-100 text-red-700',       label: 'High Risk Review' },
  rejected:             { color: 'bg-red-200 text-red-800',       label: 'Rejected' },
}

const STATUS_CONFIG = {
  submitted: { color: 'bg-blue-100 text-blue-700',   label: 'Submitted' },
  draft:     { color: 'bg-gray-100 text-gray-600',   label: 'Draft' },
  approved:  { color: 'bg-green-100 text-green-700', label: 'Approved' },
  rejected:  { color: 'bg-red-100 text-red-700',     label: 'Rejected' },
}

const SEVERITY_CONFIG = {
  high:   { color: 'bg-red-100 text-red-700 border-red-200',       dot: 'bg-red-500' },
  medium: { color: 'bg-yellow-100 text-yellow-700 border-yellow-200', dot: 'bg-yellow-500' },
  low:    { color: 'bg-gray-100 text-gray-600 border-gray-200',    dot: 'bg-gray-400' },
}

const AI_STATUS_CONFIG = {
  done:       { color: 'text-green-600', label: 'Done' },
  processing: { color: 'text-blue-600',  label: 'Processing' },
  failed:     { color: 'text-red-600',   label: 'Failed' },
  not_started:{ color: 'text-gray-400',  label: 'Not started' },
}

// ─── Score Bar ────────────────────────────────────────────────────────────────

function ScoreBar({ score }) {
  if (score == null) return <span className="text-gray-400 text-sm">—</span>
  const color = score >= 76 ? 'bg-red-500' : score >= 51 ? 'bg-orange-400' : score >= 6 ? 'bg-yellow-400' : 'bg-green-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-sm font-semibold text-gray-700">{score}</span>
    </div>
  )
}

// ─── Badge ────────────────────────────────────────────────────────────────────

function Badge({ config, value }) {
  const c = config[value]
  if (!c) return <span className="text-gray-400 text-sm">—</span>
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${c.color}`}>
      {c.label}
    </span>
  )
}

// ─── Severity Tag ─────────────────────────────────────────────────────────────

function SeverityTag({ severity }) {
  const c = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.low
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold border ${c.color}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {severity?.toUpperCase()}
    </span>
  )
}

// ─── Vendors Tab ─────────────────────────────────────────────────────────────

function VendorsTab({ vendors, loading, error }) {
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState(null)

  const filtered = vendors.filter(v => {
    const q = search.toLowerCase()
    return (
      v.email?.toLowerCase().includes(q) ||
      v.latest_application?.company_name?.toLowerCase().includes(q) ||
      v.review?.decision?.includes(q)
    )
  })

  if (loading) return <p className="text-sm text-gray-500 text-center py-16">Loading vendors...</p>
  if (error) return <p className="text-sm text-red-500 text-center py-16">{error}</p>
  if (!vendors.length) return <p className="text-sm text-gray-400 text-center py-16">No vendors yet.</p>

  return (
    <div>
      <div className="mb-4">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by company, email, or decision..."
          className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {/* Table header */}
        <div className="grid grid-cols-[2fr_2fr_1fr_1.5fr_1.5fr_1fr] gap-3 px-4 py-3 bg-gray-50 border-b border-gray-200 text-xs font-semibold text-gray-500 uppercase tracking-wide">
          <span>Company</span>
          <span>Email</span>
          <span>Ver.</span>
          <span>Status</span>
          <span>Decision</span>
          <span>Score</span>
        </div>

        {filtered.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-8">No results for "{search}"</p>
        )}

        {filtered.map(v => {
          const app = v.latest_application
          const rev = v.review
          const isOpen = expanded === v.vendor_id

          return (
            <div key={v.vendor_id} className="border-b border-gray-100 last:border-0">
              {/* Row */}
              <button
                onClick={() => setExpanded(isOpen ? null : v.vendor_id)}
                className="w-full grid grid-cols-[2fr_2fr_1fr_1.5fr_1.5fr_1fr] gap-3 px-4 py-4 text-left hover:bg-gray-50 transition items-center"
              >
                <span className="text-sm font-medium text-gray-900 truncate">
                  {app?.company_name || <span className="text-gray-400 italic">No application</span>}
                </span>
                <span className="text-sm text-gray-500 truncate">{v.email}</span>
                <span className="text-sm text-gray-700">{app ? `v${app.version}` : '—'}</span>
                <span><Badge config={STATUS_CONFIG} value={app?.status} /></span>
                <span><Badge config={DECISION_CONFIG} value={rev?.decision} /></span>
                <ScoreBar score={rev?.risk_score} />
              </button>

              {/* Expanded detail panel */}
              {isOpen && (
                <div className="px-6 pb-6 bg-gray-50 border-t border-gray-200">

                  {/* AI Status */}
                  <div className="flex items-center gap-2 pt-4 mb-5">
                    <span className="text-xs text-gray-500">AI Status:</span>
                    <span className={`text-xs font-semibold ${AI_STATUS_CONFIG[rev?.ai_status]?.color || 'text-gray-400'}`}>
                      {AI_STATUS_CONFIG[rev?.ai_status]?.label || '—'}
                    </span>
                    {rev?.email_sent_at && (
                      <span className="text-xs text-gray-400 ml-2">
                        · Email sent {new Date(rev.email_sent_at).toLocaleString()}
                      </span>
                    )}
                  </div>

                  {/* Risk Reasoning */}
                  {rev?.risk_reasoning && (
                    <div className="mb-5">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">AI Risk Reasoning</p>
                      <div className="bg-white border border-indigo-100 rounded-lg px-4 py-3">
                        <p className="text-sm text-gray-800 leading-relaxed">{rev.risk_reasoning}</p>
                      </div>
                    </div>
                  )}

                  {/* User Flags */}
                  {rev?.user_flags?.length > 0 && (
                    <div className="mb-5">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                        Flags Sent to Vendor ({rev.user_flags.length})
                      </p>
                      <div className="space-y-2">
                        {rev.user_flags.map((f, i) => (
                          <div key={i} className="bg-white border border-gray-200 rounded-lg px-4 py-3 flex items-start gap-3">
                            <SeverityTag severity={f.severity} />
                            <div>
                              <p className="text-xs text-gray-400 font-mono mb-0.5">{f.field}</p>
                              <p className="text-sm text-gray-800">{f.message}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Risk Factors */}
                  {rev?.risk_factors?.length > 0 && (
                    <div className="mb-5">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                        Internal Risk Factors ({rev.risk_factors.length})
                      </p>
                      <div className="space-y-2">
                        {rev.risk_factors.map((f, i) => (
                          <div key={i} className="bg-white border border-gray-200 rounded-lg px-4 py-3 flex items-start gap-3">
                            <SeverityTag severity={f.severity} />
                            <div>
                              <p className="text-xs text-gray-400 font-mono mb-0.5">{f.factor}</p>
                              <p className="text-sm text-gray-700">{f.note}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Unreadable Docs */}
                  {rev?.unreadable_docs?.length > 0 && (
                    <div className="mb-5">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                        Unreadable Documents ({rev.unreadable_docs.length})
                      </p>
                      <div className="space-y-2">
                        {rev.unreadable_docs.map((d, i) => (
                          <div key={i} className="bg-white border border-red-100 rounded-lg px-4 py-3">
                            <p className="text-xs text-red-500 font-mono mb-0.5">{d.doc_type}</p>
                            <p className="text-sm text-gray-700">{d.message}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Notified Factors */}
                  {rev?.notified_factors?.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                        Notified Factors (vendor was told)
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {rev.notified_factors.map((f, i) => (
                          <span key={i} className="px-2 py-1 bg-indigo-50 text-indigo-700 rounded text-xs font-mono">{f}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {!rev && (
                    <p className="text-sm text-gray-400 italic py-2">No AI review yet for this application.</p>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Analytics Tab ────────────────────────────────────────────────────────────

function AnalyticsTab() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <p className="text-5xl mb-4">🚧</p>
      <h2 className="text-xl font-semibold text-gray-700">To be continued</h2>
      <p className="text-sm text-gray-400 mt-2 max-w-sm">
        Analytics dashboard — decision distribution, risk factor frequency, submission trends — coming in the next phase.
      </p>
    </div>
  )
}

// ─── Documentation Tab ────────────────────────────────────────────────────────

function FieldCard({ field }) {
  const [open, setOpen] = useState(false)

  const rows = [
    { label: 'Definition',        value: field.definition },
    { label: 'Why Collected',     value: field.whyCollected },
    { label: 'Example',           value: field.example, mono: true },
    { label: 'Documents (OCR)',   value: field.documents.length ? field.documents : null, list: true },
    { label: 'Layer 1 Validation', value: field.layer1 },
    { label: 'Layer 3 — AI Use',  value: field.layer3 },
  ]

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3.5 bg-white hover:bg-gray-50 transition text-left"
      >
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-gray-400 w-40 shrink-0">{field.key}</span>
          <span className="text-sm font-semibold text-gray-800">{field.label}</span>
        </div>
        <span className="text-gray-400 text-sm">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="border-t border-gray-100 divide-y divide-gray-100">
          {rows.map(row => (
            row.value ? (
              <div key={row.label} className="grid grid-cols-[160px_1fr] gap-4 px-4 py-3.5">
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide pt-0.5 shrink-0">
                  {row.label}
                </span>
                {row.list ? (
                  <ul className="space-y-1">
                    {row.value.map((item, i) => (
                      <li key={i} className="text-sm text-gray-700 flex items-start gap-1.5">
                        <span className="text-gray-300 mt-1">•</span> {item}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className={`text-sm leading-relaxed ${
                    row.mono ? 'font-mono text-indigo-700 bg-indigo-50 px-2 py-1 rounded inline-block' :
                    row.highlight ? 'text-amber-800 bg-amber-50 px-3 py-2 rounded-lg border border-amber-100' :
                    'text-gray-700'
                  }`}>
                    {row.value}
                  </p>
                )}
              </div>
            ) : null
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Document Card (for uploaded document types) ──────────────────────────────

function DocCard({ doc }) {
  const [open, setOpen] = useState(false)

  const rows = [
    { label: 'Definition',    value: doc.definition },
    { label: 'Why Collected', value: doc.whyCollected },
    { label: 'When Required', value: doc.whenRequired },
    { label: 'OCR Extracts',  value: doc.ocrExtracts, mono: true },
    { label: 'AI Use',        value: doc.aiUse },
  ]

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3.5 bg-white hover:bg-gray-50 transition text-left"
      >
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-gray-400 w-40 shrink-0">{doc.key}</span>
          <span className="text-sm font-semibold text-gray-800">{doc.label}</span>
        </div>
        <span className="text-gray-400 text-sm">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="border-t border-gray-100 divide-y divide-gray-100">
          {rows.map(row => (
            row.value ? (
              <div key={row.label} className="grid grid-cols-[160px_1fr] gap-4 px-4 py-3.5">
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide pt-0.5 shrink-0">
                  {row.label}
                </span>
                <p className={`text-sm leading-relaxed ${
                  row.mono ? 'font-mono text-indigo-700 bg-indigo-50 px-2 py-1 rounded' :
                  row.highlight ? 'text-amber-800 bg-amber-50 px-3 py-2 rounded-lg border border-amber-100' :
                  'text-gray-700'
                }`}>
                  {row.value}
                </p>
              </div>
            ) : null
          ))}
        </div>
      )}
    </div>
  )
}

function DocumentationTab() {
  const [search, setSearch] = useState('')

  const query = search.toLowerCase()
  const filtered = FIELD_GROUPS.map(g => ({
    ...g,
    fields: g.fields.filter(f =>
      !query ||
      f.key.includes(query) ||
      f.label.toLowerCase().includes(query) ||
      f.definition.toLowerCase().includes(query) ||
      f.layer3.toLowerCase().includes(query)
    ),
  })).filter(g => g.fields.length > 0)

  const filteredDocs = DOCUMENT_DOCS.filter(d =>
    !query ||
    d.key.includes(query) ||
    d.label.toLowerCase().includes(query) ||
    d.definition.toLowerCase().includes(query) ||
    d.ocrExtracts.toLowerCase().includes(query) ||
    d.aiUse.toLowerCase().includes(query)
  )

  const totalFields = FIELD_GROUPS.reduce((s, g) => s + g.fields.length, 0)
  const noResults = filtered.length === 0 && filteredDocs.length === 0

  return (
    <div>
      <div className="mb-6">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder={`Search across all ${totalFields} fields + ${DOCUMENT_DOCS.length} documents...`}
          className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      {noResults && (
        <p className="text-sm text-gray-400 text-center py-12">No results match "{search}"</p>
      )}

      {/* Uploaded Documents section */}
      {filteredDocs.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">📎</span>
            <h3 className="text-base font-bold text-gray-800">Uploaded Documents</h3>
            <span className="text-xs text-gray-400">({filteredDocs.length} document types)</span>
          </div>
          <div className="space-y-1">
            {filteredDocs.map(d => <DocCard key={d.key} doc={d} />)}
          </div>
        </div>
      )}

      {/* Form Fields section */}
      <div className="space-y-8">
        {filtered.map(g => (
          <div key={g.group}>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-lg">{g.icon}</span>
              <h3 className="text-base font-bold text-gray-800">{g.group}</h3>
              <span className="text-xs text-gray-400">({g.fields.length} fields)</span>
            </div>
            <div className="space-y-1">
              {g.fields.map(f => <FieldCard key={f.key} field={f} />)}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Dashboard Shell ──────────────────────────────────────────────────────────

const TABS = ['Vendors', 'Analytics', 'Documentation']

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('Vendors')
  const [vendors, setVendors] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const adminEmail = localStorage.getItem('adminEmail') || 'Admin'

  useEffect(() => {
    adminGetVendors()
      .then(setVendors)
      .catch(err => {
        if (err.message === '401' || err.message === '403') {
          localStorage.removeItem('adminToken')
          navigate('/admin')
        }
        setError(err.message)
      })
      .finally(() => setLoading(false))
  }, [navigate])

  function handleLogout() {
    localStorage.removeItem('adminToken')
    localStorage.removeItem('adminEmail')
    navigate('/admin')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-lg">⚙</span>
            <h1 className="text-lg font-bold text-gray-900">Admin Dashboard</h1>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">{adminEmail}</span>
            <button
              onClick={handleLogout}
              className="text-sm text-gray-400 hover:text-gray-700 transition"
            >
              Logout
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-0">
            {TABS.map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-5 py-3 text-sm font-medium border-b-2 transition ${
                  activeTab === tab
                    ? 'border-indigo-600 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'Vendors' && (
          <VendorsTab vendors={vendors} loading={loading} error={error} />
        )}
        {activeTab === 'Analytics' && <AnalyticsTab />}
        {activeTab === 'Documentation' && <DocumentationTab />}
      </div>
    </div>
  )
}
