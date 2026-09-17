import { useEffect, useRef, useState } from 'react'
import { UDocClient, type UDocViewer } from '@docmentis/udoc-viewer'
import type { ArtifactSpec } from '../types/artifact'
import { resolveApiPath, toSameOriginApiUrl } from '../lib/apiBase'
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

/**
 * In-browser Office/PDF preview via udoc (WASM). Loads bytes through the
 * authenticated artifact download URL (same-origin /api rewrite).
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
    let client: UDocClient | null = null
    let viewer: UDocViewer | null = null

    setStatus('loading')
    setError(null)

    void (async () => {
      try {
        const bytes = await fetchArtifactBytes(downloadUrl)
        if (cancelled) return

        client = await UDocClient.create({
          disableUpdateCheck: true,
          // Self-hosted via vite copy plugin → public/udoc/
          baseUrl: `${window.location.origin}/udoc/`,
        })
        if (cancelled) {
          client.destroy()
          return
        }

        viewer = await client.createViewer({
          container,
          theme: 'light',
        })
        await viewer.load(bytes)

        if (initialPage != null && initialPage >= 1) {
          viewer.goToPage(initialPage - 1)
        }

        if (cancelled) {
          viewer.destroy()
          client.destroy()
          return
        }
        setStatus('ready')
      } catch (err) {
        if (cancelled) return
        const message = err instanceof Error ? err.message : String(err)
        setError(message || 'Preview failed')
        setStatus('error')
        viewer?.destroy()
        client?.destroy()
        viewer = null
        client = null
      }
    })()

    return () => {
      cancelled = true
      viewer?.destroy()
      client?.destroy()
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
