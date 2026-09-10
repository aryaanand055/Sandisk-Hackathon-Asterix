const BASE = '/api'

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, opts)
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch { /* non-JSON error body */ }
    throw new Error(detail)
  }
  return res.json()
}

export const health = () => req('/health')

export function analyzeUpload(files, params) {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  const q = new URLSearchParams(params).toString()
  return req(`/analyze?${q}`, { method: 'POST', body: fd })
}

export const analyzeSample = (params) =>
  req(`/analyze-sample?${new URLSearchParams(params)}`, { method: 'POST' })

export const jobStatus = (id) => req(`/jobs/${id}`)
export const jobResult = (id) => req(`/jobs/${id}/result`)
export const jobRuns = (id, params) =>
  req(`/jobs/${id}/runs?${new URLSearchParams(params)}`)
export const jobDiff = (id, runA, runB) =>
  req(`/jobs/${id}/diff?${new URLSearchParams({ run_a: runA, run_b: runB })}`)
export const exportUrl = (id) => `${BASE}/jobs/${id}/export`
