import { useCallback, useEffect, useRef, useState, type SyntheticEvent } from 'react'
import type { ArtifactSpec } from '../types/artifact'
import { resolveApiPath } from '../lib/apiBase'
import { LoadingSpinner } from './LoadingSpinner'

type Props = {
  spec: ArtifactSpec
}

const PREVIEW_PAD_PX = 24
const SLIDE_RATIO = 16 / 9

/**
 * Normalize the iframe entry URL for slide previews.
 * - Slidev: avoid `/index.html` (router breaks); use the preview index route instead.
 * - Vercel frontend rewrites 404 on `/preview/` (trailing slash); entry must be `/preview`.
 */
export function normalizeSlidePreviewUrl(url: string): string {
  const trimmed = url.trim()
  if (!trimmed) return trimmed
  const withoutIndex = trimmed.replace(/\/index\.html\/?$/i, '/preview')
  return withoutIndex.replace(/\/preview\/+$/i, '/preview')
}

function notifyDeckResize(iframe: HTMLIFrameElement | null) {
  try {
    iframe?.contentWindow?.postMessage({ type: 'deck-resize' }, '*')
  } catch {
    // Cross-origin or detached iframe.
  }
}

function isPreviewLoadFailure(bodyText: string): boolean {
  const text = bodyText.trim()
  if (!text) return false
  if (/Preview file not found/i.test(text)) return true
  if (/Not authenticated/i.test(text)) return true
  if (/\b404\b/i.test(text) && (/not\s*found/i.test(text) || /NOT_FOUND/i.test(text))) return true
  return false
}

export function SlideDeckViewer({ spec }: Props) {
  const previewUrl = spec.preview_url
    ? normalizeSlidePreviewUrl(resolveApiPath(spec.preview_url))
    : null
  const wrapRef = useRef<HTMLDivElement>(null)
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [iframeState, setIframeState] = useState<'loading' | 'ready' | 'error'>(
    previewUrl ? 'loading' : 'ready',
  )

  const fitIframe = useCallback(() => {
    const wrap = wrapRef.current
    const iframe = iframeRef.current
    if (!wrap || !iframe) return

    const cw = Math.max(0, wrap.clientWidth - PREVIEW_PAD_PX)
    const ch = Math.max(0, wrap.clientHeight - PREVIEW_PAD_PX)
    if (!cw || !ch) return

    let width = cw
    let height = width / SLIDE_RATIO
    if (height > ch) {
      height = ch
      width = height * SLIDE_RATIO
    }

    iframe.style.width = `${Math.floor(width)}px`
    iframe.style.height = `${Math.floor(height)}px`
    notifyDeckResize(iframe)
  }, [])

  useEffect(() => {
    setIframeState(previewUrl ? 'loading' : 'ready')
  }, [previewUrl])

  useEffect(() => {
    const wrap = wrapRef.current
    if (!wrap || !previewUrl) return

    fitIframe()

    if (typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(() => fitIframe())
      ro.observe(wrap)
      return () => ro.disconnect()
    }

    window.addEventListener('resize', fitIframe)
    return () => window.removeEventListener('resize', fitIframe)
  }, [previewUrl, iframeState, fitIframe])

  const handleIframeLoad = (event: SyntheticEvent<HTMLIFrameElement>) => {
    const iframe = event.currentTarget
    try {
      const bodyText = iframe.contentDocument?.body?.innerText ?? ''
      if (isPreviewLoadFailure(bodyText)) {
        setIframeState('error')
        return
      }
    } catch {
      // Cross-origin iframe — cannot inspect document.
    }
    setIframeState('ready')
    fitIframe()
  }

  if (previewUrl) {
    return (
      <div ref={wrapRef} className="slide-deck-viewer-wrap">
        {iframeState === 'loading' ? (
          <div className="slide-deck-viewer-loading" aria-live="polite">
            <LoadingSpinner size="lg" />
            <p className="panel-loading-caption">Loading slide preview…</p>
          </div>
        ) : null}
        {iframeState === 'error' ? (
          <div className="slide-deck-viewer-error" role="alert">
            <p>Slide preview failed to load.</p>
            <p className="panel-loading-caption">Try re-running render_slidev or open Download for the source.</p>
          </div>
        ) : null}
        <iframe
          ref={iframeRef}
          className="slide-deck-viewer"
          title={spec.title}
          src={previewUrl}
          sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox"
          referrerPolicy="no-referrer"
          aria-hidden={iframeState === 'error'}
          onLoad={handleIframeLoad}
          onError={() => setIframeState('error')}
        />
      </div>
    )
  }

  if (!spec.content) {
    return (
      <div className="panel-loading-state">
        <p>Slide preview is not available yet.</p>
      </div>
    )
  }

  return (
    <pre className="slide-deck-source-fallback">{spec.content}</pre>
  )
}
