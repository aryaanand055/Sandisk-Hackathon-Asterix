import React from 'react'
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  CHART_AXIS, CHART_GRID, Alert, Card, Empty, Stat, Table, TOOLTIP_STYLE,
  int, num, pct,
} from '../ui.jsx'

export default function Recommend({ data }) {
  const r = data.recommendations || {}

  if (r.skipped) {
    return <Empty icon="target" title="Recommender disabled">
      The Optuna recommender was disabled for this run.
    </Empty>
  }
  if (r.error) return <Alert tone="danger" title="Recommender failed">{r.error}</Alert>

  const feasible = r.constraint_satisfiable
  const list = feasible ? r.recommendations : r.fallback_recommendations
  const keys = list?.length ? Object.keys(list[0].config) : []

  return (
    <div className="stack">
      <div className="grid g4">
        <Stat label="Risk ceiling" value={pct(r.max_risk, 1)} icon="target" tone="neutral" />
        <Stat label="Trials evaluated" value={int(r.n_trials)} icon="zap" tone="neutral"
              delta="Optuna TPE sampler" />
        <Stat label="Feasible configs" value={int(r.n_feasible)} icon="check-circle"
              tone={feasible ? 'success' : 'danger'}
              color={feasible ? 'var(--success)' : 'var(--danger)'}
              delta={pct(r.feasible_rate, 1) + ' of trials'} />
        <Stat label="Throughput uplift"
              value={r.throughput_uplift_pct === null || r.throughput_uplift_pct === undefined
                ? '–' : `${num(r.throughput_uplift_pct, 1)}%`}
              icon="arrow-up-right" tone="accent" color="var(--accent)"
              delta={`vs ${num(r.baseline_mean_throughput_mbps, 1)} MB/s observed mean`} />
      </div>

      {!feasible && (
        <Alert tone="warning" title={`No configuration met the ${pct(r.max_risk, 1)} risk ceiling`}>
          The lowest risk reachable anywhere in the search space was{' '}
          {pct(r.min_achievable_risk, 2)}. The table below falls back to the
          lowest-risk configurations found, ranked by risk then throughput —
          raise the ceiling to get true optimisation instead.
        </Alert>
      )}

      <Card title={feasible ? 'Recommended configurations' : 'Lowest-risk configurations found'}
            hint={feasible
              ? `Maximising predicted throughput subject to predicted failure probability ≤ ${pct(r.max_risk, 1)}. Throughput is modelled on passing runs only, so it reflects the speed you get when the run actually works.`
              : 'Constraint could not be satisfied — showing best effort.'}>
        {!list?.length ? (
          <Empty icon="target" title="No configurations returned" />
        ) : (
          <Table
            cols={[
              { key: 'rank', label: '#', render: (_, i) => i + 1 },
              { key: 'predicted_throughput_mbps', label: 'Throughput (MB/s)', align: 'right',
                render: (x) => num(x.predicted_throughput_mbps, 1) },
              { key: 'predicted_risk', label: 'Predicted risk', align: 'right',
                render: (x) => (
                  <span style={{ color: x.predicted_risk <= r.max_risk ? 'var(--success)' : 'var(--warning)' }}>
                    {pct(x.predicted_risk, 2)}
                  </span>) },
              ...keys.map(k => ({
                key: k, label: k,
                render: (x) => String(x.config[k]),
              })),
            ]}
            rows={list.map((x, i) => ({ ...x, rank: i + 1 }))}
            rowKey={(_, i) => i}
          />
        )}
      </Card>

      {r.history?.length > 1 && (
        <Card title="Optimisation history"
              hint="Objective value per trial. TPE concentrates sampling on promising regions as the study progresses.">
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={r.history} margin={{ left: 10, right: 20, top: 5, bottom: 18 }}>
              <CartesianGrid {...CHART_GRID} />
              <XAxis dataKey="trial" {...CHART_AXIS}
                     label={{ value: 'Trial', position: 'insideBottom', offset: -8,
                              fill: '#6d7380', fontSize: 11 }} />
              <YAxis {...CHART_AXIS} />
              <Tooltip {...TOOLTIP_STYLE} formatter={(v) => num(v, 1)} />
              <Line type="monotone" dataKey="value" stroke="#9d7bf0"
                    dot={false} strokeWidth={1.6} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      <Card title="Search space"
            hint="Derived from the observed corpus — the optimiser never proposes a value the hardware was not exercised at.">
        <Table
          cols={[
            { key: 'field', label: 'Parameter' },
            { key: 'kind', label: 'Type' },
            { key: 'domain', label: 'Domain', wrap: true },
          ]}
          rows={Object.entries(r.search_space || {}).map(([field, spec]) => ({
            field, kind: spec.kind,
            domain: spec.kind === 'categorical'
              ? (spec.choices || []).join(', ')
              : `${spec.low} … ${spec.high}`,
          }))}
        />
      </Card>
    </div>
  )
}
