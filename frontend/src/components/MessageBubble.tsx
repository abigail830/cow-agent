import type { ChatAttachment, Message, MessageAttachmentMeta } from '../types'
import { MarkdownContent } from './MarkdownContent'
import { segmentInputByMentions } from '../lib/attachmentMentions'
import { formatUserFacingError } from '../lib/userFacingError'

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

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const attachments = messageAttachments(message)

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
      <div className="flex justify-start">
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
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
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
    </div>
  )
}
