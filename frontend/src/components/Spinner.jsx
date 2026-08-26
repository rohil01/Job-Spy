export default function Spinner({ label }) {
  return (
    <span className="spinner" role="status" aria-live="polite">
      <span className="spinner__dot" />
      {label ? <span>{label}</span> : null}
    </span>
  )
}
