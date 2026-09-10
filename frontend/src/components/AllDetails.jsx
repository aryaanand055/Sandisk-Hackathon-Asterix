const card = {
  background: '#fff',
  padding: '20px',
  borderRadius: '8px',
  boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
  marginBottom: '20px',
}
const th = {
  padding: '12px',
  textAlign: 'left',
  fontWeight: 600,
  fontSize: '13px',
  color: '#374151',
  borderBottom: '2px solid #e5e7eb',
}
const td = { padding: '10px 12px', fontSize: '13px', borderBottom: '1px solid #e5e7eb' }

export default function AllDetails({ data }) {
  if (!data?.analysis) return <div>Loading details...</div>

  const { analysis, meta } = data
  const parse = analysis.summary?.parse_stats || {}
  const stages = analysis.stage_log || []
  const byField = analysis.failure_by_field || []

  return (
    <div>
      <h2>All Details</h2>

      <div style={card}>
        <h3 style={{ margin: '0 0 15px 0' }}>Parse Statistics</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            <tr><td style={td}>Files parsed</td><td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>{parse.files?.toLocaleString()}</td></tr>
            <tr><td style={td}>Lines read</td><td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>{parse.lines?.toLocaleString()}</td></tr>
            <tr><td style={td}>Runs extracted</td><td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>{parse.runs?.toLocaleString()}</td></tr>
            <tr><td style={td}>Error lines</td><td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>{parse.error_lines?.toLocaleString()}</td></tr>
            <tr><td style={td}>Malformed blocks</td><td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>{parse.malformed_blocks?.toLocaleString()}</td></tr>
            <tr><td style={td}>Unparsed lines</td><td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>{parse.unparsed_lines?.toLocaleString()}</td></tr>
          </tbody>
        </table>
      </div>

      <div style={card}>
        <h3 style={{ margin: '0 0 5px 0' }}>Stage Timing</h3>
        <p style={{ margin: '0 0 15px 0', fontSize: '13px', color: '#6b7280' }}>
          Total {analysis.total_seconds?.toFixed(2)}s across {stages.length} stages
        </p>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f3f4f6' }}>
              <th style={th}>Stage</th>
              <th style={th}>Status</th>
              <th style={{ ...th, textAlign: 'right' }}>Seconds</th>
            </tr>
          </thead>
          <tbody>
            {stages.map((s) => (
              <tr key={s.stage}>
                <td style={td}>{s.stage}</td>
                <td style={td}>
                  <span
                    style={{
                      padding: '3px 8px',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 600,
                      background: s.status === 'ok' ? '#d1fae5' : '#fee2e2',
                      color: s.status === 'ok' ? '#065f46' : '#991b1b',
                    }}
                  >
                    {s.status}
                  </span>
                </td>
                <td style={{ ...td, textAlign: 'right' }}>{s.seconds?.toFixed(2)}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={card}>
        <h3 style={{ margin: '0 0 5px 0' }}>Failure Rate by Field</h3>
        <p style={{ margin: '0 0 15px 0', fontSize: '13px', color: '#6b7280' }}>
          Lift above 1.0 means that value fails more often than the corpus average
        </p>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f3f4f6' }}>
              <th style={th}>Field</th>
              <th style={th}>Value</th>
              <th style={{ ...th, textAlign: 'right' }}>Runs</th>
              <th style={{ ...th, textAlign: 'right' }}>Fail Rate</th>
              <th style={{ ...th, textAlign: 'right' }}>Lift</th>
            </tr>
          </thead>
          <tbody>
            {byField.flatMap((f) =>
              (f.levels || []).map((lv, i) => (
                <tr key={`${f.field}-${lv.level}`}>
                  <td style={{ ...td, fontWeight: i === 0 ? 600 : 400, color: i === 0 ? '#1f2937' : '#9ca3af' }}>
                    {i === 0 ? f.field : ''}
                  </td>
                  <td style={td}>{lv.level}</td>
                  <td style={{ ...td, textAlign: 'right' }}>{lv.n?.toLocaleString()}</td>
                  <td style={{ ...td, textAlign: 'right' }}>{(lv.fail_rate * 100).toFixed(2)}%</td>
                  <td style={{ ...td, textAlign: 'right' }}>
                    <span
                      style={{
                        padding: '3px 8px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontWeight: 600,
                        background: lv.lift >= 1 ? '#fee2e2' : '#d1fae5',
                        color: lv.lift >= 1 ? '#991b1b' : '#065f46',
                      }}
                    >
                      {lv.lift?.toFixed(3)}×
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div style={card}>
        <h3 style={{ margin: '0 0 15px 0' }}>Job Metadata</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            <tr><td style={td}>Job ID</td><td style={{ ...td, textAlign: 'right', fontFamily: 'monospace' }}>{meta?.job_id}</td></tr>
            <tr><td style={td}>Status</td><td style={{ ...td, textAlign: 'right' }}>{meta?.status}</td></tr>
            <tr><td style={td}>Elapsed</td><td style={{ ...td, textAlign: 'right' }}>{meta?.elapsed}s</td></tr>
            <tr><td style={td}>Runs</td><td style={{ ...td, textAlign: 'right' }}>{meta?.n_runs?.toLocaleString()}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
