import { useState } from 'react'
import './UploadZone.css'

export default function UploadZone({ onUpload, onSample }) {
  const [dragActive, setDragActive] = useState(false)

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(e.type !== 'dragleave')
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    const files = Array.from(e.dataTransfer.files).filter(f => f.name.endsWith('.log'))
    if (files.length > 0) onUpload(files)
  }

  const handleChange = (e) => {
    const files = Array.from(e.target.files)
    if (files.length > 0) onUpload(files)
  }

  return (
    <div className="upload-container">
      <div className="upload-card">
        <h2>Upload UVM Simulation Logs</h2>

        <div
          className={`dropzone ${dragActive ? 'active' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <div className="dropzone-content">
            <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p className="dropzone-text">Drag .log files here or click to select</p>
            <p className="dropzone-hint">Max 512 MB per upload</p>
          </div>
          <input
            type="file"
            multiple
            accept=".log"
            onChange={handleChange}
            className="file-input"
          />
        </div>

        <div className="button-group">
          <button className="btn btn-secondary" onClick={onSample}>
            Use Bundled Sample
          </button>
        </div>
      </div>
    </div>
  )
}
