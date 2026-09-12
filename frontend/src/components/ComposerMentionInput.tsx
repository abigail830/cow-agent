import type { ClipboardEvent, KeyboardEvent, RefObject } from 'react'
import type { ChatAttachment } from '../types'
import { segmentInputByMentions } from '../lib/attachmentMentions'

type ComposerMentionInputProps = {
  textareaRef: RefObject<HTMLTextAreaElement | null>
  value: string
  attachments: ChatAttachment[]
  placeholder?: string
  disabled?: boolean
  onChange: (value: string) => void
  onSelect: () => void
  onPaste: (event: ClipboardEvent<HTMLTextAreaElement>) => void
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
}

export function ComposerMentionInput({
  textareaRef,
  value,
  attachments,
  placeholder,
  disabled = false,
  onChange,
  onSelect,
  onPaste,
  onKeyDown,
}: ComposerMentionInputProps) {
  const segments = segmentInputByMentions(value, attachments)

  return (
    <div className="composer-mention-input">
      <div className="composer-mention-input-mirror" aria-hidden="true">
        {segments.length === 0 ? (
          <span className="composer-mention-input-placeholder">{placeholder}</span>
        ) : (
          segments.map((segment, index) => {
            if (segment.kind === 'text') {
              return <span key={index}>{segment.value}</span>
            }
            return (
              <span
                key={index}
                className="composer-mention-chip"
                title={segment.attachment.filename}
              >
                {segment.value}
              </span>
            )
          })
        )}
      </div>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onSelect={onSelect}
        onClick={onSelect}
        onPaste={onPaste}
        onKeyDown={onKeyDown}
        placeholder=""
        className="chat-composer-textarea composer-mention-input-textarea"
        aria-label={placeholder}
        disabled={disabled}
        spellCheck
      />
    </div>
  )
}
