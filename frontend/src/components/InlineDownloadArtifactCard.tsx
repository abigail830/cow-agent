import { useState } from 'react'
import type { ArtifactSpec } from '../types/artifact'
import { artifactCardSubtitle, isUdocPreviewableArtifact } from '../lib/artifactKinds'
import {
  ArtifactCoverIllustration,
  resolveArtifactCoverKind,
} from './ArtifactCoverIllustration'
import { ArtifactPreviewIcon } from './ArtifactPreviewIcon'
import { ArtifactDownloadIcon } from './ArtifactDownloadIcon'
import { LoadingSpinner } from './LoadingSpinner'
import { downloadArtifactFile } from '../lib/artifactDownload'

type Props = {
  spec: ArtifactSpec
  showDownload?: boolean
  expanded?: boolean
  onExpand?: (spec: ArtifactSpec) => void
}

function canDownloadSpec(spec: ArtifactSpec): boolean {
  return Boolean(spec.download_url?.trim()) || Boolean(spec.content?.trim())
}

export function InlineDownloadArtifactCard({
  spec,
  showDownload = true,
  expanded = false,
  onExpand,
}: Props) {
  const [downloading, setDownloading] = useState(false)
  const canDownload = showDownload && canDownloadSpec(spec)
  const canPreview = isUdocPreviewableArtifact(spec)
  const coverKind = resolveArtifactCoverKind(spec)

  async function handleDownload() {
    if (!canDownload || downloading) return
    setDownloading(true)
    try {
      await downloadArtifactFile(spec)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div
      className={`artifact-inline-card inline-download-artifact-card${expanded ? ' artifact-inline-card-expanded' : ''}`}
      aria-label={spec.title}
    >
      <ArtifactCoverIllustration kind={coverKind} />
      <div className="artifact-inline-card-main">
        <h4 className="artifact-inline-card-title" title={spec.title}>
          {spec.title}
        </h4>
        <p className="artifact-inline-card-subtitle">{artifactCardSubtitle(spec)}</p>
      </div>
      {canPreview || canDownload ? (
        <div className="artifact-inline-card-actions inline-download-artifact-actions" role="toolbar" aria-label="Artifact actions">
          <div className="artifact-inline-action-group">
            {canPreview ? (
              <>
                <button
                  type="button"
                  className={`artifact-inline-action-btn${expanded ? ' artifact-inline-action-btn-active' : ''}`}
                  aria-label={expanded ? 'Showing in side panel' : 'Open document preview'}
                  title={expanded ? 'Open in side panel' : 'Preview'}
                  aria-pressed={expanded}
                  onClick={() => onExpand?.(spec)}
                >
                  <ArtifactPreviewIcon />
                  <span>Preview</span>
                </button>
                {canDownload ? <span className="artifact-inline-action-divider" aria-hidden /> : null}
              </>
            ) : null}
            {canDownload ? (
              <button
                type="button"
                className="artifact-inline-action-btn"
                aria-label={downloading ? 'Downloading' : 'Download artifact'}
                title={downloading ? 'Downloading…' : 'Download'}
                disabled={downloading}
                aria-busy={downloading}
                onClick={() => void handleDownload()}
              >
                {downloading ? <LoadingSpinner size="sm" /> : <ArtifactDownloadIcon />}
                <span>Download</span>
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}
