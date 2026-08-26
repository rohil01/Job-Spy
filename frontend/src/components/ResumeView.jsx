import { useState } from 'react'
import { assessSuitability, tailorResume, downloadBlob } from '../api.js'
import Spinner from './Spinner.jsx'
import ErrorBanner from './ErrorBanner.jsx'

function verdictClass(verdict) {
  const v = (verdict || '').toLowerCase()
  if (v.includes('strong')) return 'verdict verdict--strong'
  if (v.includes('good') || v.includes('moderate')) return 'verdict verdict--mid'
  if (v.includes('weak') || v.includes('poor')) return 'verdict verdict--low'
  return 'verdict'
}

function scoreClass(score) {
  if (typeof score !== 'number') return 'score'
  if (score >= 75) return 'score score--high'
  if (score >= 50) return 'score score--mid'
  return 'score score--low'
}

export default function ResumeView({ resume, setResume, jobs, selectedJob, setSelectedJob }) {
  const [assessing, setAssessing] = useState(false)
  const [rewriting, setRewriting] = useState(false)
  const [assessment, setAssessment] = useState(null)
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
      setError(new Error('Upload a .docx resume first.'))
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
      setError(new Error('Select a job (from the Jobs tab) or paste a job JSON.'))
      return null
    }
    return job
  }

  async function doAssess() {
    setError(null)
    setAssessment(null)
    const job = validate()
    if (!job) return
    setAssessing(true)
    try {
      const data = await assessSuitability(resume, job)
      setAssessment(data)
    } catch (e) {
      setError(e)
    } finally {
      setAssessing(false)
    }
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
    error?.status === 502
      ? 'The AI request failed (often a missing/invalid key). Set a real NVIDIA_API_KEY in the backend .env and restart run_api.py.'
      : null

  return (
    <section>
      <div className="panel">
        <h3 className="panel__title">1 · Your resume</h3>
        <input type="file" accept=".docx" onChange={onFile} />
        <div>
          {resume ? (
            <span className="muted small">Loaded: {resume.name}</span>
          ) : (
            <span className="muted small">Only .docx is supported.</span>
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
              <p className="muted small">Tip: load jobs in the Jobs tab and click “Use for resume”.</p>
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
        <h3 className="panel__title">3 · Act</h3>
        <div className="actions">
          <button className="btn" onClick={doAssess} disabled={assessing}>
            {assessing ? <Spinner label="Assessing…" /> : 'Assess suitability'}
          </button>
          <button className="btn btn--primary" onClick={doRewrite} disabled={rewriting}>
            {rewriting ? <Spinner label="Rewriting…" /> : 'Rewrite & download .docx'}
          </button>
        </div>
      </div>

      <ErrorBanner error={error} hint={hint} />

      {assessment ? (
        <div className="assessment">
          <div className="assessment__head">
            <div className={scoreClass(assessment.score)}>
              <span className="score__num">{assessment.score ?? '—'}</span>
              <span className="score__lbl">/ 100</span>
            </div>
            <div>
              <span className={verdictClass(assessment.verdict)}>{assessment.verdict}</span>
              {assessment.experience_match != null ? (
                <span className={`exp ${assessment.experience_match ? 'exp--ok' : 'exp--no'}`}>
                  {assessment.experience_match ? 'experience matches' : 'experience mismatch'}
                </span>
              ) : null}
            </div>
          </div>

          {assessment.matched_skills?.length ? (
            <div className="skillset">
              <h4>Matched skills</h4>
              <div className="chips">
                {assessment.matched_skills.map((s, i) => (
                  <span key={i} className="chip chip--ok">{s}</span>
                ))}
              </div>
            </div>
          ) : null}

          {assessment.missing_skills?.length ? (
            <div className="skillset">
              <h4>Missing skills</h4>
              <div className="chips">
                {assessment.missing_skills.map((s, i) => (
                  <span key={i} className="chip chip--miss">{s}</span>
                ))}
              </div>
            </div>
          ) : null}

          {assessment.reasoning ? (
            <div className="reasoning">
              <h4>Reasoning</h4>
              <p>{assessment.reasoning}</p>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
