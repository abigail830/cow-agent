import { useState } from 'react'
import { RotateCcw } from 'lucide-react'
import type { ArtifactSpec } from '../types/artifact'
import { artifactCardSubtitle, isMarkdownPreviewableArtifact } from '../lib/artifactKinds'
import { ArtifactCoverIllustration, resolveArtifactCoverKind } from './ArtifactCoverIllustration'
import { ArtifactPreviewIcon } from './ArtifactPreviewIcon'
import { ArtifactDownloadIcon } from './ArtifactDownloadIcon'
import { LoadingSpinner } from './LoadingSpinner'
import { downloadArtifactFile } from '../lib/artifactDownload'

type Props = {
  spec: ArtifactSpec
  expanded?: boolean
  onExpand?: (spec: ArtifactSpec) => void
  onViewPipeline?: (attachmentId: string) => void
  onRetry?: (params: { attachmentId: string; captureId?: string | null }) => Promise<void>
}

export function AudioTranscriptArtifactCard({
  spec,
  expanded = false,
  onExpand,
  onViewPipeline,
  onRetry,
}: Props) {
  const [downloading, setDownloading] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const jobStatus = spec.job_status ?? 'running'
  const isRunning = jobStatus === 'running'
  const isFailed = jobStatus === 'failed'
  const canPreview = isMarkdownPreviewableArtifact(spec)
  const canDownload = Boolean(spec.download_url?.trim()) || Boolean(spec.content?.trim())
  const attachmentId = spec.attachment_id ?? spec.artifact_id
  const canViewPipeline = Boolean(attachmentId && onViewPipeline)
  const canRetry = Boolean(isFailed && attachmentId && onRetry)

  async function handleDownload() {
    if (!canDownload || downloading) return
    setDownloading(true)
    try {
      await downloadArtifactFile(spec)
    } finally {
      setDownloading(false)
    }
  }

  async function handleRetry() {
    if (!canRetry || !attachmentId || !onRetry || retrying) return
    setRetrying(true)
    try {
      await onRetry({ attachmentId, captureId: spec.capture_id })
    } finally {
      setRetrying(false)
    }
  }

  return (
    <div
      className={`artifact-inline-card inline-download-artifact-card audio-transcript-artifact-card${expanded ? ' artifact-inline-card-expanded' : ''}${isRunning ? ' audio-transcript-artifact-card-running' : ''}${isFailed ? ' audio-transcript-artifact-card-failed' : ''}`}
      aria-label={spec.title}
    >
      <ArtifactCoverIllustration kind={resolveArtifactCoverKind(spec)} />
      <div className="artifact-inline-card-main">
        <h4 className="artifact-inline-card-title" title={spec.title}>
          {spec.title}
        </h4>
        <p className="artifact-inline-card-subtitle">{artifactCardSubtitle(spec)}</p>
        {isRunning ? (
          <p className="audio-transcript-artifact-hint">
            Transcription is running — you can keep chatting and check back later.
          </p>
        ) : null}
        {isFailed ? (
          <p className="audio-transcript-artifact-hint audio-transcript-artifact-hint-error">
            Transcription failed. Open the pipeline for details or retry below.
          </p>
        ) : null}
      </div>
      <div className="artifact-inline-card-actions inline-download-artifact-actions" role="toolbar" aria-label="Artifact actions">
        <div className="artifact-inline-action-group">
          {canViewPipeline ? (
            <button
              type="button"
              className="artifact-inline-action-btn"
              onClick={() => onViewPipeline!(attachmentId!)}
            >
              View pipeline
            </button>
          ) : null}
          {canRetry ? (
            <button
              type="button"
              className="artifact-inline-action-btn artifact-inline-action-btn-retry"
              disabled={retrying}
              onClick={() => void handleRetry()}
            >
              {retrying ? <LoadingSpinner size="sm" /> : <RotateCcw size={14} aria-hidden />}
              <span>{retrying ? 'Retrying…' : 'Retry'}</span>
            </button>
          ) : null}
          {canPreview ? (
            <button
              type="button"
              className={`artifact-inline-action-btn${expanded ? ' artifact-inline-action-btn-active' : ''}`}
              aria-pressed={expanded}
              onClick={() => onExpand?.(spec)}
            >
              <ArtifactPreviewIcon />
              <span>Preview</span>
            </button>
          ) : null}
          {canDownload ? (
            <button
              type="button"
              className="artifact-inline-action-btn"
              disabled={downloading}
              onClick={() => void handleDownload()}
            >
              {downloading ? <LoadingSpinner size="sm" /> : <ArtifactDownloadIcon />}
              <span>{downloading ? 'Downloading' : 'Download'}</span>
            </button>
          ) : null}
          {isRunning ? <LoadingSpinner size="sm" className="audio-transcript-artifact-spinner" /> : null}
        </div>
      </div>
    </div>
  )
}
