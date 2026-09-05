import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

function salaryText(job) {
  const { min_amount, max_amount, currency, interval } = job
  if (!min_amount && !max_amount) return null
  const cur = currency || ''
  const fmt = (n) => (typeof n === 'number' ? n.toLocaleString() : n)
  const range =
    min_amount && max_amount
      ? `${fmt(min_amount)}–${fmt(max_amount)}`
      : fmt(min_amount || max_amount)
  return `${cur} ${range}${interval ? ` / ${interval}` : ''}`.trim()
}

function requiredYearsText(ry) {
  if (!ry || typeof ry.min !== 'number') return null
  const { min, max } = ry
  if (max == null) return `needs ${min}+ yrs`
  if (min === max) return `needs ${min} yr${min === 1 ? '' : 's'}`
  return `needs ${min}–${max} yrs`
}

function postingMeta(p) {
  return [p.site, p.location, p.date_posted].filter(Boolean).join(' · ')
}

function scoreTier(score) {
  if (typeof score !== 'number') return ''
  if (score >= 75) return 'high'
  if (score >= 50) return 'mid'
  return 'low'
}

function verdictBadgeClass(verdict) {
  const v = (verdict || '').toLowerCase()
  if (v.includes('strong')) return 'badge badge--ok'
  if (v.includes('good') || v.includes('moderate')) return 'badge badge--warn'
  if (v.includes('weak') || v.includes('poor')) return 'badge badge--no'
  return 'badge'
}

function detailLabel(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function detailValue(value) {
  if (value == null || value === '') return '—'
  if (Array.isArray(value)) return value.length ? value.join(', ') : '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function JobDetails({ job, onClose }) {
  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const aiKeys = new Set([
    'score', 'verdict', 'required_years', 'experience_match',
    'matched_skills', 'missing_skills', 'reasoning',
  ])
  const entries = Object.entries(job).filter(
    ([key]) => key !== 'description' && !aiKeys.has(key),
  )
  const hasAiDetails = Object.keys(job).some((key) => aiKeys.has(key))

  return (
    <div className="details-modal" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section className="details-modal__window" role="dialog" aria-modal="true" aria-labelledby="job-details-title">
        <div className="details-modal__head">
          <div>
            <p className="eyebrow">Posting details</p>
            <h2 id="job-details-title">{job.title || 'Untitled role'}</h2>
            <p className="muted">{job.company || 'Unknown company'}{job.location ? ` · ${job.location}` : ''}</p>
          </div>
          <button className="icon-btn" type="button" onClick={onClose} aria-label="Close details">×</button>
        </div>
        <div className="details-modal__body">
          {hasAiDetails ? (
            <div className="details-ai">
              <h3>AI assessment</h3>
              <div className="details-ai__summary">
                {job.score != null ? <strong className="details-ai__score">{job.score}<small>/100 fit</small></strong> : null}
                {job.verdict && job.verdict !== 'unknown' ? (
                  <span className={verdictBadgeClass(job.verdict)}>{job.verdict} fit</span>
                ) : null}
                {job.required_years ? <span className="badge badge--accent">{requiredYearsText(job.required_years)}</span> : null}
                {job.experience_match != null ? (
                  <span className={job.experience_match ? 'badge badge--ok' : 'badge badge--no'}>
                    {job.experience_match ? 'matches experience' : 'outside experience window'}
                  </span>
                ) : null}
              </div>
              {Array.isArray(job.matched_skills) && job.matched_skills.length ? (
                <div className="details-ai__skills"><b>Matched skills</b>{job.matched_skills.map((skill, index) => <span className="chip chip--ok" key={`matched-${index}`}>{skill}</span>)}</div>
              ) : null}
              {Array.isArray(job.missing_skills) && job.missing_skills.length ? (
                <div className="details-ai__skills"><b>Missing skills</b>{job.missing_skills.map((skill, index) => <span className="chip chip--miss" key={`missing-${index}`}>{skill}</span>)}</div>
              ) : null}
              {job.reasoning ? <p className="details-ai__reasoning">{job.reasoning}</p> : null}
            </div>
          ) : null}
          {job.description ? (
            <div className="details-modal__description">
              <h3>Description</h3>
              <p>{job.description}</p>
            </div>
          ) : null}
          <dl className="details-grid">
            {entries.map(([key, value]) => (
              <div className="details-grid__item" key={key}>
                <dt>{detailLabel(key)}</dt>
                <dd>{detailValue(value)}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="details-modal__foot">
          {job.job_url ? (
            <a className="btn btn--primary" href={job.job_url} target="_blank" rel="noreferrer">
              Open original ↗
            </a>
          ) : null}
          <button className="btn" type="button" onClick={onClose}>Close</button>
        </div>
      </section>
    </div>
  )
}

// Signature element: a radial "confidence readout" of the fit score (0–100).
function FitGauge({ score }) {
  const tier = scoreTier(score)
  const r = 22
  const c = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(100, score)) / 100
  return (
    <span className={`gauge gauge--${tier}`} role="img" aria-label={`fit score ${score} of 100`}>
      <svg width="56" height="56" viewBox="0 0 56 56">
        <circle className="gauge__track" cx="28" cy="28" r={r} fill="none" strokeWidth="5" />
        <circle
          className="gauge__fill"
          cx="28"
          cy="28"
          r={r}
          fill="none"
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          transform="rotate(-90 28 28)"
        />
      </svg>
      <span className="gauge__label">
        <span className="gauge__num">{score}</span>
        <span className="gauge__unit">FIT</span>
      </span>
    </span>
  )
}

// `matchTag` conveys the experience verdict ('selected' | 'not-selected') and is
// kept distinct from the resume `selected` prop (the action button). `useLabel`
// overrides that button's default text. Screening adds job.score / job.verdict /
// job.matched_skills / job.missing_skills / job.reasoning, rendered when present.
export default function JobCard({ job, onUse, selected, group, matchTag, useLabel }) {
  const [dupOpen, setDupOpen] = useState(false)
  const [detailsJob, setDetailsJob] = useState(null)
  const salary = salaryText(job)
  const desc = job.description || ''
  const skills = Array.isArray(job.skills) ? job.skills : []
  const matched = Array.isArray(job.matched_skills) ? job.matched_skills : []
  const missing = Array.isArray(job.missing_skills) ? job.missing_skills : []
  const dupCount = group && group.count > 1 ? group.count : 0
  const hasScore = typeof job.score === 'number'
  const hasFit = hasScore || (job.verdict && job.verdict !== 'unknown') || job.reasoning

  function openFromTile(event) {
    if (event.target.closest('button, a, input, select, textarea')) return
    setDetailsJob(job)
  }

  return (
    <article className={`card ${selected ? 'card--selected' : ''}`} onClick={openFromTile}>
      <div className="card__head">
        <div>
          <h3 className="card__title">{job.title || 'Untitled role'}</h3>
          <div className="card__company">
            {job.company || 'Unknown company'}
            {job.location ? <span className="card__loc"> · {job.location}</span> : null}
          </div>
        </div>
        {onUse ? (
          <button className="btn btn--small" onClick={() => onUse(job)}>
            {selected ? 'Selected ✓' : (useLabel || 'Use for resume →')}
          </button>
        ) : null}
      </div>

      <div className="badges">
        {matchTag === 'selected' ? (
          <span className="badge badge--ok">✓ matches experience</span>
        ) : null}
        {matchTag === 'not-selected' ? (
          <span className="badge badge--no">✕ outside window</span>
        ) : null}
        {requiredYearsText(job.required_years) ? (
          <span className="badge badge--accent">{requiredYearsText(job.required_years)}</span>
        ) : null}
        {job.site ? <span className="badge">{job.site}</span> : null}
        {job.job_type ? <span className="badge">{job.job_type}</span> : null}
        {job.is_remote ? <span className="badge badge--accent">remote</span> : null}
        {job.job_level ? <span className="badge">{job.job_level}</span> : null}
        {salary ? <span className="badge badge--muted">{salary}</span> : null}
        {job.date_posted ? <span className="badge badge--muted">{job.date_posted}</span> : null}
      </div>

      {hasFit ? (
        <div className="fit">
          {hasScore ? <FitGauge score={job.score} /> : null}
          <div className="fit__body">
            <div className="fit__verdict">
              {job.verdict && job.verdict !== 'unknown' ? (
                <span className={verdictBadgeClass(job.verdict)}>{job.verdict} fit</span>
              ) : null}
              {matched.length || missing.length ? (
                <span className="badge badge--muted">
                  {matched.length}✓ · {missing.length}✕ skills
                </span>
              ) : null}
            </div>
            {matched.length || missing.length ? (
              <div className="chips">
                {matched.slice(0, 10).map((s, i) => (
                  <span key={`m${i}`} className="chip chip--ok">✓ {s}</span>
                ))}
                {missing.slice(0, 10).map((s, i) => (
                  <span key={`x${i}`} className="chip chip--miss">✕ {s}</span>
                ))}
              </div>
            ) : null}
            {job.reasoning ? <p className="fit__why">{job.reasoning}</p> : null}
          </div>
        </div>
      ) : null}

      {skills.length ? (
        <div className="chips">
          {skills.slice(0, 12).map((s, i) => (
            <span key={i} className="chip">{s}</span>
          ))}
        </div>
      ) : null}

      {dupCount ? (
        <div className="dups">
          <button className="dups__toggle" onClick={() => setDupOpen((v) => !v)}>
            🗂 {dupCount} postings{dupOpen ? ' ▲' : ' ▼'}
          </button>
          {dupOpen ? (
            <ul className="dups__list">
              {group.postings.map((p, i) => (
                <li key={p.id || p.job_url || i} className="dups__item">
                  <span className="dups__meta">
                    {postingMeta(p) || 'posting'}
                    {i === 0 ? <span className="dups__rep"> (shown above)</span> : null}
                  </span>
                  {p.job_url ? (
                    <button className="link-btn" type="button" onClick={() => setDetailsJob(p)}>
                      View details
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {desc ? (
        <div className="card__desc">
          <div className="desc">{desc}</div>
        </div>
      ) : null}

      <div className="card__foot">
        {job.job_url ? (
          <button className="link-btn" type="button" onClick={() => setDetailsJob(job)}>
            View details
          </button>
        ) : <span />}
        {job.id ? <span className="card__id">{job.id}</span> : null}
      </div>
      {detailsJob ? createPortal(
        <JobDetails job={detailsJob} onClose={() => setDetailsJob(null)} />,
        document.body,
      ) : null}
    </article>
  )
}
