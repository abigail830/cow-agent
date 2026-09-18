import { useLayoutEffect, useRef } from 'react'
import type { ClipboardEvent, KeyboardEvent, RefObject, UIEvent } from 'react'
import type { ChatAttachment } from '../types'
import { segmentInputByMentions } from '../lib/attachmentMentions'

const COMPOSER_MAX_LINES = 4

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
  const mirrorRef = useRef<HTMLDivElement>(null)
  const segments = segmentInputByMentions(value, attachments)

  useLayoutEffect(() => {
    const textarea = textareaRef.current
    const mirror = mirrorRef.current
    if (!textarea || !mirror) return

    const syncHeight = () => {
      const styles = window.getComputedStyle(textarea)
      const fontSize = Number.parseFloat(styles.fontSize) || 14
      const lineHeightRaw = styles.lineHeight
      const lineHeight =
        lineHeightRaw === 'normal'
          ? fontSize * 1.65
          : Number.parseFloat(lineHeightRaw) || fontSize * 1.65
      const minHeight = Number.parseFloat(styles.minHeight) || lineHeight
      const maxHeight = lineHeight * COMPOSER_MAX_LINES

      textarea.style.height = '0px'
      mirror.style.height = 'auto'
      const contentHeight = Math.max(mirror.scrollHeight, textarea.scrollHeight, minHeight)
      const nextHeight = Math.min(contentHeight, maxHeight)
      const overflow = contentHeight > maxHeight

      textarea.style.height = `${nextHeight}px`
      mirror.style.height = `${nextHeight}px`
      textarea.style.overflowY = overflow ? 'auto' : 'hidden'
      mirror.scrollTop = textarea.scrollTop
    }

    syncHeight()

    const observer = new ResizeObserver(syncHeight)
    observer.observe(mirror)
    return () => observer.disconnect()
  }, [textareaRef, value, attachments, placeholder])

  const syncMirrorScroll = (event: UIEvent<HTMLTextAreaElement>) => {
    const mirror = mirrorRef.current
    if (mirror) mirror.scrollTop = event.currentTarget.scrollTop
  }

  return (
    <div className="composer-mention-input">
      <div ref={mirrorRef} className="composer-mention-input-mirror" aria-hidden="true">
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
        onScroll={syncMirrorScroll}
        placeholder=""
        className="chat-composer-textarea composer-mention-input-textarea"
        aria-label={placeholder}
        disabled={disabled}
        spellCheck
        rows={1}
      />
    </div>
  )
}
