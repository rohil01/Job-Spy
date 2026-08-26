export default function HealthPill({ health }) {
  if (!health) {
    return <span className="pill pill--muted"><span className="pill__dot" />checking…</span>
  }
  if (health.status === 'unreachable') {
    return <span className="pill pill--warn"><span className="pill__dot" />backend offline</span>
  }
  const ready = health.ai_client_ready
  return (
    <span
      className={`pill ${ready ? 'pill--ok' : 'pill--warn'}`}
      title={health.ai_model || ''}
    >
      <span className="pill__dot" />
      {ready ? 'AI ready' : 'AI not configured'}
      {health.ai_model ? <span className="pill__model">{health.ai_model}</span> : null}
    </span>
  )
}
