import React from 'react'
import {
  Bar, BarChart, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  CHART_AXIS, CHART_GRID, Card, PALETTE, Stat, Table, TOOLTIP_STYLE,
  int, num, pct,
} from '../ui.jsx'

export default function Summary({ data }) {
  const s = data.summary
  const rm = data.risk_model
  const meter = data.risk_meter
  const m = rm?.metrics || {}
  const cm = rm?.confusion_matrix || {}

  const verdictData = [
    { name: 'Pass', value: s.n_pass, fill: '#2fb768' },
    { name: 'Fail', value: s.n_fail, fill: '#ef5350' },
  ]

  const shap = (rm?.shap_importance || []).slice(0, 12).map(e => ({
    feature: e.feature, importance: e.importance_pct, direction: e.direction,
  }))

  const tags = Object.entries(s.error_tag_distribution || {})
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)

  const bands = Object.entries(meter?.risk_bands || {})
    .map(([name, value]) => ({ name, value }))

  return (
    <div className="stack">
      {/* ── KPI strip ─────────────────────────────────────────────── */}
      <div className="grid g4">
        <Stat label="Total runs" value={int(s.n_runs)} icon="cpu" tone="neutral" />
        <Stat label="Pass / Fail" value={`${int(s.n_pass)} / ${int(s.n_fail)}`}
              icon="scale" tone="danger"
              delta={`${pct(s.fail_rate)} failure rate`} />
        <Stat label="Model ROC-AUC" value={num(m.roc_auc, 3)}
              icon="target" tone="accent" color="var(--accent)"
              delta={`PR-AUC ${num(m.pr_auc, 3)}`} />
        <Stat label="Mean predicted risk" value={pct(meter?.mean_predicted_risk)}
              icon="zap" tone="warning" color="var(--warning)"
              delta={`${int(s.n_error_lines)} UVM error lines`} />
      </div>

      <div className="grid g2">
        {/* ── Pass/Fail donut ─────────────────────────────────────── */}
        <Card title="Pass / fail ratio"
              hint={`${int(s.n_runs)} runs parsed from ${s.parse_stats?.files ?? '?'} file(s)`}>
          <ResponsiveContainer width="100%" height={230}>
            <PieChart>
              <Pie data={verdictData} dataKey="value" nameKey="name"
                   innerRadius={58} outerRadius={92} paddingAngle={2}
                   label={(e) => `${e.name} ${(e.percent * 100).toFixed(1)}%`}>
                {verdictData.map((d, i) => <Cell key={i} fill={d.fill} />)}
              </Pie>
              <Tooltip {...TOOLTIP_STYLE} formatter={(v) => int(v)} />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        {/* ── Risk bands ──────────────────────────────────────────── */}
        <Card title="Predicted risk distribution"
              hint="Every run scored by the trained classifier">
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={bands} layout="vertical"
                      margin={{ left: 40, right: 20, top: 5, bottom: 5 }}>
              <XAxis type="number" {...CHART_AXIS} />
              <YAxis type="category" dataKey="name" width={110} {...CHART_AXIS} />
              <Tooltip {...TOOLTIP_STYLE} formatter={(v) => int(v)} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {bands.map((_, i) => (
                  <Cell key={i} fill={['#2fb768', '#e0a324', '#f0975a', '#ef5350'][i]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* ── SHAP importance ───────────────────────────────────────── */}
      <Card title="Global SHAP feature importance"
            hint="Mean |SHAP| across the sampled runs, normalised to 100%. Only configuration knobs are used as features — outcome columns are excluded to prevent label leakage.">
        <ResponsiveContainer width="100%" height={Math.max(260, shap.length * 26)}>
          <BarChart data={shap} layout="vertical"
                    margin={{ left: 60, right: 30, top: 5, bottom: 5 }}>
            <XAxis type="number" unit="%" {...CHART_AXIS} />
            <YAxis type="category" dataKey="feature" width={140} {...CHART_AXIS} />
            <Tooltip {...TOOLTIP_STYLE}
                     formatter={(v, _n, p) => [
                       `${num(v, 2)}%`,
                       p.payload.direction === null || p.payload.direction === undefined
                         ? 'importance'
                         : `importance (corr with risk ${num(p.payload.direction, 2)})`,
                     ]} />
            <Bar dataKey="importance" fill="#5b7cfa" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid g2">
        {/* ── Error tags ──────────────────────────────────────────── */}
        <Card title="Failure mode distribution"
              hint="Primary UVM error tag per failing run">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={tags} margin={{ left: 0, right: 10, top: 5, bottom: 45 }}>
              <XAxis dataKey="name" angle={-32} textAnchor="end"
                     interval={0} height={70} {...CHART_AXIS} />
              <YAxis {...CHART_AXIS} />
              <Tooltip {...TOOLTIP_STYLE} formatter={(v) => int(v)} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {tags.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* ── ROC curve ───────────────────────────────────────────── */}
        <Card title="ROC curve" hint={`Held-out test set (${int(rm?.n_test)} runs)`}>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={rm?.roc_curve || []}
                       margin={{ left: 0, right: 10, top: 5, bottom: 5 }}>
              <XAxis dataKey="fpr" type="number" domain={[0, 1]}
                     label={{ value: 'False positive rate', position: 'insideBottom',
                              offset: -3, fill: '#6d7380', fontSize: 11 }}
                     {...CHART_AXIS} />
              <YAxis domain={[0, 1]} {...CHART_AXIS} />
              <Tooltip {...TOOLTIP_STYLE} formatter={(v) => num(v, 3)} />
              <Line type="monotone" dataKey="tpr" stroke="#5b7cfa"
                    dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* ── Metrics + confusion matrix ────────────────────────────── */}
      <div className="grid g2">
        <Card title="Classifier metrics"
              hint={`LightGBM · ${int(rm?.n_train)} train / ${int(rm?.n_test)} test`}>
          <Table
            cols={[
              { key: 'k', label: 'Metric' },
              { key: 'v', label: 'Value', align: 'right' },
            ]}
            rows={Object.entries(m).map(([k, v]) => ({ k, v: num(v, 4) }))}
          />
        </Card>
        <Card title="Confusion matrix" hint="Rows = actual, columns = predicted">
          <Table
            cols={[
              { key: 'actual', label: '' },
              { key: 'pass', label: 'Pred. pass', align: 'right' },
              { key: 'fail', label: 'Pred. fail', align: 'right' },
            ]}
            rows={[
              { actual: 'Actual pass', pass: int(cm.true_negative), fail: int(cm.false_positive) },
              { actual: 'Actual fail', pass: int(cm.false_negative), fail: int(cm.true_positive) },
            ]}
          />
        </Card>
      </div>

      {/* ── Timing by failure mode ────────────────────────────────── */}
      <Card title="Execution time by failure mode"
            hint="Each failure mode has its own timing signature — timeouts sit at the watchdog ceiling, early-abort errors finish faster than a clean pass.">
        <Table
          cols={[
            { key: 'tag', label: 'Error tag' },
            { key: 'count', label: 'Runs', align: 'right' },
            { key: 'mean', label: 'Mean exec (ms)', align: 'right' },
          ]}
          rows={Object.entries(s.by_error_tag || {})
            .map(([tag, v]) => ({ tag, count: int(v.count), mean: num(v.mean_execution_time_ms, 1), raw: v.mean_execution_time_ms }))
            .sort((a, b) => b.raw - a.raw)}
        />
      </Card>
    </div>
  )
}
