import React, { useState } from 'react'
import { Icon } from '../icons.jsx'
import { Badge, Button, Card, Stat, Table, int, num, pct } from '../ui.jsx'

export default function Details({ data, meta }) {
  const s = data.summary || {}
  const ps = s.parse_stats || {}
  const [openField, setOpenField] = useState(null)

  return (
    <div className="stack">
      {/* ── Parse stats ───────────────────────────────────────────── */}
      <div className="grid g4">
        <Stat label="Files parsed" value={int(ps.files)} icon="file-text" tone="neutral" />
        <Stat label="Lines scanned" value={int(ps.lines)} icon="list-detail" tone="neutral" />
        <Stat label="Malformed blocks" value={int(ps.malformed_blocks)} icon="alert-triangle"
              tone={ps.malformed_blocks ? 'danger' : 'success'}
              color={ps.malformed_blocks ? 'var(--danger)' : 'var(--success)'} />
        <Stat label="Unparsed lines" value={int(ps.unparsed_lines)} icon="alert-triangle"
              tone={ps.unparsed_lines ? 'warning' : 'success'}
              color={ps.unparsed_lines ? 'var(--warning)' : 'var(--success)'} />
      </div>

      {/* ── Pipeline stage log ────────────────────────────────────── */}
      <Card title="Pipeline stage log"
            hint={`Total analysis time ${num(data.total_seconds, 2)}s. A failed stage does not abort the report — the rest still renders.`}>
        <Table
          rowKey={(r) => r.stage}
          cols={[
            { key: 'stage', label: 'Stage' },
            { key: 'status', label: 'Status',
              render: (r) => (
                <Badge kind={r.status === 'ok' ? 'pass' : 'fail'}>{r.status}</Badge>) },
            { key: 'seconds', label: 'Seconds', align: 'right',
              render: (r) => num(r.seconds, 2) },
            { key: 'error', label: 'Error', wrap: true,
              render: (r) => r.error || '' },
          ]}
          rows={data.stage_log || []}
        />
      </Card>

      {/* ── Failure rate by field ─────────────────────────────────── */}
      <Card title="Observed failure rate by configuration field"
            hint="Model-free ground truth straight from the data. Spread = highest minus lowest failure rate across that field's levels; a wide spread means the setting matters. Select a field to expand.">
        <Table
          rowKey={(r) => r.field}
          cols={[
            { key: 'field', label: 'Field',
              render: (r) => (
                <Button size="sm" variant={openField === r.field ? 'primary' : 'secondary'}
                        iconRight={openField === r.field ? 'chevron-up' : 'chevron-down'}
                        onClick={() => setOpenField(openField === r.field ? null : r.field)}>
                  {r.field}
                </Button>) },
            { key: 'spread', label: 'Spread', align: 'right',
              render: (r) => (
                <span style={{ color: r.spread > 0.15 ? 'var(--warning)' : 'var(--text-tertiary)' }}>
                  {pct(r.spread)}
                </span>) },
            { key: 'levels', label: 'Levels', align: 'right',
              render: (r) => int(r.levels.length) },
            { key: 'worst', label: 'Worst level',
              render: (r) => r.levels[0]
                ? `${r.levels[0].level} — ${pct(r.levels[0].fail_rate)} (${int(r.levels[0].n)} runs)`
                : '' },
          ]}
          rows={data.failure_by_field || []}
        />

        {openField && (
          <div style={{ marginTop: 16 }}>
            <div className="field-label" style={{ marginBottom: 8 }}>
              Levels of <strong style={{ color: 'var(--text)' }}>{openField}</strong>
            </div>
            <Table
              rowKey={(r) => r.level}
              cols={[
                { key: 'level', label: 'Level' },
                { key: 'n', label: 'Runs', align: 'right', render: (r) => int(r.n) },
                { key: 'fail_rate', label: 'Failure rate', align: 'right',
                  render: (r) => pct(r.fail_rate) },
                { key: 'lift', label: 'Lift vs overall', align: 'right',
                  render: (r) => (
                    <span style={{ color: r.lift > 1.5 ? 'var(--danger)' : r.lift < 0.7 ? 'var(--success)' : 'var(--text-tertiary)' }}>
                      {num(r.lift, 2)}×
                    </span>) },
              ]}
              rows={(data.failure_by_field || []).find(f => f.field === openField)?.levels || []}
            />
          </div>
        )}
      </Card>

      {/* ── Metric stats ──────────────────────────────────────────── */}
      <Card title="Metric distributions">
        <Table
          rowKey={(r) => r.metric}
          cols={[
            { key: 'metric', label: 'Metric' },
            { key: 'mean', label: 'Mean', align: 'right' },
            { key: 'median', label: 'Median', align: 'right' },
            { key: 'p95', label: 'P95', align: 'right' },
            { key: 'min', label: 'Min', align: 'right' },
            { key: 'max', label: 'Max', align: 'right' },
          ]}
          rows={Object.entries(s.metric_stats || {}).map(([metric, v]) => ({
            metric,
            mean: num(v.mean, 2), median: num(v.median, 2), p95: num(v.p95, 2),
            min: num(v.min, 2), max: num(v.max, 2),
          }))}
        />
      </Card>

      {/* ── Highest risk runs ─────────────────────────────────────── */}
      <Card title="Highest-risk runs"
            hint="Ranked by the classifier's predicted failure probability.">
        <Table
          maxHeight={380}
          rowKey={(r) => r.run_id}
          cols={[
            { key: 'run_id', label: 'Run', render: (r) => <span className="mono">{r.run_id}</span> },
            { key: 'predicted_risk', label: 'Predicted risk', align: 'right',
              render: (r) => (
                <span style={{ color: r.predicted_risk > 0.7 ? 'var(--danger)' : 'var(--warning)' }}>
                  {pct(r.predicted_risk, 1)}
                </span>) },
            { key: 'pass_fail', label: 'Actual',
              render: (r) => (
                <Badge kind={r.pass_fail === 'fail' ? 'fail' : 'pass'}>{r.pass_fail}</Badge>) },
            { key: 'config', label: 'Configuration', wrap: true,
              render: (r) => (
                <span className="mono" style={{ color: 'var(--text-tertiary)' }}>
                  {Object.entries(r.config).map(([k, v]) => `${k}=${v}`).join('  ')}
                </span>) },
          ]}
          rows={data.risk_meter?.highest_risk_runs || []}
        />
      </Card>

      {/* ── Job + column inventory ────────────────────────────────── */}
      <div className="grid g2">
        <Card title="Job metadata">
          <Table
            cols={[{ key: 'k', label: 'Key' }, { key: 'v', label: 'Value', wrap: true }]}
            rows={[
              { k: 'Job ID', v: meta?.job_id },
              { k: 'Files', v: (meta?.files || []).join(', ') },
              { k: 'Elapsed', v: `${num(meta?.elapsed, 2)}s` },
              { k: 'Risk ceiling', v: pct(meta?.params?.max_risk, 1) },
              { k: 'Optuna trials', v: int(meta?.params?.n_trials) },
              { k: 'DBSCAN eps', v: num(meta?.params?.dbscan_eps ?? 0.35, 2) },
              { k: 'Features used', v: (data.risk_model?.features || []).join(', ') },
            ]}
          />
        </Card>
        <Card title="Parsed columns" hint={`${(s.columns || []).length} columns extracted from the logs`}>
          <div className="trace" style={{ maxHeight: 300 }}>
            {(s.columns || []).join('\n')}
          </div>
        </Card>
      </div>
    </div>
  )
}
