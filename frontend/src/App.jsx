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
import AICopilot from './components/AICopilot'
import LogGenerator from './components/LogGenerator'
import './App.css'

function isGenerateRoute() {
  const path = window.location.pathname.toLowerCase()
  const hash = window.location.hash.toLowerCase()
  return (
    path.startsWith('/generate') ||
    path.startsWith('/generator') ||
    hash.startsWith('#/generate') ||
    hash.startsWith('#generate') ||
    hash.startsWith('#/generator')
  )
}

export default function App() {
  const [jobId, setJobId] = useState(null)
  const [progress, setProgress] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('summary')
  const [error, setError] = useState(null)
  const [isGenerate, setIsGenerate] = useState(isGenerateRoute)

  const handleReset = () => {
    setJobId(null)
    setProgress(null)
    setResult(null)
    setLoading(false)
    setError(null)
    setActiveTab('summary')
    if (window.location.search.includes('job_id')) {
      window.history.pushState({}, '', window.location.pathname)
    }
  }

  useEffect(() => {
    const handleLocationChange = () => {
      const isGen = isGenerateRoute()
      setIsGenerate(isGen)
      if (!isGen) {
        const params = new URLSearchParams(window.location.search)
        const urlJobId = params.get('job_id')
        if (urlJobId) {
          setJobId(urlJobId)
        }
      }
    }

    if (!isGenerateRoute()) {
      const params = new URLSearchParams(window.location.search)
      const urlJobId = params.get('job_id')
      if (urlJobId) {
        setJobId(urlJobId)
      }
    }

    window.addEventListener('popstate', handleLocationChange)
    window.addEventListener('hashchange', handleLocationChange)
    return () => {
      window.removeEventListener('popstate', handleLocationChange)
      window.removeEventListener('hashchange', handleLocationChange)
    }
  }, [])

  useEffect(() => {
    if (!jobId) return

    let cancelled = false
    let interval = null

    const stop = () => {
      if (interval) clearInterval(interval)
      interval = null
    }

    const pollStatus = async () => {
      try {
        const res = await axios.get(`/api/jobs/${jobId}`)
        if (cancelled) return
        setProgress(res.data)

        if (res.data.status === 'completed') {
          stop()
          const resultRes = await axios.get(`/api/jobs/${jobId}/result`)
          if (cancelled) return
          setResult(resultRes.data)
          setLoading(false)
        } else if (res.data.status === 'failed') {
          stop()
          setError('Analysis failed: ' + res.data.error)
          setLoading(false)
        }
      } catch (err) {
        if (cancelled) return
        stop()
        setError('Error fetching status: ' + err.message)
        setLoading(false)
      }
    }

    interval = setInterval(pollStatus, 1000)
    return () => {
      cancelled = true
      stop()
    }
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
      setError('Upload failed: ' + (err.response?.data?.detail || err.message))
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
      setError('Sample analysis failed: ' + (err.response?.data?.detail || err.message))
      setLoading(false)
    }
  }

  const handleGenerated = async (corpusId) => {
    handleReset()
    setLoading(true)
    setError(null)
    try {
      const res = await axios.post(`/api/generate/${corpusId}/analyze`)
      const newJobId = res.data.job_id
      setJobId(newJobId)
      window.history.pushState({}, '', `/?job_id=${newJobId}`)
      setIsGenerate(false)
    } catch (err) {
      setError('Analysis failed: ' + (err.response?.data?.detail || err.message))
      setLoading(false)
    }
  }

  // Separate page for Log Generator (accessible only via separate URL, e.g. /generate)
  if (isGenerate) {
    return (
      <div className="app">
        <header className="app-header">
          <div className="brand-group">
            <img src="/sandisk-logo-clean.png" alt="SanDisk" className="brand-logo-sandisk" />
            <div className="brand-divider" />
            <img src="/asterix-logo-clean.png" alt="Team Asterix" className="brand-logo-asterix" />
            <span className="app-title">Synthetic Log Generator</span>
          </div>
          <button
            className="btn btn-secondary"
            onClick={() => {
              window.history.pushState({}, '', '/')
              setIsGenerate(false)
            }}
            style={{ fontSize: '0.85rem' }}
          >
            ← Back to Dashboard
          </button>
        </header>

        {error && <div className="error-box">{error}</div>}

        <LogGenerator onAnalyze={handleGenerated} />
      </div>
    )
  }

  // Main Page: Analysis Dashboard (not directly linked to generator)
  return (
    <div className="app">
      <header className="app-header">
        <div className="brand-group">
          <img src="/sandisk-logo-clean.png" alt="SanDisk" className="brand-logo-sandisk" />
          <div className="brand-divider" />
          <img src="/asterix-logo-clean.png" alt="Team Asterix" className="brand-logo-asterix" />
          <span className="app-title">Configuration Intelligence Dashboard</span>
        </div>
      </header>

      {error && <div className="error-box">{error}</div>}

      {!jobId ? (
        <UploadZone onUpload={handleUpload} onSample={handleSample} />
      ) : (
        <>
          {loading && (
            <div className="progress-box">
              <h3>Analysing…</h3>
              {progress && (
                <>
                  <p style={{ color: '#374151' }}>
                    {progress.message || progress.status} — {progress.progress}%
                  </p>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${progress.progress}%` }} />
                  </div>
                </>
              )}
            </div>
          )}

          {result && (
            <div className="tabs-container">
              <div className="tab-buttons">
                {[
                  { id: 'summary', label: 'Executive Summary' },
                  { id: 'copilot', label: 'AI Copilot' },
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
                {activeTab === 'copilot' && <AICopilot jobId={jobId} result={result} />}
                {activeTab === 'fingerprints' && <FailureFingerprints data={result} />}
                {activeTab === 'tradeoff' && <TradeoffMatrix data={result} />}
                {activeTab === 'recommendations' && <Recommendations data={result} />}
                {activeTab === 'diff' && <ConfigDiff data={result} jobId={jobId} />}
                {activeTab === 'explorer' && <RunExplorer jobId={jobId} />}
                {activeTab === 'details' && <AllDetails data={result} />}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
