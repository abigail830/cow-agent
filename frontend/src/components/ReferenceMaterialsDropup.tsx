import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { AtSign, FileText, Paperclip, Plus, Search, Trash2 } from 'lucide-react'
import type { ChatAttachmentListItem } from '../lib/attachmentUpload'
import { isAttachmentReferenceCompatible } from '../lib/attachmentCompat'
import { formatAttachmentTimestamp } from '../lib/attachmentMentions'
import { SUPPORTED_ATTACHMENT_LABEL } from '../lib/attachments'
import { LoadingSpinner } from './LoadingSpinner'

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

interface ReferenceMaterialsDropupProps {
  open: boolean
  onClose: () => void
  anchorRef: RefObject<HTMLElement | null>
  attachments: ChatAttachmentListItem[]
  loading: boolean
  deletingAttachmentId: string | null
  searchQuery: string
  onSearchChange: (query: string) => void
  onUploadClick: () => void
  onReferenceAttachment: (attachment: ChatAttachmentListItem) => void
  onDeleteAttachment: (attachment: ChatAttachmentListItem) => void
  referencedAttachmentIds?: string[]
  recentlyReferencedId?: string | null
  disabled?: boolean
}

export function ReferenceMaterialsDropup({
  open,
  onClose,
  anchorRef,
  attachments,
  loading,
  deletingAttachmentId,
  searchQuery,
  onSearchChange,
  onUploadClick,
  onReferenceAttachment,
  onDeleteAttachment,
  referencedAttachmentIds = [],
  recentlyReferencedId = null,
  disabled = false,
}: ReferenceMaterialsDropupProps) {
  const referencedSet = new Set(referencedAttachmentIds)
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
    if (!open) return
    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node
      if (panelRef.current?.contains(target)) return
      if ((target as HTMLElement).closest?.('[data-ref-materials-trigger]')) return
      onClose()
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [open, onClose])

  if (!open) return null

  const normalizedQuery = searchQuery.trim().toLowerCase()
  const filtered = attachments.filter((att) =>
    !normalizedQuery ? true : att.filename.toLowerCase().includes(normalizedQuery),
  )

  const panel = (
    <div
      ref={panelRef}
      className="ref-materials-dropup ref-materials-dropup-portal"
      style={{ left: position.left, bottom: position.bottom }}
      role="dialog"
      aria-label="Attachments"
    >
      <div className="ref-materials-header">
        <div className="ref-materials-title">
          <Paperclip size={14} strokeWidth={1.75} aria-hidden="true" />
          <span>Attachments</span>
        </div>
        <button
          type="button"
          className="ref-materials-add"
          onClick={onUploadClick}
          disabled={disabled}
          aria-label="Upload attachment"
          title="Upload attachment"
        >
          <Plus size={16} strokeWidth={2} aria-hidden="true" />
        </button>
      </div>

      <div className="ref-materials-search-wrap">
        <Search size={14} strokeWidth={1.75} aria-hidden="true" />
        <input
          type="search"
          className="ref-materials-search"
          placeholder="Search attachments..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          disabled={disabled}
        />
      </div>

      <div className="ref-materials-list">
        {loading && attachments.length === 0 ? (
          <p className="ref-materials-empty">Loading…</p>
        ) : filtered.length === 0 ? (
          <p className="ref-materials-empty">
            {attachments.length === 0
              ? 'No attachments yet. Click + to upload.'
              : 'No matching files.'}
          </p>
        ) : (
          filtered.map((att) => {
            const compat = isAttachmentReferenceCompatible(att)
            const isUploading = att.upload_status === 'uploading'
            const isFailed = att.upload_status === 'failed'
            const isDeleting = deletingAttachmentId === att.id
            const isReferenced = referencedSet.has(att.id)
            const isJustReferenced = recentlyReferencedId === att.id
            return (
              <div
                key={att.id}
                className={[
                  'ref-materials-item',
                  isUploading ? 'ref-materials-item-uploading' : '',
                  isFailed ? 'ref-materials-item-failed' : '',
                  !compat.compatible && !isUploading ? 'ref-materials-item-disabled' : '',
                  isReferenced ? 'ref-materials-item-referenced' : '',
                  isJustReferenced ? 'ref-materials-item-just-referenced' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                <FileText size={16} strokeWidth={1.5} aria-hidden="true" />
                <div className="ref-materials-item-body">
                  <span className="ref-materials-item-name" title={att.filename}>
                    {att.filename}
                  </span>
                  <span className="ref-materials-item-meta">
                    {isUploading
                      ? 'Uploading…'
                      : isFailed
                        ? 'Upload failed'
                        : formatFileSize(att.size_bytes)}
                    {!isUploading && !isFailed && att.created_at
                      ? ` · ${formatAttachmentTimestamp(att.created_at)}`
                      : ''}
                    {!isUploading && !compat.compatible ? ` · ${compat.reason}` : ''}
                  </span>
                </div>
                <div className="ref-materials-item-actions">
                  {isUploading ? (
                    <span className="ref-materials-item-upload-spinner" aria-label="Uploading">
                      <LoadingSpinner size="sm" />
                    </span>
                  ) : (
                    <>
                      <button
                        type="button"
                        className={[
                          'ref-materials-item-action',
                          isReferenced ? 'ref-materials-item-action-referenced' : '',
                        ]
                          .filter(Boolean)
                          .join(' ')}
                        disabled={disabled || !compat.compatible}
                        aria-label={`Reference @${att.filename}`}
                        title={`Reference @${att.filename}`}
                        aria-pressed={isReferenced}
                        onClick={() => onReferenceAttachment(att)}
                      >
                        <AtSign size={14} strokeWidth={1.75} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className="ref-materials-item-action ref-materials-item-action-delete"
                        disabled={disabled || isDeleting}
                        aria-label={`Delete ${att.filename}`}
                        title={`Delete ${att.filename}`}
                        onClick={() => onDeleteAttachment(att)}
                      >
                        {isDeleting ? (
                          <LoadingSpinner size="sm" />
                        ) : (
                          <Trash2 size={14} strokeWidth={1.75} aria-hidden="true" />
                        )}
                      </button>
                    </>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      <div className="ref-materials-footer">
        <span>
          {attachments.length === 1 ? '1 item' : `${attachments.length} items`}
          {attachments.some((att) => att.upload_status === 'uploading')
            ? ` · ${attachments.filter((att) => att.upload_status === 'uploading').length} uploading`
            : ''}
        </span>
        <span className="ref-materials-footer-hint">{SUPPORTED_ATTACHMENT_LABEL}</span>
      </div>
    </div>
  )

  return createPortal(panel, document.body)
}
