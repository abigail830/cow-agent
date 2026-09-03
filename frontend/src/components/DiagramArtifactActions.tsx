import { useState } from 'react'
import type { ArtifactSpec } from '../types/artifact'
import { copyArtifactSource, downloadArtifactFile, canDownloadDiagramPng } from '../lib/artifactDownload'
import { ArtifactCopyIcon } from './ArtifactCopyIcon'
import { ArtifactDownloadIcon } from './ArtifactDownloadIcon'
import { LoadingSpinner } from './LoadingSpinner'
import { VizMaximizeIcon } from './VizMaximizeIcon'

type DownloadVariant = 'png' | 'svg'

type Props = {
  spec: ArtifactSpec
  variant: 'card' | 'panel'
  expanded?: boolean
  onExpand?: (spec: ArtifactSpec) => void
  onClose?: () => void
}

export function DiagramArtifactActions({
  spec,
  variant,
  expanded = false,
  onExpand,
  onClose,
}: Props) {
  const [downloading, setDownloading] = useState<DownloadVariant | null>(null)
  const canCopySource = Boolean(spec.source?.trim())
  const canDownloadPng = canDownloadDiagramPng(spec)
  const isDownloading = downloading !== null

  async function handleDownload(variant: DownloadVariant) {
    if (isDownloading) return
    setDownloading(variant)
    try {
      await downloadArtifactFile(spec, variant === 'png' ? 'png' : 'default')
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div
      className={`diagram-artifact-card-actions${variant === 'panel' ? ' diagram-artifact-panel-actions' : ''}`}
      role="toolbar"
      aria-label="Diagram actions"
    >
      <button
        type="button"
        className="diagram-artifact-action-btn"
        aria-label="Copy PlantUML source"
        title="Copy source"
        disabled={!canCopySource}
        onClick={() => void copyArtifactSource(spec)}
      >
        <ArtifactCopyIcon />
        <span>Copy</span>
      </button>
      <button
        type="button"
        className="diagram-artifact-action-btn"
        aria-label={downloading === 'png' ? 'Downloading PNG' : 'Download PNG'}
        title={downloading === 'png' ? 'Downloading…' : 'Download PNG'}
        disabled={!canDownloadPng || isDownloading}
        aria-busy={downloading === 'png'}
        onClick={() => void handleDownload('png')}
      >
        {downloading === 'png' ? <LoadingSpinner size="sm" /> : <ArtifactDownloadIcon />}
        <span>PNG</span>
      </button>
      <button
        type="button"
        className="diagram-artifact-action-btn"
        aria-label={downloading === 'svg' ? 'Downloading SVG' : 'Download SVG'}
        title={downloading === 'svg' ? 'Downloading…' : 'Download SVG'}
        disabled={isDownloading}
        aria-busy={downloading === 'svg'}
        onClick={() => void handleDownload('svg')}
      >
        {downloading === 'svg' ? <LoadingSpinner size="sm" /> : <ArtifactDownloadIcon />}
        <span>SVG</span>
      </button>
      {variant === 'card' ? (
        <button
          type="button"
          className={`diagram-artifact-action-btn${expanded ? ' diagram-artifact-action-btn-active' : ''}`}
          aria-label={expanded ? 'Showing in side panel' : 'Open preview panel'}
          title={expanded ? 'Open in side panel' : 'Open preview panel'}
          aria-pressed={expanded}
          onClick={() => onExpand?.(spec)}
        >
          <VizMaximizeIcon />
          <span>Preview</span>
        </button>
      ) : (
        <button
          type="button"
          className="diagram-artifact-action-btn"
          aria-label="Close preview"
          title="Close"
          onClick={onClose}
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
          <span>Close</span>
        </button>
      )}
    </div>
  )
}
