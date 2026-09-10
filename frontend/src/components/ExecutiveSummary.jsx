export default function ExecutiveSummary({ data }) {
  if (!data?.analysis?.summary) return <div>Loading analysis...</div>

  const summary = data.analysis.summary
  const risk = data.analysis.risk_model

  return (
    <div>
      <h2>Executive Summary</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '30px' }}>
        <div style={{ background: '#fff', padding: '20px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{summary.n_runs.toLocaleString()}</div>
          <div style={{ fontSize: '12px', color: '#666' }}>Total Runs</div>
        </div>
        <div style={{ background: '#fff', padding: '20px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{(summary.fail_rate * 100).toFixed(1)}%</div>
          <div style={{ fontSize: '12px', color: '#666' }}>Failure Rate</div>
        </div>
        <div style={{ background: '#fff', padding: '20px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{(risk.metrics.roc_auc * 100).toFixed(1)}%</div>
          <div style={{ fontSize: '12px', color: '#666' }}>Model ROC-AUC</div>
        </div>
        <div style={{ background: '#fff', padding: '20px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{(risk.metrics.accuracy * 100).toFixed(1)}%</div>
          <div style={{ fontSize: '12px', color: '#666' }}>Accuracy</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
        <div style={{ background: '#fff', padding: '20px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <h3 style={{ margin: '0 0 15px 0' }}>Model Performance</h3>
          <table style={{ width: '100%', fontSize: '14px' }}>
            <tbody>
              <tr style={{ borderBottom: '1px solid #eee' }}><td>Accuracy</td><td style={{ textAlign: 'right' }}>{(risk.metrics.accuracy * 100).toFixed(1)}%</td></tr>
              <tr style={{ borderBottom: '1px solid #eee' }}><td>Precision</td><td style={{ textAlign: 'right' }}>{(risk.metrics.precision * 100).toFixed(1)}%</td></tr>
              <tr style={{ borderBottom: '1px solid #eee' }}><td>Recall</td><td style={{ textAlign: 'right' }}>{(risk.metrics.recall * 100).toFixed(1)}%</td></tr>
              <tr style={{ borderBottom: '1px solid #eee' }}><td>F1-Score</td><td style={{ textAlign: 'right' }}>{(risk.metrics.f1 * 100).toFixed(1)}%</td></tr>
              <tr><td>ROC-AUC</td><td style={{ textAlign: 'right' }}>{(risk.metrics.roc_auc * 100).toFixed(1)}%</td></tr>
            </tbody>
          </table>
        </div>

        <div style={{ background: '#fff', padding: '20px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <h3 style={{ margin: '0 0 15px 0' }}>Summary Statistics</h3>
          <table style={{ width: '100%', fontSize: '14px' }}>
            <tbody>
              <tr style={{ borderBottom: '1px solid #eee' }}><td>Pass Runs</td><td style={{ textAlign: 'right', fontWeight: 'bold' }}>{summary.n_pass.toLocaleString()}</td></tr>
              <tr style={{ borderBottom: '1px solid #eee' }}><td>Fail Runs</td><td style={{ textAlign: 'right', fontWeight: 'bold' }}>{summary.n_fail.toLocaleString()}</td></tr>
              <tr style={{ borderBottom: '1px solid #eee' }}><td>Error Lines</td><td style={{ textAlign: 'right' }}>{summary.n_error_lines.toLocaleString()}</td></tr>
              <tr><td>Mean Exec Time</td><td style={{ textAlign: 'right' }}>{summary.metric_stats.execution_time_ms.mean.toFixed(1)}ms</td></tr>
            </tbody>
          </table>
        </div>

        <div style={{ background: '#fff', padding: '20px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <h3 style={{ margin: '0 0 15px 0' }}>Top Error Types</h3>
          <table style={{ width: '100%', fontSize: '14px' }}>
            <tbody>
              {Object.entries(summary.error_tag_distribution).slice(0, 5).map(([tag, count]) => (
                <tr key={tag} style={{ borderBottom: '1px solid #eee' }}>
                  <td>{tag}</td>
                  <td style={{ textAlign: 'right' }}>{count.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
