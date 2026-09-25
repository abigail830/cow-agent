import { LoadingSpinner } from './LoadingSpinner'
import { NewChatIcon } from './NewChatIcon'
import type { ChatSummary } from '../types'

type Props = {
  agentName: string
  agentDescription: string | null
  lastChat: ChatSummary | null
  busy: boolean
  onNewConversation: () => void
  onContinueLast: () => void
}

function formatLastOpened(iso: string | null | undefined): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function ChatStandbyPanel({
  agentName,
  agentDescription,
  lastChat,
  busy,
  onNewConversation,
  onContinueLast,
}: Props) {
  const lastOpenedLabel = lastChat
    ? formatLastOpened(lastChat.updated_at ?? lastChat.created_at)
    : ''

  return (
    <div className="chat-standby-panel">
      <div className="chat-standby-inner">
        <h2 className="chat-standby-greeting">Hi, I&apos;m {agentName}</h2>
        {agentDescription ? (
          <p className="chat-standby-description">{agentDescription}</p>
        ) : (
          <p className="chat-standby-description">What would you like to work on?</p>
        )}
        <div className="chat-standby-actions">
          <button
            type="button"
            className="chat-standby-btn chat-standby-btn-primary"
            disabled={busy}
            onClick={onNewConversation}
          >
            {busy ? (
              <LoadingSpinner size="sm" />
            ) : (
              <NewChatIcon className="chat-standby-btn-icon" />
            )}
            <span>New conversation</span>
          </button>
          {lastChat ? (
            <button
              type="button"
              className="chat-standby-btn chat-standby-btn-secondary"
              disabled={busy}
              onClick={onContinueLast}
            >
              <span className="chat-standby-btn-label">Continue last conversation</span>
              <span className="chat-standby-btn-meta">
                {lastChat.title || 'Untitled chat'}
                {lastOpenedLabel ? ` · ${lastOpenedLabel}` : ''}
              </span>
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
