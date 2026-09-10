import React, { useState } from 'react'
import {
  CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  CHART_AXIS, CHART_GRID, Card, Empty, Stat, Switch, Table, TOOLTIP_STYLE,
  int, num, pct,
} from '../ui.jsx'

function ConfigCard({ title, point, color }) {
  if (!point) {
    return (
      <Card title={title}>
        <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>None found.</div>
      </Card>
    )
  }
  return (
    <Card title={title}>
      <div className="stack" style={{ gap: 6, marginBottom: 12 }}>
        <span className="stat-value" style={{ color, fontSize: 24 }}>
          {num(point.throughput_mbps, 1)} <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-tertiary)' }}>MB/s</span>
        </span>
        <span className="stat-delta">
          predicted risk {pct(point.predicted_risk, 2)} · observed{' '}
          {pct(point.observed_fail_rate, 1)} · {int(point.n_runs)} run(s)
        </span>
      </div>
      <div className="trace" style={{ maxHeight: 150 }}>
        {Object.entries(point.config || {})
          .map(([k, v]) => `${k} = ${v}`).join('\n')}
      </div>
    </Card>
  )
}

export default function Tradeoff({ data }) {
  const p = data.pareto || {}
  const [showCloud, setShowCloud] = useState(true)

  if (!p.frontier?.length) {
    return <Empty icon="scale" title="No frontier available">
      Not enough distinct configurations to build a Pareto frontier.
    </Empty>
  }

  const cloud = (p.points || []).map(d => ({
    risk: d.predicted_risk * 100, tp: d.throughput_mbps, n: d.n_runs,
  }))
  const front = (p.frontier || []).map(d => ({
    risk: d.predicted_risk * 100, tp: d.throughput_mbps, n: d.n_runs,
  }))

  return (
    <div className="stack">
      <div className="grid g4">
        <Stat label="Distinct configs" value={int(p.n_configs)} icon="layers" tone="neutral" />
        <Stat label="On the frontier" value={int(p.n_frontier)} icon="scale" tone="success" color="var(--success)" />
        <Stat label="Peak throughput"
              value={`${num(p.max_throughput_config?.throughput_mbps, 0)} MB/s`}
              icon="arrow-up-right" tone="accent" color="var(--accent)"
              delta={`at ${pct(p.max_throughput_config?.predicted_risk, 1)} risk`} />
        <Stat label="Lowest risk"
              value={pct(p.lowest_risk_config?.predicted_risk, 2)}
              icon="target" tone="success" color="var(--success)"
              delta={`${num(p.lowest_risk_config?.throughput_mbps, 0)} MB/s`} />
      </div>

      <Card title="Throughput vs predicted failure risk"
            hint={`Each point is a configuration defined over ${(p.group_features || []).join(', ')} — the settings SHAP ranked highest, aggregated across at least ${p.min_runs_per_config} runs each. The green frontier is Pareto-optimal: no other config gives both more throughput and less risk.`}
            actions={
              <Switch checked={showCloud} onChange={setShowCloud}
                      label={`Show dominated (${int(cloud.length)})`} />
            }>
        <ResponsiveContainer width="100%" height={380}>
          <ScatterChart margin={{ left: 10, right: 20, top: 10, bottom: 24 }}>
            <CartesianGrid {...CHART_GRID} />
            <XAxis type="number" dataKey="risk" unit="%" name="Predicted risk"
                   label={{ value: 'Predicted failure probability (%)',
                            position: 'insideBottom', offset: -12,
                            fill: '#6d7380', fontSize: 11 }}
                   {...CHART_AXIS} />
            <YAxis type="number" dataKey="tp" name="Throughput"
                   label={{ value: 'Throughput (MB/s)', angle: -90,
                            position: 'insideLeft', fill: '#6d7380', fontSize: 11 }}
                   {...CHART_AXIS} />
            <Tooltip {...TOOLTIP_STYLE} cursor={{ strokeDasharray: '3 3' }}
                     formatter={(v, n) => [
                       n === 'Predicted risk' ? `${num(v, 2)}%` : num(v, 1), n]} />
            <Legend verticalAlign="top" align="right" height={26}
                    wrapperStyle={{ fontSize: 12 }} />
            {showCloud && (
              <Scatter name="Dominated" data={cloud} fill="#b9bec8" fillOpacity={0.65} />
            )}
            <Scatter name="Pareto-optimal" data={front} fill="#2fb768" line
                     shape="circle" />
          </ScatterChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid g3">
        <ConfigCard title="Peak throughput" point={p.max_throughput_config} color="var(--accent)" />
        <ConfigCard title="Knee — best balance" point={p.knee_config} color="var(--warning)" />
        <ConfigCard title="Best within risk budget" point={p.best_safe_config} color="var(--success)" />
      </div>

      <Card title="Pareto frontier configurations"
            hint="Sorted by throughput. These are the only configurations worth choosing between.">
        <Table
          rowKey={(r) => r.signature}
          cols={[
            { key: 'throughput_mbps', label: 'Throughput (MB/s)', align: 'right',
              render: (r) => num(r.throughput_mbps, 1) },
            { key: 'predicted_risk', label: 'Predicted risk', align: 'right',
              render: (r) => pct(r.predicted_risk, 2) },
            { key: 'observed_fail_rate', label: 'Observed fail', align: 'right',
              render: (r) => pct(r.observed_fail_rate, 1) },
            { key: 'execution_time_ms', label: 'Exec (ms)', align: 'right',
              render: (r) => num(r.execution_time_ms, 1) },
            { key: 'n_runs', label: 'Runs', align: 'right',
              render: (r) => int(r.n_runs) },
            { key: 'config', label: 'Configuration', wrap: true,
              render: (r) => (
                <span className="mono" style={{ color: 'var(--text-tertiary)' }}>
                  {Object.entries(r.config).map(([k, v]) => `${k}=${v}`).join('  ')}
                </span>) },
          ]}
          rows={p.frontier}
        />
      </Card>
    </div>
  )
}
