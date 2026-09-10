import { useState } from 'react'

export default function RunExplorer({ data, jobId }) {
  const [page, setPage] = useState(0)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  if (!data?.runs) return <div>No run data</div>

  const pageSize = 50
  const runs = data.runs || []
  const filtered = runs.filter(r => {
    const matchesSearch = r.run_id?.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = statusFilter === 'all' || r.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const totalPages = Math.ceil(filtered.length / pageSize)
  const displayRuns = filtered.slice(page * pageSize, (page + 1) * pageSize)

  return (
    <div className="explorer-container">
      <div className="explorer-controls">
        <h3>Run Explorer</h3>
        <div className="control-row">
          <input
            type="text"
            placeholder="Search run ID..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value)
              setPage(0)
            }}
            className="search-input"
          />
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="filter-select">
            <option value="all">All</option>
            <option value="pass">Pass</option>
            <option value="fail">Fail</option>
          </select>
        </div>
      </div>

      <div className="runs-table">
        <table>
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Test Name</th>
              <th>Status</th>
              <th>Execution Time</th>
              <th>Throughput</th>
            </tr>
          </thead>
          <tbody>
            {displayRuns.map((r, i) => (
              <tr key={i} className={r.status === 'fail' ? 'fail-row' : ''}>
                <td className="run-id">{r.run_id}</td>
                <td>{r.test_name}</td>
                <td>
                  <span className={`badge badge-${r.status}`}>
                    {r.status?.toUpperCase()}
                  </span>
                </td>
                <td>{r.execution_time_ms?.toFixed(1)} ms</td>
                <td>{r.throughput_mbps?.toFixed(1)} Mbps</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="pagination">
        <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}>
          Previous
        </button>
        <span>Page {page + 1} of {Math.max(1, totalPages)}</span>
        <button onClick={() => setPage(Math.min(totalPages - 1, page + 1))} disabled={page >= totalPages - 1}>
          Next
        </button>
      </div>

      <style jsx>{`
        .explorer-controls {
          margin-bottom: 20px;
        }
        .control-row {
          display: flex;
          gap: 10px;
          margin-top: 15px;
        }
        .search-input, .filter-select {
          padding: 8px 12px;
          border: 1px solid #bdc3c7;
          border-radius: 4px;
          font-size: 14px;
        }
        .search-input {
          flex: 1;
        }
        .runs-table {
          margin: 20px 0;
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
        .fail-row {
          background: #fadbd8;
        }
        .run-id {
          font-family: monospace;
          font-size: 12px;
        }
        .badge {
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 600;
        }
        .badge-pass {
          background: #d5f4e6;
          color: #0e6251;
        }
        .badge-fail {
          background: #fadbd8;
          color: #c0392b;
        }
        .pagination {
          display: flex;
          justify-content: center;
          gap: 20px;
          align-items: center;
          margin-top: 20px;
        }
        .pagination button {
          padding: 8px 16px;
          border: 1px solid #bdc3c7;
          background: white;
          border-radius: 4px;
          cursor: pointer;
        }
        .pagination button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  )
}
