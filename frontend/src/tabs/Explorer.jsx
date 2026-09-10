import React, { useEffect, useState } from 'react'
import { jobRuns } from '../api.js'
import { Icon, Spinner } from '../icons.jsx'
import { Badge, Button, Card, Empty, Table, int } from '../ui.jsx'

const HIDE = new Set(['error_trace', 'trace_fingerprint'])

export default function Explorer({ data, jobId }) {
  const [rows, setRows] = useState([])
  const [cols, setCols] = useState([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [page, setPage] = useState(1)
  const [verdict, setVerdict] = useState('all')
  const [tag, setTag] = useState('all')
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const tags = Object.keys(data.summary?.error_tag_distribution || {})

  useEffect(() => {
    let alive = true
    setBusy(true)
    jobRuns(jobId, {
      page, page_size: 50, verdict, error_tag: tag, search: query,
    })
      .then(d => {
        if (!alive) return
        setRows(d.rows); setTotal(d.total); setPages(d.pages)
        setCols(d.columns.filter(c => !HIDE.has(c)))
        setErr(null)
      })
      .catch(e => alive && setErr(e.message))
      .finally(() => alive && setBusy(false))
    return () => { alive = false }
  }, [jobId, page, verdict, tag, query])

  useEffect(() => { setPage(1) }, [verdict, tag, query])

  return (
    <Card title="Run explorer"
          hint="Every parsed run, filterable and searchable. Search matches any column."
          actions={
            <span className="row" style={{ color: 'var(--text-tertiary)', fontSize: 12, gap: 6 }}>
              {busy ? <Spinner size={12} /> : <Icon name="cpu" size={12} />}
              {busy ? 'Loading…' : `${int(total)} run(s)`}
            </span>
          }>
      <div className="row" style={{ marginBottom: 16, alignItems: 'flex-end' }}>
        <div className="field">
          <label className="field-label">Verdict</label>
          <select value={verdict} onChange={e => setVerdict(e.target.value)}>
            <option value="all">All</option>
            <option value="pass">Pass</option>
            <option value="fail">Fail</option>
          </select>
        </div>
        <div className="field">
          <label className="field-label">Error tag</label>
          <select value={tag} onChange={e => setTag(e.target.value)}>
            <option value="all">All</option>
            {tags.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="field" style={{ flex: 1, minWidth: 220 }}>
          <label className="field-label">Search</label>
          <div style={{ position: 'relative' }}>
            <Icon name="search" size={14}
                  style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-tertiary)' }} />
            <input value={search} onChange={e => setSearch(e.target.value)}
                   onKeyDown={e => e.key === 'Enter' && setQuery(search)}
                   placeholder="run id, value, tag…"
                   style={{ width: '100%', paddingLeft: 30 }} />
          </div>
        </div>
        <Button variant="secondary" onClick={() => setQuery(search)}>Apply</Button>
        {query && <Button variant="ghost" onClick={() => { setSearch(''); setQuery('') }}>Clear</Button>}
      </div>

      {err && <div style={{ marginBottom: 16 }}><Empty icon="alert-triangle" title="Failed to load">{err}</Empty></div>}

      {rows.length === 0 && !busy ? (
        <Empty icon="search" title="No matches">No runs match these filters.</Empty>
      ) : (
        <Table
          rowKey={(r) => r.run_id}
          cols={cols.map(c => ({
            key: c, label: c,
            render: c === 'pass_fail'
              ? (r) => <Badge kind={r.pass_fail === 'fail' ? 'fail' : 'pass'}>{r.pass_fail}</Badge>
              : undefined,
          }))}
          rows={rows}
        />
      )}

      <div className="row" style={{ marginTop: 16, justifyContent: 'center' }}>
        <Button variant="ghost" size="sm" icon="chevrons-left" disabled={page <= 1 || busy} onClick={() => setPage(1)} />
        <Button variant="secondary" size="sm" icon="chevron-left" disabled={page <= 1 || busy} onClick={() => setPage(p => p - 1)}>Prev</Button>
        <span style={{ color: 'var(--text-tertiary)', fontSize: 12, padding: '0 4px' }}>
          Page {page} of {pages}
        </span>
        <Button variant="secondary" size="sm" iconRight="chevron-right" disabled={page >= pages || busy} onClick={() => setPage(p => p + 1)}>Next</Button>
        <Button variant="ghost" size="sm" icon="chevrons-right" disabled={page >= pages || busy} onClick={() => setPage(pages)} />
      </div>
    </Card>
  )
}
