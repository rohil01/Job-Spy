import { useEffect, useState } from 'react'
import { getHealth, API_BASE } from './api.js'
import HealthPill from './components/HealthPill.jsx'
import JobsView from './components/JobsView.jsx'
import FilteredView from './components/FilteredView.jsx'
import ResumeView from './components/ResumeView.jsx'

const TABS = [
  { key: 'jobs', label: 'Jobs' },
  { key: 'filtered', label: 'Filtered' },
  { key: 'resume', label: 'Resume' },
]

export default function App() {
  const [tab, setTab] = useState('jobs')
  const [health, setHealth] = useState(null)
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState(null)
  const [resume, setResume] = useState(null)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: 'unreachable', ai_client_ready: false }))
  }, [])

  function useJob(job) {
    setSelectedJob(job)
    setTab('resume')
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand__logo">🕵️</span>
          <div>
            <h1 className="brand__name">JobSpy</h1>
            <p className="brand__tag">Browse jobs · filter by experience · tailor your resume</p>
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
          </button>
        ))}
      </nav>

      <main className="main">
        {tab === 'jobs' ? (
          <JobsView jobs={jobs} setJobs={setJobs} selectedJob={selectedJob} onUseJob={useJob} />
        ) : null}
        {tab === 'filtered' ? (
          <FilteredView jobs={jobs} onUseJob={useJob} selectedJob={selectedJob} />
        ) : null}
        {tab === 'resume' ? (
          <ResumeView
            resume={resume}
            setResume={setResume}
            jobs={jobs}
            selectedJob={selectedJob}
            setSelectedJob={setSelectedJob}
          />
        ) : null}
      </main>

      <footer className="footer">
        <span>API: <code>{API_BASE}</code></span>
      </footer>
    </div>
  )
}
