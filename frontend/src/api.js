// Thin fetch wrappers around the JobSpy FastAPI backend.
// Base URL is configurable via VITE_API_BASE (see .env.example).

const BASE = (import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000').replace(/\/$/, '')

export const API_BASE = BASE

// FastAPI errors come back as {detail: "..."} (detail may be a string or a list).
async function readError(res) {
  let detail = `${res.status} ${res.statusText}`
  try {
    const data = await res.json()
    if (data && data.detail != null) {
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    }
  } catch {
    // non-JSON body — keep the status line
  }
  const err = new Error(detail)
  err.status = res.status
  return err
}

async function getJSON(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw await readError(res)
  return res.json()
}

async function postJSON(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
  if (!res.ok) throw await readError(res)
  return res.json()
}

// Backend accepts either `job` (a JSON object as a string) or `job_id`.
function buildResumeForm(file, job) {
  const form = new FormData()
  form.append('resume', file, file.name)
  form.append('job', JSON.stringify(job))
  return form
}

export function getHealth() {
  return getJSON('/health')
}

export function getJobs(limit) {
  const q = limit ? `?limit=${encodeURIComponent(limit)}` : ''
  return getJSON(`/jobs${q}`)
}

export function getGroupedJobs(limit) {
  const q = limit ? `?limit=${encodeURIComponent(limit)}` : ''
  return getJSON(`/jobs/grouped${q}`)
}

// Read an NDJSON (one JSON object per line) response body, calling onEvent(obj)
// for every parsed line. Shared by the JSON and multipart streaming helpers.
async function pumpNDJSON(res, onEvent) {
  if (!res.body) throw new Error('Streaming responses are not supported in this browser.')
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const emit = (line) => {
    const trimmed = line.trim()
    if (!trimmed) return
    let obj
    try {
      obj = JSON.parse(trimmed)
    } catch {
      return // ignore an incomplete / malformed line
    }
    onEvent(obj)
  }

  // Let React paint each streamed job before consuming the next buffered line.
  const yieldToBrowser = () => new Promise((resolve) => setTimeout(resolve, 0))

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let nl
    while ((nl = buffer.indexOf('\n')) >= 0) {
      emit(buffer.slice(0, nl))
      buffer = buffer.slice(nl + 1)
      await yieldToBrowser()
    }
  }
  // Flush any trailing line that wasn't newline-terminated.
  buffer += decoder.decode()
  emit(buffer)
}

// Stream NDJSON from a JSON POST endpoint. Calls onEvent(obj) for every parsed
// line and resolves when the stream ends.
export async function streamNDJSON(path, body, onEvent, { signal } = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
    signal,
  })
  if (!res.ok) throw await readError(res)
  await pumpNDJSON(res, onEvent)
}

export function streamScrape(params, onEvent, opts) {
  return streamNDJSON('/scrape/stream', params || {}, onEvent, opts)
}

export function startScrape(params) {
  return postJSON('/scrape', params || {})
}

export function getScrapeStatus(runId) {
  return getJSON(`/scrape/${encodeURIComponent(runId)}`)
}

export function getScrapeConfig() {
  return getJSON('/config/scrape')
}

export function filterExperience(jobs, minYears, maxYears) {
  // min is always a number; max is a number, or null for an open-ended "N+".
  const body = { min_years: minYears, max_years: maxYears ?? null }
  if (jobs) body.jobs = jobs
  return postJSON('/filter/experience', body)
}

export function streamFilterExperience(jobs, minYears, maxYears, onEvent, opts) {
  const body = { min_years: minYears, max_years: maxYears ?? null }
  if (jobs) body.jobs = jobs
  return streamNDJSON('/filter/experience/stream', body, onEvent, opts)
}

// Combined screen (multipart: resume .docx + window + optional jobs). Streams
// one `job` event per posting, each tagged `match` and carrying the fit score.
export async function streamScreen(file, jobs, minYears, maxYears, onEvent, { signal } = {}) {
  const form = new FormData()
  form.append('resume', file, file.name)
  if (minYears != null) form.append('min_years', String(minYears))
  if (maxYears != null) form.append('max_years', String(maxYears))
  if (jobs && jobs.length) form.append('jobs', JSON.stringify(jobs))
  const res = await fetch(`${BASE}/screen/stream`, { method: 'POST', body: form, signal })
  if (!res.ok) throw await readError(res)
  await pumpNDJSON(res, onEvent)
}

export async function assessSuitability(file, job) {
  const res = await fetch(`${BASE}/suitability`, {
    method: 'POST',
    body: buildResumeForm(file, job),
  })
  if (!res.ok) throw await readError(res)
  return res.json()
}

export async function tailorResume(file, job) {
  const res = await fetch(`${BASE}/tailor-resume`, {
    method: 'POST',
    body: buildResumeForm(file, job),
  })
  if (!res.ok) throw await readError(res)
  const blob = await res.blob()
  const cd = res.headers.get('Content-Disposition') || ''
  const match = cd.match(/filename="?([^"]+)"?/i)
  const filename = match ? match[1] : 'tailored_resume.docx'
  return { blob, filename }
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
