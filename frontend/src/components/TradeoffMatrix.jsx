import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function TradeoffMatrix({ data }) {
  if (!data?.pareto) return <div>No tradeoff data</div>

  const pareto = data.pareto
  const frontierData = (pareto.frontier || []).map(p => ({
    throughput: p.throughput,
    risk: p.predicted_risk,
    label: p.label
  }))

  const operatingPoints = [
    { name: 'Peak Throughput', ...pareto.peak_throughput },
    { name: 'Knee Point', ...pareto.knee_point },
    { name: 'Best Safe', ...pareto.best_safe_config }
  ]

  return (
    <div className="tradeoff-container">
      <div className="chart-box">
        <h3>Throughput vs Risk Frontier</h3>
        <ResponsiveContainer width="100%" height={400}>
          <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="throughput" name="Throughput (Mbps)" />
            <YAxis dataKey="risk" name="Predicted Risk" />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
            <Legend />
            <Scatter name="Pareto Frontier" data={frontierData} fill="#2ecc71" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="operating-points">
        <h3>Operating Points</h3>
        <div className="point-cards">
          {operatingPoints.map((p, i) => (
            <div key={i} className="point-card">
              <h4>{p.name}</h4>
              <p>Throughput: {p.throughput?.toFixed(0)} Mbps</p>
              <p>Risk: {(p.predicted_risk * 100).toFixed(1)}%</p>
            </div>
          ))}
        </div>
      </div>

      <style jsx>{`
        .operating-points {
          margin-top: 30px;
        }
        .point-cards {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 20px;
          margin-top: 15px;
        }
        .point-card {
          background: #f8f9fa;
          border-left: 4px solid #3498db;
          padding: 15px;
          border-radius: 4px;
        }
        .point-card h4 {
          margin: 0 0 10px 0;
          color: #2c3e50;
        }
        .point-card p {
          margin: 5px 0;
          color: #7f8c8d;
        }
      `}</style>
    </div>
  )
}
