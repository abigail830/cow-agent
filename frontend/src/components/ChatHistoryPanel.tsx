import { useEffect, useState } from 'react'
import { Trash2 } from 'lucide-react'
import { LoadingSpinner } from './LoadingSpinner'
import type { ChatSummary } from '../types'

type Props = {
  open: boolean
  chats: ChatSummary[]
  activeChatId: string | null
  loading: boolean
  deletingChatId?: string | null
  onClose: () => void
  onSelect: (chatId: string) => void
  onDelete: (chatId: string) => Promise<void>
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

function chatLabel(chat: ChatSummary): string {
  return chat.title?.trim() || 'New Chat'
}

export function ChatHistoryPanel({
  open,
  chats,
  activeChatId,
  loading,
  deletingChatId = null,
  onClose,
  onSelect,
  onDelete,
}: Props) {
  const [pendingDelete, setPendingDelete] = useState<ChatSummary | null>(null)

  useEffect(() => {
    if (!open) setPendingDelete(null)
  }, [open])

  useEffect(() => {
    if (!pendingDelete) return
    if (!chats.some((chat) => chat.id === pendingDelete.id)) {
      setPendingDelete(null)
    }
  }, [chats, pendingDelete])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (pendingDelete) {
        setPendingDelete(null)
        return
      }
      onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose, pendingDelete])

  const groups = groupChats(chats)

  const handleConfirmDelete = () => {
    if (!pendingDelete) return
    const chatId = pendingDelete.id
    setPendingDelete(null)
    void onDelete(chatId)
  }

  return (
    <>
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
                    const deleting = chat.id === deletingChatId
                    const title = chatLabel(chat)
                    return (
                      <li
                        key={chat.id}
                        className={`chat-history-panel-row${active ? ' chat-history-panel-row-active' : ''}${deleting ? ' chat-history-panel-row-deleting' : ''}`}
                      >
                        <button
                          type="button"
                          className={`chat-history-panel-item ${active ? 'chat-history-panel-item-active' : ''}`}
                          onClick={() => onSelect(chat.id)}
                          disabled={deleting}
                        >
                          {title}
                        </button>
                        <button
                          type="button"
                          className={`chat-history-panel-delete${deleting ? ' chat-history-panel-delete-busy' : ''}`}
                          onClick={(event) => {
                            event.stopPropagation()
                            if (!deleting) setPendingDelete(chat)
                          }}
                          disabled={deleting}
                          aria-busy={deleting}
                          aria-label={deleting ? `Deleting ${title}` : `Delete ${title}`}
                          title={deleting ? 'Deleting…' : 'Delete'}
                        >
                          {deleting ? (
                            <LoadingSpinner size="sm" className="chat-history-delete-spinner" />
                          ) : (
                            <Trash2 size={14} strokeWidth={2} aria-hidden />
                          )}
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

      {pendingDelete ? (
        <div
          className="chat-history-delete-overlay"
          role="presentation"
          onClick={() => setPendingDelete(null)}
        >
          <div
            className="chat-history-delete-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="chat-history-delete-title"
            aria-describedby="chat-history-delete-desc"
            onClick={(event) => event.stopPropagation()}
          >
            <h3 id="chat-history-delete-title">Delete conversation?</h3>
            <p id="chat-history-delete-desc">
              This permanently deletes “{chatLabel(pendingDelete)}” and all of its
              messages, files, and artifacts. This cannot be undone.
            </p>
            <div className="chat-history-delete-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setPendingDelete(null)}
              >
                Cancel
              </button>
              <button type="button" className="btn btn-danger" onClick={handleConfirmDelete}>
                Delete
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
