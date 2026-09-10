import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { card, th, td, mono, num, pct, fixed } from './ui'

export default function TradeoffMatrix({ data }) {
  const p = data?.analysis?.pareto
  if (!p) return <div>Loading Pareto analysis…</div>

  const points = p.points || []
  const frontier = p.frontier || []

  const operating = [
    ['Best Safe', p.best_safe_config, '#10b981'],
    ['Knee', p.knee_config, '#f59e0b'],
    ['Max Throughput', p.max_throughput_config, '#ef4444'],
    ['Lowest Risk', p.lowest_risk_config, '#3b82f6'],
  ]

  return (
    <div>
      <div style={{
        background: '#f0f9ff', borderLeft: '4px solid #0284c7', padding: '12px 16px',
        borderRadius: 4, marginBottom: 20, fontSize: 13, color: '#0c4a6e',
      }}>
        {num(p.n_configs)} configurations grouped over{' '}
        <strong>{(p.group_features || []).join(', ')}</strong> (min {p.min_runs_per_config} runs
        each) · {num(p.n_frontier)} on the frontier
      </div>

      <div style={{ ...card, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>Throughput vs Predicted Risk</h3>
        <ResponsiveContainer width="100%" height={380}>
          <ScatterChart margin={{ top: 10, right: 20, bottom: 24, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="throughput_mbps" type="number" name="Throughput"
                   label={{ value: 'Throughput (Mbps)', position: 'bottom', offset: 4 }} />
            <YAxis dataKey="predicted_risk" type="number" name="Predicted risk"
                   tickFormatter={(v) => v.toFixed(2)}
                   label={{ value: 'Predicted risk', angle: -90, position: 'insideLeft' }} />
            <Tooltip
              cursor={{ strokeDasharray: '3 3' }}
              content={({ payload }) => {
                if (!payload?.length) return null
                const d = payload[0].payload
                return (
                  <div style={{ background: '#fff', border: '1px solid #d1d5db', padding: 10, borderRadius: 6 }}>
                    <div style={{ ...mono, fontWeight: 600 }}>{d.signature}</div>
                    <div style={{ fontSize: 12, marginTop: 6, color: '#4b5563' }}>
                      throughput {fixed(d.throughput_mbps)} Mbps<br />
                      predicted risk {pct(d.predicted_risk, 2)}<br />
                      observed {pct(d.observed_fail_rate, 2)} · {num(d.n_runs)} runs
                    </div>
                  </div>
                )
              }}
            />
            <Legend verticalAlign="top" />
            <Scatter name="All configs" data={points} fill="#cbd5e1" />
            <Scatter name="Pareto frontier" data={frontier} fill="#2563eb" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: 16, marginBottom: 20 }}>
        {operating.map(([label, cfg, color]) => (
          <div key={label} style={{ ...card, borderLeft: `4px solid ${color}` }}>
            <h4 style={{ margin: '0 0 10px', fontSize: 15 }}>{label}</h4>
            {cfg ? (
              <>
                <Row k="Throughput" v={`${fixed(cfg.throughput_mbps)} Mbps`} />
                <Row k="Predicted risk" v={pct(cfg.predicted_risk, 2)} />
                <Row k="Observed" v={pct(cfg.observed_fail_rate, 2)} />
                <Row k="Runs" v={num(cfg.n_runs)} />
                <div style={{ ...mono, marginTop: 8, color: '#6b7280' }}>{cfg.signature}</div>
              </>
            ) : (
              <div style={{ fontSize: 13, color: '#9ca3af' }}>
                No configuration met this criterion.
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={card}>
        <h3 style={{ marginTop: 0 }}>Frontier</h3>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f3f4f6' }}>
                <th style={th}>Signature</th>
                <th style={{ ...th, textAlign: 'right' }}>Throughput</th>
                <th style={{ ...th, textAlign: 'right' }}>Predicted Risk</th>
                <th style={{ ...th, textAlign: 'right' }}>Observed</th>
                <th style={{ ...th, textAlign: 'right' }}>Exec Time</th>
                <th style={{ ...th, textAlign: 'right' }}>Runs</th>
              </tr>
            </thead>
            <tbody>
              {frontier.map((f) => (
                <tr key={f.signature}>
                  <td style={{ ...td, ...mono }}>{f.signature}</td>
                  <td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>{fixed(f.throughput_mbps)}</td>
                  <td style={{ ...td, textAlign: 'right' }}>{pct(f.predicted_risk, 2)}</td>
                  <td style={{ ...td, textAlign: 'right' }}>{pct(f.observed_fail_rate, 2)}</td>
                  <td style={{ ...td, textAlign: 'right' }}>{fixed(f.execution_time_ms)} ms</td>
                  <td style={{ ...td, textAlign: 'right' }}>{num(f.n_runs)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function Row({ k, v }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '3px 0' }}>
      <span style={{ color: '#6b7280' }}>{k}</span>
      <span style={{ fontWeight: 600, color: '#111827' }}>{v}</span>
    </div>
  )
}
