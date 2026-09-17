import { lazy, Suspense, useState } from 'react'
import { ArtifactDownloadIcon } from './ArtifactDownloadIcon'
import { LoadingSpinner } from './LoadingSpinner'
import { downloadArtifactFile } from '../lib/artifactDownload'
import { artifactCardSubtitle } from '../lib/artifactKinds'
import type { ArtifactSpec } from '../types/artifact'

const UDocArtifactViewer = lazy(async () => {
  const mod = await import('./UDocArtifactViewer')
  return { default: mod.UDocArtifactViewer }
})

type Props = {
  spec: ArtifactSpec
  onClose: () => void
}

export function ContentDocumentPanel({ spec, onClose }: Props) {
  const [downloading, setDownloading] = useState(false)
  const canDownload = Boolean(spec.download_url?.trim())

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
    <>
      <div className="artifact-side-panel-header artifact-side-panel-header-document">
        <div className="artifact-side-panel-title-stack">
          <h2 className="artifact-side-panel-title" title={spec.title}>
            {spec.title}
          </h2>
          <p className="artifact-side-panel-subtitle">{artifactCardSubtitle(spec)}</p>
        </div>
        <div className="artifact-side-panel-actions">
          {canDownload ? (
            <button
              type="button"
              className="diagram-artifact-action-btn"
              aria-label={downloading ? 'Downloading' : 'Download document'}
              title={downloading ? 'Downloading…' : 'Download'}
              disabled={downloading}
              aria-busy={downloading}
              onClick={() => void handleDownload()}
            >
              {downloading ? <LoadingSpinner size="sm" /> : <ArtifactDownloadIcon />}
              <span>Download</span>
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
      <div className="artifact-side-panel-scroll artifact-side-panel-scroll-document">
        <Suspense
          fallback={
            <div className="panel-loading-state" role="status">
              <LoadingSpinner />
              <span>Loading viewer…</span>
            </div>
          }
        >
          <UDocArtifactViewer spec={spec} />
        </Suspense>
      </div>
    </>
  )
}
