import {
  useCallback,
  useEffect,
  useRef,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react'

const MIN_PANEL_WIDTH = 320
const MAX_PANEL_RATIO = 0.72
const RESIZE_HANDLE_WIDTH = 6
const STORAGE_KEY = 'proposal-panel-width'

export type ProposalPanelTab = 'preview' | 'state'

const TAB_LABELS: Record<ProposalPanelTab, string> = {
  preview: 'Proposal Preview',
  state: 'Section View',
}

function readStoredWidth(): number {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return 480
    const parsed = Number.parseInt(raw, 10)
    return Number.isFinite(parsed) && parsed >= MIN_PANEL_WIDTH ? parsed : 480
  } catch {
    return 480
  }
}

type Props = {
  open: boolean
  width: number
  activeTab: ProposalPanelTab
  syncing?: boolean
  onTabChange: (tab: ProposalPanelTab) => void
  onWidthChange: (width: number) => void
  onExpand: (tab?: ProposalPanelTab) => void
  children: ReactNode
}

export function ProposalPanelShell({
  open,
  width,
  activeTab,
  syncing = false,
  onTabChange,
  onWidthChange,
  onExpand,
  children,
}: Props) {
  const shellRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(Math.round(width)))
    } catch {
      /* ignore quota / private mode */
    }
  }, [width])

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

  const onTabClick = (tab: ProposalPanelTab) => {
    if (!open) {
      onExpand(tab)
      return
    }
    if (tab !== activeTab) {
      onTabChange(tab)
    }
  }

  const shellWidth = open ? width + RESIZE_HANDLE_WIDTH : 0
  const activeTabId = `proposal-tab-${activeTab}`

  return (
    <div
      ref={shellRef}
      className={`proposal-preview-shell${open ? ' proposal-preview-shell-open' : ''}`}
      style={{ width: shellWidth }}
    >
      <div className="proposal-panel-tabs" role="tablist" aria-label="Proposal side panel">
        {(Object.keys(TAB_LABELS) as ProposalPanelTab[]).map((tab) => {
          const selected = open && activeTab === tab
          const showSync = syncing && tab === 'preview'
          return (
            <button
              key={tab}
              type="button"
              role="tab"
              id={`proposal-tab-${tab}`}
              aria-selected={selected}
              aria-controls={open ? 'proposal-panel-content' : undefined}
              className={`proposal-panel-tab${selected ? ' proposal-panel-tab-active' : ''}${
                showSync ? ' proposal-panel-tab-syncing' : ''
              }`}
              onClick={() => onTabClick(tab)}
              aria-label={TAB_LABELS[tab]}
              title={TAB_LABELS[tab]}
            >
              {TAB_LABELS[tab]}
            </button>
          )
        })}
      </div>

      {open && (
        <>
          <div
            className="proposal-resize-handle"
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize proposal panel"
            style={{ width: RESIZE_HANDLE_WIDTH }}
            onPointerDown={onResizePointerDown}
            onPointerMove={onResizePointerMove}
            onPointerUp={onResizePointerUp}
            onPointerCancel={onResizePointerUp}
          />
          <div
            id="proposal-panel-content"
            role="tabpanel"
            aria-labelledby={activeTabId}
            className="proposal-panel-content"
            style={{ width }}
          >
            {children}
          </div>
        </>
      )}
    </div>
  )
}

export { readStoredWidth as readProposalPanelWidth }
