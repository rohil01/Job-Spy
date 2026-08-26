import { useState } from 'react'

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

export default function JobCard({ job, onUse, selected }) {
  const [open, setOpen] = useState(false)
  const salary = salaryText(job)
  const desc = job.description || ''
  const skills = Array.isArray(job.skills) ? job.skills : []

  return (
    <article className={`card ${selected ? 'card--selected' : ''}`}>
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
            {selected ? 'Selected ✓' : 'Use for resume →'}
          </button>
        ) : null}
      </div>

      <div className="badges">
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

      {skills.length ? (
        <div className="chips">
          {skills.slice(0, 12).map((s, i) => (
            <span key={i} className="chip">{s}</span>
          ))}
        </div>
      ) : null}

      {desc ? (
        <div className="card__desc">
          <div className={open ? 'desc desc--open' : 'desc'}>{desc}</div>
          <button className="link-btn" onClick={() => setOpen((v) => !v)}>
            {open ? 'Show less' : 'Show more'}
          </button>
        </div>
      ) : null}

      <div className="card__foot">
        {job.job_url ? (
          <a className="link" href={job.job_url} target="_blank" rel="noreferrer">
            View original ↗
          </a>
        ) : <span />}
        {job.id ? <span className="card__id">{job.id}</span> : null}
      </div>
    </article>
  )
}
