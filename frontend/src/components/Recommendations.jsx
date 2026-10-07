import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { card, th, td, mono, num, pct, fixed, PASS_BADGE, FAIL_BADGE, xLabel, yLabel } from './ui'

export default function Recommendations({ data }) {
  const r = data?.analysis?.recommendations
  if (!r) return <div>Loading recommendations…</div>

  if (r.skipped) {
    return (
      <div style={{ ...card, color: '#6b7280' }}>
        The recommender was disabled for this job.
      </div>
    )
  }

  const feasible = r.constraint_satisfiable
  const recs = (feasible ? r.recommendations : r.fallback_recommendations) || []
  const history = (r.history || []).map((h, i) => ({
    trial: h.trial ?? i,
    value: h.value ?? h.throughput ?? null,
  })).filter((h) => h.value != null)

  // Trials whose risk blew past the ceiling carry a six-figure penalty in the
  // objective. Left on the axis they flatten every useful value into one line,
  // so the chart is scaled to the real objective and those trials fall off the
  // bottom, which is how a rejected trial should read.
  const penalised = history.filter((h) => h.value < 0).length
  const topValue = Math.max(0, ...history.map((h) => h.value))

  // Union of keys across recommended configs, so the table adapts to whatever
  // knobs the search space actually contained.
  const configKeys = [...new Set(recs.flatMap((x) => Object.keys(x.config || {})))]

  return (
    <div>
      <div style={{
        background: feasible ? '#f0fdf4' : '#fffbeb',
        borderLeft: `4px solid ${feasible ? '#16a34a' : '#d97706'}`,
        padding: '12px 16px', borderRadius: 4, marginBottom: 20,
        fontSize: 13, color: feasible ? '#14532d' : '#78350f',
      }}>
        {feasible
          ? <>Found {num(r.n_feasible)} configuration(s) under the {pct(r.max_risk)} risk
             ceiling across {num(r.n_trials)} trials.</>
          : <>No configuration reached the {pct(r.max_risk)} risk ceiling. Lowest achievable
             risk was {pct(r.min_achievable_risk, 2)} — showing the lowest-risk configs found.</>}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 16, marginBottom: 24 }}>
        <Stat label="Trials" value={num(r.n_trials)} />
        <Stat label="Feasible" value={num(r.n_feasible)} />
        <Stat label="Feasible Rate" value={pct(r.feasible_rate)} />
        <Stat label="Min Achievable Risk" value={pct(r.min_achievable_risk, 2)} />
        <Stat label="Throughput Uplift" value={r.throughput_uplift_pct != null ? `${fixed(r.throughput_uplift_pct, 1)}%` : '—'} />
      </div>

      {history.length > 0 && (
        <div style={{ ...card, marginBottom: 20 }}>
          <h3 style={{ marginTop: 0 }}>Optimisation History</h3>
          <p style={{ margin: '0 0 10px', fontSize: 13, color: '#6b7280' }}>
            Objective per trial: predicted throughput, minus a heavy penalty when the
            trial&apos;s risk exceeds the ceiling.
            {penalised > 0 && ` ${penalised} of ${history.length} trials were penalised and
             fall below the axis, so the feasible trials stay readable.`}
          </p>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={history} margin={{ left: 20, right: 20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="trial" label={xLabel('Optimiser trial number')} />
              <YAxis domain={[0, topValue > 0 ? Math.ceil(topValue * 1.05) : 'auto']}
                     allowDataOverflow
                     label={yLabel('Objective (predicted Mbps)')} />
              <Tooltip formatter={(v) => fixed(v)} />
              <Line dataKey="value" stroke="#8b5cf6" dot={false} strokeWidth={2} name="Objective" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div style={{ ...card, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>
          {feasible ? 'Recommended Configurations' : 'Lowest-Risk Configurations Found'}
        </h3>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f3f4f6' }}>
                <th style={th}>#</th>
                <th style={{ ...th, textAlign: 'right' }}>Throughput</th>
                <th style={{ ...th, textAlign: 'right' }}>Predicted Risk</th>
                <th style={th}>Status</th>
                {configKeys.map((k) => <th key={k} style={th}>{k}</th>)}
              </tr>
            </thead>
            <tbody>
              {recs.map((rec, i) => (
                <tr key={i}>
                  <td style={{ ...td, fontWeight: 600 }}>{i + 1}</td>
                  <td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>
                    {fixed(rec.predicted_throughput_mbps)} Mbps
                  </td>
                  <td style={{ ...td, textAlign: 'right' }}>{pct(rec.predicted_risk, 2)}</td>
                  <td style={td}>
                    <span style={rec.feasible ? PASS_BADGE : FAIL_BADGE}>
                      {rec.feasible ? 'within ceiling' : 'over ceiling'}
                    </span>
                  </td>
                  {configKeys.map((k) => (
                    <td key={k} style={{ ...td, ...mono }}>{String(rec.config?.[k] ?? '—')}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div style={card}>
        <h3 style={{ marginTop: 0 }}>Derived Search Space</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
          {Object.entries(r.search_space || {}).map(([k, v]) => {
            const isCat = v?.kind === 'categorical' || Array.isArray(v?.choices)
            const isRange = v?.low != null && v?.high != null
            return (
              <div
                key={k}
                style={{
                  padding: '12px 14px',
                  background: '#f9fafb',
                  borderRadius: 6,
                  border: '1px solid #e5e7eb',
                  borderLeft: '4px solid #3b82f6',
                  overflow: 'hidden',
                  wordBreak: 'break-word',
                  overflowWrap: 'anywhere',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, fontSize: 13, color: '#111827' }}>{k}</span>
                  {v?.kind && (
                    <span style={{ fontSize: 11, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      {v.kind}
                    </span>
                  )}
                </div>
                <div
                  style={{
                    ...mono,
                    color: '#4b5563',
                    lineHeight: 1.5,
                    whiteSpace: 'normal',
                    wordBreak: 'break-word',
                    overflowWrap: 'anywhere',
                  }}
                >
                  {isCat ? (
                    (v.choices || []).join(', ')
                  ) : isRange ? (
                    `${v.low} … ${v.high}`
                  ) : Array.isArray(v) ? (
                    v.join(', ')
                  ) : typeof v === 'object' && v !== null ? (
                    JSON.stringify(v, null, 1)
                  ) : (
                    String(v)
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div style={{ ...card, padding: 18 }}>
      <div style={{ fontSize: 24, fontWeight: 700, color: '#111827' }}>{value}</div>
      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>{label}</div>
    </div>
  )
}
