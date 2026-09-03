import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { downloadBinaryUrl } from '../lib/downloadBinaryUrl'
import { PanelLoadingState } from './PanelLoadingState'
import { LoadingSpinner } from './LoadingSpinner'
import { MarkdownContent } from './MarkdownContent'
import { ArtifactDownloadIcon } from './ArtifactDownloadIcon'
import type { ProposalPreview } from '../types/proposalPreview'

type Props = {
  chatId: string | null
  open: boolean
  embedded?: boolean
  preview: ProposalPreview | null
  loading: boolean
  syncing?: boolean
  error: string | null
  onCollapse: () => void
  onRefresh: () => void
}

function downloadPreview(preview: ProposalPreview) {
  if (!preview.markdown) return
  const blob = new Blob([preview.markdown], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = preview.filename || 'proposal.md'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export function ProposalLivePanel({
  chatId,
  open,
  embedded = false,
  preview,
  loading,
  syncing = false,
  error,
  onCollapse,
  onRefresh,
}: Props) {
  const [exportingWord, setExportingWord] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCollapse()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onCollapse])

  const title = preview?.title || 'Proposal draft'
  const canDownload = Boolean(preview?.markdown)
  const wordExport = preview?.export?.word
  const canExportWord = Boolean(
    chatId &&
      wordExport?.available &&
      preview?.completeness.ready_to_generate &&
      !exportingWord,
  )
  const missing = preview?.completeness.missing_required ?? []
  const subtitle = syncing
    ? 'Syncing draft…'
    : 'Current draft · live from state'

  const wordExportTitle = !wordExport?.available
    ? 'Word template not configured for this proposal'
    : !preview?.completeness.ready_to_generate
      ? 'Complete required fields before exporting Word'
      : 'Export Word (.docx)'

  async function handleExportWord() {
    if (!chatId || !canExportWord) return
    setExportingWord(true)
    setExportError(null)
    try {
      const result = await api.exportProposalWord(chatId)
      if (result.download_url) {
        await downloadBinaryUrl(result.download_url, result.filename)
      }
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Word export failed')
    } finally {
      setExportingWord(false)
    }
  }

  return (
    <aside
      className={`artifact-side-panel${open ? ' artifact-side-panel-open' : ''}${
        embedded ? ' artifact-side-panel-embedded' : ''
      }${syncing ? ' proposal-live-panel-syncing' : ''}`}
      aria-hidden={!open}
      aria-label={title}
      aria-busy={syncing || loading || exportingWord}
    >
      <div className="artifact-side-panel-inner">
        {syncing && (
          <div className="proposal-live-panel-sync-bar" aria-hidden>
            <span className="proposal-live-panel-sync-bar-fill" />
          </div>
        )}
        <div className="artifact-side-panel-header">
          <div className="proposal-live-panel-heading">
            <h2 className="artifact-side-panel-title" title={title}>
              {title}
            </h2>
            <p className="proposal-live-panel-subtitle">
              {syncing && <span className="proposal-live-panel-sync-dot" aria-hidden />}
              {subtitle}
            </p>
          </div>
          <div className="artifact-side-panel-actions">
            <button
              type="button"
              className="viz-widget-btn"
              aria-label="Refresh preview"
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
              className="viz-widget-btn proposal-live-panel-export-btn"
              aria-label="Download markdown draft"
              title="Download markdown draft"
              onClick={() => preview && downloadPreview(preview)}
              disabled={!canDownload}
            >
              <ArtifactDownloadIcon />
              <span className="proposal-live-panel-format-label">MD</span>
            </button>
            {wordExport?.available ? (
              <button
                type="button"
                className="viz-widget-btn proposal-live-panel-export-btn"
                aria-label="Export Word document"
                title={wordExportTitle}
                onClick={() => void handleExportWord()}
                disabled={!canExportWord}
              >
                {exportingWord ? (
                  <LoadingSpinner size="sm" />
                ) : (
                  <>
                    <ArtifactDownloadIcon />
                    <span className="proposal-live-panel-format-label">WORD</span>
                  </>
                )}
              </button>
            ) : null}
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
          {loading && !preview?.markdown && (
            <PanelLoadingState message="Loading proposal preview…" />
          )}
          {error && !loading && <p className="proposal-live-panel-error">{error}</p>}
          {exportError && <p className="proposal-live-panel-error">{exportError}</p>}
          {!loading && !error && !preview?.markdown && !preview?.message && (
            <p className="proposal-live-panel-placeholder">
              Send a message to start drafting your proposal.
            </p>
          )}
          {!loading && !error && preview?.status !== 'ok' && preview?.message && (
            <p className="proposal-live-panel-placeholder">{preview.message}</p>
          )}
          {!loading && !error && missing.length > 0 && (
            <p className="proposal-live-panel-hint">
              Draft preview — {missing.length} required field{missing.length === 1 ? '' : 's'}{' '}
              still open.
            </p>
          )}
          {preview?.markdown ? (
            <MarkdownContent
              content={preview.markdown}
              className={`markdown-body artifact-markdown-body${
                syncing ? ' proposal-live-panel-content-syncing' : ''
              }`}
              allowHtml
            />
          ) : null}
        </div>
      </div>
    </aside>
  )
}
