import {
  PieChart, Pie, Cell, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceDot,
} from 'recharts'
import { card, th, td, pct, num, xLabel, yLabel } from './ui'

export default function ExecutiveSummary({ data }) {
  const a = data?.analysis
  if (!a?.summary) return <div>Loading analysis…</div>

  const s = a.summary
  const risk = a.risk_model || {}
  const metrics = risk.metrics || {}
  const meter = a.risk_meter || {}

  const outcome = [
    { name: 'Pass', value: s.n_pass, fill: '#10b981' },
    { name: 'Fail', value: s.n_fail, fill: '#ef4444' },
  ]

  const errorTags = Object.entries(s.error_tag_distribution || {})
    .map(([name, count]) => ({ name, count }))
    .sort((x, y) => y.count - x.count)

  // direction = correlation between a numeric setting's value and its SHAP
  // value: > 0 means raising the setting raises risk. Categorical settings have
  // no direction; they carry per-option average SHAP pushes instead.
  const shap = (risk.shap_importance || []).slice(0, 10).map((e) => ({
    feature: e.feature,
    importance: e.importance_pct,
    direction: e.direction,
    perValue: e.per_value_shap,
  }))

  const bands = Object.entries(meter.risk_bands || {})
    .map(([name, count]) => ({ name, count }))

  const roc = Array.isArray(risk.roc_curve)
    ? risk.roc_curve
    : (risk.roc_curve?.fpr || []).map((f, i) => ({
        fpr: f, tpr: risk.roc_curve?.tpr?.[i] || 0,
      }))

  const cm = risk.confusion_matrix || {}
  const ops = risk.roc_operating_points || {}

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 16, marginBottom: 24 }}>
        <Kpi label="Runs Analysed" value={num(s.n_runs)} />
        <Kpi label="Failure Rate" value={pct(s.fail_rate)} />
        <Kpi label="Model ROC-AUC" value={metrics.roc_auc != null ? metrics.roc_auc.toFixed(3) : '—'} />
        <Kpi label="Error Lines" value={num(s.n_error_lines)} />
        <Kpi label="Mean Predicted Risk" value={pct(meter.mean_predicted_risk)} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(380px,1fr))', gap: 20 }}>
        <div style={card}>
          <h3 style={{ marginTop: 0 }}>Pass / Fail</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={outcome} dataKey="value" cx="50%" cy="50%" outerRadius={90}
                   label={({ name, value }) => `${name}: ${num(value)}`}>
                {outcome.map((e) => <Cell key={e.name} fill={e.fill} />)}
              </Pie>
              <Tooltip formatter={(v) => num(v)} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div style={card}>
          <h3 style={{ marginTop: 0 }}>Failure Modes</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={errorTags} layout="vertical" margin={{ left: 20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" allowDecimals={false} label={xLabel('Failing runs (count)')} />
              <YAxis dataKey="name" type="category" width={150} tick={{ fontSize: 11 }}
                     label={yLabel('Failure mode (error tag)')} />
              <Tooltip formatter={(v) => num(v)} />
              <Bar dataKey="count" fill="#3b82f6" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div style={card}>
          <h3 style={{ marginTop: 0 }}>Global SHAP Importance</h3>
          <p style={{ margin: '0 0 10px', fontSize: 12, color: '#6b7280' }}>
            Bar length = how much the setting matters. Colour = which way it pushes risk
            as its value rises:{' '}
            <span style={{ color: SHAP_UP, fontWeight: 600 }}>red raises risk</span>,{' '}
            <span style={{ color: SHAP_DOWN, fontWeight: 600 }}>green lowers it</span>,{' '}
            <span style={{ color: SHAP_NONE, fontWeight: 600 }}>grey</span> = text setting
            or no clear direction. Hover a bar for the direction value.
          </p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={shap} layout="vertical" margin={{ left: 20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" unit="%" label={xLabel('Share of model importance (%)')} />
              <YAxis dataKey="feature" type="category" width={150} tick={{ fontSize: 11 }}
                     label={yLabel('Configuration feature')} />
              <Tooltip content={<ShapTooltip />} />
              <Bar dataKey="importance" radius={[0, 6, 6, 0]}>
                {shap.map((e) => <Cell key={e.feature} fill={shapColor(e.direction)} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div style={card}>
          <h3 style={{ marginTop: 0 }}>Predicted Risk Bands</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={bands} margin={{ left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }}
                     label={xLabel('Predicted failure-risk band')} />
              <YAxis allowDecimals={false} label={yLabel('Runs (count)')} />
              <Tooltip formatter={(v) => num(v)} />
              <Bar dataKey="count" fill="#f59e0b" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {roc.length > 0 && (
          <div style={card}>
            <h3 style={{ marginTop: 0 }}>ROC Curve</h3>
            <p style={{ margin: '0 0 10px', fontSize: 12, color: '#6b7280' }}>
              Each point is one risk cut-off: runs scoring above it are flagged as likely
              to fail. Hover the line to see the cut-off behind any point.
            </p>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={roc} margin={{ left: 10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="fpr" type="number" domain={[0, 1]} ticks={UNIT_TICKS}
                       tickFormatter={(v) => v.toFixed(1)}
                       label={xLabel('False positive rate (passing runs flagged, 0–1)')} />
                <YAxis domain={[0, 1]} ticks={UNIT_TICKS} tickFormatter={(v) => v.toFixed(1)}
                       label={yLabel('True positive rate (failures caught, 0–1)')} />
                <Tooltip content={<RocTooltip />} />
                <Legend verticalAlign="top" />
                <Line dataKey="tpr" stroke="#0ea5e9" dot={false} strokeWidth={2}
                      name={`ROC (AUC ${metrics.roc_auc?.toFixed(3) ?? '—'})`} />
                {ops.default && (
                  <ReferenceDot x={ops.default.fpr} y={ops.default.tpr} r={6}
                                fill={ROC_DEFAULT} stroke="#fff" strokeWidth={2} />
                )}
                {ops.best_balance && (
                  <ReferenceDot x={ops.best_balance.fpr} y={ops.best_balance.tpr} r={6}
                                fill={ROC_BEST} stroke="#fff" strokeWidth={2} />
                )}
              </LineChart>
            </ResponsiveContainer>
            {(ops.best_balance || ops.default) && (
              <div style={{ display: 'grid', gap: 6, marginTop: 10, fontSize: 12 }}>
                {[['best_balance', 'Best balance', ROC_BEST], ['default', 'Current cut-off', ROC_DEFAULT]]
                  .filter(([k]) => ops[k])
                  .map(([k, label, color]) => (
                    <div key={k} style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                      <span style={{ width: 10, height: 10, borderRadius: 5, background: color,
                                     flex: '0 0 auto', transform: 'translateY(1px)' }} />
                      <span>
                        <strong>{label}: cut-off {pct(ops[k].threshold, 0)}</strong>
                        {' '}catches {pct(ops[k].tpr, 0)} of failures
                        ({num(ops[k].true_positive)}), flags {pct(ops[k].fpr, 0)} of
                        passing runs ({num(ops[k].false_positive)} false alarms)
                      </span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}

        <div style={card}>
          <h3 style={{ marginTop: 0 }}>Model Metrics</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {['accuracy', 'precision', 'recall', 'f1', 'roc_auc', 'pr_auc'].map((k) => (
                <tr key={k}>
                  <td style={td}>{k}</td>
                  <td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>
                    {metrics[k] != null ? metrics[k].toFixed(3) : '—'}
                  </td>
                </tr>
              ))}
              <tr>
                <td style={td}>train / test</td>
                <td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>
                  {num(risk.n_train)} / {num(risk.n_test)}
                </td>
              </tr>
              {cm.tp != null && (
                <tr>
                  <td style={td}>TP / FP / TN / FN</td>
                  <td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>
                    {cm.tp} / {cm.fp} / {cm.tn} / {cm.fn}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

const UNIT_TICKS = [0, 0.2, 0.4, 0.6, 0.8, 1]
const ROC_BEST = '#16a34a'
const ROC_DEFAULT = '#f59e0b'

function RocTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div style={{ background: '#fff', border: '1px solid #d1d5db', padding: 10, borderRadius: 6, fontSize: 12 }}>
      {p.threshold != null && (
        <div style={{ fontWeight: 600, marginBottom: 4 }}>Cut-off {pct(p.threshold, 0)}</div>
      )}
      <div>Failures caught: {pct(p.tpr, 0)}</div>
      <div>Passing runs flagged: {pct(p.fpr, 0)}</div>
    </div>
  )
}

const SHAP_UP = '#dc2626'
const SHAP_DOWN = '#16a34a'
const SHAP_NONE = '#9ca3af'

// |direction| below 0.2 is too weak a correlation to call a direction.
function shapColor(direction) {
  if (direction == null || Math.abs(direction) < 0.2) return SHAP_NONE
  return direction > 0 ? SHAP_UP : SHAP_DOWN
}

function ShapTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const e = payload[0].payload
  const options = Object.entries(e.perValue || {}).sort((x, y) => y[1] - x[1])
  return (
    <div style={{ background: '#fff', border: '1px solid #d1d5db', padding: 10, borderRadius: 6, fontSize: 12, maxWidth: 300 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{e.feature}</div>
      <div>Importance: {e.importance}%</div>
      {e.direction != null ? (
        <div style={{ color: shapColor(e.direction) }}>
          Direction: {e.direction > 0 ? '+' : ''}{e.direction.toFixed(2)}{' '}
          ({Math.abs(e.direction) < 0.2 ? 'no clear direction'
            : e.direction > 0 ? 'higher value → higher risk' : 'higher value → lower risk'})
        </div>
      ) : options.length > 0 && (
        <div style={{ marginTop: 4 }}>
          <div style={{ color: '#6b7280' }}>Avg push on risk by option:</div>
          {options.map(([k, v]) => (
            <div key={k} style={{ color: v > 0 ? SHAP_UP : SHAP_DOWN }}>
              {k}: {v > 0 ? '+' : ''}{v.toFixed(3)}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Kpi({ label, value }) {
  return (
    <div style={{ ...card, padding: 18 }}>
      <div style={{ fontSize: 26, fontWeight: 700, color: '#111827' }}>{value}</div>
      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>{label}</div>
    </div>
  )
}
