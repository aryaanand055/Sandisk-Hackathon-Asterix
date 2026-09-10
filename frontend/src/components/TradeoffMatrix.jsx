import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts'

export default function TradeoffMatrix({ data }) {
  if (!data?.analysis?.pareto) return <div>Loading Pareto analysis...</div>

  const pareto = data.analysis.pareto
  const frontierData = (pareto.frontier || []).map((p, i) => ({
    throughput: p.throughput,
    risk: p.predicted_risk,
    configs: p.n_configs,
    label: ['Best Safe', 'Knee Point', 'Peak Throughput'][i] || `Config ${i}`
  }))

  const operatingPoints = [
    { name: 'Best Safe Config', ...pareto.best_safe, color: '#10b981' },
    { name: 'Knee Point', ...pareto.knee, color: '#f59e0b' },
    { name: 'Peak Throughput', ...pareto.peak, color: '#ef4444' }
  ]

  return (
    <div className="tradeoff-container">
      <div className="summary-info">
        <p>Pareto frontier analysis based on {pareto.n_points} unique configurations</p>
      </div>

      <div className="chart-box">
        <h3>Performance vs Risk Tradeoff</h3>
        <ResponsiveContainer width="100%" height={400}>
          <ScatterChart margin={{ top: 20, right: 20, bottom: 60, left: 60 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="throughput"
              name="Throughput (Mbps)"
              label={{ value: 'Throughput (Mbps)', position: 'bottom', offset: 10 }}
            />
            <YAxis
              dataKey="risk"
              name="Predicted Failure Risk"
              label={{ value: 'Risk', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip
              cursor={{ strokeDasharray: '3 3' }}
              contentStyle={{ background: '#fff', border: '1px solid #ccc', borderRadius: '4px' }}
              formatter={(value) => typeof value === 'number' ? value.toFixed(3) : value}
            />
            <Legend />
            <Scatter
              name="Pareto Frontier"
              data={frontierData}
              fill="#3b82f6"
              shape="circle"
              isAnimationActive={true}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="operating-points">
        <h3>Operating Point Recommendations</h3>
        <div className="point-cards">
          {operatingPoints.map((p, i) => (
            <div key={i} className="point-card" style={{ borderLeftColor: p.color }}>
              <div className="point-header">
                <h4>{p.name}</h4>
                <span className="point-badge" style={{ backgroundColor: p.color }}>
                  {i === 0 ? '✓ Safest' : i === 1 ? '⚖ Balanced' : '⚡ Peak'}
                </span>
              </div>
              <div className="point-details">
                <div className="point-metric">
                  <span className="metric-label">Throughput</span>
                  <span className="metric-value">{p.throughput.toFixed(1)} Mbps</span>
                </div>
                <div className="point-metric">
                  <span className="metric-label">Risk</span>
                  <span className="metric-value">{(p.predicted_risk * 100).toFixed(1)}%</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <style>{`
        .tradeoff-container .summary-info {
        .tradeoff-container .summary-info {
          background: #f0f9ff;
          border-left: 4px solid #0284c7;
          padding: 12px 16px;
          border-radius: 4px;
          margin-bottom: 20px;
          color: #0c4a6e;
          font-size: 14px;
        }
        .tradeoff-container .operating-points {
          margin-top: 30px;
        }
        .tradeoff-container .point-cards {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 20px;
          margin-top: 20px;
        }
        .tradeoff-container .point-card {
          background: white;
          border-left: 4px solid;
          border-radius: 6px;
          padding: 20px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
          transition: box-shadow 0.2s;
        }
        .tradeoff-container .point-card:hover {
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        .tradeoff-container .point-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 15px;
        }
        .tradeoff-container .point-header h4 {
          margin: 0;
          color: #1f2937;
          font-size: 16px;
        }
        .tradeoff-container .point-badge {
          color: white;
          padding: 4px 10px;
          border-radius: 20px;
          font-size: 11px;
          font-weight: 600;
        }
        .tradeoff-container .point-details {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .tradeoff-container .point-metric {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .tradeoff-container .metric-label {
          color: #6b7280;
          font-size: 13px;
        }
        .tradeoff-container .metric-value {
          color: #1f2937;
          font-weight: 600;
          font-size: 14px;
        }
      `}</style>
    </div>
  )
}
