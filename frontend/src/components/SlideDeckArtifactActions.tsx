import { useState } from 'react'
import type { ArtifactSpec } from '../types/artifact'
import { ArtifactDownloadIcon } from './ArtifactDownloadIcon'
import { LoadingSpinner } from './LoadingSpinner'
import { downloadArtifactFile } from '../lib/artifactDownload'

type Props = {
  spec: ArtifactSpec
  variant: 'card'
  expanded?: boolean
  onExpand?: (spec: ArtifactSpec) => void
}

export function SlideDeckArtifactActions({ spec, variant, expanded = false, onExpand }: Props) {
  const [downloading, setDownloading] = useState(false)
  const canDownload = Boolean(spec.download_url)
  const canPreview = Boolean(spec.preview_url)

  const handleDownload = async () => {
    if (!canDownload || downloading) return
    setDownloading(true)
    try {
      await downloadArtifactFile(spec, 'default')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div
      className={`slide-deck-artifact-actions${variant === 'card' ? ' slide-deck-artifact-actions-card' : ''}`}
      role="toolbar"
      aria-label="Slide deck actions"
    >
      <button
        type="button"
        className={`slide-deck-artifact-action-btn${expanded ? ' slide-deck-artifact-action-btn-active' : ''}`}
        aria-label={expanded ? 'Showing in side panel' : 'Open slide preview'}
        title={expanded ? 'Open in side panel' : 'Preview'}
        aria-pressed={expanded}
        disabled={!canPreview}
        onClick={() => onExpand?.(spec)}
      >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
        <span>Preview</span>
      </button>
      <span className="slide-deck-artifact-action-divider" aria-hidden />
      <button
        type="button"
        className="slide-deck-artifact-action-btn"
        aria-label={downloading ? 'Downloading' : 'Download slide source'}
        title={downloading ? 'Downloading…' : 'Download'}
        disabled={!canDownload || downloading}
        aria-busy={downloading}
        onClick={() => void handleDownload()}
      >
        {downloading ? <LoadingSpinner size="sm" /> : <ArtifactDownloadIcon />}
        <span>Download</span>
      </button>
    </div>
  )
}
