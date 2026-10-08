import { useState, useRef } from 'react'
import ExecutiveSummary from './ExecutiveSummary'
import FailureFingerprints from './FailureFingerprints'
import TradeoffMatrix from './TradeoffMatrix'
import Recommendations from './Recommendations'
import AllDetails from './AllDetails'

/* ─────────────────────────────────────────────────────────────────────────
   Inline print stylesheet injected once into <head> when the component
   first mounts. It is scoped to the `#pdf-report` container so it never
   bleeds into the normal UI.
───────────────────────────────────────────────────────────────────────── */
const PRINT_CSS = `
@media print {
  /* Hide everything except the report */
  body > *:not(#pdf-report-portal) { display: none !important; }
  #pdf-report-portal { display: block !important; }

  #pdf-report {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 11pt;
    color: #171a21;
    background: #fff;
    padding: 0;
    margin: 0;
  }

  .pdf-cover {
    page-break-after: always;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 90vh;
    text-align: center;
  }

  .pdf-section {
    page-break-before: always;
    padding: 8mm 0;
  }

  .pdf-section-title {
    font-size: 16pt;
    font-weight: 700;
    color: #4a5fe0;
    border-bottom: 2px solid #4a5fe0;
    padding-bottom: 6px;
    margin-bottom: 20px;
  }

  /* Recharts SVG should not be clipped across pages */
  svg { overflow: visible !important; }

  /* Tables */
  table { page-break-inside: auto; }
  tr { page-break-inside: avoid; }

  /* Suppress interactive/decorative elements */
  button, input, .tab-buttons, .export-section { display: none !important; }
}
`

function injectPrintCSS() {
  if (document.getElementById('__export-print-css')) return
  const style = document.createElement('style')
  style.id = '__export-print-css'
  style.textContent = PRINT_CSS
  document.head.appendChild(style)
}

/* ─────────────────────────────────────────────────────────────────────────
   Main component
───────────────────────────────────────────────────────────────────────── */
export default function ExportReport({ result, jobId }) {
  const [generating, setGenerating] = useState(false)
  const [stage, setStage] = useState('')
  const portalRef = useRef(null)

  const meta = result?.meta || {}
  const files = meta.files || []
  const createdAt = meta.created
    ? new Date(meta.created * 1000).toLocaleString()
    : '—'

  const handleExport = async () => {
    injectPrintCSS()
    setGenerating(true)
    setStage('Preparing report…')

    // Let React paint the portal before triggering print
    await new Promise((r) => setTimeout(r, 400))
    setStage('Opening print dialog…')
    await new Promise((r) => setTimeout(r, 200))

    window.print()

    // Cleanup after print dialog closes (print() is synchronous so this fires after)
    setGenerating(false)
    setStage('')
  }

  return (
    <>
      {/* ── Visible Export Section ── */}
      <div className="export-section">
        {/* Header */}
        <div className="export-header">
          <div className="export-header-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
          </div>
          <div>
            <h2 className="export-title">Export Full Report</h2>
            <p className="export-subtitle">
              Download all analysis sections — Executive Summary, Failure Fingerprints,
              Tradeoff Matrix, Recommendations, and Details — as a single PDF.
            </p>
          </div>
        </div>

        {/* Job info pills */}
        <div className="export-meta-row">
          <span className="export-pill">
            <span className="export-pill-dot export-pill-dot--blue" />
            Job&nbsp;<code>{jobId}</code>
          </span>
          <span className="export-pill">
            <span className="export-pill-dot export-pill-dot--green" />
            {meta.n_runs?.toLocaleString?.() ?? '—'} runs analysed
          </span>
          <span className="export-pill">
            <span className="export-pill-dot export-pill-dot--purple" />
            {files.length} source file{files.length !== 1 ? 's' : ''}
          </span>
          <span className="export-pill">
            <span className="export-pill-dot export-pill-dot--orange" />
            Generated {createdAt}
          </span>
        </div>

        {/* Sections included */}
        <div className="export-sections-grid">
          {[
            { icon: '📊', title: 'Executive Summary', desc: 'KPIs, pass/fail pie, SHAP importance, risk bands, ROC curve' },
            { icon: '🔍', title: 'Failure Fingerprints', desc: 'Cluster-level failure patterns and error-tag breakdown' },
            { icon: '⚖️', title: 'Tradeoff Matrix', desc: 'Risk vs throughput configuration tradeoffs' },
            { icon: '💡', title: 'Recommendations', desc: 'Bayesian-optimised config suggestions and optimisation history' },
            { icon: '📋', title: 'All Details', desc: 'Parse stats, stage timing, failure-by-field, and highest-risk runs' },
          ].map((s) => (
            <div key={s.title} className="export-section-card">
              <span className="export-section-card-icon">{s.icon}</span>
              <div>
                <div className="export-section-card-title">{s.title}</div>
                <div className="export-section-card-desc">{s.desc}</div>
              </div>
            </div>
          ))}
        </div>

        {/* CTA */}
        <div className="export-cta">
          <button
            id="export-pdf-btn"
            className="btn btn-export"
            onClick={handleExport}
            disabled={generating}
          >
            {generating ? (
              <>
                <span className="export-spinner" />
                {stage}
              </>
            ) : (
              <>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 8 }}>
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Download PDF
              </>
            )}
          </button>
          <p className="export-hint">
            Uses your browser&apos;s print-to-PDF. In the dialog, choose <em>Save as PDF</em> as the destination.
          </p>
        </div>
      </div>

      {/* ── Hidden print portal – rendered off-screen, shown only during print ── */}
      <div id="pdf-report-portal" ref={portalRef} style={{ display: 'none' }}>
        <div id="pdf-report">
          {/* Cover page */}
          <div className="pdf-cover">
            <div style={{ fontSize: 42, marginBottom: 16 }}>🔬</div>
            <h1 style={{ fontSize: 28, fontWeight: 800, color: '#4a5fe0', marginBottom: 8 }}>
              UVM Configuration Intelligence Report
            </h1>
            <p style={{ color: '#565d6b', fontSize: 13, marginBottom: 24 }}>
              Powered by Team Asterix · SanDisk Hackathon
            </p>
            <table style={{ fontSize: 13, borderCollapse: 'collapse', minWidth: 340 }}>
              <tbody>
                {[
                  ['Job ID', jobId],
                  ['Runs Analysed', (meta.n_runs ?? '—').toLocaleString?.() ?? meta.n_runs],
                  ['Source Files', files.join(', ') || '—'],
                  ['Generated', createdAt],
                  ['Elapsed', meta.elapsed != null ? `${meta.elapsed.toFixed(1)} s` : '—'],
                ].map(([k, v]) => (
                  <tr key={k}>
                    <td style={{ padding: '5px 12px 5px 0', color: '#565d6b', fontWeight: 600, whiteSpace: 'nowrap' }}>{k}</td>
                    <td style={{ padding: '5px 0', fontFamily: 'monospace' }}>{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Section 1 – Executive Summary */}
          <div className="pdf-section">
            <div className="pdf-section-title">1 · Executive Summary</div>
            <ExecutiveSummary data={result} />
          </div>

          {/* Section 2 – Failure Fingerprints */}
          <div className="pdf-section">
            <div className="pdf-section-title">2 · Failure Fingerprints</div>
            <FailureFingerprints data={result} />
          </div>

          {/* Section 3 – Tradeoff Matrix */}
          <div className="pdf-section">
            <div className="pdf-section-title">3 · Tradeoff Matrix</div>
            <TradeoffMatrix data={result} />
          </div>

          {/* Section 4 – Recommendations */}
          <div className="pdf-section">
            <div className="pdf-section-title">4 · Recommendations</div>
            <Recommendations data={result} />
          </div>

          {/* Section 5 – All Details */}
          <div className="pdf-section">
            <div className="pdf-section-title">5 · All Details</div>
            <AllDetails data={result} />
          </div>
        </div>
      </div>
    </>
  )
}
