import { useState } from 'react'
import type { ArtifactSpec } from '../types/artifact'
import { ArtifactDownloadIcon } from './ArtifactDownloadIcon'
import { ArtifactPreviewIcon } from './ArtifactPreviewIcon'
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

  if (variant !== 'card') return null

  return (
    <div className="artifact-inline-card-actions slide-deck-artifact-actions" role="toolbar" aria-label="Slide deck actions">
      <div className="artifact-inline-action-group">
        <button
          type="button"
          className={`artifact-inline-action-btn${expanded ? ' artifact-inline-action-btn-active' : ''}`}
          aria-label={expanded ? 'Showing in side panel' : 'Open slide preview'}
          title={expanded ? 'Open in side panel' : 'Preview'}
          aria-pressed={expanded}
          disabled={!canPreview}
          onClick={() => onExpand?.(spec)}
        >
          <ArtifactPreviewIcon />
          <span>Preview</span>
        </button>
        <span className="artifact-inline-action-divider" aria-hidden />
        <button
          type="button"
          className="artifact-inline-action-btn"
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
    </div>
  )
}
