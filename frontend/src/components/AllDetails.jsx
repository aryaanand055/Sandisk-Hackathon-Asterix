export default function AllDetails({ data }) {
  if (!data?.details) return <div>No details data</div>

  const details = data.details

  return (
    <div className="details-container">
      <div className="detail-section">
        <h3>Parse Statistics</h3>
        <dl>
          <dt>Total lines parsed</dt>
          <dd>{details.parse_stats?.total_lines}</dd>
          <dt>Malformed blocks</dt>
          <dd>{details.parse_stats?.malformed_blocks}</dd>
          <dt>Parse time</dt>
          <dd>{details.parse_stats?.parse_time_sec?.toFixed(2)}s</dd>
        </dl>
      </div>

      <div className="detail-section">
        <h3>Timing Breakdown</h3>
        <table className="timing-table">
          <thead>
            <tr>
              <th>Stage</th>
              <th>Duration (s)</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(details.stage_timing || {}).map(([stage, duration]) => (
              <tr key={stage}>
                <td>{stage}</td>
                <td>{duration?.toFixed(2)}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="detail-section">
        <h3>Field Analysis</h3>
        <table className="field-table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Fail Rate</th>
              <th>Lift</th>
              <th>Top Value</th>
            </tr>
          </thead>
          <tbody>
            {(details.field_analysis || []).slice(0, 20).map((f, i) => (
              <tr key={i}>
                <td>{f.field}</td>
                <td>{(f.fail_rate * 100).toFixed(1)}%</td>
                <td>{f.lift?.toFixed(2)}x</td>
                <td>{f.top_value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <style jsx>{`
        .details-container {
          display: flex;
          flex-direction: column;
          gap: 30px;
        }
        .detail-section {
          border: 1px solid #ecf0f1;
          padding: 20px;
          border-radius: 6px;
        }
        .detail-section h3 {
          margin: 0 0 15px 0;
        }
        dl {
          display: grid;
          grid-template-columns: 200px 1fr;
          gap: 10px;
        }
        dt {
          font-weight: 600;
          color: #2c3e50;
        }
        dd {
          margin: 0;
          color: #7f8c8d;
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
