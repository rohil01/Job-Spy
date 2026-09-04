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

function postingMeta(p) {
  return [p.site, p.location, p.date_posted].filter(Boolean).join(' · ')
}

function scoreBadgeClass(score) {
  if (typeof score !== 'number') return 'badge'
  if (score >= 75) return 'badge badge--score-high'
  if (score >= 50) return 'badge badge--score-mid'
  return 'badge badge--score-low'
}

function verdictBadgeClass(verdict) {
  const v = (verdict || '').toLowerCase()
  if (v.includes('strong')) return 'badge badge--ok'
  if (v.includes('good') || v.includes('moderate')) return 'badge badge--warn'
  if (v.includes('weak') || v.includes('poor')) return 'badge badge--no'
  return 'badge'
}

// `matchTag` conveys the experience verdict ('selected' | 'not-selected') and is
// kept distinct from the resume `selected` prop (the action button). `useLabel`
// overrides that button's default text. Screening adds job.score / job.verdict /
// job.matched_skills / job.missing_skills / job.reasoning, rendered when present.
export default function JobCard({ job, onUse, selected, group, matchTag, useLabel }) {
  const [open, setOpen] = useState(false)
  const [dupOpen, setDupOpen] = useState(false)
  const salary = salaryText(job)
  const desc = job.description || ''
  const skills = Array.isArray(job.skills) ? job.skills : []
  const matched = Array.isArray(job.matched_skills) ? job.matched_skills : []
  const missing = Array.isArray(job.missing_skills) ? job.missing_skills : []
  const dupCount = group && group.count > 1 ? group.count : 0

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
        {typeof job.score === 'number' ? (
          <span className={scoreBadgeClass(job.score)}>{job.score}/100</span>
        ) : null}
        {job.verdict && job.verdict !== 'unknown' ? (
          <span className={verdictBadgeClass(job.verdict)}>{job.verdict}</span>
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
                    <a className="link" href={p.job_url} target="_blank" rel="noreferrer">
                      View ↗
                    </a>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
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
