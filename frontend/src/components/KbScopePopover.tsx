import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { DatabaseSearch } from 'lucide-react'
import { api } from '../api/client'
import type { KnowledgeBaseItem } from '../types'

type Props = {
  agentId: string
  disabled?: boolean
}

type KbListCacheEntry = {
  at: number
  connected: boolean
  message: string | null
  items: KnowledgeBaseItem[]
}

const KB_LIST_CACHE_TTL_MS = 60_000
const PERSIST_DEBOUNCE_MS = 280
const kbListCache = new Map<string, KbListCacheEntry>()

function formatKbMeta(item: KnowledgeBaseItem): string | null {
  const parts = [
    item.type,
    typeof item.item_count === 'number' ? `${item.item_count} docs` : null,
  ].filter(Boolean)
  return parts.length > 0 ? parts.join(' · ') : null
}

export function KbScopePopover({ agentId, disabled = false }: Props) {
  const panelId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const persistTimerRef = useRef<number | null>(null)
  const persistSeqRef = useRef(0)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [items, setItems] = useState<KnowledgeBaseItem[]>([])

  const applyCacheEntry = useCallback((entry: KbListCacheEntry) => {
    setConnected(entry.connected)
    setMessage(entry.message)
    setItems(entry.items)
  }, [])

  const load = useCallback(
    async (opts?: { force?: boolean; silent?: boolean }) => {
      const cached = kbListCache.get(agentId)
      const cacheFresh = cached != null && Date.now() - cached.at < KB_LIST_CACHE_TTL_MS

      if (cached && !opts?.force) {
        applyCacheEntry(cached)
        if (cacheFresh) {
          setLoading(false)
          return
        }
      }

      if (!opts?.silent && !cached) {
        setLoading(true)
      }
      setError(null)
      try {
        const result = await api.listAgentKnowledgeBases(agentId)
        const entry: KbListCacheEntry = {
          at: Date.now(),
          connected: result.connected,
          message: result.message ?? null,
          items: result.items,
        }
        kbListCache.set(agentId, entry)
        applyCacheEntry(entry)
      } catch (err) {
        setConnected(false)
        setItems([])
        setError(err instanceof Error ? err.message : 'Failed to load knowledge bases')
      } finally {
        setLoading(false)
      }
    },
    [agentId, applyCacheEntry],
  )

  useEffect(() => {
    setItems([])
    setConnected(false)
    setMessage(null)
    void load({ silent: true })
  }, [agentId, load])

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

  useEffect(
    () => () => {
      if (persistTimerRef.current != null) {
        window.clearTimeout(persistTimerRef.current)
      }
    },
    [],
  )

  const flushPersist = useCallback(
    async (nextItems: KnowledgeBaseItem[]) => {
      const seq = ++persistSeqRef.current
      setSaving(true)
      setError(null)
      const disabledIds = nextItems.filter((item) => !item.enabled).map((item) => item.id)
      try {
        await api.putAgentKbPreferences(agentId, disabledIds)
        if (seq !== persistSeqRef.current) return
        const cached = kbListCache.get(agentId)
        if (cached) {
          kbListCache.set(agentId, { ...cached, at: Date.now(), items: nextItems })
        }
      } catch (err) {
        if (seq !== persistSeqRef.current) return
        setError(err instanceof Error ? err.message : 'Failed to save preference')
        await load({ force: true })
      } finally {
        if (seq === persistSeqRef.current) {
          setSaving(false)
        }
      }
    },
    [agentId, load],
  )

  const schedulePersist = useCallback(
    (nextItems: KnowledgeBaseItem[], options?: { immediate?: boolean }) => {
      setItems(nextItems)
      if (persistTimerRef.current != null) {
        window.clearTimeout(persistTimerRef.current)
        persistTimerRef.current = null
      }
      if (options?.immediate) {
        void flushPersist(nextItems)
        return
      }
      persistTimerRef.current = window.setTimeout(() => {
        persistTimerRef.current = null
        void flushPersist(nextItems)
      }, PERSIST_DEBOUNCE_MS)
    },
    [flushPersist],
  )

  const toggleOne = (id: string, enabled: boolean) => {
    const next = items.map((item) => (item.id === id ? { ...item, enabled } : item))
    schedulePersist(next)
  }

  const setAll = (enabled: boolean) => {
    schedulePersist(
      items.map((item) => ({ ...item, enabled })),
      { immediate: true },
    )
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
                <button type="button" onClick={() => setAll(true)} disabled={loading}>
                  All on
                </button>
                <button type="button" onClick={() => setAll(false)} disabled={loading}>
                  All off
                </button>
              </div>
            ) : null}
          </div>
          {loading && items.length === 0 ? <p className="kb-scope-popover-status">Loading…</p> : null}
          {!loading && error ? <p className="kb-scope-popover-error">{error}</p> : null}
          {!error && !connected && !(loading && items.length === 0) ? (
            <p className="kb-scope-popover-status">
              {message || 'Connect Hybrid Search in Integrations to list knowledge bases.'}
            </p>
          ) : null}
          {!error && connected && items.length === 0 && !loading ? (
            <p className="kb-scope-popover-status">{message || 'No knowledge bases visible for this key.'}</p>
          ) : null}
          {connected && items.length > 0 ? (
            <ul className="kb-scope-popover-list">
              {items.map((item) => {
                const meta = formatKbMeta(item)
                return (
                  <li key={item.id}>
                    <label className="kb-scope-popover-item">
                      <input
                        type="checkbox"
                        checked={item.enabled}
                        onChange={(event) => toggleOne(item.id, event.target.checked)}
                      />
                      <span className="kb-scope-popover-item-text">
                        <span className="kb-scope-popover-item-name">{item.name}</span>
                        {meta ? <span className="kb-scope-popover-item-meta">{meta}</span> : null}
                      </span>
                    </label>
                  </li>
                )
              })}
            </ul>
          ) : null}
          {saving ? <p className="kb-scope-popover-status kb-scope-popover-saving">Saving…</p> : null}
        </div>
      ) : null}
    </div>
  )
}
