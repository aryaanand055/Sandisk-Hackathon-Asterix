import { useState, useEffect } from 'react'
import axios from 'axios'
import UploadZone from './components/UploadZone'
import ExecutiveSummary from './components/ExecutiveSummary'
import FailureFingerprints from './components/FailureFingerprints'
import TradeoffMatrix from './components/TradeoffMatrix'
import Recommendations from './components/Recommendations'
import ConfigDiff from './components/ConfigDiff'
import RunExplorer from './components/RunExplorer'
import AllDetails from './components/AllDetails'
import './App.css'

export default function App() {
  const [jobId, setJobId] = useState(null)
  const [progress, setProgress] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('summary')
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!jobId) return

    const pollStatus = async () => {
      try {
        const res = await axios.get(`/api/jobs/${jobId}`)
        setProgress(res.data)

        if (res.data.status === 'completed') {
          const resultRes = await axios.get(`/api/jobs/${jobId}/result`)
          setResult(resultRes.data)
          setLoading(false)
        } else if (res.data.status === 'failed') {
          setError('Analysis failed: ' + res.data.error)
          setLoading(false)
        }
      } catch (err) {
        setError('Error fetching status: ' + err.message)
      }
    }

    const interval = setInterval(pollStatus, 1000)
    return () => clearInterval(interval)
  }, [jobId])

  const handleUpload = async (files) => {
    setLoading(true)
    setError(null)
    const formData = new FormData()
    files.forEach(f => formData.append('files', f))

    try {
      const res = await axios.post('/api/analyze', formData)
      setJobId(res.data.job_id)
    } catch (err) {
      setError('Upload failed: ' + err.message)
      setLoading(false)
    }
  }

  const handleSample = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await axios.post('/api/analyze-sample')
      setJobId(res.data.job_id)
    } catch (err) {
      setError('Sample analysis failed: ' + err.message)
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>UVM Configuration Intelligence Dashboard</h1>
        <p>Upload UVM simulation logs, get parsed and clustered analysis</p>
      </header>

      {!jobId ? (
        <UploadZone onUpload={handleUpload} onSample={handleSample} />
      ) : (
        <>
          {loading && (
            <div className="progress-box">
              <h3>Analysis in progress...</h3>
              {progress && (
                <>
                  <p>Status: {progress.status}</p>
                  <p>Progress: {progress.progress}%</p>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${progress.progress}%` }} />
                  </div>
                </>
              )}
            </div>
          )}

          {error && <div className="error-box">{error}</div>}

          {result && (
            <div className="tabs-container">
              <div className="tab-buttons">
                {[
                  { id: 'summary', label: 'Executive Summary' },
                  { id: 'fingerprints', label: 'Failure Fingerprints' },
                  { id: 'tradeoff', label: 'Tradeoff Matrix' },
                  { id: 'recommendations', label: 'Recommendations' },
                  { id: 'diff', label: 'Config Diff' },
                  { id: 'explorer', label: 'Run Explorer' },
                  { id: 'details', label: 'All Details' }
                ].map(tab => (
                  <button
                    key={tab.id}
                    className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <div className="tab-content">
                {activeTab === 'summary' && <ExecutiveSummary data={result} />}
                {activeTab === 'fingerprints' && <FailureFingerprints data={result} />}
                {activeTab === 'tradeoff' && <TradeoffMatrix data={result} />}
                {activeTab === 'recommendations' && <Recommendations data={result} />}
                {activeTab === 'diff' && <ConfigDiff data={result} jobId={jobId} />}
                {activeTab === 'explorer' && <RunExplorer data={result} jobId={jobId} />}
                {activeTab === 'details' && <AllDetails data={result} />}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
