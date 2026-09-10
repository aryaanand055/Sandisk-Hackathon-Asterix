import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function ExecutiveSummary({ data }) {
  if (!data?.analysis?.summary) return <div>Loading analysis...</div>

  const summary = data.analysis.summary
  const risk = data.analysis.risk_model
  const chartData = [
    { name: 'Pass', value: summary.n_pass, fill: '#10b981' },
    { name: 'Fail', value: summary.n_fail, fill: '#ef4444' }
  ]

  const errorData = Object.entries(summary.error_tag_distribution).map(([tag, count]) => ({
    name: tag,
    count: count
  }))

  return (
    <div className="summary-grid">
      <div className="kpi-strip">
        <div className="kpi-card">
          <div className="kpi-value">{summary.n_runs.toLocaleString()}</div>
          <div className="kpi-label">Total Runs Analyzed</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{(summary.fail_rate * 100).toFixed(1)}%</div>
          <div className="kpi-label">Overall Failure Rate</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{(risk.metrics.roc_auc * 100).toFixed(1)}%</div>
          <div className="kpi-label">Model ROC-AUC</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{(risk.metrics.accuracy * 100).toFixed(1)}%</div>
          <div className="kpi-label">Prediction Accuracy</div>
        </div>
      </div>

      <div className="chart-grid">
        <div className="chart-box">
          <h3>Simulation Outcome Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, value, fill }) => `${name}: ${value.toLocaleString()} (${((value / summary.n_runs) * 100).toFixed(1)}%)`}
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-box">
          <h3>Error Type Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={errorData} layout="horizontal">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis dataKey="name" type="category" width={120} />
              <Tooltip formatter={(value) => value.toLocaleString()} />
              <Bar dataKey="count" fill="#3b82f6" radius={[0, 8, 8, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="metrics-grid">
        <div className="metrics-box">
          <h3>Model Performance</h3>
          <table>
            <tbody>
              <tr><td>Accuracy</td><td className="value">{(risk.metrics.accuracy * 100).toFixed(1)}%</td></tr>
              <tr><td>Precision</td><td className="value">{(risk.metrics.precision * 100).toFixed(1)}%</td></tr>
              <tr><td>Recall</td><td className="value">{(risk.metrics.recall * 100).toFixed(1)}%</td></tr>
              <tr><td>F1-Score</td><td className="value">{(risk.metrics.f1 * 100).toFixed(1)}%</td></tr>
              <tr><td>ROC-AUC</td><td className="value">{(risk.metrics.roc_auc * 100).toFixed(1)}%</td></tr>
            </tbody>
          </table>
        </div>

        <div className="metrics-box">
          <h3>Execution Metrics</h3>
          <table>
            <tbody>
              <tr><td>Mean Time</td><td className="value">{summary.metric_stats.execution_time_ms.mean.toFixed(1)} ms</td></tr>
              <tr><td>Median Time</td><td className="value">{summary.metric_stats.execution_time_ms.median.toFixed(1)} ms</td></tr>
              <tr><td>P95 Time</td><td className="value">{summary.metric_stats.execution_time_ms.p95.toFixed(1)} ms</td></tr>
              <tr><td>Max Time</td><td className="value">{summary.metric_stats.execution_time_ms.max.toFixed(0)} ms</td></tr>
            </tbody>
          </table>
        </div>

        <div className="metrics-box">
          <h3>Throughput Metrics</h3>
          <table>
            <tbody>
              <tr><td>Mean</td><td className="value">{summary.metric_stats.throughput_mbps.mean.toFixed(1)} Mbps</td></tr>
              <tr><td>Median</td><td className="value">{summary.metric_stats.throughput_mbps.median.toFixed(1)} Mbps</td></tr>
              <tr><td>P95</td><td className="value">{summary.metric_stats.throughput_mbps.p95.toFixed(1)} Mbps</td></tr>
              <tr><td>Max</td><td className="value">{summary.metric_stats.throughput_mbps.max.toFixed(1)} Mbps</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <style jsx>{`
        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 20px;
          margin-top: 30px;
        }
        .metrics-box {
          background: white;
          padding: 20px;
          border-radius: 6px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .metrics-box h3 {
          margin: 0 0 15px 0;
          font-size: 16px;
          color: #1f2937;
        }
        table {
          width: 100%;
          font-size: 14px;
        }
        tr {
          border-bottom: 1px solid #e5e7eb;
        }
        td {
          padding: 8px 0;
          color: #6b7280;
        }
        .value {
          text-align: right;
          font-weight: 600;
          color: #1f2937;
        }
      `}</style>
    </div>
  )
}
