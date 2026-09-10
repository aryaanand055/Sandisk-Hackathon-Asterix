import { useState } from 'react'

export default function AICopilot({ jobId, result }) {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([
    {
      sender: 'assistant',
      text: 'Hello! I am your Verification Intelligence Copilot. Ask me about failure risk drivers, recommended configurations, root cause analysis, or Pareto trade-offs in your dataset.',
    },
  ])
  const [loading, setLoading] = useState(false)

  const handleSend = async (e) => {
    e.preventDefault()
    if (!question.trim() || loading) return

    const userText = question.trim()
    setQuestion('')
    setMessages((prev) => [...prev, { sender: 'user', text: userText }])
    setLoading(true)

    try {
      const res = await fetch('http://127.0.0.1:8000/api/copilot/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId, question: userText }),
      })
      if (!res.ok) throw new Error('Copilot query failed')
      const data = await res.json()
      setMessages((prev) => [
        ...prev,
        { sender: 'assistant', text: data.answer },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: `⚠️ Query failed: ${err.message}. Please check if the backend is running.`,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const suggestedQuestions = [
    'What are the top configuration knobs driving test failures?',
    'What is the recommended optimal configuration for low risk?',
    'How many failure clusters were identified in this run?',
    'Summarize the corpus performance and pass/fail metrics.',
  ]

  return (
    <div style={{ padding: '24px', maxWidth: '900px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
        <div style={{
          width: '40px', height: '40px', borderRadius: '8px',
          background: 'linear-gradient(135deg, #6366f1, #a855f7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontWeight: 'bold', fontSize: '20px'
        }}>
          🤖
        </div>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 600 }}>AI Verification Copilot</h2>
          <p style={{ margin: 0, color: '#64748b', fontSize: '0.875rem' }}>
            Interactive AI insights over parsed logs & configuration datasets
          </p>
        </div>
      </div>

      <div style={{
        background: '#1e293b', borderRadius: '12px', padding: '20px',
        minHeight: '380px', maxHeight: '500px', overflowY: 'auto',
        display: 'flex', flexDirection: 'column', gap: '16px',
        border: '1px solid #334155', marginBottom: '16px'
      }}>
        {messages.map((m, idx) => (
          <div key={idx} style={{
            alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '80%',
            background: m.sender === 'user' ? '#3b82f6' : '#0f172a',
            color: '#f8fafc', padding: '12px 16px', borderRadius: '12px',
            fontSize: '0.925rem', lineHeight: '1.5', whiteSpace: 'pre-wrap',
            border: m.sender === 'user' ? 'none' : '1px solid #334155',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
          }}>
            {m.text}
          </div>
        ))}
        {loading && (
          <div style={{
            alignSelf: 'flex-start', background: '#0f172a', color: '#94a3b8',
            padding: '12px 16px', borderRadius: '12px', fontSize: '0.875rem',
            fontStyle: 'italic', border: '1px solid #334155'
          }}>
            Thinking and analyzing verification telemetry...
          </div>
        )}
      </div>

      <div style={{ marginBottom: '16px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        <span style={{ fontSize: '0.8rem', color: '#64748b', alignSelf: 'center' }}>Suggested:</span>
        {suggestedQuestions.map((q, idx) => (
          <button
            key={idx}
            onClick={() => setQuestion(q)}
            style={{
              background: '#0f172a', border: '1px solid #334155', color: '#cbd5e1',
              padding: '6px 12px', borderRadius: '20px', fontSize: '0.775rem',
              cursor: 'pointer', transition: 'all 0.2s'
            }}
          >
            {q}
          </button>
        ))}
      </div>

      <form onSubmit={handleSend} style={{ display: 'flex', gap: '12px' }}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about test failures, risks, or settings..."
          style={{
            flex: 1, background: '#0f172a', border: '1px solid #334155',
            borderRadius: '8px', padding: '12px 16px', color: '#f8fafc',
            fontSize: '0.925rem'
          }}
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          style={{
            background: 'linear-gradient(135deg, #6366f1, #3b82f6)', color: '#fff',
            border: 'none', borderRadius: '8px', padding: '12px 24px',
            fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading || !question.trim() ? 0.6 : 1
          }}
        >
          Send
        </button>
      </form>
    </div>
  )
}
