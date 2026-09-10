export default function FailureFingerprints({ data }) {
  if (!data?.analysis?.fingerprints) return <div>Loading fingerprint analysis...</div>

  const fingerprints = data.analysis.fingerprints
  const clusters = fingerprints.clusters || []

  return (
    <div>
      <h2>Failure Fingerprints</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '20px', marginBottom: '20px' }}>
        <div style={{ background: '#fff', padding: '20px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{fingerprints.n_clusters}</div>
          <div style={{ fontSize: '12px', color: '#666' }}>Distinct Clusters</div>
        </div>
        <div style={{ background: '#fff', padding: '20px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{fingerprints.n_templates}</div>
          <div style={{ fontSize: '12px', color: '#666' }}>Error Templates</div>
        </div>
      </div>

      <div style={{ background: '#fff', padding: '20px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <h3>Cluster Analysis</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f3f4f6' }}>
              <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600', borderBottom: '2px solid #e5e7eb' }}>Error Type</th>
              <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600', borderBottom: '2px solid #e5e7eb' }}>Runs</th>
              <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600', borderBottom: '2px solid #e5e7eb' }}>Templates</th>
              <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600', borderBottom: '2px solid #e5e7eb' }}>Determinism</th>
              <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600', borderBottom: '2px solid #e5e7eb' }}>Type</th>
            </tr>
          </thead>
          <tbody>
            {clusters.map((c, i) => (
              <tr key={i} style={{ background: c.is_rtl_bug ? '#fef3c7' : '#fff', borderBottom: '1px solid #e5e7eb' }}>
                <td style={{ padding: '12px' }}>{c.error_type}</td>
                <td style={{ padding: '12px' }}>{c.n_runs.toLocaleString()}</td>
                <td style={{ padding: '12px' }}>{c.n_distinct_templates}</td>
                <td style={{ padding: '12px' }}>{(c.determinism * 100).toFixed(1)}%</td>
                <td style={{ padding: '12px' }}>{c.is_rtl_bug ? '🐛 RTL Bug' : 'Random'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
