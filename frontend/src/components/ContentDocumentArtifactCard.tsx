import { useState } from 'react'
import type { ArtifactSpec } from '../types/artifact'
import { ArtifactDownloadIcon } from './ArtifactDownloadIcon'
import { LoadingSpinner } from './LoadingSpinner'
import { downloadArtifactFile } from '../lib/artifactDownload'

type Props = {
  spec: ArtifactSpec
}

export function ContentDocumentArtifactCard({ spec }: Props) {
  const [downloading, setDownloading] = useState(false)

  async function handleDownload() {
    if (!spec.download_url || downloading) return
    setDownloading(true)
    try {
      await downloadArtifactFile(spec)
    } finally {
      setDownloading(false)
    }
  }

  const formatLabel =
    spec.format === 'docx'
      ? 'Word'
      : spec.format === 'pptx'
        ? 'PowerPoint'
        : spec.format.toUpperCase()

  return (
    <div className="viz-widget-frame artifact-widget-frame">
      <div className="viz-bubble-header">
        <h4 className="viz-bubble-title">{spec.title}</h4>
        <div className="viz-widget-toolbar">
          <span className="viz-bubble-badge">{formatLabel}</span>
        </div>
      </div>
      <div className="viz-widget-body">
        <div className="artifact-markdown-wrap">
          <p className="artifact-download-filename">{spec.filename}</p>
          {spec.download_url ? (
            <button
              type="button"
              className="viz-widget-action-btn"
              onClick={() => void handleDownload()}
              disabled={downloading}
            >
              {downloading ? <LoadingSpinner size="sm" /> : <ArtifactDownloadIcon />}
              <span>Download</span>
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
