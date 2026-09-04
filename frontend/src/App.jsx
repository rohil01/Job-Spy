import { useEffect, useMemo, useRef, useState } from 'react'
import { getHealth, API_BASE, streamScreen } from './api.js'
import HealthPill from './components/HealthPill.jsx'
import JobsView from './components/JobsView.jsx'
import ScreenView from './components/ScreenView.jsx'

const TABS = [
  { key: 'jobs', label: 'Jobs' },
  { key: 'screen', label: 'Screen' },
]

export default function App() {
  const [tab, setTab] = useState('jobs')
  const [health, setHealth] = useState(null)
  // `groups` is the source of truth for scrape results; the flat job list is derived.
  const [groups, setGroups] = useState([])
  // The résumé (a File) is uploaded once and shared by the screening workflow.
  const [resume, setResume] = useState(null)
  const [screenRun, setScreenRun] = useState(null)
  const screenAbort = useRef(null)

  const jobs = useMemo(() => groups.flatMap((g) => g.postings || []), [groups])

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: 'unreachable', ai_client_ready: false }))
  }, [])

  // Screen every posting against the résumé + target window: one combined AI
  // call per job estimates its required experience AND scores the fit. Results
  // stream into two sections (matches / doesn't match). Callable from ScreenView.
  async function startScreen(minYears, maxYears) {
    if (!resume) {
      setScreenRun({
        running: false, min: minYears, max: maxYears, pct: 0, total: null,
        matches: [], noMatches: [], done: false,
        error: new Error('Upload a .docx résumé first.'),
      })
      return
    }
    if (screenAbort.current) screenAbort.current.abort()
    const controller = new AbortController()
    screenAbort.current = controller

    setTab('screen')
    setScreenRun({
      running: true,
      min: minYears,
      max: maxYears,
      pct: 0,
      total: null,
      matches: [],
      noMatches: [],
      done: false,
      error: null,
    })

    try {
      await streamScreen(
        resume,
        jobs && jobs.length ? jobs : null,
        minYears,
        maxYears,
        (ev) => {
          setScreenRun((prev) => {
            if (!prev) return prev
            if (ev.type === 'start') {
              return { ...prev, total: ev.total, min: ev.min_years, max: ev.max_years }
            }
            if (ev.type === 'job') {
              const bucket = ev.match ? 'matches' : 'noMatches'
              return { ...prev, pct: ev.percent, [bucket]: [...prev[bucket], ev.job] }
            }
            if (ev.type === 'done') {
              return { ...prev, running: false, done: true, pct: 100 }
            }
            if (ev.type === 'error') {
              return { ...prev, running: false, error: new Error(ev.message) }
            }
            return prev
          })
        },
        { signal: controller.signal },
      )
      // Stream ended without a terminal event -> just stop the spinner.
      setScreenRun((prev) => (prev && prev.running ? { ...prev, running: false } : prev))
    } catch (e) {
      if (e.name === 'AbortError') return
      setScreenRun((prev) => (prev ? { ...prev, running: false, error: e } : prev))
    }
  }

  const screenCount = screenRun ? screenRun.matches.length + screenRun.noMatches.length : 0

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand__logo">🕵️</span>
          <div>
            <h1 className="brand__name">JobSpy</h1>
            <p className="brand__tag">Browse jobs · screen against your résumé · tailor your resume</p>
          </div>
        </div>
        <HealthPill health={health} />
      </header>

      {health && health.status === 'unreachable' ? (
        <div className="error-banner" role="alert">
          <strong>Can’t reach the backend.</strong>
          <div className="error-banner__msg">
            Start it with <code>run_api.py --port 8000</code>, or set <code>VITE_API_BASE</code>.
            Currently trying <code>{API_BASE}</code>.
          </div>
        </div>
      ) : null}

      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab ${tab === t.key ? 'tab--active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
            {t.key === 'jobs' && jobs.length ? <span className="tab__count">{jobs.length}</span> : null}
            {t.key === 'screen' && screenCount ? <span className="tab__count">{screenCount}</span> : null}
          </button>
        ))}
      </nav>

      <main className="main">
        {tab === 'jobs' ? (
          <JobsView groups={groups} setGroups={setGroups} />
        ) : null}
        {tab === 'screen' ? (
          <ScreenView
            screenRun={screenRun}
            resume={resume}
            setResume={setResume}
            jobs={jobs}
            onStartScreen={startScreen}
          />
        ) : null}
      </main>

      <footer className="footer">
        <span>API: <code>{API_BASE}</code></span>
      </footer>
    </div>
  )
}
