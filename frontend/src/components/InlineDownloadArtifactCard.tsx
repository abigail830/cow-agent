import { useState } from 'react'
import type { ArtifactSpec } from '../types/artifact'
import { artifactCardSubtitle, isUdocPreviewableArtifact } from '../lib/artifactKinds'
import { ArtifactDownloadIcon } from './ArtifactDownloadIcon'
import { LoadingSpinner } from './LoadingSpinner'
import { downloadArtifactFile } from '../lib/artifactDownload'

type Props = {
  spec: ArtifactSpec
  showDownload?: boolean
  expanded?: boolean
  onExpand?: (spec: ArtifactSpec) => void
}

function resolveIcon(spec: ArtifactSpec): { label: string; className: string } {
  if (spec.format === 'docx' || spec.kind === 'proposal_word') {
    return { label: 'W', className: 'content-document-artifact-icon-docx' }
  }
  if (spec.format === 'pptx') {
    return { label: 'P', className: 'content-document-artifact-icon-pptx' }
  }
  if (spec.format === 'pdf') {
    return { label: 'D', className: 'content-document-artifact-icon-pdf' }
  }
  if (spec.kind.startsWith('proposal_')) {
    return { label: 'P', className: 'proposal-artifact-icon' }
  }
  if (spec.format === 'markdown') {
    return { label: 'M', className: 'content-document-artifact-icon-markdown' }
  }
  return { label: 'D', className: 'content-document-artifact-icon-markdown' }
}

function canDownloadSpec(spec: ArtifactSpec): boolean {
  return Boolean(spec.download_url?.trim()) || Boolean(spec.content?.trim())
}

function PreviewEyeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

export function InlineDownloadArtifactCard({
  spec,
  showDownload = true,
  expanded = false,
  onExpand,
}: Props) {
  const [downloading, setDownloading] = useState(false)
  const icon = resolveIcon(spec)
  const canDownload = showDownload && canDownloadSpec(spec)
  const canPreview = isUdocPreviewableArtifact(spec)

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
      <div
        className={`artifact-inline-card-icon content-document-artifact-icon ${icon.className}`}
        aria-hidden
      >
        {icon.label}
      </div>
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
                  <PreviewEyeIcon />
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
