import {
  useCallback,
  useEffect,
  useRef,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react'

const MIN_PANEL_WIDTH = 360
const MAX_PANEL_RATIO = 0.82
const RESIZE_HANDLE_WIDTH = 6
const DEFAULT_STORAGE_KEY = 'artifact-panel-width'
const LEGACY_DIAGRAM_STORAGE_KEY = 'diagram-panel-width'

function readStoredWidth(storageKey: string): number {
  try {
    const keys = storageKey === DEFAULT_STORAGE_KEY
      ? [DEFAULT_STORAGE_KEY, LEGACY_DIAGRAM_STORAGE_KEY]
      : [storageKey]
    for (const key of keys) {
      const raw = localStorage.getItem(key)
      if (!raw) continue
      const parsed = Number.parseInt(raw, 10)
      if (Number.isFinite(parsed) && parsed >= MIN_PANEL_WIDTH) return parsed
    }
    return 520
  } catch {
    return 520
  }
}

type Props = {
  open: boolean
  width: number
  onWidthChange: (width: number) => void
  storageKey?: string
  resizeLabel?: string
  children: ReactNode
}

export function ArtifactPanelShell({
  open,
  width,
  onWidthChange,
  storageKey = DEFAULT_STORAGE_KEY,
  resizeLabel = 'Resize artifact panel',
  children,
}: Props) {
  const shellRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null)

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, String(Math.round(width)))
    } catch {
      /* ignore */
    }
  }, [storageKey, width])

  const clampWidth = useCallback((next: number) => {
    const layout = shellRef.current?.parentElement
    const max = layout
      ? Math.max(MIN_PANEL_WIDTH, layout.getBoundingClientRect().width * MAX_PANEL_RATIO)
      : 960
    return Math.min(Math.max(next, MIN_PANEL_WIDTH), max)
  }, [])

  const onResizePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!open) return
    event.preventDefault()
    dragRef.current = { startX: event.clientX, startWidth: width }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const onResizePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragRef.current) return
    const delta = dragRef.current.startX - event.clientX
    onWidthChange(clampWidth(dragRef.current.startWidth + delta))
  }

  const onResizePointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragRef.current) return
    dragRef.current = null
    event.currentTarget.releasePointerCapture(event.pointerId)
  }

  const shellWidth = open ? width + RESIZE_HANDLE_WIDTH : 0

  return (
    <div
      ref={shellRef}
      className={`diagram-panel-shell artifact-panel-shell${open ? ' diagram-panel-shell-open artifact-panel-shell-open' : ''}`}
      style={{ width: shellWidth }}
    >
      {open && (
        <>
          <div
            className="diagram-resize-handle artifact-resize-handle"
            role="separator"
            aria-orientation="vertical"
            aria-label={resizeLabel}
            style={{ width: RESIZE_HANDLE_WIDTH }}
            onPointerDown={onResizePointerDown}
            onPointerMove={onResizePointerMove}
            onPointerUp={onResizePointerUp}
            onPointerCancel={onResizePointerUp}
          />
          <div className="diagram-panel-content artifact-panel-content" style={{ width }}>
            {children}
          </div>
        </>
      )}
    </div>
  )
}

export function readArtifactPanelWidth(storageKey = DEFAULT_STORAGE_KEY): number {
  return readStoredWidth(storageKey)
}
