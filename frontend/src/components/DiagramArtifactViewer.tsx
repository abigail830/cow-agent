import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type WheelEvent as ReactWheelEvent,
} from 'react'
import type { ArtifactSpec } from '../types/artifact'
import { resolveApiPath } from '../lib/apiBase'
import { prepareSvgForDisplay } from '../lib/svgDisplay'

type Props = {
  spec: ArtifactSpec
}

function isSvgMarkup(value: string): boolean {
  const raw = value.trim()
  return raw.startsWith('<') && raw.includes('svg')
}

const MIN_ZOOM = 0.25
const MAX_ZOOM = 4
const ZOOM_STEP = 0.25
const SCROLL_PADDING_X = 32

export function DiagramArtifactViewer({ spec }: Props) {
  const inlineSvg = useMemo(() => {
    const raw = spec.content?.trim() || ''
    return isSvgMarkup(raw) ? raw : ''
  }, [spec.content])

  const [remoteSvg, setRemoteSvg] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [zoom, setZoom] = useState(1)
  const [containerWidth, setContainerWidth] = useState(0)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setRemoteSvg(null)
    setLoadError(null)
    setZoom(1)
    if (inlineSvg || !spec.download_url) return

    let cancelled = false
    void fetch(resolveApiPath(spec.download_url), { credentials: 'include' })
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text())
        return res.text()
      })
      .then((text) => {
        if (cancelled) return
        if (!isSvgMarkup(text)) {
          throw new Error('Diagram download did not return SVG markup.')
        }
        setRemoteSvg(text)
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : 'Failed to load diagram')
        }
      })

    return () => {
      cancelled = true
    }
  }, [spec.download_url, spec.artifact_id, inlineSvg])

  const displaySvg = useMemo(() => {
    const raw = (inlineSvg || remoteSvg || '').trim()
    if (!isSvgMarkup(raw)) return ''
    return prepareSvgForDisplay(raw)
  }, [inlineSvg, remoteSvg])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const measure = () => {
      setContainerWidth(Math.max(0, el.clientWidth - SCROLL_PADDING_X))
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [displaySvg])

  const zoomIn = useCallback(() => {
    setZoom((value) => Math.min(MAX_ZOOM, Number((value + ZOOM_STEP).toFixed(2))))
  }, [])

  const zoomOut = useCallback(() => {
    setZoom((value) => Math.max(MIN_ZOOM, Number((value - ZOOM_STEP).toFixed(2))))
  }, [])

  const resetZoom = useCallback(() => setZoom(1), [])

  const onWheel = useCallback(
    (event: ReactWheelEvent<HTMLDivElement>) => {
      if (!event.ctrlKey) return
      event.preventDefault()
      if (event.deltaY < 0) zoomIn()
      else zoomOut()
    },
    [zoomIn, zoomOut],
  )

  const expandedWidth = useMemo(() => {
    if (containerWidth <= 0) return undefined
    return Math.round(containerWidth * zoom)
  }, [containerWidth, zoom])

  if (loadError) {
    return <p className="artifact-diagram-empty">{loadError}</p>
  }

  if (!displaySvg) {
    if (spec.download_url && !inlineSvg) {
      return <p className="artifact-diagram-empty">Loading diagram…</p>
    }
    return <p className="artifact-diagram-empty">Diagram preview unavailable.</p>
  }

  return (
    <div className="diagram-viewer">
      <div className="diagram-viewer-toolbar" role="toolbar" aria-label="Diagram zoom">
        <button type="button" className="diagram-viewer-btn" onClick={zoomOut} aria-label="Zoom out">
          −
        </button>
        <span className="diagram-viewer-zoom-label">{Math.round(zoom * 100)}%</span>
        <button type="button" className="diagram-viewer-btn" onClick={zoomIn} aria-label="Zoom in">
          +
        </button>
        <button type="button" className="diagram-viewer-btn diagram-viewer-btn-text" onClick={resetZoom}>
          Fit width
        </button>
      </div>
      <div ref={scrollRef} className="diagram-viewer-scroll" onWheel={onWheel}>
        <div
          className="diagram-viewer-canvas diagram-viewer-canvas-inline"
          style={
            expandedWidth != null
              ? { width: `${expandedWidth}px` }
              : { width: '100%' }
          }
        >
          <div
            className="diagram-viewer-inline-svg"
            role="img"
            aria-label={spec.title}
            dangerouslySetInnerHTML={{ __html: displaySvg }}
          />
        </div>
      </div>
    </div>
  )
}
