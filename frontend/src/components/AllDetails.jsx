import { card, th, td, mono, num, pct, fixed, PASS_BADGE, FAIL_BADGE, WARN_BADGE, INFO_BADGE } from './ui'

export default function AllDetails({ data }) {
  const a = data?.analysis
  if (!a) return <div>Loading details…</div>

  const meta = data.meta || {}
  const s = a.summary || {}
  const parse = s.parse_stats || {}
  const stages = a.stage_log || []
  const byField = a.failure_by_field || []
  const meter = a.risk_meter || {}
  const highest = meter.highest_risk_runs || []

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 20, marginBottom: 20 }}>
        <div style={card}>
          <h3 style={{ marginTop: 0 }}>Parse Statistics</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              <KV k="Files" v={num(parse.files)} />
              <KV k="Lines read" v={num(parse.lines)} />
              <KV k="Runs extracted" v={num(parse.runs)} />
              <KV k="Error lines" v={num(parse.error_lines)} />
              <KV k="Malformed blocks" v={num(parse.malformed_blocks)}
                  warn={parse.malformed_blocks > 0} />
              <KV k="Unparsed lines" v={num(parse.unparsed_lines)}
                  warn={parse.unparsed_lines > 0} />
            </tbody>
          </table>
        </div>

        <div style={card}>
          <h3 style={{ marginTop: 0 }}>Job Metadata</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              <KV k="Job ID" v={<span style={mono}>{meta.job_id}</span>} />
              <KV k="Runs" v={num(meta.n_runs)} />
              <KV k="Elapsed" v={`${fixed(meta.elapsed)} s`} />
              <KV k="Files" v={(meta.files || []).length} />
              {Object.entries(meta.params || {}).map(([k, v]) => (
                <KV key={k} k={k} v={String(v)} />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div style={{ ...card, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>Stage Timing</h3>
        <p style={{ margin: '0 0 14px', fontSize: 13, color: '#6b7280' }}>
          Total {fixed(a.total_seconds)} s across {stages.length} stages. A failed stage
          is reported here rather than killing the job.
        </p>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f3f4f6' }}>
              <th style={th}>Stage</th>
              <th style={th}>Status</th>
              <th style={{ ...th, textAlign: 'right' }}>Seconds</th>
              <th style={th}>Error</th>
            </tr>
          </thead>
          <tbody>
            {stages.map((st) => (
              <tr key={st.stage}>
                <td style={{ ...td, fontWeight: 600 }}>{st.stage}</td>
                <td style={td}>
                  <span style={st.status === 'ok' ? PASS_BADGE : FAIL_BADGE}>{st.status}</span>
                </td>
                <td style={{ ...td, textAlign: 'right' }}>{fixed(st.seconds)}</td>
                <td style={{ ...td, ...mono, color: '#b91c1c' }}>{st.error || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ ...card, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>Metric Distributions</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f3f4f6' }}>
              <th style={th}>Metric</th>
              <th style={{ ...th, textAlign: 'right' }}>Mean</th>
              <th style={{ ...th, textAlign: 'right' }}>Median</th>
              <th style={{ ...th, textAlign: 'right' }}>P95</th>
              <th style={{ ...th, textAlign: 'right' }}>Min</th>
              <th style={{ ...th, textAlign: 'right' }}>Max</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(s.metric_stats || {}).map(([metric, v]) => (
              <tr key={metric}>
                <td style={{ ...td, fontWeight: 600 }}>{metric}</td>
                <td style={{ ...td, textAlign: 'right' }}>{num(Math.round(v.mean))}</td>
                <td style={{ ...td, textAlign: 'right' }}>{num(Math.round(v.median))}</td>
                <td style={{ ...td, textAlign: 'right' }}>{num(Math.round(v.p95))}</td>
                <td style={{ ...td, textAlign: 'right' }}>{num(Math.round(v.min))}</td>
                <td style={{ ...td, textAlign: 'right' }}>{num(Math.round(v.max))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ ...card, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>Failure Rate by Field</h3>
        <p style={{ margin: '0 0 14px', fontSize: 13, color: '#6b7280' }}>
          Lift above 1.0 means that value fails more often than the corpus average.
        </p>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f3f4f6' }}>
                <th style={th}>Field</th>
                <th style={th}>Value</th>
                <th style={{ ...th, textAlign: 'right' }}>Runs</th>
                <th style={{ ...th, textAlign: 'right' }}>Fail Rate</th>
                <th style={{ ...th, textAlign: 'right' }}>Lift</th>
              </tr>
            </thead>
            <tbody>
              {byField.flatMap((f) =>
                (f.levels || []).map((lv, i) => (
                  <tr key={`${f.field}::${lv.level}`}>
                    <td style={{ ...td, fontWeight: i === 0 ? 600 : 400, color: i === 0 ? '#111827' : '#d1d5db' }}>
                      {i === 0 ? f.field : '↳'}
                    </td>
                    <td style={{ ...td, ...mono }}>{String(lv.level)}</td>
                    <td style={{ ...td, textAlign: 'right' }}>{num(lv.n)}</td>
                    <td style={{ ...td, textAlign: 'right' }}>{pct(lv.fail_rate, 2)}</td>
                    <td style={{ ...td, textAlign: 'right' }}>
                      <span style={lv.lift >= 1.5 ? WARN_BADGE : INFO_BADGE}>
                        {fixed(lv.lift, 3)}×
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {highest.length > 0 && (
        <div style={{ ...card, marginBottom: 20 }}>
          <h3 style={{ marginTop: 0 }}>Highest-Risk Runs</h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f3f4f6' }}>
                  <th style={th}>Run</th>
                  <th style={th}>Actual</th>
                  <th style={{ ...th, textAlign: 'right' }}>Predicted Risk</th>
                  <th style={th}>Config</th>
                </tr>
              </thead>
              <tbody>
                {highest.map((r) => (
                  <tr key={r.run_id}>
                    <td style={{ ...td, ...mono }}>{r.run_id}</td>
                    <td style={td}>
                      <span style={r.pass_fail === 'fail' ? FAIL_BADGE : PASS_BADGE}>
                        {r.pass_fail}
                      </span>
                    </td>
                    <td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>
                      {pct(r.predicted_risk, 1)}
                    </td>
                    <td style={{ ...td, ...mono, color: '#6b7280' }}>
                      {Object.entries(r.config || {}).slice(0, 4)
                        .map(([k, v]) => `${k}=${v}`).join('  ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div style={card}>
        <h3 style={{ marginTop: 0 }}>Column Inventory</h3>
        <div style={{ ...mono, color: '#4b5563', lineHeight: 1.9 }}>
          {(s.columns || []).map((c) => (
            <span key={c} style={{
              display: 'inline-block', padding: '2px 8px', margin: '0 6px 6px 0',
              background: '#f3f4f6', borderRadius: 4,
            }}>{c}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

function KV({ k, v, warn }) {
  return (
    <tr>
      <td style={td}>{k}</td>
      <td style={{ ...td, textAlign: 'right', fontWeight: 600, color: warn ? '#b91c1c' : '#111827' }}>
        {v}
      </td>
    </tr>
  )
}
