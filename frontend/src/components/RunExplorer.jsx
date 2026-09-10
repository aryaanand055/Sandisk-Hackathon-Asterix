import { useState, useEffect } from 'react'
import axios from 'axios'
import { card, th, td, mono, num, fixed, PASS_BADGE, FAIL_BADGE } from './ui'

const NUMERIC = new Set([
  'execution_time_ms', 'throughput_mbps', 'queue_depth',
  'clock_freq_mhz', 'seed', 'test_mode_enabled',
])

export default function RunExplorer({ jobId }) {
  const [page, setPage] = useState(0)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [sort, setSort] = useState('')
  const [desc, setDesc] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  // Debounce typing so we don't fire a request per keystroke.
  const [debounced, setDebounced] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 250)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => { setPage(0) }, [debounced, status, sort, desc])

  useEffect(() => {
    if (!jobId) return
    let cancelled = false

    axios.get(`/api/jobs/${jobId}/runs`, {
      params: { page, per_page: 50, search: debounced, status, sort, desc },
    })
      .then((res) => { if (!cancelled) { setData(res.data); setError(null) } })
      .catch((err) => {
        if (!cancelled) setError(err.response?.data?.detail || err.message)
      })

    return () => { cancelled = true }
  }, [jobId, page, debounced, status, sort, desc])

  const toggleSort = (col) => {
    if (sort === col) setDesc((d) => !d)
    else { setSort(col); setDesc(true) }
  }

  if (error) return <div style={{ ...card, color: '#b91c1c' }}>Failed to load runs: {error}</div>
  if (!data) return <div>Loading runs…</div>

  const cols = data.columns || []

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Search run ID or test name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1, minWidth: 240, padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 4, fontSize: 14 }}
        />
        <select value={status} onChange={(e) => setStatus(e.target.value)}
                style={{ padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 4, fontSize: 14 }}>
          <option value="all">All</option>
          <option value="pass">Pass only</option>
          <option value="fail">Fail only</option>
        </select>
      </div>

      <div style={card}>
        <div style={{ marginBottom: 10, fontSize: 13, color: '#6b7280' }}>
          {num(data.total)} run{data.total === 1 ? '' : 's'} matched
          {sort && <> · sorted by <strong>{sort}</strong> {desc ? '↓' : '↑'}</>}
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f3f4f6' }}>
                {cols.map((c) => (
                  <th key={c} style={{ ...th, cursor: 'pointer', userSelect: 'none' }}
                      onClick={() => toggleSort(c)}
                      title={`Sort by ${c}`}>
                    {c}{sort === c ? (desc ? ' ↓' : ' ↑') : ''}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.runs.map((r) => (
                <tr key={r.run_id} style={{ background: r.pass_fail === 'fail' ? '#fef2f2' : '#fff' }}>
                  {cols.map((c) => (
                    <td key={c} style={{
                      ...td,
                      ...(c === 'run_id' ? mono : {}),
                      textAlign: NUMERIC.has(c) ? 'right' : 'left',
                    }}>
                      {renderCell(c, r[c])}
                    </td>
                  ))}
                </tr>
              ))}
              {data.runs.length === 0 && (
                <tr>
                  <td style={{ ...td, color: '#9ca3af' }} colSpan={cols.length || 1}>
                    No runs match this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 20, marginTop: 20 }}>
          <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}
                  style={pagerStyle(page === 0)}>
            Previous
          </button>
          <span style={{ fontSize: 14, color: '#6b7280' }}>
            Page {data.page + 1} of {num(data.n_pages)}
          </span>
          <button onClick={() => setPage((p) => p + 1)}
                  disabled={data.page + 1 >= data.n_pages}
                  style={pagerStyle(data.page + 1 >= data.n_pages)}>
            Next
          </button>
        </div>
      </div>
    </div>
  )
}

function renderCell(col, v) {
  if (v == null || v === '') return '—'
  if (col === 'pass_fail') {
    return <span style={v === 'fail' ? FAIL_BADGE : PASS_BADGE}>{String(v).toUpperCase()}</span>
  }
  if (col === 'execution_time_ms') return `${fixed(v)} ms`
  if (col === 'throughput_mbps') return `${fixed(v)} Mbps`
  if (typeof v === 'number' && !Number.isInteger(v)) return fixed(v)
  if (typeof v === 'number') return num(v)
  return String(v)
}

const pagerStyle = (disabled) => ({
  padding: '8px 16px',
  border: '1px solid #d1d5db',
  background: '#fff',
  borderRadius: 4,
  fontSize: 13,
  cursor: disabled ? 'not-allowed' : 'pointer',
  opacity: disabled ? 0.5 : 1,
})
