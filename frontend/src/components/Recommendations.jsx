import { useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { card, th, td, mono, num, pct, fixed, PASS_BADGE, FAIL_BADGE, xLabel, yLabel } from './ui'

export default function Recommendations({ data }) {
  const [simulating, setSimulating] = useState(false)
  const [simResult, setSimResult] = useState(null)
  const [simError, setSimError] = useState(null)
  const [topModule, setTopModule] = useState('uvm_test_top')
  const [testName, setTestName] = useState('uvm_config_stress_test')
  const [cycles, setCycles] = useState(50000)
  const [showConfigDetails, setShowConfigDetails] = useState(false)
  const [showEmulationPrompt, setShowEmulationPrompt] = useState(false)
  const [pendingSimulate, setPendingSimulate] = useState(false)

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
  const topConfig = recs[0] // The top optimal configuration chosen by Optuna

  const executeSimulation = async () => {
    if (!topConfig || !topConfig.config) return
    setSimulating(true)
    setSimError(null)
    setSimResult(null)
    setShowEmulationPrompt(false)

    try {
      const resp = await fetch('/api/simulate/xsim', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config: topConfig.config,
          top_module: topModule,
          test_name: testName,
          cycles: Number(cycles) || 50000,
        }),
      })

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Simulation request failed' }))
        throw new Error(err.detail || 'Failed to simulate with xSim')
      }

      const result = await resp.json()
      setSimResult(result)
    } catch (err) {
      setSimError(err.message)
    } finally {
      setSimulating(false)
    }
  }

  const handleSimulateTop = async () => {
    if (!topConfig || !topConfig.config) return
    setSimError(null)

    // Check if Vivado xSim is installed
    try {
      const infoResp = await fetch('/api/simulate/info')
      const info = await infoResp.json()

      if (!info.xsim_available) {
        // Alert user that Vivado is not installed and ask for confirmation to run simulation emulator
        setShowEmulationPrompt(true)
        return
      }
    } catch (e) {
      console.warn('Failed to check xsim info:', e)
    }

    // Vivado xSim is installed: call CLI directly
    await executeSimulation()
  }
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

      {/* Top Optimal Configuration xSim Verification Panel */}
      {topConfig && (
        <div style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderLeft: '4px solid #e10600',
          borderRadius: 8,
          padding: '20px 24px',
          marginBottom: 24,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#e10600', background: '#fff5f5', padding: '2px 8px', borderRadius: 4 }}>
                  Top Optimal Candidate
                </span>
                <span style={{ fontSize: 12, color: '#64748b' }}>Selected by Optuna Bayesian Optimizer</span>
              </div>
              <h3 style={{ margin: '4px 0 8px', fontSize: 18, color: '#0f172a' }}>
                Hardware-in-the-Loop Verification via Vivado xSim
              </h3>
              <p style={{ margin: 0, fontSize: 13, color: '#475569', maxWidth: 650 }}>
                Directly pass the optimal parameter tuple as UVM plusargs into Vivado xSim (top module: <code>{topModule}</code>) to measure physical throughput and verify zero UVM_ERROR occurrences.
              </p>
            </div>

            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <button
                type="button"
                className="btn btn-outline-sandisk"
                onClick={() => setShowConfigDetails(!showConfigDetails)}
                style={{ fontSize: 12, padding: '7px 14px' }}
              >
                {showConfigDetails ? 'Hide Settings' : 'Configure Testbench'}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSimulateTop}
                disabled={simulating}
                style={{ fontSize: 13, padding: '8px 18px', display: 'flex', alignItems: 'center', gap: 8 }}
              >
                {simulating ? 'Simulating in xSim…' : '▶ Simulate Top Config in xSim'}
              </button>
            </div>
          </div>

          {showConfigDetails && (
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px dashed #cbd5e1', display: 'flex', gap: 20, flexWrap: 'wrap' }}>
              <div>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                  Top Testbench Module:
                </label>
                <input
                  type="text"
                  value={topModule}
                  onChange={(e) => setTopModule(e.target.value)}
                  style={{ padding: '6px 10px', fontSize: 12, border: '1px solid #cbd5e1', borderRadius: 4, width: 180 }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                  UVM Test Name (+UVM_TESTNAME):
                </label>
                <input
                  type="text"
                  value={testName}
                  onChange={(e) => setTestName(e.target.value)}
                  style={{ padding: '6px 10px', fontSize: 12, border: '1px solid #cbd5e1', borderRadius: 4, width: 220 }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                  Simulation Cycles:
                </label>
                <input
                  type="number"
                  value={cycles}
                  onChange={(e) => setCycles(e.target.value)}
                  style={{ padding: '6px 10px', fontSize: 12, border: '1px solid #cbd5e1', borderRadius: 4, width: 120 }}
                />
              </div>
            </div>
          )}

          {/* Applied Top Parameters Preview */}
          <div style={{ marginTop: 14, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {Object.entries(topConfig.config || {}).map(([k, v]) => (
              <span key={k} style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                padding: '4px 10px',
                borderRadius: 4,
                fontSize: 12,
                fontFamily: mono.fontFamily,
                color: '#334155'
              }}>
                <strong style={{ color: '#0f172a' }}>{k}</strong>={String(v)}
              </span>
            ))}
          </div>

          {/* Alert: Vivado not installed confirmation prompt */}
          {showEmulationPrompt && (
            <div style={{
              marginTop: 16,
              background: '#fffbeb',
              border: '1px solid #fde68a',
              borderLeft: '4px solid #d97706',
              borderRadius: 6,
              padding: '16px 20px',
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14, color: '#92400e', marginBottom: 4 }}>
                    ⚠️ Xilinx Vivado (xSim) is not detected on this machine
                  </div>
                  <p style={{ margin: 0, fontSize: 13, color: '#78350f', maxWidth: 680, lineHeight: 1.5 }}>
                    The <code>xsim</code> binary was not found in your system <code>PATH</code>. Would you like to run the built-in <strong>UVM Simulation Engine</strong> to simulate transaction cycles, scoreboard checks, and measure throughput for this configuration?
                  </p>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => setShowEmulationPrompt(false)}
                    style={{ fontSize: 12, padding: '6px 12px' }}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={executeSimulation}
                    style={{ fontSize: 12, padding: '6px 14px', background: '#d97706', borderColor: '#d97706' }}
                  >
                    Yes, Simulate Now
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Live Simulation Status & Results */}
          {simError && (
            <div style={{ marginTop: 16, background: '#fef2f2', border: '1px solid #fecaca', padding: '10px 14px', borderRadius: 6, color: '#991b1b', fontSize: 13 }}>
              <strong>xSim Execution Error:</strong> {simError}
            </div>
          )}

          {simResult && (
            <div style={{ marginTop: 18, background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 6, padding: '16px 20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{
                    padding: '4px 12px',
                    borderRadius: 4,
                    fontSize: 12,
                    fontWeight: 700,
                    background: simResult.status === 'PASS' ? '#dcfce7' : '#fee2e2',
                    color: simResult.status === 'PASS' ? '#15803d' : '#b91c1c',
                  }}>
                    xSim Verdict: {simResult.status}
                  </span>
                  <span style={{ fontSize: 13, color: '#334155' }}>
                    Engine: <strong>{simResult.execution_mode === 'xsim_live' ? 'Vivado xSim (Live Binary)' : 'UVM Simulation Simulator'}</strong>
                  </span>
                  <span style={{ fontSize: 12, color: '#64748b' }}>
                    ({simResult.duration_seconds}s)
                  </span>
                </div>
              </div>

              {/* Comparison Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14, marginBottom: 16 }}>
                <div style={{ padding: '10px 14px', background: '#f8fafc', borderRadius: 6, border: '1px solid #f1f5f9' }}>
                  <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase' }}>Optuna Predicted Throughput</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', marginTop: 2 }}>
                    {fixed(topConfig.predicted_throughput_mbps)} Mbps
                  </div>
                </div>
                <div style={{ padding: '10px 14px', background: '#f8fafc', borderRadius: 6, border: '1px solid #f1f5f9' }}>
                  <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase' }}>xSim Simulated Throughput</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: '#16a34a', marginTop: 2 }}>
                    {fixed(simResult.throughput_mbps)} Mbps
                  </div>
                </div>
                <div style={{ padding: '10px 14px', background: '#f8fafc', borderRadius: 6, border: '1px solid #f1f5f9' }}>
                  <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase' }}>UVM Errors / Fatals</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: simResult.uvm_errors > 0 ? '#b91c1c' : '#16a34a', marginTop: 2 }}>
                    {simResult.uvm_errors} / {simResult.uvm_fatals}
                  </div>
                </div>
                <div style={{ padding: '10px 14px', background: '#f8fafc', borderRadius: 6, border: '1px solid #f1f5f9' }}>
                  <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase' }}>Simulated Cycles</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', marginTop: 2 }}>
                    {num(simResult.sim_cycles)}
                  </div>
                </div>
              </div>

              {/* Collapsible Simulation Log */}
              <details style={{ marginTop: 10 }}>
                <summary style={{ cursor: 'pointer', fontSize: 12, fontWeight: 600, color: '#475569', userSelect: 'none' }}>
                  View Full xSim UVM Log Transcript ({simResult.logs?.split('\n').length || 0} lines)
                </summary>
                <pre style={{
                  ...mono,
                  marginTop: 10,
                  padding: 12,
                  background: '#0f172a',
                  color: '#e2e8f0',
                  borderRadius: 6,
                  maxHeight: 260,
                  overflowY: 'auto',
                  fontSize: 11.5,
                  lineHeight: 1.5,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                }}>
                  {simResult.logs}
                </pre>
              </details>
            </div>
          )}
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
                <tr key={i} style={i === 0 ? { background: '#fefefe' } : {}}>
                  <td style={{ ...td, fontWeight: 600 }}>
                    {i === 0 ? <span style={{ color: '#e10600' }}>★ 1 (Top)</span> : i + 1}
                  </td>
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
    <div style={{ padding: '8px 0' }}>
      <div style={{ fontSize: 24, fontWeight: 700, color: '#111827' }}>{value}</div>
      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>{label}</div>
    </div>
  )
}
