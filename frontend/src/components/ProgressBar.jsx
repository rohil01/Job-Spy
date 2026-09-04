// Reusable progress bar. Renders nothing when pct is null/undefined.
export default function ProgressBar({ pct }) {
  if (pct == null) return null
  const value = Math.max(0, Math.min(100, pct))
  return (
    <div
      className="progress"
      role="progressbar"
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className="progress__bar" style={{ width: `${value}%` }} />
    </div>
  )
}
