import { useState } from 'react'
import type { ArtifactSpec } from '../types/artifact'
import { artifactCardSubtitle } from '../lib/artifactKinds'
import { ArtifactDownloadIcon } from './ArtifactDownloadIcon'
import { LoadingSpinner } from './LoadingSpinner'
import { downloadArtifactFile } from '../lib/artifactDownload'

type Props = {
  spec: ArtifactSpec
  showDownload?: boolean
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

export function InlineDownloadArtifactCard({ spec, showDownload = true }: Props) {
  const [downloading, setDownloading] = useState(false)
  const icon = resolveIcon(spec)
  const canDownload = showDownload && canDownloadSpec(spec)

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
    <div className="artifact-inline-card inline-download-artifact-card" aria-label={spec.title}>
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
      {canDownload ? (
        <div className="artifact-inline-card-actions inline-download-artifact-actions" role="toolbar" aria-label="Artifact actions">
          <div className="artifact-inline-action-group">
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
          </div>
        </div>
      ) : null}
    </div>
  )
}
