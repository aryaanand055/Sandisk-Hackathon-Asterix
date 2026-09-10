import { useState } from 'react'
import axios from 'axios'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { card, th, td, mono, num, pct, fixed, WARN_BADGE, INFO_BADGE } from './ui'

export default function ConfigDiff({ data, jobId }) {
  const cd = data?.analysis?.config_diff
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [diff, setDiff] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  if (!cd) return <div>Loading configuration analysis…</div>

  const twin = cd.nearest_twin || {}
  const ranking = twin.field_ranking || []
  const examples = twin.example_pairs || []
  const aggregate = cd.aggregate || []

  const chart = ranking.slice(0, 12).map((f) => ({
    field: f.field,
    rate: Number((f.diff_rate * 100).toFixed(1)),
  }))

  const loadDiff = async () => {
    if (!a || !b) return
    setBusy(true); setErr(null)
    try {
      const res = await axios.get(`/api/jobs/${jobId}/diff`, { params: { run_a: a, run_b: b } })
      setDiff(res.data)
    } catch (e) {
      setErr(e.response?.data?.detail || e.message)
      setDiff(null)
    } finally {
      setBusy(false)
    }
  }

  const useExample = (p) => {
    setA(p.failing_run)
    setB(p.passing_run)
    setDiff(null)
    setErr(null)
  }

  return (
    <div>
      <div style={{ ...card, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>Nearest-Twin Divergence</h3>
        <p style={{ margin: '0 0 14px', fontSize: 13, color: '#6b7280' }}>
          Each failing run paired with its most similar passing run
          ({num(twin.total_pairs)} pairs). Numeric fields only count as changed when
          they move at least 0.5 SD, so noise like voltage doesn't dominate.
        </p>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chart} layout="vertical" margin={{ left: 50 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" unit="%" />
            <YAxis dataKey="field" type="category" width={160} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => `${v}%`} />
            <Bar dataKey="rate" fill="#8b5cf6" radius={[0, 6, 6, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div style={{ ...card, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>Two-Run Diff</h3>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <input value={a} onChange={(e) => setA(e.target.value)} placeholder="run A (e.g. RUN-000001)"
                 style={inputStyle} />
          <input value={b} onChange={(e) => setB(e.target.value)} placeholder="run B"
                 style={inputStyle} />
          <button onClick={loadDiff} disabled={!a || !b || busy} style={btnStyle}>
            {busy ? 'Diffing…' : 'Compare'}
          </button>
        </div>

        {examples.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>
              Closest fail/pass twins — click to load:
            </div>
            {examples.slice(0, 8).map((p, i) => (
              <button key={i} onClick={() => useExample(p)} style={chipStyle}
                      title={`${p.failing_run} vs ${p.passing_run} · distance ${fixed(p.distance)}`}>
                {p.error_tag} · {p.n_differences} diff{p.n_differences === 1 ? '' : 's'}
              </button>
            ))}
          </div>
        )}

        {err && <div style={{ marginTop: 12, color: '#b91c1c', fontSize: 13 }}>{err}</div>}

        {diff && (
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 10 }}>
              <span style={mono}>{diff.run_a}</span> vs <span style={mono}>{diff.run_b}</span> —{' '}
              <strong>{num(diff.n_config_changed)}</strong> configuration difference(s),{' '}
              <strong>{num(diff.n_outcome_changed)}</strong> outcome difference(s)
            </div>
            {['config', 'outcome'].map((kind) => {
              const rows = diff.fields.filter((f) => f.changed && f.kind === kind)
              if (!rows.length) return null
              return (
                <div key={kind} style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 6 }}>
                    {kind === 'config'
                      ? 'Configuration — these are the inputs that could have caused the divergence'
                      : 'Outcome — consequences, not causes'}
                  </div>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ background: '#f3f4f6' }}>
                          <th style={th}>Field</th>
                          <th style={th}>{diff.run_a}</th>
                          <th style={th}>{diff.run_b}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((f) => (
                          <tr key={f.field} style={{ background: kind === 'config' ? '#fffbeb' : '#f9fafb' }}>
                            <td style={{ ...td, fontWeight: 600 }}>{f.field}</td>
                            <td style={{ ...td, ...mono }}>{String(f.run_a ?? '—')}</td>
                            <td style={{ ...td, ...mono }}>{String(f.run_b ?? '—')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div style={{ ...card, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>Field Divergence Ranking</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f3f4f6' }}>
              <th style={th}>#</th>
              <th style={th}>Field</th>
              <th style={{ ...th, textAlign: 'right' }}>Differing Pairs</th>
              <th style={{ ...th, textAlign: 'right' }}>Rate</th>
            </tr>
          </thead>
          <tbody>
            {ranking.map((f, i) => (
              <tr key={f.field}>
                <td style={{ ...td, fontWeight: 600 }}>{i + 1}</td>
                <td style={td}>{f.field}</td>
                <td style={{ ...td, textAlign: 'right' }}>{num(f.diff_count)}</td>
                <td style={{ ...td, textAlign: 'right' }}>
                  <span style={f.diff_rate >= 0.5 ? WARN_BADGE : INFO_BADGE}>
                    {pct(f.diff_rate)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={card}>
        <h3 style={{ marginTop: 0 }}>Aggregate Delta by Test Sequence</h3>
        <p style={{ margin: '0 0 14px', fontSize: 13, color: '#6b7280' }}>
          How each setting's distribution shifts between passing and failing runs
          of the same sequence.
        </p>
        {aggregate.map((seq) => (
          <div key={seq.sequence} style={{ marginBottom: 18 }}>
            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 6 }}>
              {seq.sequence}
              <span style={{ fontWeight: 400, color: '#6b7280', fontSize: 12, marginLeft: 8 }}>
                {num(seq.n_fail)} fail / {num(seq.n_pass)} pass · {pct(seq.fail_rate)} fail rate
              </span>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f9fafb' }}>
                  <th style={th}>Field</th>
                  <th style={th}>Value</th>
                  <th style={{ ...th, textAlign: 'right' }}>Fail Share</th>
                  <th style={{ ...th, textAlign: 'right' }}>Pass Share</th>
                  <th style={{ ...th, textAlign: 'right' }}>Delta</th>
                </tr>
              </thead>
              <tbody>
                {(seq.fields || []).slice(0, 6).map((f, i) => (
                  <tr key={i}>
                    <td style={td}>{f.field}</td>
                    <td style={{ ...td, ...mono }}>{String(f.value ?? '—')}</td>
                    <td style={{ ...td, textAlign: 'right' }}>{pct(f.fail_share)}</td>
                    <td style={{ ...td, textAlign: 'right' }}>{pct(f.pass_share)}</td>
                    <td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>
                      {f.delta > 0 ? '+' : ''}{fixed(f.delta, 3)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  )
}

const inputStyle = {
  padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 4,
  fontSize: 13, minWidth: 200,
}
const btnStyle = {
  padding: '8px 16px', border: '1px solid #2563eb', background: '#2563eb',
  color: '#fff', borderRadius: 4, fontSize: 13, fontWeight: 600, cursor: 'pointer',
}
const chipStyle = {
  marginRight: 6, padding: '3px 8px', border: '1px solid #d1d5db',
  background: '#fff', borderRadius: 12, fontSize: 11, cursor: 'pointer',
}
