import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function ConfigDiff({ data, jobId }) {
  if (!data?.analysis?.config_diff) return <div>Loading configuration analysis...</div>

  const config_diff = data.analysis.config_diff
  const failure_by_field = data.analysis.failure_by_field || []

  const deltas = config_diff.field_deltas || []
  const chartData = failure_by_field.map(f => ({
    field: f.field,
    lift: f.lift.toFixed(2)
  }))

  return (
    <div className="diff-container">
      <div className="diff-summary">
        <h3>Configuration Impact Analysis</h3>
        <p>Twin-based divergence: comparing configurations in passing vs failing runs</p>
        <div className="summary-stat">
          <span className="stat-label">Twin Pairs Analyzed</span>
          <span className="stat-value">{config_diff.n_twins.toLocaleString()}</span>
        </div>
      </div>

      <div className="chart-box">
        <h3>Setting Lift by Failure Rate</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 150, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis dataKey="field" type="category" width={140} />
            <Tooltip />
            <Legend />
            <Bar dataKey="lift" fill="#8b5cf6" name="Lift Factor" radius={[0, 8, 8, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="deltas-table">
        <h3>Field Divergence Ranking</h3>
        <p className="table-desc">Settings ranked by difference frequency between passing/failing runs</p>
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Setting</th>
              <th>Fail vs Pass Rate</th>
              <th>Impact</th>
            </tr>
          </thead>
          <tbody>
            {deltas.map((d, i) => (
              <tr key={i} className={i === 0 ? 'critical' : i === 1 ? 'high' : 'medium'}>
                <td className="rank">{i + 1}</td>
                <td className="field-name">{d.field}</td>
                <td>
                  <span className="rate-badge">{(d.fail_vs_pass_rate * 100).toFixed(1)}%</span>
                </td>
                <td>
                  <span className={`impact-badge impact-${i === 0 ? 'critical' : i === 1 ? 'high' : 'medium'}`}>
                    {i === 0 ? '🔴 Critical' : i === 1 ? '🟠 High' : '🟡 Medium'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <style>{`
        .diff-container .diff-summary {
        .diff-summary {
          background: white;
          padding: 20px;
          border-radius: 6px;
          margin-bottom: 20px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .diff-summary h3 {
          margin: 0 0 10px 0;
        }
        .diff-summary p {
          margin: 0 0 15px 0;
          color: #6b7280;
          font-size: 14px;
        }
        .summary-stat {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px;
          background: #f3f4f6;
          border-radius: 4px;
        }
        .stat-label {
          color: #6b7280;
          font-size: 13px;
          font-weight: 600;
        }
        .stat-value {
          color: #1f2937;
          font-size: 18px;
          font-weight: 700;
        }
        .deltas-table {
          background: white;
          padding: 20px;
          border-radius: 6px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
          margin-top: 20px;
        }
        .deltas-table h3 {
          margin: 0 0 5px 0;
        }
        .table-desc {
          margin: 0 0 15px 0;
          color: #6b7280;
          font-size: 13px;
        }
        table {
          width: 100%;
          border-collapse: collapse;
        }
        th {
          background: #f3f4f6;
          padding: 12px;
          text-align: left;
          font-weight: 600;
          color: #374151;
          font-size: 13px;
          border-bottom: 2px solid #e5e7eb;
        }
        td {
          padding: 12px;
          border-bottom: 1px solid #e5e7eb;
          color: #6b7280;
        }
        tr.critical:hover {
          background: #fef2f2;
        }
        tr.high:hover {
          background: #fffbf0;
        }
        tr.medium:hover {
          background: #fffde7;
        }
        .rank {
          font-weight: 600;
          color: #1f2937;
          width: 40px;
        }
        .field-name {
          font-weight: 500;
          color: #1f2937;
        }
        .rate-badge {
          background: #dbeafe;
          color: #1e40af;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 600;
        }
        .impact-badge {
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 600;
        }
        .impact-critical {
          background: #fee2e2;
          color: #991b1b;
        }
        .impact-high {
          background: #fed7aa;
          color: #92400e;
        }
        .impact-medium {
          background: #fef3c7;
          color: #78350f;
        }
      `}</style>
    </div>
  )
}
