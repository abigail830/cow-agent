import { useEffect, useRef, useState } from 'react'
import type { UDocViewer } from '@docmentis/udoc-viewer'
import type { ArtifactSpec } from '../types/artifact'
import { resolveApiPath, toSameOriginApiUrl } from '../lib/apiBase'
import { getUdocClient } from '../lib/udocClient'
import { LoadingSpinner } from './LoadingSpinner'

type Props = {
  spec: ArtifactSpec
  /** 1-based page from KB locator; optional for generated artifacts. */
  initialPage?: number | null
}

async function fetchArtifactBytes(downloadUrl: string): Promise<Uint8Array> {
  const url = toSameOriginApiUrl(resolveApiPath(downloadUrl))
  const res = await fetch(url, { credentials: 'include' })
  if (!res.ok) {
    throw new Error((await res.text()) || res.statusText || 'Failed to load document')
  }
  return new Uint8Array(await res.arrayBuffer())
}

function documentLoadUrl(downloadUrl: string): string {
  return toSameOriginApiUrl(resolveApiPath(downloadUrl))
}

/**
 * In-browser Office/PDF preview via udoc (WASM). Reuses a shared UDocClient.
 * Prefers URL load so udoc can stream; falls back to authenticated byte fetch.
 */
export function UDocArtifactViewer({ spec, initialPage = null }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const downloadUrl = spec.download_url?.trim()
    const container = containerRef.current
    if (!downloadUrl || !container) {
      setStatus('error')
      setError('No downloadable document')
      return
    }

    let cancelled = false
    let viewer: UDocViewer | null = null
    const loadUrl = documentLoadUrl(downloadUrl)

    setStatus('loading')
    setError(null)

    void (async () => {
      try {
        const client = await getUdocClient()
        if (cancelled) return

        viewer = await client.createViewer({
          container,
          theme: 'light',
        })

        try {
          await viewer.load(loadUrl)
        } catch {
          const bytes = await fetchArtifactBytes(downloadUrl)
          if (cancelled) return
          await viewer.load(bytes)
        }

        if (initialPage != null && initialPage >= 1) {
          viewer.goToPage(initialPage - 1)
        }

        if (cancelled) {
          viewer.destroy()
          viewer = null
          return
        }
        setStatus('ready')
      } catch (err) {
        if (cancelled) return
        const message = err instanceof Error ? err.message : String(err)
        setError(message || 'Preview failed')
        setStatus('error')
        viewer?.destroy()
        viewer = null
      }
    })()

    return () => {
      cancelled = true
      viewer?.destroy()
    }
  }, [spec.artifact_id, spec.download_url, initialPage])

  return (
    <div className="udoc-artifact-viewer">
      {status === 'loading' ? (
        <div className="panel-loading-state udoc-artifact-viewer-status" role="status">
          <LoadingSpinner />
          <span>Loading preview…</span>
        </div>
      ) : null}
      {status === 'error' ? (
        <div className="panel-loading-state udoc-artifact-viewer-status" role="alert">
          <span>{error || 'Preview failed'}</span>
        </div>
      ) : null}
      <div ref={containerRef} className="udoc-artifact-viewer-host" />
    </div>
  )
}
