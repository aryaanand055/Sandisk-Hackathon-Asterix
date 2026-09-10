import { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function FailureFingerprints({ data }) {
  const [selectedCluster, setSelectedCluster] = useState(null)

  if (!data?.analysis?.fingerprints) return <div>Loading fingerprint analysis...</div>

  const fingerprints = data.analysis.fingerprints
  const clusters = fingerprints.clusters || []

  const determinsimData = clusters.map(c => ({
    name: c.error_type,
    determinism: (c.determinism * 100).toFixed(1),
    runs: c.n_runs
  }))

  return (
    <div className="fingerprints-container">
      <div className="summary-stats">
        <div className="stat-box">
          <div className="stat-value">{fingerprints.n_clusters}</div>
          <div className="stat-label">Distinct Clusters</div>
        </div>
        <div className="stat-box">
          <div className="stat-value">{fingerprints.n_templates}</div>
          <div className="stat-label">Error Templates</div>
        </div>
      </div>

      <div className="chart-box">
        <h3>Determinism by Failure Type</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={determinsimData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis yAxisId="left" label={{ value: 'Determinism %', angle: -90, position: 'insideLeft' }} />
            <YAxis yAxisId="right" orientation="right" label={{ value: 'Run Count', angle: 90, position: 'insideRight' }} />
            <Tooltip />
            <Legend />
            <Bar yAxisId="left" dataKey="determinism" fill="#3b82f6" name="Determinism %" />
            <Bar yAxisId="right" dataKey="runs" fill="#10b981" name="Runs" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="clusters-table">
        <h3>Cluster Analysis</h3>
        <table>
          <thead>
            <tr>
              <th>Cluster ID</th>
              <th>Error Type</th>
              <th>Run Count</th>
              <th>Templates</th>
              <th>Determinism</th>
              <th>Classification</th>
            </tr>
          </thead>
          <tbody>
            {clusters.map((c, i) => (
              <tr key={i} className={c.is_rtl_bug ? 'rtl-bug-row' : ''} onClick={() => setSelectedCluster(c.id)}>
                <td className="cluster-id">{c.id}</td>
                <td className="error-type">{c.error_type}</td>
                <td>{c.n_runs.toLocaleString()}</td>
                <td>{c.n_distinct_templates}</td>
                <td><span className="det-badge">{(c.determinism * 100).toFixed(1)}%</span></td>
                <td>{c.is_rtl_bug ? <span className="rtl-badge">🐛 RTL Bug</span> : <span className="random-badge">Random</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedCluster && (
        <div className="cluster-detail">
          <h3>Cluster {selectedCluster} Signature Analysis</h3>
          <p>Shows deterministic vs stochastic behavior within this failure mode</p>
        </div>
      )}

      <style>{`
        .fingerprints-container .summary-stats {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 15px;
          margin-bottom: 30px;
        }
        .fingerprints-container .stat-box {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          padding: 20px;
          border-radius: 8px;
          text-align: center;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .fingerprints-container .stat-value {
          font-size: 32px;
          font-weight: bold;
          margin-bottom: 5px;
        }
        .fingerprints-container .stat-label {
          font-size: 12px;
          opacity: 0.9;
        }
        .fingerprints-container .clusters-table {
          margin-top: 30px;
        }
        .fingerprints-container table {
          width: 100%;
          border-collapse: collapse;
          background: white;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
          border-radius: 6px;
          overflow: hidden;
        }
        .fingerprints-container th {
          background: #f3f4f6;
          padding: 12px;
          text-align: left;
          font-weight: 600;
          color: #374151;
          border-bottom: 2px solid #e5e7eb;
        }
        .fingerprints-container td {
          padding: 12px;
          border-bottom: 1px solid #e5e7eb;
          color: #6b7280;
        }
        .fingerprints-container tr:hover {
          background: #f9fafb;
          cursor: pointer;
        }
        .fingerprints-container .cluster-id {
          font-weight: 600;
          color: #1f2937;
        }
        .fingerprints-container .error-type {
          color: #1f2937;
          font-weight: 500;
        }
        .fingerprints-container .det-badge {
          background: #dbeafe;
          color: #1e40af;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 600;
        }
        .fingerprints-container .rtl-bug-row {
          background: #fef3c7;
        }
        .fingerprints-container .rtl-badge {
          background: #fed7aa;
          color: #92400e;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 600;
        }
        .fingerprints-container .random-badge {
          background: #d1fae5;
          color: #065f46;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 600;
        }
      `}</style>
    </div>
  )
}
