export default function ErrorBanner({ error, hint }) {
  if (!error) return null
  const message = typeof error === 'string' ? error : error.message
  return (
    <div className="error-banner" role="alert">
      <strong>Something went wrong.</strong>
      <div className="error-banner__msg">{message}</div>
      {hint ? <div className="error-banner__hint">{hint}</div> : null}
    </div>
  )
}
