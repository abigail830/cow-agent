import { useEffect } from 'react'
import type { ChatSummary } from '../types'

type Props = {
  open: boolean
  chats: ChatSummary[]
  activeChatId: string | null
  loading: boolean
  onClose: () => void
  onSelect: (chatId: string) => void
}

type ChatGroup = {
  label: string
  chats: ChatSummary[]
}

function groupChats(chats: ChatSummary[]): ChatGroup[] {
  const now = Date.now()
  const ms7d = 7 * 24 * 60 * 60 * 1000
  const startOfToday = new Date()
  startOfToday.setHours(0, 0, 0, 0)
  const todayStart = startOfToday.getTime()

  const today: ChatSummary[] = []
  const last7: ChatSummary[] = []
  const older: ChatSummary[] = []

  for (const chat of chats) {
    const iso = chat.updated_at ?? chat.created_at
    const ts = iso ? new Date(iso).getTime() : 0
    if (ts >= todayStart) today.push(chat)
    else if (now - ts <= ms7d) last7.push(chat)
    else older.push(chat)
  }

  const groups: ChatGroup[] = []
  if (today.length) groups.push({ label: 'Today', chats: today })
  if (last7.length) groups.push({ label: 'Last 7 days', chats: last7 })
  if (older.length) groups.push({ label: 'Older', chats: older })
  return groups
}

export function ChatHistoryPanel({
  open,
  chats,
  activeChatId,
  loading,
  onClose,
  onSelect,
}: Props) {
  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  const groups = groupChats(chats)

  return (
    <aside
      className={`chat-history-panel ${open ? 'chat-history-panel-open' : ''}`}
      aria-hidden={!open}
    >
      <div className="chat-history-panel-inner">
        <div className="chat-history-panel-header">
          <button
            type="button"
            className="chat-history-panel-close"
            onClick={onClose}
            aria-label="Close chat history"
            title="Close"
          >
            <svg
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              aria-hidden
            >
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </button>
        </div>

        <div className="chat-history-panel-scroll">
          {loading && <p className="chat-history-panel-empty">Loading…</p>}
          {!loading && chats.length === 0 && (
            <p className="chat-history-panel-empty">No conversations yet</p>
          )}
          {!loading &&
            groups.map((group) => (
              <section key={group.label} className="chat-history-panel-group">
                <h2 className="chat-history-panel-heading">{group.label}</h2>
                <ul className="chat-history-panel-list">
                  {group.chats.map((chat) => {
                    const active = chat.id === activeChatId
                    return (
                      <li key={chat.id}>
                        <button
                          type="button"
                          className={`chat-history-panel-item ${active ? 'chat-history-panel-item-active' : ''}`}
                          onClick={() => onSelect(chat.id)}
                        >
                          {chat.title || 'New Chat'}
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </section>
            ))}
        </div>
      </div>
    </aside>
  )
}
