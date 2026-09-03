import { useState } from 'react'
import type { ActivityEntry } from '../lib/messageActivity'

type Props = {
  item: ActivityEntry
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={`process-step-chevron ${open ? 'process-step-chevron-open' : ''}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  )
}

function SpinnerIcon() {
  return (
    <svg
      className="process-step-spinner"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden
    >
      <path d="M12 2v4" />
      <path d="M12 18v4" opacity="0.3" />
      <path d="m4.93 4.93 2.83 2.83" opacity="0.7" />
      <path d="m16.24 16.24 2.83 2.83" opacity="0.3" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg
      className="process-step-check"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  )
}

function ErrorIcon() {
  return (
    <svg
      className="process-step-error-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v5" />
      <path d="M12 16h.01" />
    </svg>
  )
}

function StatusIcon({ status }: { status: ActivityEntry['status'] }) {
  if (status === 'running') return <SpinnerIcon />
  if (status === 'error') return <ErrorIcon />
  if (status === 'cancelled') return <CancelIcon />
  return <CheckIcon />
}

function CancelIcon() {
  return (
    <svg
      className="process-step-cancel-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden
    >
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  )
}

function runningHintForTitle(title: string): string {
  if (title === 'render_slidev') return 'Building slides…'
  if (title === 'render_html_ppt') return 'Publishing HTML deck…'
  if (title === 'load_slide') return 'Loading…'
  return 'Running…'
}

export function ProcessStepCard({ item }: Props) {
  const showRequest = Boolean(item.request?.trim())
  const showResponse = Boolean(item.response?.trim())
  const showRunningHint = item.status === 'running' && item.kind !== 'reasoning'
  const showLegacyDetail =
    item.kind === 'reasoning' || (!showRequest && !showResponse && Boolean(item.detail.trim()))
  const [open, setOpen] = useState(false)

  return (
    <div className={`process-step process-step-${item.status}`}>
      <button
        type="button"
        className="process-step-header"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <StatusIcon status={item.status} />
        <span className="process-step-title">{item.title}</span>
        {showRunningHint ? (
          <span className="process-step-running-label">{runningHintForTitle(item.title)}</span>
        ) : null}
        <ChevronIcon open={open} />
      </button>
      {open && (showRequest || showResponse || showRunningHint || showLegacyDetail) && (
        <div className="process-step-body">
          {showRequest ? (
            <div className="process-step-section">
              <div className="process-step-section-label">Request</div>
              <pre className="process-step-detail process-step-detail-compact">{item.request}</pre>
            </div>
          ) : null}
          {showResponse ? (
            <div className="process-step-section">
              <div className="process-step-section-label">Response</div>
              <pre className="process-step-detail process-step-detail-compact">{item.response}</pre>
            </div>
          ) : null}
          {showRunningHint && !showResponse ? (
            <div className="process-step-section">
              <div className="process-step-section-label">Response</div>
              <p className="process-step-running-hint">Running…</p>
            </div>
          ) : null}
          {showLegacyDetail ? (
            <pre className="process-step-detail process-step-detail-compact">{item.detail}</pre>
          ) : null}
        </div>
      )}
    </div>
  )
}
