import type { Message, MessageAttachmentMeta } from '../types'
import { MarkdownContent } from './MarkdownContent'

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
          <>
            {attachments.length > 0 && (
              <ul className="msg-user-attachments">
                {attachments.map((item) => (
                  <li key={item.id}>{item.filename}</li>
                ))}
              </ul>
            )}
            {message.content ? <p className="whitespace-pre-wrap">{message.content}</p> : null}
          </>
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
