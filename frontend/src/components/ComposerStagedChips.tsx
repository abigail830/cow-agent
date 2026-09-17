import { X } from 'lucide-react'
import { LoadingSpinner } from './LoadingSpinner'
import type { ChatAttachmentListItem } from '../lib/attachmentUpload'
import { isPendingAttachmentId } from '../lib/attachmentUpload'

type Props = {
  attachments: ChatAttachmentListItem[]
  onRemove: (id: string) => void
  disabled?: boolean
}

export function ComposerStagedChips({ attachments, onRemove, disabled = false }: Props) {
  if (attachments.length === 0) return null

  return (
    <div className="composer-staged-chips" role="list" aria-label="Attachments for this message">
      {attachments.map((att) => {
        const uploading = att.upload_status === 'uploading' || isPendingAttachmentId(att.id)
        const failed = att.upload_status === 'failed'
        return (
          <div
            key={att.id}
            className={[
              'composer-staged-chip',
              uploading ? 'composer-staged-chip-uploading' : '',
              failed ? 'composer-staged-chip-failed' : '',
            ]
              .filter(Boolean)
              .join(' ')}
            role="listitem"
          >
            {uploading ? (
              <span className="composer-staged-chip-spinner" aria-label="Uploading">
                <LoadingSpinner size="sm" />
              </span>
            ) : null}
            <span className="composer-staged-chip-name" title={att.filename}>
              {att.filename}
            </span>
            <button
              type="button"
              className="composer-staged-chip-remove"
              aria-label={`Remove ${att.filename}`}
              title="Remove"
              disabled={disabled}
              onClick={() => onRemove(att.id)}
            >
              <X size={14} strokeWidth={2} aria-hidden="true" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
