import { draftTemplateId } from '../lib/proposalDraftView'
import { PanelLoadingState } from './PanelLoadingState'
import { ProposalDraftView } from './ProposalDraftView'

type Props = {
  open: boolean
  embedded?: boolean
  state: Record<string, unknown> | null
  fingerprint: string | null
  loading: boolean
  syncing?: boolean
  error: string | null
  onCollapse: () => void
  onRefresh: () => void
}

export function ProposalStatePanel({
  open,
  embedded = false,
  state,
  fingerprint,
  loading,
  syncing = false,
  error,
  onCollapse,
  onRefresh,
}: Props) {
  const hasDraft = Boolean(state && Object.keys(state).length > 0)
  const templateId = state ? draftTemplateId(state) : null
  const subtitle = syncing
    ? 'Syncing draft…'
    : fingerprint
      ? `Fingerprint ${fingerprint}`
      : 'Structured draft view'

  return (
    <aside
      className={`artifact-side-panel${open ? ' artifact-side-panel-open' : ''}${
        embedded ? ' artifact-side-panel-embedded' : ''
      }${syncing ? ' proposal-live-panel-syncing' : ''}`}
      aria-hidden={!open}
      aria-label="Proposal draft"
      aria-busy={syncing || loading}
    >
      <div className="artifact-side-panel-inner">
        {syncing && (
          <div className="proposal-live-panel-sync-bar" aria-hidden>
            <span className="proposal-live-panel-sync-bar-fill" />
          </div>
        )}
        <div className="artifact-side-panel-header">
          <div className="proposal-live-panel-heading">
            <div className="proposal-live-panel-title-row">
              <h2 className="artifact-side-panel-title">Proposal draft</h2>
              {templateId ? (
                <span className="proposal-draft-bagel proposal-live-panel-template-bagel">{templateId}</span>
              ) : null}
            </div>
            <p className="proposal-live-panel-subtitle">
              {syncing && <span className="proposal-live-panel-sync-dot" aria-hidden />}
              {subtitle}
            </p>
          </div>
          <div className="artifact-side-panel-actions">
            <button
              type="button"
              className="viz-widget-btn"
              aria-label="Refresh draft"
              title="Refresh"
              onClick={onRefresh}
              disabled={loading}
            >
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                <path d="M21 12a9 9 0 1 1-2.64-6.36" />
                <path d="M21 3v6h-6" />
              </svg>
            </button>
            <button
              type="button"
              className="viz-widget-btn artifact-side-panel-close"
              onClick={onCollapse}
              aria-label="Hide proposal draft"
              title="Hide"
            >
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                aria-hidden
              >
                <path d="M18 6 6 18" />
                <path d="m6 6 12 12" />
              </svg>
            </button>
          </div>
        </div>
        <div className="artifact-side-panel-scroll">
          {loading && !hasDraft && (
            <PanelLoadingState message="Loading draft view…" />
          )}
          {error && !loading && <p className="proposal-live-panel-error">{error}</p>}
          {state && hasDraft ? (
            <ProposalDraftView draft={state} />
          ) : !loading && !error ? (
            <p className="proposal-live-panel-placeholder">No proposal draft yet.</p>
          ) : null}
        </div>
      </div>
    </aside>
  )
}
