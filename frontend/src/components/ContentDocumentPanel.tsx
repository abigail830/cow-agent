import { lazy, Suspense, useEffect, useState } from 'react'
import { ArtifactDownloadIcon } from './ArtifactDownloadIcon'
import { LoadingSpinner } from './LoadingSpinner'
import { MarkdownContent } from './MarkdownContent'
import { downloadArtifactFile } from '../lib/artifactDownload'
import { resolveApiPath, toSameOriginApiUrl } from '../lib/apiBase'
import { artifactCardSubtitle, isMarkdownPreviewableArtifact } from '../lib/artifactKinds'
import type { ArtifactSpec } from '../types/artifact'

const UDocArtifactViewer = lazy(async () => {
  const mod = await import('./UDocArtifactViewer')
  return { default: mod.UDocArtifactViewer }
})

type Props = {
  spec: ArtifactSpec
  onClose: () => void
}

async function loadMarkdownText(spec: ArtifactSpec): Promise<string> {
  const inline = spec.content?.trim()
  if (inline) return spec.content
  const url = spec.download_url?.trim()
  if (!url) return ''
  const res = await fetch(toSameOriginApiUrl(resolveApiPath(url)), { credentials: 'include' })
  if (!res.ok) {
    throw new Error(await res.text())
  }
  return await res.text()
}

function MarkdownDocumentBody({ spec }: { spec: ArtifactSpec }) {
  const [text, setText] = useState(spec.content?.trim() ? spec.content : '')
  const [loading, setLoading] = useState(!spec.content?.trim())
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const inline = spec.content?.trim()
    if (inline) {
      setText(spec.content)
      setLoading(false)
      setError(null)
      return
    }
    setLoading(true)
    setError(null)
    void loadMarkdownText(spec)
      .then((body) => {
        if (cancelled) return
        setText(body)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load markdown')
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [spec])

  if (loading) {
    return (
      <div className="panel-loading-state" role="status">
        <LoadingSpinner />
        <span>Loading markdown…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="panel-loading-state" role="alert">
        <span>{error}</span>
      </div>
    )
  }

  if (!text.trim()) {
    return (
      <div className="panel-loading-state" role="status">
        <span>No preview content</span>
      </div>
    )
  }

  return (
    <MarkdownContent
      content={text}
      className="markdown-body artifact-markdown-body"
    />
  )
}

export function ContentDocumentPanel({ spec, onClose }: Props) {
  const [downloading, setDownloading] = useState(false)
  const canDownload = Boolean(spec.download_url?.trim()) || Boolean(spec.content?.trim())
  const isMarkdown = isMarkdownPreviewableArtifact(spec)

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
        {isMarkdown ? (
          <MarkdownDocumentBody spec={spec} />
        ) : (
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
        )}
      </div>
    </>
  )
}
