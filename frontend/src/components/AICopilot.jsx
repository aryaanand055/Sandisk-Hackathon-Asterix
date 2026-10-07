import { useState, useEffect } from 'react'

function renderFormattedMarkdown(content) {
  if (!content) return null
  const lines = content.split('\n')
  const elements = []
  let tableRows = []
  let inTable = false
  let tableKey = 0

  const parseInline = (text) => {
    const boldRegex = /\*\*(.*?)\*\*/g
    const res = []
    let lastIdx = 0
    let match
    while ((match = boldRegex.exec(text)) !== null) {
      if (match.index > lastIdx) {
        res.push(text.substring(lastIdx, match.index))
      }
      res.push(<strong key={match.index} style={{ color: '#0f172a', fontWeight: 600 }}>{match[1]}</strong>)
      lastIdx = boldRegex.lastIndex
    }
    if (lastIdx < text.length) {
      res.push(text.substring(lastIdx))
    }
    return res.length > 0 ? res : text
  }

  const flushTable = () => {
    if (tableRows.length > 0) {
      const headerRow = tableRows[0]
      const bodyRows = tableRows.slice(1).filter(r => !r.every(c => c.match(/^:?-+:?$/)))
      elements.push(
        <div key={`table-${tableKey++}`} style={{ overflowX: 'auto', margin: '14px 0' }}>
          <table style={{
            width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem',
            background: '#ffffff', borderRadius: '6px', overflow: 'hidden',
            border: '1px solid #e2e8f0'
          }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0' }}>
                {headerRow.map((h, i) => (
                  <th key={i} style={{ padding: '9px 12px', textAlign: 'left', color: '#1e293b', fontWeight: 600 }}>
                    {parseInline(h.trim())}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bodyRows.map((row, rIdx) => (
                <tr key={rIdx} style={{
                  borderBottom: '1px solid #f1f5f9',
                  background: rIdx % 2 === 0 ? '#ffffff' : '#f8fafc'
                }}>
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} style={{ padding: '8px 12px', color: '#334155' }}>
                      {parseInline(cell.trim())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
      tableRows = []
    }
    inTable = false
  }

  lines.forEach((line, idx) => {
    const trimmed = line.trim()

    // Table Row detection
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      inTable = true
      const cells = trimmed.split('|').slice(1, -1)
      tableRows.push(cells)
      return
    } else if (inTable) {
      flushTable()
    }

    // Horizontal rule
    if (trimmed === '---' || trimmed === '***') {
      elements.push(<hr key={idx} style={{ border: 'none', borderTop: '1px solid #e2e8f0', margin: '14px 0' }} />)
      return
    }

    // Headers
    if (trimmed.startsWith('### ')) {
      elements.push(
        <h4 key={idx} style={{ color: '#0f172a', fontSize: '0.975rem', fontWeight: 600, marginTop: '12px', marginBottom: '6px' }}>
          {parseInline(trimmed.replace(/^###\s+/, ''))}
        </h4>
      )
      return
    }

    if (trimmed.startsWith('## ')) {
      elements.push(
        <h3 key={idx} style={{ color: '#0f172a', fontSize: '1.05rem', fontWeight: 600, marginTop: '14px', marginBottom: '8px' }}>
          {parseInline(trimmed.replace(/^##\s+/, ''))}
        </h3>
      )
      return
    }

    // Bullet lists
    if (trimmed.startsWith('* ') || trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
      const bulletText = trimmed.replace(/^(\*|-|•)\s+/, '')
      elements.push(
        <div key={idx} style={{ display: 'flex', gap: '8px', marginLeft: '6px', marginBottom: '4px', lineHeight: '1.5' }}>
          <span style={{ color: '#e10600', fontWeight: 'bold' }}>•</span>
          <div style={{ flex: 1, color: '#334155' }}>{parseInline(bulletText)}</div>
        </div>
      )
      return
    }

    // Numbered lists
    const numMatch = trimmed.match(/^(\d+)\.\s+(.*)$/)
    if (numMatch) {
      elements.push(
        <div key={idx} style={{ display: 'flex', gap: '8px', marginLeft: '6px', marginBottom: '4px', lineHeight: '1.5' }}>
          <span style={{ color: '#64748b', fontWeight: 600, minWidth: '18px' }}>{numMatch[1]}.</span>
          <div style={{ flex: 1, color: '#334155' }}>{parseInline(numMatch[2])}</div>
        </div>
      )
      return
    }

    // Empty lines
    if (!trimmed) {
      elements.push(<div key={idx} style={{ height: '6px' }} />)
      return
    }

    // Regular paragraphs
    elements.push(
      <p key={idx} style={{ margin: '4px 0', lineHeight: '1.55', color: '#334155' }}>
        {parseInline(trimmed)}
      </p>
    )
  })

  if (inTable) {
    flushTable()
  }

  return elements
}

export default function AICopilot({ jobId, result }) {
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('gemini_api_key') || '')
  const [showKeyInput, setShowKeyInput] = useState(false)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([
    {
      sender: 'assistant',
      text: 'Hello! Telemetry and model analysis context is loaded for this simulation run (failure probability, SHAP feature importance, failure fingerprints, and recommended configurations).\n\nAsk any question about root causes, failure clusters, or recommended knob settings.',
    },
  ])
  const [loading, setLoading] = useState(false)
  const [geminiConnected, setGeminiConnected] = useState(false)

  useEffect(() => {
    if (apiKey) {
      localStorage.setItem('gemini_api_key', apiKey)
    }
  }, [apiKey])

  const handleSend = async (e) => {
    if (e) e.preventDefault()
    if (!question.trim() || loading) return

    const userText = question.trim()
    setQuestion('')
    setMessages((prev) => [...prev, { sender: 'user', text: userText }])
    setLoading(true)

    try {
      const res = await fetch('http://127.0.0.1:8000/api/copilot/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: jobId,
          question: userText,
          api_key: apiKey || undefined,
        }),
      })
      if (!res.ok) throw new Error('Copilot query failed')
      const data = await res.json()
      
      if (data.gemini_used) {
        setGeminiConnected(true)
      }
      
      setMessages((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: data.answer,
          model: data.model,
          geminiUsed: data.gemini_used
        },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: `**Query error**: ${err.message}. Ensure backend is running.`,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleChipClick = (q) => {
    setQuestion(q)
  }

  const suggestedQuestions = [
    'What are the primary configuration drivers causing test failures?',
    'Explain the root causes behind the identified failure clusters.',
    'What specific knob settings minimize risk while preserving max throughput?',
    'Analyze the trade-offs on the Pareto throughput vs risk frontier.',
    'Provide an executive summary report for engineering leads.',
  ]

  return (
    <div style={{ maxWidth: '980px', margin: '0 auto', fontFamily: 'inherit' }}>
      {/* Top Controls Bar */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: '#ffffff',
        padding: '12px 18px',
        borderRadius: '8px',
        border: '1px solid #e2e8f0',
        marginBottom: '16px',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontWeight: 600, fontSize: '0.95rem', color: '#0f172a' }}>
            Verification Copilot
          </span>
          <span style={{
            background: geminiConnected || apiKey ? '#f0fdf4' : '#f8fafc',
            color: geminiConnected || apiKey ? '#16a34a' : '#64748b',
            border: `1px solid ${geminiConnected || apiKey ? '#bbf7d0' : '#e2e8f0'}`,
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '0.75rem',
            fontWeight: 600
          }}>
            {geminiConnected || apiKey ? 'Gemini Connected' : 'Local Rule Engine'}
          </span>
        </div>

        <button
          onClick={() => setShowKeyInput(!showKeyInput)}
          style={{
            background: '#ffffff',
            border: '1px solid #cbd5e1',
            color: '#334155',
            padding: '6px 12px',
            borderRadius: '6px',
            fontSize: '0.825rem',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'all 0.15s ease'
          }}
        >
          {showKeyInput ? 'Close Settings' : 'Configure API Key'}
        </button>
      </div>

      {/* Collapsible Key input box */}
      {showKeyInput && (
        <div style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: '8px',
          padding: '14px 16px',
          marginBottom: '16px'
        }}>
          <label style={{ display: 'block', fontSize: '0.825rem', color: '#334155', fontWeight: 600, marginBottom: '6px' }}>
            Google Gemini API Key (Optional — fallback rule model used if blank):
          </label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Paste Gemini API key here..."
              style={{
                flex: 1,
                background: '#ffffff',
                border: '1px solid #cbd5e1',
                color: '#0f172a',
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '0.875rem',
                outline: 'none'
              }}
            />
            <button
              onClick={() => {
                localStorage.setItem('gemini_api_key', apiKey)
                alert('API key saved.')
              }}
              style={{
                background: '#e10600',
                color: '#fff',
                border: 'none',
                padding: '8px 16px',
                borderRadius: '6px',
                fontSize: '0.825rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Save
            </button>
          </div>
        </div>
      )}

      {/* Chat Messages Log */}
      <div style={{
        background: '#ffffff',
        borderRadius: '8px',
        padding: '18px',
        minHeight: '360px',
        maxHeight: '520px',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
        border: '1px solid #e2e8f0',
        marginBottom: '14px'
      }}>
        {messages.map((m, idx) => {
          const isUser = m.sender === 'user'
          return (
            <div key={idx} style={{
              alignSelf: isUser ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: isUser ? 'flex-end' : 'flex-start'
            }}>
              <span style={{ fontSize: '0.725rem', color: '#94a3b8', marginBottom: '3px', paddingLeft: '4px' }}>
                {isUser ? 'Engineer' : 'Verification Copilot'}
              </span>
              <div style={{
                background: isUser ? '#1e293b' : '#f8fafc',
                color: isUser ? '#ffffff' : '#1e293b',
                padding: '12px 16px',
                borderRadius: isUser ? '8px 8px 2px 8px' : '8px 8px 8px 2px',
                fontSize: '0.9rem',
                lineHeight: '1.55',
                border: isUser ? 'none' : '1px solid #e2e8f0',
                boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
              }}>
                {isUser ? m.text : renderFormattedMarkdown(m.text)}
                {m.model && (
                  <div style={{
                    marginTop: '10px',
                    fontSize: '0.75rem',
                    color: '#64748b',
                    borderTop: '1px solid #e2e8f0',
                    paddingTop: '6px'
                  }}>
                    Model: <span style={{ fontWeight: 600, color: '#334155' }}>{m.model}</span>
                  </div>
                )}
              </div>
            </div>
          )
        })}
        {loading && (
          <div style={{
            alignSelf: 'flex-start',
            background: '#f8fafc',
            color: '#64748b',
            padding: '10px 16px',
            borderRadius: '8px',
            fontSize: '0.85rem',
            border: '1px solid #e2e8f0'
          }}>
            Analyzing telemetry context…
          </div>
        )}
      </div>

      {/* Suggested Questions */}
      <div style={{ marginBottom: '14px' }}>
        <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600, marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Suggested Queries
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
          {suggestedQuestions.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleChipClick(q)}
              style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                color: '#475569',
                padding: '5px 10px',
                borderRadius: '6px',
                fontSize: '0.785rem',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                textAlign: 'left'
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.borderColor = '#cbd5e1'
                e.currentTarget.style.color = '#0f172a'
                e.currentTarget.style.background = '#f8fafc'
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.borderColor = '#e2e8f0'
                e.currentTarget.style.color = '#475569'
                e.currentTarget.style.background = '#ffffff'
              }}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Input Form */}
      <form onSubmit={handleSend} style={{ display: 'flex', gap: '10px' }}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about root causes, failure clusters, or recommended settings..."
          style={{
            flex: 1,
            background: '#ffffff',
            border: '1px solid #cbd5e1',
            borderRadius: '6px',
            padding: '10px 14px',
            color: '#0f172a',
            fontSize: '0.9rem',
            outline: 'none'
          }}
          onFocus={(e) => e.target.style.borderColor = '#e10600'}
          onBlur={(e) => e.target.style.borderColor = '#cbd5e1'}
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          style={{
            background: '#e10600',
            color: '#ffffff',
            border: 'none',
            borderRadius: '6px',
            padding: '10px 20px',
            fontWeight: 600,
            fontSize: '0.875rem',
            cursor: loading || !question.trim() ? 'not-allowed' : 'pointer',
            opacity: loading || !question.trim() ? 0.6 : 1,
            transition: 'background 0.15s ease'
          }}
          onMouseOver={(e) => { if (!loading && question.trim()) e.currentTarget.style.background = '#b80500' }}
          onMouseOut={(e) => { if (!loading && question.trim()) e.currentTarget.style.background = '#e10600' }}
        >
          Send
        </button>
      </form>
    </div>
  )
}
