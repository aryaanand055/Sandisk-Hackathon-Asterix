import { useState } from 'react'

export default function ConfigDiff({ data, jobId }) {
  const [selectedRuns, setSelectedRuns] = useState(null)

  if (!data?.config_diff) return <div>No diff data</div>

  const diff = data.config_diff
  const twins = diff.twin_divergence || []

  return (
    <div className="diff-container">
      <div className="diff-summary">
        <h3>Configuration Divergence Analysis</h3>
        <p>Twin-diffing: most similar passing/failing run pairs</p>
      </div>

      <div className="twins-table">
        <h3>Highest-Impact Differences</h3>
        <table>
          <thead>
            <tr>
              <th>Setting</th>
              <th>Failing Value</th>
              <th>Passing Value</th>
              <th>Divergence %</th>
              <th>Impact</th>
            </tr>
          </thead>
          <tbody>
            {twins.slice(0, 15).map((t, i) => (
              <tr key={i}>
                <td className="setting-name">{t.setting}</td>
                <td>{t.failing_value}</td>
                <td>{t.passing_value}</td>
                <td>{(t.divergence_rate * 100).toFixed(1)}%</td>
                <td>
                  <span className={`impact ${t.impact_level || 'low'}`}>
                    {t.impact_level || 'low'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <style jsx>{`
        .twins-table {
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
        .setting-name {
          font-weight: 500;
          color: #2c3e50;
        }
        .impact {
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 600;
        }
        .impact.high {
          background: #fadbd8;
          color: #c0392b;
        }
        .impact.medium {
          background: #fdf2e9;
          color: #d68910;
        }
        .impact.low {
          background: #d5f4e6;
          color: #0e6251;
        }
      `}</style>
    </div>
  )
}
