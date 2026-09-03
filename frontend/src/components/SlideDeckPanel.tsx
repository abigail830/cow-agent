import { useState } from 'react'
import { ArtifactCopyIcon } from './ArtifactCopyIcon'
import { ArtifactDownloadIcon } from './ArtifactDownloadIcon'
import { SlideDeckViewer } from './SlideDeckViewer'
import { LoadingSpinner } from './LoadingSpinner'
import {
  canDownloadSlidePdf,
  copyArtifactSource,
  downloadArtifactFile,
} from '../lib/artifactDownload'
import type { ArtifactSpec } from '../types/artifact'

type Props = {
  spec: ArtifactSpec
  onClose: () => void
}

export function SlideDeckPanel({ spec, onClose }: Props) {
  const [downloading, setDownloading] = useState<'md' | 'pdf' | null>(null)
  const canDownloadMd = Boolean(spec.download_url)
  const canDownloadPdf = canDownloadSlidePdf(spec)
  const sourceDownloadLabel = spec.format === 'html' ? 'HTML' : 'MD'

  const handleDownload = async (variant: 'default' | 'pdf') => {
    setDownloading(variant === 'pdf' ? 'pdf' : 'md')
    try {
      await downloadArtifactFile(spec, variant)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <>
      <div className="artifact-side-panel-header artifact-side-panel-header-slide">
        <h2 className="artifact-side-panel-title" title={spec.title}>
          {spec.title}
        </h2>
        <div className="artifact-side-panel-actions">
          {spec.source || spec.content ? (
            <button
              type="button"
              className="diagram-artifact-action-btn"
              aria-label="Copy Slidev source"
              title="Copy Slidev source"
              onClick={() => void copyArtifactSource(spec)}
            >
              <ArtifactCopyIcon />
              <span>Copy</span>
            </button>
          ) : null}
          {canDownloadMd ? (
            <button
              type="button"
              className="diagram-artifact-action-btn"
              aria-label={downloading === 'md' ? `Downloading ${sourceDownloadLabel}` : `Download ${sourceDownloadLabel}`}
              title={downloading === 'md' ? 'Downloading…' : `Download ${sourceDownloadLabel} source`}
              disabled={downloading !== null}
              aria-busy={downloading === 'md'}
              onClick={() => void handleDownload('default')}
            >
              {downloading === 'md' ? <LoadingSpinner size="sm" /> : <ArtifactDownloadIcon />}
              <span>{sourceDownloadLabel}</span>
            </button>
          ) : null}
          {canDownloadPdf ? (
            <button
              type="button"
              className="diagram-artifact-action-btn"
              aria-label={downloading === 'pdf' ? 'Downloading PDF' : 'Download PDF'}
              title={downloading === 'pdf' ? 'Downloading…' : 'Download PDF'}
              disabled={downloading !== null}
              aria-busy={downloading === 'pdf'}
              onClick={() => void handleDownload('pdf')}
            >
              {downloading === 'pdf' ? <LoadingSpinner size="sm" /> : <ArtifactDownloadIcon />}
              <span>PDF</span>
            </button>
          ) : null}
          <button
            type="button"
            className="viz-widget-btn artifact-side-panel-close"
            onClick={onClose}
            aria-label="Close preview"
            title="Close"
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
      <div className="artifact-side-panel-scroll artifact-side-panel-scroll-slide">
        <SlideDeckViewer spec={spec} />
      </div>
    </>
  )
}
