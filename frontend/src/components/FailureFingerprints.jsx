import { useState } from 'react'
import {
  ScatterChart, Scatter, Cell, XAxis, YAxis, ZAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { card, th, td, mono, num, pct, WARN_BADGE, INFO_BADGE } from './ui'

const PALETTE = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
                 '#ec4899', '#14b8a6', '#f97316', '#6366f1']

export default function FailureFingerprints({ data }) {
  const fp = data?.analysis?.fingerprints
  const [selected, setSelected] = useState(null)

  if (!fp) return <div>Loading fingerprint analysis…</div>

  const clusters = fp.clusters || []
  const scatter = fp.scatter || []
  const chosen = clusters.find((c) => c.cluster_id === selected)
  // deterministic_clusters is a list of cluster ids, not a count.
  const detIds = Array.isArray(fp.deterministic_clusters)
    ? fp.deterministic_clusters
    : (fp.deterministic_clusters != null ? [fp.deterministic_clusters] : [])

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 16, marginBottom: 24 }}>
        <Stat label="Failing Runs" value={num(fp.n_failing)} />
        <Stat label="Distinct Templates" value={num(fp.n_templates)} />
        <Stat label="Clusters" value={num(fp.n_clusters)} />
        <Stat label="Deterministic (RTL bugs)" value={num(detIds.length)} />
      </div>

      {scatter.length > 0 && (
        <div style={{ ...card, marginBottom: 20 }}>
          <h3 style={{ marginTop: 0 }}>Cluster Map (SVD projection of error templates)</h3>
          <ResponsiveContainer width="100%" height={340}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="x" type="number" name="SVD-1" tickFormatter={(v) => v.toFixed(2)} />
              <YAxis dataKey="y" type="number" name="SVD-2" tickFormatter={(v) => v.toFixed(2)} />
              <ZAxis dataKey="count" range={[40, 400]} name="runs" />
              <Tooltip
                cursor={{ strokeDasharray: '3 3' }}
                content={({ payload }) => {
                  if (!payload?.length) return null
                  const p = payload[0].payload
                  return (
                    <div style={{ background: '#fff', border: '1px solid #d1d5db', padding: 10, borderRadius: 6, maxWidth: 380 }}>
                      <div style={{ fontWeight: 600 }}>Cluster {p.cluster} · {num(p.count)} runs</div>
                      <div style={{ ...mono, marginTop: 6, color: '#4b5563' }}>{p.template}</div>
                    </div>
                  )
                }}
              />
              <Scatter data={scatter}>
                {scatter.map((p, i) => (
                  <Cell key={i} fill={PALETTE[(p.cluster + 1) % PALETTE.length]} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )}

      <div style={card}>
        <h3 style={{ marginTop: 0 }}>Clusters</h3>
        <p style={{ margin: '0 0 14px', fontSize: 13, color: '#6b7280' }}>
          determinism = 1 − (distinct raw traces ÷ runs in cluster). Near 1.0 means the
          same byte-identical trace across many seeds — a deterministic RTL bug.
          Select a row for its template and an example trace.
        </p>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f3f4f6' }}>
                <th style={th}>Cluster</th>
                <th style={th}>Dominant Tag</th>
                <th style={{ ...th, textAlign: 'right' }}>Runs</th>
                <th style={{ ...th, textAlign: 'right' }}>Share</th>
                <th style={{ ...th, textAlign: 'right' }}>Traces</th>
                <th style={{ ...th, textAlign: 'right' }}>Seeds</th>
                <th style={{ ...th, textAlign: 'right' }}>Determinism</th>
                <th style={th}>Classification</th>
              </tr>
            </thead>
            <tbody>
              {clusters.map((c) => {
                const rtl = detIds.includes(c.cluster_id)
                return (
                  <tr
                    key={c.cluster_id}
                    onClick={() => setSelected(c.cluster_id === selected ? null : c.cluster_id)}
                    style={{
                      cursor: 'pointer',
                      background: c.cluster_id === selected ? '#eff6ff'
                        : rtl ? '#fffbeb' : '#fff',
                    }}
                  >
                    <td style={{ ...td, fontWeight: 600 }}>
                      {c.is_noise_cluster ? 'noise' : `c${c.cluster_id}`}
                    </td>
                    <td style={td}>{c.dominant_tag}</td>
                    <td style={{ ...td, textAlign: 'right' }}>{num(c.size)}</td>
                    <td style={{ ...td, textAlign: 'right' }}>{pct(c.share_of_failures)}</td>
                    <td style={{ ...td, textAlign: 'right' }}>{num(c.distinct_raw_traces)}</td>
                    <td style={{ ...td, textAlign: 'right' }}>{num(c.distinct_seeds)}</td>
                    <td style={{ ...td, textAlign: 'right' }}>
                      <span style={rtl ? WARN_BADGE : INFO_BADGE}>{c.determinism?.toFixed(4)}</span>
                    </td>
                    <td style={{ ...td, fontSize: 12 }}>
                      {rtl ? '🐛 ' : ''}{c.classification}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {chosen && (
        <div style={{ ...card, marginTop: 20 }}>
          <h3 style={{ marginTop: 0 }}>
            Cluster {chosen.cluster_id} · {chosen.dominant_tag}
          </h3>
          <Field label="Masked template">{chosen.representative_template}</Field>
          <Field label="Example raw trace">{chosen.example_trace}</Field>
          <div style={{ fontSize: 13, color: '#6b7280', marginTop: 12 }}>
            {num(chosen.n_templates)} template(s) · {num(chosen.distinct_raw_traces)} distinct
            trace(s) across {num(chosen.distinct_seeds)} seed(s)
          </div>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div style={{ ...card, padding: 18 }}>
      <div style={{ fontSize: 26, fontWeight: 700, color: '#111827' }}>{value}</div>
      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>{label}</div>
    </div>
  )
}

function Field({ label, children }) {
  if (!children) return null
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 4 }}>{label}</div>
      <pre style={{
        ...mono, background: '#f9fafb', border: '1px solid #e5e7eb',
        borderRadius: 6, padding: 12, margin: 0, whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>{children}</pre>
    </div>
  )
}
