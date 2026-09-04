import { useEffect, useState } from 'react'
import JobCard from './JobCard.jsx'
import ProgressBar from './ProgressBar.jsx'
import Spinner from './Spinner.jsx'
import ErrorBanner from './ErrorBanner.jsx'

function windowText(min, max) {
  return max == null ? `${min}+ years` : `${min}–${max} years`
}

export default function ScreenView({
  screenRun,
  resume,
  setResume,
  jobs,
  onStartScreen,
}) {
  const [minYears, setMinYears] = useState('0')
  const [maxYears, setMaxYears] = useState('3')

  // Keep the inputs in sync with the window of the active/last run so
  // "Screen again" starts from what's on screen.
  useEffect(() => {
    if (!screenRun) return
    setMinYears(String(screenRun.min ?? 0))
    setMaxYears(screenRun.max == null ? '' : String(screenRun.max))
  }, [screenRun?.min, screenRun?.max])

  const invalidRange = maxYears !== '' && Number(minYears || 0) > Number(maxYears)
  const running = screenRun?.running

  function onFile(e) {
    const f = e.target.files?.[0]
    if (f) setResume(f)
  }

  function run() {
    const min = minYears === '' ? 0 : Number(minYears)
    const max = maxYears === '' ? null : Number(maxYears)
    onStartScreen(min, max)
  }

  const hint =
    screenRun?.error && /AI client|api key|502|503/i.test(screenRun.error.message || '')
      ? 'This calls the AI once per posting. Set a real NVIDIA_API_KEY in the backend .env and restart run_api.py.'
      : null

  const matches = screenRun?.matches || []
  const noMatches = screenRun?.noMatches || []
  const done = matches.length + noMatches.length

  return (
    <section>
      <div className="panel">
        <h3 className="panel__title">1 · Your résumé</h3>
        <input type="file" accept=".docx" onChange={onFile} />
        <div>
          {resume ? (
            <span className="muted small">Loaded: {resume.name}</span>
          ) : (
            <span className="muted small">Upload a .docx résumé to screen against.</span>
          )}
        </div>
      </div>

      <div className="panel">
        <h3 className="panel__title">2 · Experience window &amp; screen</h3>
        <p className="muted">
          One AI call per posting estimates the <strong>years it requires</strong> and scores
          how well your résumé <strong>fits</strong>. Postings whose required experience overlaps
          your window land under <strong>Matches your experience</strong>; the rest under{' '}
          <strong>Doesn’t match</strong> — each showing its fit score.
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
          <button
            className="btn btn--primary"
            onClick={run}
            disabled={!resume || running || invalidRange}
          >
            {running ? <Spinner label="Screening…" /> : screenRun ? 'Screen again' : 'Screen jobs'}
          </button>
          <span className="muted small">
            {invalidRange
              ? ''
              : jobs?.length
                ? `screens the ${jobs.length} loaded posting${jobs.length === 1 ? '' : 's'}`
                : 'uses the latest scraped jobs on disk'}
          </span>
        </div>
        {invalidRange ? (
          <p className="small" style={{ color: 'var(--danger)' }}>
            Min years can’t be greater than max years.
          </p>
        ) : null}
        {!resume ? (
          <p className="muted small">Upload a résumé above to enable screening.</p>
        ) : null}
      </div>

      {screenRun?.error ? <ErrorBanner error={screenRun.error} hint={hint} /> : null}

      {screenRun && !screenRun.error ? (
        <>
          <ProgressBar pct={screenRun.pct} />
          <div className="summary">
            <span className="stat stat--ok"><b>{matches.length}</b> match</span>
            <span className="stat"><b>{noMatches.length}</b> don’t</span>
            <span className="muted small">
              {screenRun.total != null ? `${done}/${screenRun.total} screened · ` : ''}
              window {windowText(screenRun.min ?? 0, screenRun.max)}
              {running ? ' · streaming…' : screenRun.done ? ' · done' : ''}
            </span>
          </div>

          <h3 className="section-title">Matches your experience ({matches.length})</h3>
          {matches.length ? (
            <div className="grid">
              {matches.map((job, i) => (
                <JobCard
                  key={job.id || `match-${i}`}
                  job={job}
                  matchTag="selected"
                />
              ))}
            </div>
          ) : (
            <p className="muted">
              {running ? 'Waiting for the first match…' : 'No postings matched this window.'}
            </p>
          )}

          <h3 className="section-title">Doesn’t match ({noMatches.length})</h3>
          {noMatches.length ? (
            <div className="grid">
              {noMatches.map((job, i) => (
                <JobCard
                  key={job.id || `no-${i}`}
                  job={job}
                  matchTag="not-selected"
                />
              ))}
            </div>
          ) : (
            <p className="muted">{running ? '…' : 'Everything matched your window.'}</p>
          )}
        </>
      ) : !screenRun ? (
        <p className="muted">
          Upload your résumé, set your experience window, and click <b>Screen jobs</b>. Each
          posting is checked one-by-one and sorted into <b>Matches your experience</b> /{' '}
          <b>Doesn’t match</b>, with a fit score on every card.
        </p>
      ) : null}
    </section>
  )
}
