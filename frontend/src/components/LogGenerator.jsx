import { useEffect, useState } from 'react'
import axios from 'axios'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { card, th, td, mono, num, pct, fixed, INFO_BADGE, WARN_BADGE, xLabel } from './ui'

const FALLBACK = {
  n_runs: 20000, seed: 42, parts: 4, extra_deterministic: false,
  build_fields: false, seeds_per_config: 1, base_fail_prob: 0.012, rule_strength: 1.0,
}

// One-click starting points. "Bundled sample" is the corpus the dashboard
// ships with; "Most learnable" turns every option up.
const PRESETS = [
  { label: 'Bundled sample', opts: { ...FALLBACK, n_runs: 50000, parts: 10 } },
  { label: 'More signal', opts: { ...FALLBACK, extra_deterministic: true, build_fields: true, seeds_per_config: 5 } },
  {
    label: 'Most learnable',
    opts: {
      ...FALLBACK, extra_deterministic: true, build_fields: true,
      seeds_per_config: 5, base_fail_prob: 0.005, rule_strength: 2.5,
    },
  },
]

export default function LogGenerator({ onAnalyze }) {
  const [opts, setOpts] = useState(FALLBACK)
  const [rules, setRules] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [corpus, setCorpus] = useState(null)

  useEffect(() => {
    axios.get('/api/generator/defaults')
      .then((res) => { setOpts(res.data.options); setRules(res.data.rules) })
      .catch(() => {})
  }, [])

  const set = (k) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : Number(e.target.value)
    setOpts((o) => ({ ...o, [k]: v }))
  }

  const generate = async () => {
    setBusy(true)
    setError(null)
    setCorpus(null)
    try {
      const res = await axios.post('/api/generate', opts)
      setCorpus(res.data)
    } catch (err) {
      const d = err.response?.data?.detail
      setError('Generation failed: ' + (Array.isArray(d) ? d.map((x) => x.msg).join('; ') : d || err.message))
    } finally {
      setBusy(false)
    }
  }

  const activeRules = rules ? [
    ...rules.base,
    ...(opts.extra_deterministic ? rules.extra_deterministic : []),
    ...(opts.build_fields ? rules.build_fields : []),
  ] : []

  return (
    <div style={{ padding: '0 24px 24px' }}>
      <div style={{ ...card, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>Generate synthetic UVM logs</h3>
        <p style={{ margin: '0 0 14px', fontSize: 13, color: '#6b7280' }}>
          Builds a corpus with known failure rules, so you can see how well the
          dashboard rediscovers them. Every setting at its default reproduces the
          bundled sample exactly (given the same run count, seed and file count).
        </p>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 18 }}>
          <span style={{ fontSize: 13, color: '#374151', alignSelf: 'center' }}>Presets:</span>
          {PRESETS.map((p) => (
            <button key={p.label} className="btn btn-sm" onClick={() => setOpts(p.opts)}>
              {p.label}
            </button>
          ))}
        </div>

        <Section title="Corpus size">
          <Num label="Runs" hint="500 to 200,000" value={opts.n_runs} onChange={set('n_runs')} min={500} max={200000} step={500} />
          <Num label="Random seed" hint="same seed, same corpus" value={opts.seed} onChange={set('seed')} />
          <Num label="Log files" hint="runs are split across this many files" value={opts.parts} onChange={set('parts')} min={1} max={50} />
        </Section>

        <Section title="Signal the model can learn">
          <Check
            label="More deterministic bugs"
            hint="Adds R8 and R9: two RTL bugs that fail ~97% of the time on a fixed config, with an identical trace every time."
            checked={opts.extra_deterministic} onChange={set('extra_deterministic')} />
          <Check
            label="Build-version fields"
            hint="Adds firmware_version, rtl_build and testbench_version to each run. They are known before the run starts, so they are fair model inputs. Rules R10 to R12 tie regressions to them."
            checked={opts.build_fields} onChange={set('build_fields')} />
          <Num
            label="Seeds per configuration"
            hint="Runs each config this many times with different seeds, so its failure rate is measured rather than guessed from one run."
            value={opts.seeds_per_config} onChange={set('seeds_per_config')} min={1} max={50} />
        </Section>

        <Section title="Noise">
          <Num
            label="Base failure probability"
            hint="Chance a config no rule touches still fails (random noise). Default 0.012."
            value={opts.base_fail_prob} onChange={set('base_fail_prob')} min={0} max={0.5} step={0.001} />
          <Num
            label="Rule strength"
            hint="Multiplies every additive rule. Above 1 makes the risky configs fail more reliably, which is less noise."
            value={opts.rule_strength} onChange={set('rule_strength')} min={0} max={3} step={0.1} />
        </Section>

        <button className="btn btn-primary" onClick={generate} disabled={busy}>
          {busy ? 'Generating…' : 'Generate logs'}
        </button>
        {error && <div className="error-box" style={{ marginTop: 14 }}>{error}</div>}
      </div>

      {corpus && <CorpusSummary corpus={corpus} onAnalyze={onAnalyze} />}

      {rules && (
        <div style={card}>
          <h3 style={{ marginTop: 0 }}>Rules that will be embedded ({activeRules.length})</h3>
          <RuleTable rules={activeRules} />
        </div>
      )}
    </div>
  )
}

function CorpusSummary({ corpus, onAnalyze }) {
  const md = corpus.metadata
  const tags = Object.entries(corpus.error_tag_distribution || {})
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count)

  return (
    <div style={{ ...card, marginBottom: 20, borderLeft: '4px solid #16a34a' }}>
      <h3 style={{ marginTop: 0 }}>Corpus ready</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 16, marginBottom: 16 }}>
        <Stat label="Runs" value={num(md.n_runs)} />
        <Stat label="Distinct configurations" value={num(md.distinct_configs)} />
        <Stat label="Failure rate" value={pct(md.observed_fail_rate)} />
        <Stat label="Best possible ROC-AUC" value={fixed(md.oracle_roc_auc, 3)} />
        <Stat label="Log files" value={num(md.parts)} />
      </div>
      <p style={{ fontSize: 13, color: '#6b7280', margin: '0 0 16px' }}>
        <b>Best possible ROC-AUC</b> scores the generator&apos;s own failure
        probabilities. No model can beat it on this corpus, because whatever is
        left over is pure chance. Compare it with the Model ROC-AUC on the
        Executive Summary after you analyse.
      </p>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
        <button className="btn btn-primary" onClick={() => onAnalyze(corpus.corpus_id)}>
          Analyse this corpus
        </button>
        <a className="btn" href={`/api/generate/${corpus.corpus_id}/download`}>
          Download logs (.zip)
        </a>
      </div>

      {tags.length > 0 && (
        <>
          <h4 style={{ margin: '0 0 8px' }}>Failures by error tag</h4>
          <ResponsiveContainer width="100%" height={Math.max(180, tags.length * 34)}>
            <BarChart data={tags} layout="vertical" margin={{ left: 40, right: 20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" label={xLabel('Failing runs (count)')} />
              <YAxis type="category" dataKey="tag" width={150} />
              <Tooltip />
              <Bar dataKey="count" fill="#ef4444" name="Failing runs" />
            </BarChart>
          </ResponsiveContainer>
        </>
      )}

      <h4 style={{ margin: '16px 0 8px' }}>What each rule actually did</h4>
      <RuleTable rules={corpus.rules} observed />
    </div>
  )
}

function RuleTable({ rules, observed }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#f3f4f6' }}>
            <th style={th}>Rule</th>
            <th style={th}>What it does</th>
            <th style={th}>Error tag</th>
            <th style={th}>Effect</th>
            {observed && <>
              <th style={{ ...th, textAlign: 'right' }}>Runs hit</th>
              <th style={{ ...th, textAlign: 'right' }}>Fail rate when hit</th>
              <th style={{ ...th, textAlign: 'right' }}>Otherwise</th>
              <th style={{ ...th, textAlign: 'right' }}>Lift</th>
            </>}
          </tr>
        </thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.id}>
              <td style={{ ...td, fontWeight: 600 }}>{r.id}</td>
              <td style={td}>
                {r.description}
                <div style={{ ...mono, color: '#9ca3af', marginTop: 2 }}>
                  {r.conditions.map((c) => `${c.field} ${c.op} ${c.value}`).join(' and ')}
                </div>
              </td>
              <td style={td}>{r.error_tag || '—'}</td>
              <td style={td}>
                <span style={r.deterministic ? WARN_BADGE : INFO_BADGE}>
                  {r.effect === 'set' ? `fails ${pct(r.value, 0)}` : `+${pct(r.value, 0)}`}
                  {r.deterministic ? ' · deterministic' : ''}
                </span>
              </td>
              {observed && <>
                <td style={{ ...td, textAlign: 'right' }}>{num(r.observed.rows_matched)}</td>
                <td style={{ ...td, textAlign: 'right' }}>{pct(r.observed.fail_rate_when_fired)}</td>
                <td style={{ ...td, textAlign: 'right' }}>{pct(r.observed.fail_rate_otherwise)}</td>
                <td style={{ ...td, textAlign: 'right' }}>{r.observed.lift != null ? `${fixed(r.observed.lift, 1)}×` : '—'}</td>
              </>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <fieldset style={{ border: '1px solid #e5e7eb', borderRadius: 6, padding: '12px 16px', marginBottom: 16 }}>
      <legend style={{ fontSize: 13, fontWeight: 600, color: '#374151', padding: '0 6px' }}>{title}</legend>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 14 }}>
        {children}
      </div>
    </fieldset>
  )
}

function Num({ label, hint, ...input }) {
  return (
    <label style={{ fontSize: 13, color: '#374151' }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      <input type="number" {...input}
             style={{ width: '100%', padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: 4, boxSizing: 'border-box' }} />
      {hint && <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>{hint}</div>}
    </label>
  )
}

function Check({ label, hint, ...input }) {
  return (
    <label style={{ fontSize: 13, color: '#374151', display: 'flex', gap: 8, alignItems: 'flex-start' }}>
      <input type="checkbox" {...input} style={{ marginTop: 3 }} />
      <span>
        <span style={{ fontWeight: 600 }}>{label}</span>
        {hint && <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>{hint}</div>}
      </span>
    </label>
  )
}

function Stat({ label, value }) {
  return (
    <div style={{ ...card, padding: 16, background: '#f9fafb' }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: '#111827' }}>{value}</div>
      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>{label}</div>
    </div>
  )
}
