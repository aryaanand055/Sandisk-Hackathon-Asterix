import { PieChart, Pie, Cell, LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function ExecutiveSummary({ data }) {
  if (!data?.executive_summary) return <div>No data</div>

  const summary = data.executive_summary
  const chartData = [
    { name: 'Pass', value: summary.total_runs * (1 - summary.overall_fail_rate) },
    { name: 'Fail', value: summary.total_runs * summary.overall_fail_rate }
  ]

  return (
    <div className="summary-grid">
      <div className="kpi-strip">
        <div className="kpi-card">
          <div className="kpi-value">{summary.total_runs}</div>
          <div className="kpi-label">Total Runs</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{(summary.overall_fail_rate * 100).toFixed(1)}%</div>
          <div className="kpi-label">Failure Rate</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{(summary.model_auc * 100).toFixed(1)}%</div>
          <div className="kpi-label">Model ROC-AUC</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{summary.num_rules_discovered}</div>
          <div className="kpi-label">Rules Found</div>
        </div>
      </div>

      <div className="chart-grid">
        <div className="chart-box">
          <h3>Pass/Fail Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                <Cell fill="#2ecc71" />
                <Cell fill="#e74c3c" />
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-box">
          <h3>Failure Modes</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={summary.failure_mode_distribution || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="mode" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill="#3498db" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="metrics-table">
        <h3>Performance Metrics</h3>
        <table>
          <tbody>
            {Object.entries(summary.metrics || {}).map(([key, value]) => (
              <tr key={key}>
                <td className="metric-key">{key}</td>
                <td className="metric-value">{typeof value === 'number' ? value.toFixed(3) : value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
