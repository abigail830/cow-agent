import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { DatabaseSearch } from 'lucide-react'
import { api } from '../api/client'
import type { KnowledgeBaseItem } from '../types'

type Props = {
  agentId: string
  disabled?: boolean
}

export function KbScopePopover({ agentId, disabled = false }: Props) {
  const panelId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [items, setItems] = useState<KnowledgeBaseItem[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.listAgentKnowledgeBases(agentId)
      setConnected(result.connected)
      setMessage(result.message ?? null)
      setItems(result.items)
    } catch (err) {
      setConnected(false)
      setItems([])
      setError(err instanceof Error ? err.message : 'Failed to load knowledge bases')
    } finally {
      setLoading(false)
    }
  }, [agentId])

  useEffect(() => {
    if (!open) return
    void load()
  }, [open, load])

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const persist = async (nextItems: KnowledgeBaseItem[]) => {
    setSaving(true)
    setError(null)
    const disabledIds = nextItems.filter((item) => !item.enabled).map((item) => item.id)
    try {
      await api.putAgentKbPreferences(agentId, disabledIds)
      setItems(nextItems)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save preference')
      await load()
    } finally {
      setSaving(false)
    }
  }

  const toggleOne = (id: string, enabled: boolean) => {
    const next = items.map((item) => (item.id === id ? { ...item, enabled } : item))
    void persist(next)
  }

  const setAll = (enabled: boolean) => {
    void persist(items.map((item) => ({ ...item, enabled })))
  }

  const enabledCount = items.filter((item) => item.enabled).length
  const active = open || (items.length > 0 && enabledCount < items.length)

  return (
    <div ref={rootRef} className="kb-scope-popover-root">
      <button
        type="button"
        className={`chat-composer-attach-btn${active ? ' chat-composer-attach-btn-active' : ''}`}
        disabled={disabled}
        onClick={() => setOpen((value) => !value)}
        aria-label="Knowledge bases"
        title="Knowledge bases"
        aria-expanded={open}
        aria-controls={panelId}
      >
        <DatabaseSearch size={16} strokeWidth={1.75} aria-hidden="true" />
      </button>
      {open ? (
        <div id={panelId} className="kb-scope-popover" role="dialog" aria-label="Knowledge base scope">
          <div className="kb-scope-popover-header">
            <div className="kb-scope-popover-title">Knowledge bases</div>
            {connected && items.length > 0 ? (
              <div className="kb-scope-popover-actions">
                <button type="button" onClick={() => setAll(true)} disabled={saving || loading}>
                  All on
                </button>
                <button type="button" onClick={() => setAll(false)} disabled={saving || loading}>
                  All off
                </button>
              </div>
            ) : null}
          </div>
          {loading ? <p className="kb-scope-popover-status">Loading…</p> : null}
          {!loading && error ? <p className="kb-scope-popover-error">{error}</p> : null}
          {!loading && !error && !connected ? (
            <p className="kb-scope-popover-status">
              {message || 'Connect Hybrid Search in Integrations to list knowledge bases.'}
            </p>
          ) : null}
          {!loading && !error && connected && items.length === 0 ? (
            <p className="kb-scope-popover-status">{message || 'No knowledge bases visible for this key.'}</p>
          ) : null}
          {!loading && connected && items.length > 0 ? (
            <ul className="kb-scope-popover-list">
              {items.map((item) => (
                <li key={item.id}>
                  <label className="kb-scope-popover-item">
                    <input
                      type="checkbox"
                      checked={item.enabled}
                      disabled={saving}
                      onChange={(event) => toggleOne(item.id, event.target.checked)}
                    />
                    <span className="kb-scope-popover-item-text">
                      <span className="kb-scope-popover-item-name">{item.name}</span>
                      {item.type || typeof item.item_count === 'number' ? (
                        <span className="kb-scope-popover-item-meta">
                          {[item.type, typeof item.item_count === 'number' ? `${item.item_count} docs` : null]
                            .filter(Boolean)
                            .join(' · ')}
                        </span>
                      ) : null}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          ) : null}
          {saving ? <p className="kb-scope-popover-status">Saving…</p> : null}
        </div>
      ) : null}
    </div>
  )
}
