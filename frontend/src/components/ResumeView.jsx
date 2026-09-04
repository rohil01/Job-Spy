import { useState } from 'react'
import { tailorResume, downloadBlob } from '../api.js'
import Spinner from './Spinner.jsx'
import ErrorBanner from './ErrorBanner.jsx'

export default function ResumeView({ resume, setResume, jobs, selectedJob, setSelectedJob }) {
  const [rewriting, setRewriting] = useState(false)
  const [error, setError] = useState(null)
  const [jobJsonText, setJobJsonText] = useState('')

  // Resolve the target job: the selected job, or pasted JSON. Throws on bad JSON.
  function resolveJob() {
    if (selectedJob) return selectedJob
    if (jobJsonText.trim()) return JSON.parse(jobJsonText)
    return null
  }

  function onFile(e) {
    const f = e.target.files?.[0]
    if (f) {
      setResume(f)
      setError(null)
    }
  }

  function chooseFromDropdown(e) {
    const id = e.target.value
    const job = jobs.find((j) => String(j.id) === id)
    setSelectedJob(job || null)
  }

  function validate() {
    if (!resume) {
      setError(new Error('Upload a .docx résumé first.'))
      return null
    }
    let job
    try {
      job = resolveJob()
    } catch {
      setError(new Error('Pasted job JSON is not valid.'))
      return null
    }
    if (!job) {
      setError(new Error('Pick a job (from the Screen or Jobs tab) or paste a job JSON.'))
      return null
    }
    return job
  }

  async function doRewrite() {
    setError(null)
    const job = validate()
    if (!job) return
    setRewriting(true)
    try {
      const { blob, filename } = await tailorResume(resume, job)
      downloadBlob(blob, filename)
    } catch (e) {
      setError(e)
    } finally {
      setRewriting(false)
    }
  }

  const hint =
    error?.status === 502 || error?.status === 503
      ? 'The AI request failed (often a missing/invalid key). Set a real NVIDIA_API_KEY in the backend .env and restart run_api.py.'
      : null

  return (
    <section>
      <div className="panel">
        <h3 className="panel__title">1 · Your résumé</h3>
        <input type="file" accept=".docx" onChange={onFile} />
        <div>
          {resume ? (
            <span className="muted small">Loaded: {resume.name}</span>
          ) : (
            <span className="muted small">Only .docx is supported. Shared with the Screen tab.</span>
          )}
        </div>
      </div>

      <div className="panel">
        <h3 className="panel__title">2 · Target job</h3>
        {selectedJob ? (
          <div className="selected-job">
            <b>{selectedJob.title}</b> — {selectedJob.company || 'Unknown'}
            {selectedJob.location ? ` · ${selectedJob.location}` : ''}
            <button className="link-btn" onClick={() => setSelectedJob(null)}>clear</button>
          </div>
        ) : (
          <>
            {jobs?.length ? (
              <select className="select" defaultValue="" onChange={chooseFromDropdown}>
                <option value="" disabled>Choose from loaded jobs…</option>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title} — {j.company}
                  </option>
                ))}
              </select>
            ) : (
              <p className="muted small">Tip: screen jobs in the Screen tab and click “Rewrite →”.</p>
            )}
            <details className="paste">
              <summary>…or paste a job JSON</summary>
              <textarea
                className="textarea"
                rows={4}
                value={jobJsonText}
                onChange={(e) => setJobJsonText(e.target.value)}
                placeholder='{"title": "Backend Engineer", "description": "..."}'
              />
            </details>
          </>
        )}
      </div>

      <div className="panel">
        <h3 className="panel__title">3 · Rewrite</h3>
        <p className="muted small">
          Tailors your résumé to the target job — truthfully re-ordering and rephrasing your own
          content — and downloads it as a .docx.
        </p>
        <div className="actions">
          <button className="btn btn--primary" onClick={doRewrite} disabled={rewriting}>
            {rewriting ? <Spinner label="Rewriting…" /> : 'Rewrite & download .docx'}
          </button>
        </div>
      </div>

      <ErrorBanner error={error} hint={hint} />
    </section>
  )
}
