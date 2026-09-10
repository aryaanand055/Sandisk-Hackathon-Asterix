import { useState, useEffect } from 'react'

function renderFormattedMarkdown(content) {
  if (!content) return null
  const lines = content.split('\n')
  const elements = []
  let tableRows = []
  let inTable = false
  let tableKey = 0

  const parseInline = (text) => {
    // Bold italic
    let parts = [text]
    // Parse bold **text**
    const boldRegex = /\*\*(.*?)\*\*/g
    const res = []
    
    let lastIdx = 0
    let match
    while ((match = boldRegex.exec(text)) !== null) {
      if (match.index > lastIdx) {
        res.push(text.substring(lastIdx, match.index))
      }
      res.push(<strong key={match.index} style={{ color: '#60a5fa', fontWeight: 600 }}>{match[1]}</strong>)
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
            background: 'rgba(15, 23, 42, 0.6)', borderRadius: '8px', overflow: 'hidden',
            border: '1px solid #334155'
          }}>
            <thead>
              <tr style={{ background: '#1e293b', borderBottom: '2px solid #3b82f6' }}>
                {headerRow.map((h, i) => (
                  <th key={i} style={{ padding: '10px 14px', textAlign: 'left', color: '#93c5fd', fontWeight: 600 }}>
                    {parseInline(h.trim())}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bodyRows.map((row, rIdx) => (
                <tr key={rIdx} style={{
                  borderBottom: '1px solid #1e293b',
                  background: rIdx % 2 === 0 ? 'transparent' : 'rgba(30, 41, 59, 0.4)'
                }}>
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} style={{ padding: '9px 14px', color: '#e2e8f0' }}>
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
      elements.push(<hr key={idx} style={{ border: 'none', borderTop: '1px solid #334155', margin: '16px 0' }} />)
      return
    }

    // Headers
    if (trimmed.startsWith('### ')) {
      elements.push(
        <h4 key={idx} style={{ color: '#38bdf8', fontSize: '1.05rem', fontWeight: 600, marginTop: '14px', marginBottom: '8px' }}>
          {parseInline(trimmed.replace(/^###\s+/, ''))}
        </h4>
      )
      return
    }
    if (trimmed.startsWith('## ')) {
      elements.push(
        <h3 key={idx} style={{ color: '#60a5fa', fontSize: '1.15rem', fontWeight: 700, marginTop: '16px', marginBottom: '10px' }}>
          {parseInline(trimmed.replace(/^##\s+/, ''))}
        </h3>
      )
      return
    }
    if (trimmed.startsWith('# ')) {
      elements.push(
        <h2 key={idx} style={{ color: '#818cf8', fontSize: '1.25rem', fontWeight: 800, marginTop: '18px', marginBottom: '12px' }}>
          {parseInline(trimmed.replace(/^#\s+/, ''))}
        </h2>
      )
      return
    }

    // Bullet Lists
    if (trimmed.startsWith('* ') || trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
      const bulletText = trimmed.replace(/^(\*|-|•)\s+/, '')
      elements.push(
        <div key={idx} style={{ display: 'flex', gap: '8px', marginLeft: '8px', marginBottom: '6px', lineHeight: '1.5' }}>
          <span style={{ color: '#3b82f6', fontWeight: 'bold' }}>•</span>
          <div style={{ flex: 1 }}>{parseInline(bulletText)}</div>
        </div>
      )
      return
    }

    // Numbered lists
    const numMatch = trimmed.match(/^(\d+)\.\s+(.*)$/)
    if (numMatch) {
      elements.push(
        <div key={idx} style={{ display: 'flex', gap: '8px', marginLeft: '8px', marginBottom: '6px', lineHeight: '1.5' }}>
          <span style={{ color: '#818cf8', fontWeight: 600, minWidth: '18px' }}>{numMatch[1]}.</span>
          <div style={{ flex: 1 }}>{parseInline(numMatch[2])}</div>
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
      <p key={idx} style={{ margin: '4px 0', lineHeight: '1.6' }}>
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
      text: '👋 **Welcome to the AI Verification Copilot!**\n\nI am powered by Google Gemini and have full context of all dashboard analysis results (ML risk metrics, SHAP feature importance, failure fingerprints, Pareto frontiers, and optimal config recommendations).\n\nAsk me any question in natural language about your test runs, root causes, or knob settings!',
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
          text: `⚠️ **Query error**: ${err.message}. Ensure backend is running.`,
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
    <div style={{ padding: '24px', maxWidth: '960px', margin: '0 auto', fontFamily: 'system-ui, sans-serif' }}>
      {/* Header bar with status and Gemini API key config */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: '#0f172a', padding: '16px 20px', borderRadius: '12px',
        border: '1px solid #1e293b', marginBottom: '20px', flexWrap: 'wrap', gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '42px', height: '42px', borderRadius: '10px',
            background: 'linear-gradient(135deg, #4f46e5, #9333ea)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: '22px', boxShadow: '0 4px 12px rgba(79, 70, 229, 0.4)'
          }}>
            ✨
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600, color: '#f8fafc' }}>
                AI Verification Copilot
              </h2>
              <span style={{
                background: geminiConnected || apiKey ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                color: geminiConnected || apiKey ? '#10b981' : '#f59e0b',
                border: `1px solid ${geminiConnected || apiKey ? '#10b981' : '#f59e0b'}`,
                padding: '2px 8px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 600
              }}>
                {geminiConnected || apiKey ? '⚡ Gemini Connected' : '🔑 API Key Required'}
              </span>
            </div>
            <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.85rem' }}>
              Powered by Google Gemini — Access to full ML risk, SHAP, & failure cluster payload
            </p>
          </div>
        </div>

        <button
          onClick={() => setShowKeyInput(!showKeyInput)}
          style={{
            background: '#1e293b', border: '1px solid #334155', color: '#e2e8f0',
            padding: '8px 14px', borderRadius: '8px', fontSize: '0.85rem',
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px'
          }}
        >
          ⚙️ {showKeyInput ? 'Hide API Key Settings' : 'Gemini API Key'}
        </button>
      </div>

      {/* Collapsible Key input box */}
      {showKeyInput && (
        <div style={{
          background: '#0f172a', border: '1px solid #3b82f6', borderRadius: '10px',
          padding: '16px', marginBottom: '20px'
        }}>
          <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', fontWeight: 500, marginBottom: '6px' }}>
            Google Gemini API Key:
          </label>
          <div style={{ display: 'flex', gap: '10px' }}>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="AIzaSy..."
              style={{
                flex: 1, background: '#1e293b', border: '1px solid #334155',
                color: '#fff', padding: '10px 14px', borderRadius: '6px', fontSize: '0.9rem'
              }}
            />
            <button
              onClick={() => {
                localStorage.setItem('gemini_api_key', apiKey)
                alert('Gemini API key saved to local storage!')
              }}
              style={{
                background: '#2563eb', color: '#fff', border: 'none',
                padding: '10px 18px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer'
              }}
            >
              Save Key
            </button>
          </div>
          <p style={{ fontSize: '0.75rem', color: '#64748b', margin: '6px 0 0 0' }}>
            Your key is stored locally in your browser and passed securely to the backend for Gemini API calls.
          </p>
        </div>
      )}

      {/* Chat Messages */}
      <div style={{
        background: '#0f172a', borderRadius: '12px', padding: '20px',
        minHeight: '380px', maxHeight: '520px', overflowY: 'auto',
        display: 'flex', flexDirection: 'column', gap: '16px',
        border: '1px solid #1e293b', marginBottom: '16px'
      }}>
        {messages.map((m, idx) => (
          <div key={idx} style={{
            alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '85%',
            background: m.sender === 'user' ? 'linear-gradient(135deg, #2563eb, #1d4ed8)' : '#1e293b',
            color: '#f8fafc', padding: '14px 18px', borderRadius: '14px',
            fontSize: '0.925rem', lineHeight: '1.6', whiteSpace: 'pre-wrap',
            border: m.sender === 'user' ? 'none' : '1px solid #334155',
            boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)'
          }}>
            {m.sender === 'assistant' ? renderFormattedMarkdown(m.text) : m.text}
            {m.model && (
              <div style={{ marginTop: '12px', fontSize: '0.725rem', color: '#94a3b8', fontStyle: 'italic', borderTop: '1px solid #334155', paddingTop: '6px' }}>
                Answer generated by <strong style={{ color: '#38bdf8' }}>{m.model}</strong> with full dashboard context
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div style={{
            alignSelf: 'flex-start', background: '#1e293b', color: '#94a3b8',
            padding: '12px 18px', borderRadius: '14px', fontSize: '0.875rem',
            fontStyle: 'italic', border: '1px solid #334155'
          }}>
            ✨ Querying Google Gemini with complete dashboard telemetry context...
          </div>
        )}
      </div>

      {/* Suggested Questions */}
      <div style={{ marginBottom: '16px' }}>
        <div style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 500, marginBottom: '8px' }}>
          Suggested Natural Language Questions:
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {suggestedQuestions.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleChipClick(q)}
              style={{
                background: '#1e293b', border: '1px solid #334155', color: '#cbd5e1',
                padding: '6px 12px', borderRadius: '16px', fontSize: '0.8rem',
                cursor: 'pointer', transition: 'all 0.2s'
              }}
              onMouseOver={(e) => { e.currentTarget.style.borderColor = '#3b82f6'; e.currentTarget.style.color = '#fff'; }}
              onMouseOut={(e) => { e.currentTarget.style.borderColor = '#334155'; e.currentTarget.style.color = '#cbd5e1'; }}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Input Form */}
      <form onSubmit={handleSend} style={{ display: 'flex', gap: '12px' }}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask Gemini anything about your verification run results, risk drivers, or knob choices..."
          style={{
            flex: 1, background: '#0f172a', border: '1px solid #334155',
            borderRadius: '8px', padding: '12px 16px', color: '#f8fafc',
            fontSize: '0.925rem', outline: 'none'
          }}
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          style={{
            background: 'linear-gradient(135deg, #4f46e5, #2563eb)', color: '#fff',
            border: 'none', borderRadius: '8px', padding: '12px 24px',
            fontWeight: 600, cursor: loading || !question.trim() ? 'not-allowed' : 'pointer',
            opacity: loading || !question.trim() ? 0.6 : 1,
            boxShadow: '0 4px 12px rgba(79, 70, 229, 0.3)'
          }}
        >
          Send to Gemini
        </button>
      </form>
    </div>
  )
}
