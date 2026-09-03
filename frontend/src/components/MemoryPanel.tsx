import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import { formatAgentLabel } from '../lib/agentLabel'
import type { Agent, MemoryBullet, MemoryDocument } from '../types'

type Props = {
  open: boolean
  agents: Agent[]
  activeAgentId: string | null
  refreshKey?: number
  onClose: () => void
}

type ScopeKey = 'user' | `agent:${string}`

function scopeKeyForUser(): ScopeKey {
  return 'user'
}

function scopeKeyForAgent(agentId: string): ScopeKey {
  return `agent:${agentId}`
}

type DraftState = {
  line: string
  isConstraint: boolean
}

function MemoryBulletList({
  bullets,
  saving,
  onRemove,
}: {
  bullets: MemoryBullet[]
  saving: boolean
  onRemove: (match: string) => void
}) {
  if (bullets.length === 0) {
    return <p className="memory-scope-empty">No memories yet.</p>
  }
  return (
    <ul className="memory-panel-list">
      {bullets.map((bullet) => (
        <li key={bullet.line} className="memory-panel-item">
          <span
            className={
              bullet.kind === 'constraint'
                ? 'memory-panel-badge memory-panel-badge-constraint'
                : 'memory-panel-badge'
            }
          >
            {bullet.kind === 'constraint' ? 'constraint' : 'bullet'}
          </span>
          <span className="memory-panel-item-text">{bullet.text}</span>
          <button
            type="button"
            className="memory-panel-item-remove"
            disabled={saving}
            onClick={() => onRemove(bullet.text)}
            aria-label={`Remove ${bullet.text}`}
          >
            ×
          </button>
        </li>
      ))}
    </ul>
  )
}

function MemoryScopeBlock({
  scopeKey,
  title,
  subtitle,
  doc,
  expanded,
  isActive,
  saving,
  draft,
  onToggle,
  onDraftChange,
  onAdd,
  onRemove,
}: {
  scopeKey: ScopeKey
  title: string
  subtitle?: string
  doc: MemoryDocument | null
  expanded: boolean
  isActive?: boolean
  saving: boolean
  draft: DraftState
  onToggle: () => void
  onDraftChange: (next: DraftState) => void
  onAdd: () => void
  onRemove: (match: string) => void
}) {
  const count = doc?.bullets.length ?? 0

  return (
    <section
      className={`memory-scope-block${expanded ? ' memory-scope-block-expanded' : ''}${
        isActive ? ' memory-scope-block-active' : ''
      }`}
      data-scope={scopeKey}
    >
      <button
        type="button"
        className="memory-scope-header"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <span className="memory-scope-chevron" aria-hidden>
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 6l6 6-6 6" />
          </svg>
        </span>
        <span className="memory-scope-header-text">
          <span className="memory-scope-title">{title}</span>
          {subtitle && <span className="memory-scope-subtitle">{subtitle}</span>}
        </span>
        <span className="memory-scope-count">{count}</span>
      </button>

      {expanded && (
        <div className="memory-scope-body">
          <MemoryBulletList bullets={doc?.bullets ?? []} saving={saving} onRemove={onRemove} />
          <div className="memory-scope-add">
            <label className="memory-panel-add-label">
              <input
                type="checkbox"
                checked={draft.isConstraint}
                onChange={(e) => onDraftChange({ ...draft, isConstraint: e.target.checked })}
              />
              Constraint ([!])
            </label>
            <div className="memory-panel-add-row">
              <input
                type="text"
                className="memory-panel-add-input"
                placeholder={draft.isConstraint ? 'e.g. 不要使用表格' : 'e.g. 回复用中文'}
                value={draft.line}
                onChange={(e) => onDraftChange({ ...draft, line: e.target.value })}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onAdd()
                }}
                disabled={saving}
              />
              <button
                type="button"
                className="btn btn-secondary memory-panel-add-btn"
                disabled={saving || !draft.line.trim()}
                onClick={onAdd}
              >
                Add
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

export function MemoryPanel({ open, agents, activeAgentId, refreshKey = 0, onClose }: Props) {
  const [userDoc, setUserDoc] = useState<MemoryDocument | null>(null)
  const [agentDocs, setAgentDocs] = useState<Record<string, MemoryDocument | null>>({})
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [drafts, setDrafts] = useState<Record<string, DraftState>>({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ensureDraft = useCallback((key: string): DraftState => {
    return drafts[key] ?? { line: '', isConstraint: false }
  }, [drafts])

  const setDraft = useCallback((key: string, next: DraftState) => {
    setDrafts((prev) => ({ ...prev, [key]: next }))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const user = await api.getUserMemory()
      const pairs = await Promise.all(
        agents.map(async (agent) => {
          const doc = await api.getAgentMemory(agent.id)
          return [agent.id, doc] as const
        }),
      )
      setUserDoc(user)
      setAgentDocs(Object.fromEntries(pairs))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load memory')
    } finally {
      setLoading(false)
    }
  }, [agents])

  useEffect(() => {
    if (!open) return
    void load()
  }, [open, load, refreshKey])

  useEffect(() => {
    if (!open) return
    setExpanded((prev) => {
      const next = { ...prev }
      if (!('user' in next)) next.user = true
      for (const agent of agents) {
        const key = scopeKeyForAgent(agent.id)
        if (!(key in next)) next[key] = agent.id === activeAgentId
      }
      return next
    })
  }, [open, agents, activeAgentId])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  const toggleSection = (key: string) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleAdd = async (scopeKey: ScopeKey) => {
    const draft = ensureDraft(scopeKey)
    const text = draft.line.trim()
    if (!text) return

    setSaving(true)
    setError(null)
    try {
      if (scopeKey === 'user') {
        const updated = await api.appendMemory({
          scope: 'user',
          lines: [text],
          is_constraint: draft.isConstraint,
        })
        setUserDoc(updated)
      } else {
        const agentId = scopeKey.slice('agent:'.length)
        const updated = await api.appendMemory({
          scope: 'agent',
          agent_id: agentId,
          lines: [text],
          is_constraint: draft.isConstraint,
        })
        setAgentDocs((prev) => ({ ...prev, [agentId]: updated }))
      }
      setDraft(scopeKey, { line: '', isConstraint: false })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add memory')
    } finally {
      setSaving(false)
    }
  }

  const handleRemove = async (scopeKey: ScopeKey, match: string) => {
    setSaving(true)
    setError(null)
    try {
      if (scopeKey === 'user') {
        const updated = await api.removeMemory({ scope: 'user', match })
        setUserDoc(updated)
      } else {
        const agentId = scopeKey.slice('agent:'.length)
        const updated = await api.removeMemory({ scope: 'agent', agent_id: agentId, match })
        setAgentDocs((prev) => ({ ...prev, [agentId]: updated }))
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to remove memory')
    } finally {
      setSaving(false)
    }
  }

  return (
    <aside className={`memory-panel ${open ? 'memory-panel-open' : ''}`} aria-hidden={!open}>
      <div className="memory-panel-inner">
        <div className="memory-panel-header">
          <div className="memory-panel-title-wrap">
            <img src="/alzheimer.png" alt="" className="memory-panel-icon" width={20} height={20} />
            <h2 className="memory-panel-title">Memory</h2>
          </div>
          <button
            type="button"
            className="memory-panel-close"
            onClick={onClose}
            aria-label="Close memory panel"
            title="Close"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="memory-panel-hint">
          Use <code>记住 …</code> or <code>不要总是 …</code> in chat. Only explicit commands are saved.
        </div>

        {error && <p className="memory-panel-error">{error}</p>}

        <div className="memory-panel-scroll">
          {loading ? (
            <p className="memory-panel-empty">Loading…</p>
          ) : (
            <>
              <MemoryScopeBlock
                scopeKey={scopeKeyForUser()}
                title="My preferences"
                subtitle="Cross-agent"
                doc={userDoc}
                expanded={!!expanded.user}
                saving={saving}
                draft={ensureDraft('user')}
                onToggle={() => toggleSection('user')}
                onDraftChange={(next) => setDraft('user', next)}
                onAdd={() => void handleAdd('user')}
                onRemove={(match) => void handleRemove('user', match)}
              />

              {agents.length > 0 && (
                <div className="memory-scope-group">
                  <p className="memory-scope-group-label">Agents</p>
                  {agents.map((agent) => {
                    const key = scopeKeyForAgent(agent.id)
                    return (
                      <MemoryScopeBlock
                        key={agent.id}
                        scopeKey={key}
                        title={formatAgentLabel(agent)}
                        doc={agentDocs[agent.id] ?? null}
                        expanded={!!expanded[key]}
                        isActive={agent.id === activeAgentId}
                        saving={saving}
                        draft={ensureDraft(key)}
                        onToggle={() => toggleSection(key)}
                        onDraftChange={(next) => setDraft(key, next)}
                        onAdd={() => void handleAdd(key)}
                        onRemove={(match) => void handleRemove(key, match)}
                      />
                    )
                  })}
                </div>
              )}
            </>
          )}
        </div>

        <div className="memory-panel-footer">
          <button
            type="button"
            className="btn btn-secondary"
            disabled={saving || loading}
            onClick={() => void load()}
          >
            Refresh
          </button>
        </div>
      </div>
    </aside>
  )
}
