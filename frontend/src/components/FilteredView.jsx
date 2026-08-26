import { useState } from 'react'
import { filterExperience } from '../api.js'
import JobCard from './JobCard.jsx'
import Spinner from './Spinner.jsx'
import ErrorBanner from './ErrorBanner.jsx'

function windowText(min, max) {
  return max == null ? `${min}+ years` : `${min}–${max} years`
}

export default function FilteredView({ jobs, onUseJob, selectedJob }) {
  const [minYears, setMinYears] = useState('0')
  const [maxYears, setMaxYears] = useState('3')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Max blank = open-ended ("N+"), which is always a valid window.
  const invalidRange = maxYears !== '' && Number(minYears || 0) > Number(maxYears)

  async function run() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const min = minYears === '' ? 0 : Number(minYears)
      const max = maxYears === '' ? null : Number(maxYears)
      // Filter the currently loaded jobs; if none are loaded the server falls
      // back to the latest scraped jobs on disk.
      const data = await filterExperience(jobs && jobs.length ? jobs : null, min, max)
      setResult(data)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }

  const hint =
    error?.status === 502
      ? 'This calls the AI once per job. Set a real NVIDIA_API_KEY in the backend .env and restart run_api.py.'
      : null

  return (
    <section>
      <div className="panel">
        <p className="muted">
          Keeps only jobs whose <strong>required years of experience</strong> overlap your
          target window. <strong>Runs one AI call per job</strong> — this can be slow and needs
          a working API key.
        </p>
        <div className="toolbar">
          <label className="inline">
            min years
            <input
              className="input input--num"
              type="number"
              min="0"
              value={minYears}
              onChange={(e) => setMinYears(e.target.value)}
            />
          </label>
          <label className="inline">
            max years
            <input
              className="input input--num"
              type="number"
              min="0"
              value={maxYears}
              onChange={(e) => setMaxYears(e.target.value)}
              placeholder="N+"
            />
          </label>
          <span className="muted small">leave max blank for “{minYears || 0}+ years”</span>
        </div>
        {invalidRange ? (
          <p className="small" style={{ color: 'var(--danger)' }}>
            Min years can’t be greater than max years.
          </p>
        ) : null}
        <button className="btn btn--primary" onClick={run} disabled={loading || invalidRange}>
          {loading ? (
            <Spinner label="Filtering…" />
          ) : (
            `Run experience filter${jobs?.length ? ` on ${jobs.length} loaded jobs` : ''}`
          )}
        </button>
        {jobs?.length ? null : (
          <p className="muted small">
            No jobs loaded — the server will use the latest scraped jobs on disk.
          </p>
        )}
      </div>

      <ErrorBanner error={error} hint={hint} />

      {result ? (
        <>
          <div className="summary">
            <span className="stat"><b>{result.input_count}</b> considered</span>
            <span className="stat stat--ok"><b>{result.filtered_count}</b> matched</span>
            <span className="muted small">
              requiring {windowText(result.min_years, result.max_years)}
            </span>
          </div>
          {result.filtered_count === 0 ? (
            <p className="muted">
              No jobs required {windowText(result.min_years, result.max_years)}.
            </p>
          ) : (
            <div className="grid">
              {result.jobs.map((job, i) => (
                <JobCard
                  key={job.id || i}
                  job={job}
                  onUse={onUseJob}
                  selected={selectedJob && selectedJob.id === job.id}
                />
              ))}
            </div>
          )}
        </>
      ) : null}
    </section>
  )
}
