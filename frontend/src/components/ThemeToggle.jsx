import { useEffect, useState } from 'react'

// Reads the theme the no-flash script in index.html already applied, then keeps
// <html data-theme> and localStorage in sync when the user flips it.
function initialTheme() {
  if (typeof document !== 'undefined') {
    const applied = document.documentElement.getAttribute('data-theme')
    if (applied) return applied
  }
  return 'light'
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState(initialTheme)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try {
      localStorage.setItem('jobspy-theme', theme)
    } catch {
      /* storage unavailable — the toggle still works for this session */
    }
  }, [theme])

  const dark = theme === 'dark'

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={() => setTheme(dark ? 'light' : 'dark')}
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={dark ? 'Light theme' : 'Dark theme'}
    >
      {dark ? (
        // sun
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        // moon
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
        </svg>
      )}
    </button>
  )
}
