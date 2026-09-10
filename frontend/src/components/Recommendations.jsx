export default function Recommendations({ data }) {
  if (!data?.analysis?.recommendations) return <div>Loading recommendations...</div>

  const rec = data.analysis.recommendations
  const configs = rec.best_configs || []

  return (
    <div className="recommendations-container">
      <div className="rec-summary">
        <h3>Constrained Optimization Results</h3>
        <div className="summary-stats">
          <div className="stat">
            <span className="stat-label">Trials Executed</span>
            <span className="stat-value">{rec.n_trials}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Risk Ceiling</span>
            <span className="stat-value">{(rec.max_risk * 100).toFixed(1)}%</span>
          </div>
          <div className="stat">
            <span className="stat-label">Search Space</span>
            <span className="stat-value">{Object.keys(rec.search_space || {}).length} params</span>
          </div>
        </div>
      </div>

      <div className="search-space">
        <h3>Search Space Definition</h3>
        <div className="space-grid">
          {Object.entries(rec.search_space || {}).map(([param, values]) => (
            <div key={param} className="space-item">
              <span className="space-param">{param}</span>
              <span className="space-values">
                {Array.isArray(values) ? values.join(', ') : `[${values}]`}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="configs-table">
        <h3>Optimal Configurations</h3>
        <p className="table-desc">Top configurations satisfying the risk constraint</p>
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Throughput</th>
              <th>Predicted Risk</th>
              <th>test_mode</th>
              <th>cache_policy</th>
              <th>queue_depth</th>
            </tr>
          </thead>
          <tbody>
            {configs.slice(0, 10).map((cfg, i) => (
              <tr key={i} className={cfg.predicted_risk <= rec.max_risk ? 'compliant' : 'violated'}>
                <td className="rank">{i + 1}</td>
                <td className="throughput">{cfg.throughput.toFixed(1)} Mbps</td>
                <td>
                  <span className={`risk-badge ${cfg.predicted_risk <= rec.max_risk ? 'safe' : 'unsafe'}`}>
                    {(cfg.predicted_risk * 100).toFixed(2)}%
                  </span>
                </td>
                <td>{cfg.test_mode_enabled}</td>
                <td>{cfg.cache_policy}</td>
                <td>{cfg.queue_depth}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <style>{`
        .recommendations-container .rec-summary {
        .recommendations-container .rec-summary {
          background: white;
          padding: 20px;
          border-radius: 6px;
          margin-bottom: 20px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .recommendations-container .rec-summary h3 {
          margin: 0 0 15px 0;
          font-size: 18px;
        }
        .recommendations-container .summary-stats {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 15px;
        }
        .recommendations-container .stat {
          display: flex;
          flex-direction: column;
          padding: 15px;
          background: #f3f4f6;
          border-radius: 4px;
        }
        .recommendations-container .stat-label {
          color: #6b7280;
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
          margin-bottom: 5px;
        }
        .recommendations-container .stat-value {
          color: #1f2937;
          font-size: 20px;
          font-weight: 700;
        }
        .recommendations-container .search-space {
          background: white;
          padding: 20px;
          border-radius: 6px;
          margin-bottom: 20px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .recommendations-container .search-space h3 {
          margin: 0 0 15px 0;
        }
        .recommendations-container .space-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 15px;
        }
        .recommendations-container .space-item {
          display: flex;
          flex-direction: column;
          padding: 12px;
          background: #f9fafb;
          border-radius: 4px;
          border-left: 3px solid #3b82f6;
        }
        .recommendations-container .space-param {
          font-weight: 600;
          color: #1f2937;
          font-size: 13px;
        }
        .recommendations-container .space-values {
          color: #6b7280;
          font-size: 12px;
          margin-top: 4px;
          font-family: monospace;
        }
        .recommendations-container .configs-table {
          background: white;
          padding: 20px;
          border-radius: 6px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .recommendations-container .configs-table h3 {
          margin: 0 0 5px 0;
        }
        .recommendations-container .table-desc {
          margin: 0 0 15px 0;
          color: #6b7280;
          font-size: 14px;
        }
        .recommendations-container table {
          width: 100%;
          border-collapse: collapse;
        }
        .recommendations-container th {
          background: #f3f4f6;
          padding: 12px;
          text-align: left;
          font-weight: 600;
          color: #374151;
          font-size: 13px;
          border-bottom: 2px solid #e5e7eb;
        }
        .recommendations-container td {
          padding: 12px;
          border-bottom: 1px solid #e5e7eb;
          color: #6b7280;
          font-size: 13px;
        }
        .recommendations-container tr:hover {
          background: #f9fafb;
        }
        .recommendations-container .rank {
          font-weight: 600;
          color: #1f2937;
        }
        .recommendations-container .throughput {
          font-weight: 600;
          color: #1f2937;
        }
        .recommendations-container .risk-badge {
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 600;
        }
        .recommendations-container .risk-badge.safe {
          background: #d1fae5;
          color: #065f46;
        }
        .recommendations-container .risk-badge.unsafe {
          background: #fee2e2;
          color: #991b1b;
        }
      `}</style>
    </div>
  )
}
