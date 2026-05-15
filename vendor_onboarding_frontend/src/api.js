const BASE = '/api'

function headers() {
  const token = localStorage.getItem('token')
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  }
}

export async function login(email) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  })
  if (!res.ok) throw new Error('Login failed')
  return res.json()
}

export async function submitApplication(data) {
  const res = await fetch(`${BASE}/application/submit`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data)
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Submit failed')
  }
  return res.json()
}

export async function getStatus() {
  const res = await fetch(`${BASE}/application/status`, { headers: headers() })
  if (!res.ok) throw new Error('Failed to fetch status')
  return res.json()
}

export async function saveDraft(data) {
  const res = await fetch(`/api/application/draft`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data)
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Draft save failed')
  }
  return res.json()
}

export async function getApplication(id) {
  const res = await fetch(`${BASE}/application/${id}`, { headers: headers() })
  if (!res.ok) throw new Error('Failed to fetch application')
  return res.json()
}

export async function getDocuments() {
  const res = await fetch(`${BASE}/documents/`, { headers: headers() })
  if (!res.ok) throw new Error('Failed to fetch documents')
  return res.json()
}

export async function uploadDocument(file, docType, applicationId = null) {
  const token = localStorage.getItem('token')
  const formData = new FormData()
  formData.append('file', file)
  formData.append('doc_type', docType)
  if (applicationId) formData.append('application_id', applicationId)

  const res = await fetch(`${BASE}/documents/upload`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Upload failed')
  }
  return res.json()
}
