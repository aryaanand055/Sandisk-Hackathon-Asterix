import React, { useState } from 'react'
import {
  CartesianGrid, Cell, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts'
import { Icon } from '../icons.jsx'
import {
  CHART_AXIS, CHART_GRID, Alert, Badge, Button, Card, Empty, PALETTE, Stat,
  Table, TOOLTIP_STYLE, int, num, pct,
} from '../ui.jsx'

export default function Fingerprints({ data, onCompare }) {
  const fp = data.fingerprints || {}
  const clusters = fp.clusters || []
  const [selected, setSelected] = useState(null)

  if (!clusters.length) {
    return <Empty icon="fingerprint" title="No failures to fingerprint">
      Every parsed run passed — there are no error traces to cluster.
    </Empty>
  }

  const detIds = new Set(fp.deterministic_clusters || [])
  const sel = clusters.find(c => c.cluster_id === selected) || null

  return (
    <div className="stack">
      <div className="grid g4">
        <Stat label="Failing runs" value={int(fp.n_failing)} icon="x-circle" tone="danger" />
        <Stat label="Distinct templates" value={int(fp.n_templates)} icon="layers" tone="neutral" />
        <Stat label="Clusters" value={int(fp.n_clusters)} icon="layout-grid" tone="accent" color="var(--accent)" />
        <Stat label="Deterministic bugs" value={detIds.size} icon="zap"
              tone={detIds.size ? 'purple' : 'neutral'}
              color={detIds.size ? 'var(--purple)' : undefined}
              delta={detIds.size ? 'identical trace across seeds' : 'none detected'} />
      </div>

      {detIds.size > 0 && (
        <Alert tone="info" title={`${detIds.size} deterministic RTL bug${detIds.size > 1 ? 's' : ''} isolated`}>
          These clusters produce a byte-identical error trace across many different
          random seeds, which separates a genuine RTL defect from seed-dependent noise.
        </Alert>
      )}

      <Card title="Fingerprint cluster map"
            hint="TF-IDF over seed-masked error templates, projected to 2D with truncated SVD. Point size = number of runs sharing that template.">
        <ResponsiveContainer width="100%" height={330}>
          <ScatterChart margin={{ left: 10, right: 20, top: 10, bottom: 20 }}>
            <CartesianGrid {...CHART_GRID} />
            <XAxis type="number" dataKey="x" name="SVD-1" {...CHART_AXIS} />
            <YAxis type="number" dataKey="y" name="SVD-2" {...CHART_AXIS} />
            <ZAxis type="number" dataKey="count" range={[60, 620]} />
            <Tooltip {...TOOLTIP_STYLE}
                     content={({ payload }) => {
                       if (!payload?.length) return null
                       const p = payload[0].payload
                       return (
                         <div style={{ ...TOOLTIP_STYLE.contentStyle, padding: 10, maxWidth: 380 }}>
                           <div style={{ fontWeight: 650 }}>Cluster {p.cluster} · {int(p.count)} runs</div>
                           <div style={{ color: 'var(--text-tertiary)', marginTop: 6, fontSize: 11,
                                         fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap' }}>
                             {p.template}
                           </div>
                         </div>
                       )
                     }} />
            <Scatter data={fp.scatter || []}>
              {(fp.scatter || []).map((p, i) => (
                <Cell key={i}
                      fill={detIds.has(p.cluster) ? '#9d7bf0'
                        : PALETTE[(p.cluster + 1) % PALETTE.length]}
                      fillOpacity={0.8} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Clusters"
            hint="Determinism = 1 − (distinct raw traces ÷ runs). Near 1.0 means the same text every time, regardless of seed. Select a row to inspect it.">
        <Table
          rowKey={(r) => r.cluster_id}
          cols={[
            { key: 'cluster_id', label: 'Cluster',
              render: (r) => (
                <Button size="sm" variant={selected === r.cluster_id ? 'primary' : 'secondary'}
                        onClick={() => setSelected(r.cluster_id)}>
                  c{r.cluster_id}
                </Button>) },
            { key: 'dominant_tag', label: 'Dominant tag' },
            { key: 'size', label: 'Runs', align: 'right', render: (r) => int(r.size) },
            { key: 'share_of_failures', label: 'Share', align: 'right',
              render: (r) => pct(r.share_of_failures) },
            { key: 'distinct_raw_traces', label: 'Distinct traces', align: 'right',
              render: (r) => int(r.distinct_raw_traces) },
            { key: 'distinct_seeds', label: 'Distinct seeds', align: 'right',
              render: (r) => int(r.distinct_seeds) },
            { key: 'determinism', label: 'Determinism', align: 'right',
              render: (r) => num(r.determinism, 3) },
            { key: 'classification', label: 'Verdict',
              render: (r) => (
                <Badge kind={r.determinism >= 0.8 ? 'det' : 'warn'}>
                  {r.classification}
                </Badge>) },
            { key: 'mean_execution_time_ms', label: 'Mean exec (ms)', align: 'right',
              render: (r) => num(r.mean_execution_time_ms, 1) },
          ]}
          rows={clusters}
        />
      </Card>

      {sel && (
        <Card title={`Cluster c${sel.cluster_id} detail`}
              hint={`${sel.dominant_tag} · ${int(sel.size)} runs · ${int(sel.n_templates)} template(s)`}
              actions={onCompare && sel.example_run_ids?.length >= 1 && (
                <Button size="sm" variant="secondary" iconRight="arrow-right"
                        onClick={() => onCompare(sel.example_run_ids[0])}>
                  Diff a passing twin
                </Button>
              )}>
          <div className="row" style={{ marginBottom: 14 }}>
            <Badge kind={sel.determinism >= 0.8 ? 'det' : 'warn'}>{sel.classification}</Badge>
            <span style={{ color: 'var(--text-tertiary)', fontSize: 12 }}>
              {int(sel.distinct_raw_traces)} distinct raw trace(s) across{' '}
              {int(sel.distinct_seeds)} seed(s)
            </span>
          </div>

          <div className="field-label" style={{ marginBottom: 6 }}>Seed-masked template</div>
          <div className="trace" style={{ marginBottom: 16 }}>{sel.representative_template}</div>

          <div className="field-label" style={{ marginBottom: 6 }}>Example raw trace</div>
          <div className="trace">{sel.example_trace}</div>

          <div className="divider" />
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
              Example runs: <span className="mono">{(sel.example_run_ids || []).join(', ')}</span>
            </span>
            <div className="row">
              {Object.entries(sel.tag_breakdown || {}).map(([t, n]) => (
                <Badge key={t} kind="info" icon={null}>{t}: {int(n)}</Badge>
              ))}
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
