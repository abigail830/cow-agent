import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { FileText, Search } from 'lucide-react'
import type { ChatAttachment } from '../types'
import { formatAttachmentTimestamp } from '../lib/attachmentMentions'

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

interface AttachmentMentionPopupProps {
  open: boolean
  anchorRef: RefObject<HTMLElement | null>
  query: string
  attachments: ChatAttachment[]
  loading: boolean
  highlightIndex: number
  onQueryChange: (query: string) => void
  onHighlightChange: (index: number) => void
  onSelect: (attachment: ChatAttachment) => void
}

export function AttachmentMentionPopup({
  open,
  anchorRef,
  query,
  attachments,
  loading,
  highlightIndex,
  onQueryChange,
  onHighlightChange,
  onSelect,
}: AttachmentMentionPopupProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState({ left: 16, bottom: 80 })

  useLayoutEffect(() => {
    if (!open) return

    const updatePosition = () => {
      const anchor = anchorRef.current
      if (!anchor) return
      const rect = anchor.getBoundingClientRect()
      const panelWidth = Math.min(352, window.innerWidth - 32)
      const left = Math.min(Math.max(16, rect.left), window.innerWidth - panelWidth - 16)
      setPosition({
        left,
        bottom: window.innerHeight - rect.top + 8,
      })
    }

    updatePosition()
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [anchorRef, open])

  useEffect(() => {
    if (!open || attachments.length === 0) return
    const active = panelRef.current?.querySelector<HTMLElement>(
      `[data-mention-index="${highlightIndex}"]`,
    )
    active?.scrollIntoView({ block: 'nearest' })
  }, [attachments.length, highlightIndex, open])

  if (!open) return null

  const panel = (
    <div
      ref={panelRef}
      className="attachment-mention-popup attachment-mention-popup-portal"
      style={{ left: position.left, bottom: position.bottom }}
      role="dialog"
      aria-label="Search attachments"
      onMouseDown={(e) => e.preventDefault()}
    >
      <div className="attachment-mention-search-wrap">
        <Search size={14} strokeWidth={1.75} aria-hidden="true" />
        <input
          type="search"
          className="attachment-mention-search"
          placeholder="Search attachments..."
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          aria-label="Search attachments"
        />
      </div>

      <div className="attachment-mention-list" role="listbox" aria-label="Attachment results">
        {loading && attachments.length === 0 ? (
          <p className="attachment-mention-empty">Loading…</p>
        ) : attachments.length === 0 ? (
          <p className="attachment-mention-empty">
            {query.trim() ? 'No matching files.' : 'No attachments available.'}
          </p>
        ) : (
          attachments.map((att, index) => (
            <button
              key={att.id}
              type="button"
              data-mention-index={index}
              className={`attachment-mention-item${index === highlightIndex ? ' attachment-mention-item-active' : ''}`}
              role="option"
              aria-selected={index === highlightIndex}
              onMouseEnter={() => onHighlightChange(index)}
              onMouseDown={(e) => {
                e.preventDefault()
                onSelect(att)
              }}
            >
              <span className="attachment-mention-item-icon" aria-hidden="true">
                <FileText size={16} strokeWidth={1.5} />
              </span>
              <span className="attachment-mention-item-body">
                <span className="attachment-mention-name">{att.filename}</span>
                <span className="attachment-mention-meta">
                  Attachment · {formatFileSize(att.size_bytes)}
                  {att.created_at ? ` · ${formatAttachmentTimestamp(att.created_at)}` : ''}
                </span>
              </span>
            </button>
          ))
        )}
      </div>

      <div className="attachment-mention-footer">
        {attachments.length === 1 ? '1 item' : `${attachments.length} items`}
      </div>
    </div>
  )

  return createPortal(panel, document.body)
}
