import { useState, useEffect } from 'react'
import axios from 'axios'

const card = {
  background: '#fff',
  padding: '20px',
  borderRadius: '8px',
  boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
}
const th = {
  padding: '12px',
  textAlign: 'left',
  fontWeight: 600,
  fontSize: '13px',
  color: '#374151',
  borderBottom: '2px solid #e5e7eb',
}
const td = { padding: '12px', fontSize: '13px', borderBottom: '1px solid #e5e7eb' }

export default function RunExplorer({ jobId }) {
  const [page, setPage] = useState(0)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  // Debounce the search box so typing doesn't fire a request per keystroke.
  const [debounced, setDebounced] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 250)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    setPage(0)
  }, [debounced, status])

  useEffect(() => {
    if (!jobId) return
    let cancelled = false

    axios
      .get(`/api/jobs/${jobId}/runs`, {
        params: { page, per_page: 50, search: debounced, status },
      })
      .then((res) => {
        if (!cancelled) {
          setData(res.data)
          setError(null)
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })

    return () => {
      cancelled = true
    }
  }, [jobId, page, debounced, status])

  if (error) return <div>Failed to load runs: {error}</div>
  if (!data) return <div>Loading runs...</div>

  return (
    <div>
      <h2>Run Explorer</h2>

      <div style={{ display: 'flex', gap: '10px', margin: '15px 0' }}>
        <input
          type="text"
          placeholder="Search run ID or test name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            flex: 1,
            padding: '8px 12px',
            border: '1px solid #d1d5db',
            borderRadius: '4px',
            fontSize: '14px',
          }}
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          style={{
            padding: '8px 12px',
            border: '1px solid #d1d5db',
            borderRadius: '4px',
            fontSize: '14px',
          }}
        >
          <option value="all">All</option>
          <option value="pass">Pass</option>
          <option value="fail">Fail</option>
        </select>
      </div>

      <div style={card}>
        <div style={{ marginBottom: '10px', fontSize: '13px', color: '#6b7280' }}>
          {data.total.toLocaleString()} run{data.total === 1 ? '' : 's'} matched
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f3f4f6' }}>
              <th style={th}>Run ID</th>
              <th style={th}>Test Name</th>
              <th style={th}>Status</th>
              <th style={th}>Error Tag</th>
              <th style={th}>Exec Time</th>
              <th style={th}>Throughput</th>
            </tr>
          </thead>
          <tbody>
            {data.runs.map((r) => (
              <tr key={r.run_id} style={{ background: r.status === 'fail' ? '#fef2f2' : '#fff' }}>
                <td style={{ ...td, fontFamily: 'monospace' }}>{r.run_id}</td>
                <td style={td}>{r.test_name}</td>
                <td style={td}>
                  <span
                    style={{
                      padding: '3px 8px',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 600,
                      background: r.status === 'fail' ? '#fee2e2' : '#d1fae5',
                      color: r.status === 'fail' ? '#991b1b' : '#065f46',
                    }}
                  >
                    {r.status.toUpperCase()}
                  </span>
                </td>
                <td style={{ ...td, color: '#6b7280' }}>{r.error_tag || '—'}</td>
                <td style={td}>{r.execution_time_ms.toFixed(1)} ms</td>
                <td style={td}>{r.throughput_mbps.toFixed(1)} Mbps</td>
              </tr>
            ))}
            {data.runs.length === 0 && (
              <tr>
                <td style={{ ...td, color: '#6b7280' }} colSpan={6}>
                  No runs match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>

        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '20px',
            marginTop: '20px',
          }}
        >
          <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>
            Previous
          </button>
          <span style={{ fontSize: '14px', color: '#6b7280' }}>
            Page {data.page + 1} of {data.n_pages}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={data.page + 1 >= data.n_pages}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
