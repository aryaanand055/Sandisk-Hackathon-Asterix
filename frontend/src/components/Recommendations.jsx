export default function Recommendations({ data }) {
  if (!data?.recommendations) return <div>No recommendations data</div>

  const rec = data.recommendations
  const configs = rec.recommended_configs || []

  return (
    <div className="recommendations-container">
      <div className="rec-summary">
        <h3>Optimization Results</h3>
        <p>Searched {rec.n_trials || 0} configurations with Optuna TPE</p>
        <p>Risk ceiling: {(rec.max_risk * 100).toFixed(1)}%</p>
      </div>

      <div className="configs-table">
        <h3>Top Configurations</h3>
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Throughput</th>
              <th>Predicted Risk</th>
              <th>Config Hash</th>
            </tr>
          </thead>
          <tbody>
            {configs.slice(0, 10).map((cfg, i) => (
              <tr key={i}>
                <td>{i + 1}</td>
                <td>{cfg.throughput?.toFixed(0)} Mbps</td>
                <td>{(cfg.predicted_risk * 100).toFixed(1)}%</td>
                <td className="config-hash">{cfg.config_hash?.slice(0, 8)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <style jsx>{`
        .configs-table {
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
        .config-hash {
          font-family: monospace;
          font-size: 12px;
          color: #7f8c8d;
        }
      `}</style>
    </div>
  )
}
