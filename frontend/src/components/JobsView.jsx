import { useState, useEffect } from 'react'
import { getJobs, startScrape, getScrapeStatus, getScrapeConfig } from '../api.js'
import JobCard from './JobCard.jsx'
import Spinner from './Spinner.jsx'
import ErrorBanner from './ErrorBanner.jsx'

// Job boards supported by the scraper (jobsniffer).
const ALL_SITES = [
  'linkedin',
  'indeed',
  'glassdoor',
  'google',
  'ziprecruiter',
  'naukri',
  'bayt',
  'bdjobs',
]

const EMPTY_FORM = {
  sites: [],
  search_terms: '',
  location: '',
  results_wanted: '',
  hours_old: '',
  country_indeed: '',
  linkedin_fetch_description: true,
  scrape_cooldown_minutes: '',
}

export default function JobsView({ jobs, setJobs, selectedJob, onUseJob }) {
  const [loading, setLoading] = useState(false)
  const [scraping, setScraping] = useState(false)
  const [error, setError] = useState(null)
  const [limit, setLimit] = useState('')
  const [scrapeMsg, setScrapeMsg] = useState('')
  const [scrapePct, setScrapePct] = useState(null)
  const [showFilters, setShowFilters] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)

  // Prefill the scrape filters from the backend config once, on mount.
  useEffect(() => {
    let cancelled = false
    getScrapeConfig()
      .then((cfg) => {
        if (cancelled) return
        setForm({
          sites: Array.isArray(cfg.sites) ? cfg.sites : [],
          search_terms: (cfg.search_terms || []).join(', '),
          location: cfg.location || '',
          results_wanted: cfg.results_wanted ?? '',
          hours_old: cfg.hours_old ?? '',
          country_indeed: cfg.country_indeed || '',
          linkedin_fetch_description: cfg.linkedin_fetch_description ?? true,
          scrape_cooldown_minutes: cfg.scrape_cooldown_minutes ?? '',
        })
      })
      .catch(() => {
        /* backend may be down; leave the empty form and rely on config defaults */
      })
    return () => {
      cancelled = true
    }
  }, [])

  function setField(key, value) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  function toggleSite(site) {
    setForm((f) => ({
      ...f,
      sites: f.sites.includes(site)
        ? f.sites.filter((s) => s !== site)
        : [...f.sites, site],
    }))
  }

  // Only send fields the user actually set; omitted ones fall back to config.py.
  function buildParams() {
    const p = {}
    if (form.sites.length) p.sites = form.sites
    const terms = form.search_terms
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)
    if (terms.length) p.search_terms = terms
    if (form.location.trim()) p.location = form.location.trim()
    if (String(form.results_wanted).trim() !== '') p.results_wanted = Number(form.results_wanted)
    if (String(form.hours_old).trim() !== '') p.hours_old = Number(form.hours_old)
    if (form.country_indeed.trim()) p.country_indeed = form.country_indeed.trim()
    if (String(form.scrape_cooldown_minutes).trim() !== '')
      p.scrape_cooldown_minutes = Number(form.scrape_cooldown_minutes)
    p.linkedin_fetch_description = form.linkedin_fetch_description
    return p
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await getJobs(limit ? Number(limit) : undefined)
      setJobs(data.jobs || [])
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }

  async function scrape() {
    setError(null)
    setScraping(true)
    setScrapePct(0)
    setScrapeMsg('Starting scrape…')
    try {
      const { run_id } = await startScrape(buildParams())
      // Poll until the background scrape finishes.
      // eslint-disable-next-line no-constant-condition
      while (true) {
        await new Promise((r) => setTimeout(r, 2000))
        const s = await getScrapeStatus(run_id)
        if (typeof s.percent === 'number') setScrapePct(s.percent)
        setScrapeMsg(`Scrape ${s.status}${s.progress ? ` — ${s.progress}` : ''}`)
        if (s.status === 'completed') {
          setScrapePct(100)
          setScrapeMsg(`Scrape complete — ${s.result?.count ?? 0} jobs found.`)
          await load()
          break
        }
        if (s.status === 'failed') {
          setError(new Error(s.error || 'Scrape failed'))
          setScrapeMsg('')
          setScrapePct(null)
          break
        }
      }
    } catch (e) {
      setError(e)
      setScrapeMsg('')
      setScrapePct(null)
    } finally {
      setScraping(false)
    }
  }

  return (
    <section>
      <div className="toolbar">
        <button className="btn btn--primary" onClick={load} disabled={loading}>
          {loading ? <Spinner label="Loading…" /> : 'Load jobs'}
        </button>
        <label className="inline">
          limit
          <input
            className="input input--num"
            type="number"
            min="1"
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
            placeholder="all"
          />
        </label>
        <button className="btn" onClick={() => setShowFilters((v) => !v)}>
          {showFilters ? 'Hide scrape filters' : 'Scrape filters'}
        </button>
        <button className="btn" onClick={scrape} disabled={scraping}>
          {scraping ? <Spinner label="Scraping…" /> : 'Scrape fresh'}
        </button>
        {scrapeMsg ? <span className="muted small">{scrapeMsg}</span> : null}
      </div>

      {scrapePct !== null ? (
        <div className="progress" role="progressbar" aria-valuenow={Math.round(scrapePct)} aria-valuemin={0} aria-valuemax={100}>
          <div className="progress__bar" style={{ width: `${scrapePct}%` }} />
        </div>
      ) : null}

      {showFilters ? (
        <div className="panel">
          <h3 className="panel__title">Scrape filters</h3>

          <div className="field">
            <label className="field__label">
              Search terms <span className="muted small">(comma-separated; one pass per term)</span>
            </label>
            <input
              className="select"
              type="text"
              value={form.search_terms}
              onChange={(e) => setField('search_terms', e.target.value)}
              placeholder="AI Engineer, Backend Engineer"
            />
          </div>

          <div className="field">
            <label className="field__label">Sites</label>
            <div className="levels">
              {ALL_SITES.map((s) => (
                <label
                  key={s}
                  className={`checkchip ${form.sites.includes(s) ? 'checkchip--on' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={form.sites.includes(s)}
                    onChange={() => toggleSite(s)}
                  />
                  {s}
                </label>
              ))}
            </div>
          </div>

          <div className="toolbar">
            <label className="inline">
              location
              <input
                className="input"
                type="text"
                value={form.location}
                onChange={(e) => setField('location', e.target.value)}
              />
            </label>
            <label className="inline">
              country (Indeed)
              <input
                className="input"
                type="text"
                value={form.country_indeed}
                onChange={(e) => setField('country_indeed', e.target.value)}
              />
            </label>
          </div>

          <div className="toolbar">
            <label className="inline">
              results / site
              <input
                className="input input--num"
                type="number"
                min="1"
                value={form.results_wanted}
                onChange={(e) => setField('results_wanted', e.target.value)}
              />
            </label>
            <label className="inline">
              hours old
              <input
                className="input input--num"
                type="number"
                min="1"
                value={form.hours_old}
                onChange={(e) => setField('hours_old', e.target.value)}
              />
            </label>
            <label className="inline">
              cooldown (min)
              <input
                className="input input--num"
                type="number"
                min="0"
                step="0.1"
                value={form.scrape_cooldown_minutes}
                onChange={(e) => setField('scrape_cooldown_minutes', e.target.value)}
              />
            </label>
            <label className="inline">
              <input
                type="checkbox"
                checked={form.linkedin_fetch_description}
                onChange={(e) => setField('linkedin_fetch_description', e.target.checked)}
              />
              fetch full LinkedIn descriptions
            </label>
          </div>

          <p className="muted small">
            Blank fields fall back to the server defaults from config.py. Cooldown
            is the pause between search terms in minutes (0.5 = 30s; 0 disables).
          </p>
        </div>
      ) : null}

      <ErrorBanner error={error} />

      {jobs.length === 0 && !loading ? (
        <p className="muted">
          No jobs loaded yet. Click <b>Load jobs</b> to read the latest scraped results,
          or <b>Scrape fresh</b> to fetch new ones (runs against live job boards).
        </p>
      ) : (
        <div className="grid">
          {jobs.map((job, i) => (
            <JobCard
              key={job.id || i}
              job={job}
              onUse={onUseJob}
              selected={selectedJob && selectedJob.id === job.id}
            />
          ))}
        </div>
      )}
    </section>
  )
}
