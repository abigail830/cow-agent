import { useState } from 'react'
import type { ChatAttachment, Message, MessageAttachmentMeta } from '../types'
import { MarkdownContent } from './MarkdownContent'
import { segmentInputByMentions } from '../lib/attachmentMentions'
import { formatUserFacingError } from '../lib/userFacingError'
import { ArtifactCopyIcon } from './ArtifactCopyIcon'
import { ArtifactForkIcon } from './ArtifactForkIcon'
import { LoadingSpinner } from './LoadingSpinner'

interface Props {
  message: Message
}

function messageAttachments(message: Message): MessageAttachmentMeta[] {
  const raw = message.metadata?.attachments
  if (!Array.isArray(raw)) return []
  return raw.filter(
    (item): item is MessageAttachmentMeta =>
      !!item &&
      typeof item === 'object' &&
      typeof (item as MessageAttachmentMeta).filename === 'string',
  )
}

function toChatAttachments(
  chatId: string,
  items: MessageAttachmentMeta[],
): ChatAttachment[] {
  return items.map((item) => ({
    id: item.id,
    chat_id: chatId,
    filename: item.filename,
    mime_type: item.mime_type,
    size_bytes: item.size_bytes,
    provider: item.provider,
    provider_file_id: item.provider_file_id,
    created_at: null,
  }))
}

function UserMessageBody({
  content,
  attachments,
  chatId,
}: {
  content: string
  attachments: MessageAttachmentMeta[]
  chatId: string
}) {
  const chatAttachmentRows = toChatAttachments(chatId, attachments)
  const segments = segmentInputByMentions(content, chatAttachmentRows)
  const mentionedIds = new Set<string>()
  for (const segment of segments) {
    if (segment.kind === 'mention') mentionedIds.add(segment.attachment.id)
  }
  const unstagedAttachments = attachments.filter((item) => !mentionedIds.has(item.id))

  if (segments.length === 0) {
    if (attachments.length === 0) return null
    return (
      <p className="msg-user-body whitespace-pre-wrap">
        {attachments.map((item) => (
          <span key={item.id} className="msg-user-attachment-chip" title={item.filename}>
            {item.filename}
          </span>
        ))}
      </p>
    )
  }

  return (
    <p className="msg-user-body whitespace-pre-wrap">
      {unstagedAttachments.map((item) => (
        <span key={item.id} className="msg-user-attachment-chip" title={item.filename}>
          {item.filename}
        </span>
      ))}
      {segments.map((segment, index) =>
        segment.kind === 'text' ? (
          <span key={index}>{segment.value}</span>
        ) : (
          <span
            key={index}
            className="msg-user-attachment-chip"
            title={segment.attachment.filename}
          >
            {segment.attachment.filename}
          </span>
        ),
      )}
    </p>
  )
}

function CopyCheckIcon() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M5 13l4 4L19 7" />
    </svg>
  )
}

function MessageCopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const trimmed = text.trim()
  if (!trimmed) return null

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(trimmed)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <button
      type="button"
      className={`msg-copy-btn${copied ? ' msg-copy-btn-copied' : ''}`}
      aria-label={copied ? 'Copied' : 'Copy message'}
      title={copied ? 'Copied' : 'Copy'}
      onClick={() => void handleCopy()}
    >
      {copied ? <CopyCheckIcon /> : <ArtifactCopyIcon />}
    </button>
  )
}

/** Actions at the end of an assistant turn: copy reply text + fork chat. */
export function AssistantTurnActionRow({
  copyText,
  onFork,
  forking = false,
}: {
  copyText: string
  onFork?: () => void
  forking?: boolean
}) {
  if (!copyText.trim() && !onFork) return null
  return (
    <div className="msg-wrap msg-wrap-assistant">
      <div className="msg-copy-row">
        {copyText.trim() ? <MessageCopyButton text={copyText} /> : null}
        {onFork ? (
          <button
            type="button"
            className="msg-copy-btn"
            aria-label={forking ? 'Forking chat' : 'Fork chat'}
            title={forking ? 'Forking…' : 'Fork'}
            disabled={forking}
            aria-busy={forking}
            onClick={() => onFork()}
          >
            {forking ? <LoadingSpinner size="sm" className="msg-fork-spinner" /> : <ArtifactForkIcon />}
          </button>
        ) : null}
      </div>
    </div>
  )
}

/** @deprecated use AssistantTurnActionRow */
export function AssistantTurnCopyRow({ text }: { text: string }) {
  return <AssistantTurnActionRow copyText={text} />
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const attachments = messageAttachments(message)
  const userCopyText = isUser ? (message.content ?? '').trim() : ''

  if (message.message_type === 'run_cancelled') {
    return (
      <div className="flex justify-center">
        <p className="chat-cancel-notice">{message.content}</p>
      </div>
    )
  }

  if (message.message_type === 'error') {
    return (
      <div className="flex justify-start">
        <div className="chat-assistant-block msg-assistant rounded-sm border border-brand-200 px-3 py-2 text-[12px] text-brand-700">
          {formatUserFacingError(message.content, 'Assistant run failed')}
        </div>
      </div>
    )
  }

  if (message.message_type === 'cancelled' && message.metadata?.original_type === 'text') {
    return (
      <div className="msg-wrap msg-wrap-assistant">
        <div className="chat-assistant-block msg-assistant msg-assistant-cancelled rounded-sm px-3 py-2 text-[12px] leading-relaxed">
          <MarkdownContent content={message.content ?? ''} />
        </div>
      </div>
    )
  }

  if (message.message_type !== 'text') {
    return null
  }

  const streaming = message.metadata?.streaming === true

  return (
    <div className={`msg-wrap ${isUser ? 'msg-wrap-user' : 'msg-wrap-assistant'}`}>
      <div
        className={`rounded-sm px-3 py-2 text-[12px] leading-relaxed ${
          isUser ? 'msg-user max-w-[78%]' : 'chat-assistant-block msg-assistant'
        }`}
      >
        {isUser ? (
          <UserMessageBody
            content={message.content ?? ''}
            attachments={attachments}
            chatId={message.chat_id}
          />
        ) : (
          <>
            <MarkdownContent content={message.content ?? ''} />
            {streaming && (
              <span className="mt-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500" />
            )}
          </>
        )}
      </div>
      {isUser && userCopyText ? (
        <div className="msg-copy-row">
          <MessageCopyButton text={userCopyText} />
        </div>
      ) : null}
    </div>
  )
}
