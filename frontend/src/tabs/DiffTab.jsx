import React, { useEffect, useState } from 'react'
import {
  Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { jobDiff } from '../api.js'
import { Icon } from '../icons.jsx'
import {
  CHART_AXIS, Alert, Badge, Button, Card, Empty, Stat, Table, TOOLTIP_STYLE,
  int, num, pct,
} from '../ui.jsx'

export default function DiffTab({ data, jobId, seedRun }) {
  const cd = data.config_diff || {}
  const twin = cd.nearest_twin || {}
  const agg = cd.aggregate || []

  const [runA, setRunA] = useState('')
  const [runB, setRunB] = useState('')
  const [diff, setDiff] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!seedRun) return
    setRunA(seedRun)
    const pair = (twin.example_pairs || []).find(p => p.failing_run === seedRun)
    if (pair) setRunB(pair.passing_run)
  }, [seedRun])                                  // eslint-disable-line

  async function compare(a = runA, b = runB) {
    if (!a || !b) { setErr('Enter both run IDs.'); return }
    setBusy(true); setErr(null)
    try {
      setDiff(await jobDiff(jobId, a.trim(), b.trim()))
    } catch (e) { setErr(e.message); setDiff(null) }
    finally { setBusy(false) }
  }

  const ranking = (twin.field_ranking || []).slice(0, 12).map(f => ({
    field: f.field, rate: f.diff_rate * 100,
  }))

  return (
    <div className="stack">
      <div className="grid g3">
        <Stat label="Twin pairs compared" value={int(twin.total_pairs)} icon="git-compare" tone="neutral"
              delta="failing run vs closest passing run" />
        <Stat label="Sequences analysed" value={int(agg.length)} icon="layers" tone="neutral" />
        <Stat label="Top differing setting"
              value={ranking[0]?.field || '–'} icon="alert-triangle" tone="warning" color="var(--warning)"
              delta={ranking[0] ? `${num(ranking[0].rate, 1)}% of pairs` : ''} />
      </div>

      <Card title="Nearest-twin field divergence"
            hint="For each failing run we find the most similar PASSING run of the same test sequence, then record which settings differ. Numeric fields only count when they move at least half a standard deviation, so continuous noise does not dominate.">
        <ResponsiveContainer width="100%" height={Math.max(240, ranking.length * 24)}>
          <BarChart data={ranking} layout="vertical"
                    margin={{ left: 50, right: 30, top: 5, bottom: 5 }}>
            <XAxis type="number" unit="%" {...CHART_AXIS} />
            <YAxis type="category" dataKey="field" width={150} {...CHART_AXIS} />
            <Tooltip {...TOOLTIP_STYLE} formatter={(v) => `${num(v, 1)}% of pairs`} />
            <Bar dataKey="rate" radius={[0, 4, 4, 0]}>
              {ranking.map((_, i) => (
                <Cell key={i} fill={i === 0 ? '#e0a324' : '#5b7cfa'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {/* ── Interactive log-diff viewer ───────────────────────────── */}
      <Card title="Log diff viewer"
            hint="Compare any two runs field by field, with both error traces side by side.">
        <div className="row" style={{ marginBottom: 16 }}>
          <input placeholder="Run A (e.g. RUN-000005)" value={runA}
                 onChange={e => setRunA(e.target.value)} style={{ minWidth: 190 }} />
          <span style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>vs</span>
          <input placeholder="Run B (e.g. RUN-000001)" value={runB}
                 onChange={e => setRunB(e.target.value)} style={{ minWidth: 190 }} />
          <Button variant="primary" icon="git-compare" loading={busy} onClick={() => compare()}>
            Compare
          </Button>
          {(twin.example_pairs || []).length > 0 && (
            <Button variant="ghost" size="sm" onClick={() => {
              const p = twin.example_pairs[0]
              setRunA(p.failing_run); setRunB(p.passing_run)
              compare(p.failing_run, p.passing_run)
            }}>Load closest pair</Button>
          )}
        </div>

        {err && <div style={{ marginBottom: 16 }}><Alert tone="danger">{err}</Alert></div>}

        {diff && (
          <>
            <div className="grid g2" style={{ marginBottom: 18 }}>
              {[diff.run_a, diff.run_b].map((r, i) => (
                <div key={i}>
                  <div className="row" style={{ marginBottom: 8 }}>
                    <strong className="mono">{r.run_id}</strong>
                    <Badge kind={r.pass_fail === 'fail' ? 'fail' : 'pass'}>{r.pass_fail}</Badge>
                    {r.error_tag && r.error_tag !== 'NONE' &&
                      <Badge kind="warn" icon={null}>{r.error_tag}</Badge>}
                  </div>
                  <div className="trace">{r.trace || '(no error trace — run passed)'}</div>
                </div>
              ))}
            </div>
            <div style={{ marginBottom: 10, fontSize: 12, color: 'var(--text-tertiary)' }}>
              {diff.n_changed} of {diff.fields.length} settings differ
            </div>
            <Table
              rowKey={(r) => r.field}
              cols={[
                { key: 'field', label: 'Setting',
                  render: (r) => <span className={r.changed ? 'chg' : ''}>{r.field}</span> },
                { key: 'a', label: 'Run A',
                  render: (r) => <span className={r.changed ? 'chg' : ''}>{String(r.a)}</span> },
                { key: 'b', label: 'Run B',
                  render: (r) => <span className={r.changed ? 'chg' : ''}>{String(r.b)}</span> },
                { key: 'changed', label: '',
                  render: (r) => r.changed ? <Badge kind="warn" icon={null}>changed</Badge> : '' },
              ]}
              rows={[...diff.fields].sort((a, b) => (b.changed ? 1 : 0) - (a.changed ? 1 : 0))}
            />
          </>
        )}

        {!diff && !err && (
          <Empty icon="git-compare" title="No comparison yet">
            Enter two run IDs above, or load the closest failing/passing pair.
          </Empty>
        )}
      </Card>

      <Card title="Closest failing / passing pairs"
            hint="Sorted by fewest differences — the top rows are near-identical runs with opposite verdicts, which is where a root cause usually hides.">
        <Table
          rowKey={(_, i) => i}
          maxHeight={340}
          cols={[
            { key: 'sequence', label: 'Sequence' },
            { key: 'failing_run', label: 'Failing',
              render: (r) => <span className="mono">{r.failing_run}</span> },
            { key: 'passing_run', label: 'Passing',
              render: (r) => <span className="mono">{r.passing_run}</span> },
            { key: 'error_tag', label: 'Error tag' },
            { key: 'n_differences', label: 'Δ fields', align: 'right' },
            { key: 'differences', label: 'Differences', wrap: true,
              render: (r) => (
                <span className="mono" style={{ color: 'var(--text-tertiary)' }}>
                  {r.differences.map(d =>
                    `${d.field}: ${d.failing_value} ≠ ${d.passing_value}`).join('  ·  ')}
                </span>) },
            { key: 'act', label: '',
              render: (r) => (
                <Button size="sm" variant="secondary" icon="git-compare"
                        onClick={() => {
                          setRunA(r.failing_run); setRunB(r.passing_run)
                          compare(r.failing_run, r.passing_run)
                        }}>Diff</Button>) },
          ]}
          rows={twin.example_pairs || []}
        />
      </Card>

      <Card title="Aggregate pass/fail deltas by test sequence"
            hint="How each setting's distribution shifts between passing and failing runs of the same test. Effect size is a standard-deviation shift for numerics, a share difference for categoricals.">
        {agg.length === 0 ? (
          <Empty icon="layers" title="Not enough data">
            Not enough runs per sequence to compare.
          </Empty>
        ) : (
          <div className="stack" style={{ gap: 20 }}>
            {agg.map(g => (
              <div key={g.sequence}>
                <div className="row" style={{ marginBottom: 10 }}>
                  <strong style={{ fontSize: 13 }}>{g.sequence}</strong>
                  <Badge kind="fail">{pct(g.fail_rate)} fail</Badge>
                  <span style={{ color: 'var(--text-tertiary)', fontSize: 12 }}>
                    {int(g.n_fail)} fail / {int(g.n_pass)} pass
                  </span>
                </div>
                <Table
                  maxHeight={230}
                  rowKey={(r) => r.field}
                  cols={[
                    { key: 'field', label: 'Setting' },
                    { key: 'kind', label: 'Type' },
                    { key: 'detail', label: 'Failing vs passing',
                      render: (r) => r.kind === 'numeric'
                        ? `${num(r.fail_value, 2)} vs ${num(r.pass_value, 2)}`
                        : `"${r.value}" ${pct(r.fail_share)} vs ${pct(r.pass_share)}` },
                    { key: 'effect_size', label: 'Effect size', align: 'right',
                      render: (r) => (
                        <span style={{ color: Math.abs(r.effect_size) > 0.2 ? 'var(--warning)' : 'var(--text-tertiary)' }}>
                          {num(r.effect_size, 3)}
                        </span>) },
                  ]}
                  rows={g.fields.slice(0, 8)}
                />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
