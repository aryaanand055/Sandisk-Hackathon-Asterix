import { useState } from 'react'
import './UploadZone.css'

export default function UploadZone({ onUpload, onSample }) {
  const [dragActive, setDragActive] = useState(false)
  const [localNotice, setLocalNotice] = useState(null)

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(e.type !== 'dragleave')
  }

  // Traverse files and directories dropped by user
  const extractFiles = async (dataTransfer) => {
    const validExts = ['.log', '.csv', '.vcd', '.fsdb', '.wlf']
    const collected = []

    if (dataTransfer.items && dataTransfer.items.length > 0) {
      const queue = []
      for (let i = 0; i < dataTransfer.items.length; i++) {
        const item = dataTransfer.items[i]
        if (item.kind === 'file') {
          const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null
          if (entry) {
            queue.push(entry)
          } else {
            const f = item.getAsFile()
            if (f) collected.push(f)
          }
        }
      }

      while (queue.length > 0) {
        const entry = queue.shift()
        if (entry.isFile) {
          try {
            const f = await new Promise((resolve, reject) => entry.file(resolve, reject))
            collected.push(f)
          } catch (err) {
            console.warn('Error reading file entry:', err)
          }
        } else if (entry.isDirectory) {
          try {
            const reader = entry.createReader()
            const entries = await new Promise((resolve, reject) => reader.readEntries(resolve, reject))
            queue.push(...entries)
          } catch (err) {
            console.warn('Error reading directory entry:', err)
          }
        }
      }
    } else if (dataTransfer.files) {
      collected.push(...Array.from(dataTransfer.files))
    }

    return collected.filter(f => validExts.some(ext => f.name.toLowerCase().endsWith(ext)))
  }

  const validateAndUpload = (files) => {
    setLocalNotice(null)
    if (!files || files.length === 0) {
      setLocalNotice('No valid .log, .csv, or waveform files found in upload.')
      return
    }

    // Check if only waveform files were selected
    const waveExts = ['.vcd', '.fsdb', '.wlf']
    const isWaveformOnly = files.every(f =>
      waveExts.some(ext => f.name.toLowerCase().endsWith(ext))
    )

    if (isWaveformOnly) {
      setLocalNotice(
        'Notice: You uploaded only waveform companion files (.fsdb, .vcd, .wlf). Please upload them alongside a .log or .csv file containing run execution results.'
      )
      return
    }

    onUpload(files)
  }

  const handleDrop = async (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    const files = await extractFiles(e.dataTransfer)
    validateAndUpload(files)
  }

  const handleChange = (e) => {
    const files = Array.from(e.target.files)
    validateAndUpload(files)
  }

  return (
    <div className="upload-container">
      <div className="upload-card">
        <h2>Upload Verification Files</h2>

        {localNotice && (
          <div style={{
            background: '#fff3cd',
            color: '#856404',
            border: '1px solid #ffeeba',
            borderRadius: '6px',
            padding: '10px 14px',
            marginBottom: '14px',
            fontSize: '13px',
            lineHeight: '1.4'
          }}>
            {localNotice}
          </div>
        )}

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
            <p className="dropzone-text">Drag files or entire folders here (.log, .csv) or click to browse</p>
            <p className="dropzone-hint">Supports single-file logs, multi-file CSV folders</p>
          </div>
          <input
            type="file"
            multiple
            accept=".log,.csv"
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
