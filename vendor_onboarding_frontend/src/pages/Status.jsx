import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getStatus } from '../api'

const STATUS_CONFIG = {
  submitted: { color: 'bg-blue-100 text-blue-700', label: 'Submitted', icon: '📋' },
  draft:     { color: 'bg-yellow-100 text-yellow-700', label: 'Draft', icon: '✏️' },
  approved:  { color: 'bg-green-100 text-green-700', label: 'Approved', icon: '✅' },
  rejected:  { color: 'bg-red-100 text-red-700', label: 'Rejected', icon: '❌' },
  pending:   { color: 'bg-orange-100 text-orange-700', label: 'Pending Review', icon: '⏳' },
}

export default function Status() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    getStatus()
      .then(setData)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  function handleLogout() {
    localStorage.clear()
    navigate('/')
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-sm text-gray-500">Loading...</p>
      </div>
    )
  }

  const statusKey = data?.status || 'draft'
  const config = STATUS_CONFIG[statusKey] || STATUS_CONFIG.draft

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-md mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-xl font-bold text-gray-900">Application Status</h1>
          <button onClick={handleLogout} className="text-sm text-gray-400 hover:text-gray-600">Logout</button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 mb-4">
            {error}
          </div>
        )}

        {data?.application === null || !data?.application_id ? (
          <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center">
            <p className="text-4xl mb-3">📝</p>
            <p className="font-semibold text-gray-800">No application yet</p>
            <p className="text-sm text-gray-500 mt-1">Fill and submit the form to get started.</p>
            <button
              onClick={() => navigate('/form')}
              className="mt-5 bg-indigo-600 text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-indigo-700 transition"
            >
              Start Application
            </button>
          </div>
        ) : (
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
            <div className="p-6 text-center border-b border-gray-100">
              <p className="text-4xl mb-3">{config.icon}</p>
              <span className={`inline-block px-4 py-1.5 rounded-full text-sm font-semibold ${config.color}`}>
                {config.label}
              </span>
            </div>
            <div className="p-6 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Application ID</span>
                <span className="font-mono text-xs text-gray-700 truncate max-w-[180px]">{data.application_id}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Version</span>
                <span className="font-semibold text-gray-700">v{data.version}</span>
              </div>
              {data.submitted_at && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Submitted</span>
                  <span className="text-gray-700">{new Date(data.submitted_at).toLocaleString()}</span>
                </div>
              )}
            </div>
            <div className="px-6 pb-6">
              <button
                onClick={() => navigate('/form')}
                className="w-full border border-indigo-200 text-indigo-600 rounded-lg py-2.5 text-sm font-medium hover:bg-indigo-50 transition"
              >
                Resubmit / Update
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
