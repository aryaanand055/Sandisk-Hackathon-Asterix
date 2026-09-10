import { useState } from 'react'
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function FailureFingerprints({ data }) {
  const [selectedCluster, setSelectedCluster] = useState(null)

  if (!data?.fingerprints) return <div>No fingerprint data</div>

  const clusters = data.fingerprints.clusters || []
  const chartData = clusters.map(c => ({
    id: c.id,
    x: c.svd_x || Math.random(),
    y: c.svd_y || Math.random(),
    size: c.run_count,
    determinism: c.determinism_score
  }))

  return (
    <div className="fingerprints-container">
      <div className="chart-box">
        <h3>Cluster Map (SVD Projection)</h3>
        <ResponsiveContainer width="100%" height={400}>
          <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="x" name="PC1" />
            <YAxis dataKey="y" name="PC2" />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
            <Scatter name="Clusters" data={chartData} fill="#3498db" onClick={(e) => setSelectedCluster(e.id)} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="clusters-table">
        <h3>Cluster Details</h3>
        <table>
          <thead>
            <tr>
              <th>Cluster</th>
              <th>Failure Mode</th>
              <th>Runs</th>
              <th>Determinism</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {clusters.map(c => (
              <tr key={c.id} className={c.is_deterministic ? 'rtl-bug' : ''}>
                <td>{c.id}</td>
                <td>{c.error_type}</td>
                <td>{c.run_count}</td>
                <td>{(c.determinism_score * 100).toFixed(2)}%</td>
                <td>{c.is_deterministic ? '🐛 RTL Bug' : 'Random'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedCluster && (
        <div className="cluster-detail">
          <h3>Cluster {selectedCluster} Details</h3>
          <p>Click a cluster to see templated error messages</p>
        </div>
      )}

      <style jsx>{`
        .rtl-bug {
          background: #fff3cd;
        }
        .clusters-table {
          margin-top: 30px;
        }
        table {
          width: 100%;
          border-collapse: collapse;
        }
        th, td {
          padding: 10px;
          text-align: left;
          border-bottom: 1px solid #ecf0f1;
        }
        th {
          background: #f8f9fa;
          font-weight: 600;
        }
      `}</style>
    </div>
  )
}
