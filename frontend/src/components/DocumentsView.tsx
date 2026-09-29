import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { ExternalLink, FileImage, FileText, Search, Sparkles, Workflow, X } from 'lucide-react'
import { api } from '../api/client'
import { LoadingSpinner } from './LoadingSpinner'
import { ArtifactPanelContent } from './ArtifactPanelHost'
import { ParsedDocumentPreview } from './ParsedDocumentPreview'
import { formatAttachmentTimestamp } from '../lib/attachmentMentions'
import { parseStatusDisplayLabel } from '../lib/documentParseDisplay'
import { artifactCardSubtitle, isSidePanelArtifact } from '../lib/artifactKinds'
import { downloadArtifactFile } from '../lib/artifactDownload'
import { formatFileSize } from '../lib/formatBytes'
import type { Agent, AttachmentParseStatus, DocumentItem, DocumentSourceType } from '../types'

type Props = {
  onOpenChat?: (chatId: string) => void
  /** When set, list is locked to this agent (no agent filter / column). */
  scopedAgentId?: string
}

const RESIZE_HANDLE_WIDTH = 6
const MIN_PREVIEW_WIDTH = 320
const MIN_LIST_WIDTH = 280
const MAX_PREVIEW_RATIO = 0.72
const STORAGE_KEY = 'documents-preview-width'

const PARSE_STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All statuses' },
  { value: 'ready', label: 'Ready' },
  { value: 'running', label: 'Running' },
  { value: 'pending', label: 'Pending' },
  { value: 'failed', label: 'Failed' },
  { value: 'skipped', label: 'Skipped' },
]

const MIME_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All types' },
  { value: 'application/pdf', label: 'PDF' },
  { value: 'text/', label: 'Text / Markdown' },
  { value: 'image/', label: 'Images' },
  { value: 'application/vnd', label: 'Spreadsheets / Office' },
]

const SOURCE_FILTER_OPTIONS: { value: DocumentSourceType | 'all'; label: string }[] = [
  { value: 'all', label: 'All sources' },
  { value: 'attachment', label: 'Uploads' },
  { value: 'artifact', label: 'Generated' },
]

function agentLabel(doc: DocumentItem): string {
  return doc.agent_name?.trim() || 'Unknown agent'
}

function sessionLabel(doc: DocumentItem): string {
  return doc.chat_title?.trim() || 'Untitled session'
}

function attachmentGistLine(doc: DocumentItem): string | null {
  const gist = doc.gist?.trim()
  return gist || null
}

function parseStatusClass(status: AttachmentParseStatus | undefined): string {
  return `documents-status-badge documents-status-badge-${status ?? 'ready'}`
}

function isArtifactDocument(doc: DocumentItem): boolean {
  return doc.source_type === 'artifact'
}

function documentRowKey(doc: DocumentItem): string {
  return `${doc.source_type}:${doc.id}`
}

function documentsMatch(a: DocumentItem, b: DocumentItem): boolean {
  return a.source_type === b.source_type && a.id === b.id
}

function formatDocumentSize(doc: DocumentItem): string {
  if (isArtifactDocument(doc) || doc.size_bytes == null) return '—'
  return formatFileSize(doc.size_bytes)
}

function documentStatusBadges(doc: DocumentItem): string[] {
  if (isArtifactDocument(doc)) {
    if (doc.artifact_spec) return [artifactCardSubtitle(doc.artifact_spec)]
    return [doc.artifact_kind ?? 'generated']
  }
  const badges = [parseStatusDisplayLabel(doc as Parameters<typeof parseStatusDisplayLabel>[0])]
  if (doc.has_parsed_content) badges.push('parsed')
  if (doc.parsed_artifacts?.pageindex_json) badges.push('page index')
  return badges
}

function documentSourceBadge(doc: DocumentItem): string | null {
  if (doc.source_type === 'artifact') return 'generated'
  if (doc.source_type === 'attachment') return 'upload'
  return null
}

function isSvgDocument(doc: DocumentItem): boolean {
  if (doc.artifact_kind === 'diagram_svg' || doc.artifact_format === 'svg') return true
  const name = doc.filename.toLowerCase()
  if (name.endsWith('.svg')) return true
  const mime = (doc.mime_type ?? '').toLowerCase()
  return mime === 'image/svg+xml'
}

function isRasterImageDocument(doc: DocumentItem): boolean {
  if (isSvgDocument(doc)) return false
  const mime = (doc.mime_type ?? '').toLowerCase()
  if (mime.startsWith('image/')) return true
  const name = doc.filename.toLowerCase()
  return /\.(png|jpe?g|gif|webp|bmp|ico|tiff?|heic|heif)$/.test(name)
}

function DocumentFileIcon({ doc }: { doc: DocumentItem }) {
  if (isSvgDocument(doc)) return <Workflow size={14} />
  if (isRasterImageDocument(doc)) return <FileImage size={14} />
  if (isArtifactDocument(doc)) return <Sparkles size={14} />
  return <FileText size={14} />
}

function readStoredPreviewWidth(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = Number.parseInt(raw, 10)
    return Number.isFinite(parsed) && parsed >= MIN_PREVIEW_WIDTH ? parsed : null
  } catch {
    return null
  }
}

function DocumentPreviewPane({
  document: doc,
  onClose,
  onOpenChat,
}: {
  document: DocumentItem
  onClose: () => void
  onOpenChat?: (chatId: string) => void
}) {
  const artifacts = doc.parsed_artifacts ?? {
    content_md: Boolean(doc.has_parsed_content),
    meta_json: false,
    pageindex_json: false,
  }

  return (
    <ParsedDocumentPreview
      documentRef={{ scope: 'chat', chatId: doc.chat_id, documentId: doc.id }}
      title={doc.filename}
      mimeType={doc.mime_type ?? ''}
      artifacts={artifacts}
      onClose={onClose}
      subtitle={attachmentGistLine(doc)}
      toolbarActions={
        onOpenChat ? (
          <button type="button" className="documents-preview-link-btn" onClick={() => onOpenChat(doc.chat_id)}>
            Open session
          </button>
        ) : null
      }
    />
  )
}

function ArtifactDocumentPreviewPane({
  document: doc,
  onClose,
  onOpenChat,
}: {
  document: DocumentItem
  onClose: () => void
  onOpenChat?: (chatId: string) => void
}) {
  const spec = doc.artifact_spec
  const [downloading, setDownloading] = useState(false)

  if (!spec) {
    return (
      <div className="documents-preview-pane">
        <header className="documents-preview-header">
          <div className="documents-preview-heading">
            <h3 className="documents-preview-title">{doc.filename}</h3>
            <p className="documents-preview-meta">{agentLabel(doc)} · {sessionLabel(doc)}</p>
          </div>
          <button type="button" className="documents-preview-close" onClick={onClose} aria-label="Close preview">
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        <div className="documents-preview-body">
          <p className="documents-preview-empty">Artifact metadata is unavailable.</p>
        </div>
      </div>
    )
  }

  const sidePanel = isSidePanelArtifact(spec)
  const subtitle = artifactCardSubtitle(spec)

  async function handleDownload() {
    if (downloading || !spec?.download_url?.trim()) return
    setDownloading(true)
    try {
      await downloadArtifactFile(spec)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="documents-preview-pane">
      <header className="documents-preview-header">
        <div className="documents-preview-heading">
          <h3 className="documents-preview-title">{spec.title || doc.filename}</h3>
          <p className="documents-preview-meta">
            {agentLabel(doc)} · {sessionLabel(doc)} · {subtitle}
          </p>
        </div>
        <button type="button" className="documents-preview-close" onClick={onClose} aria-label="Close preview">
          <X size={18} aria-hidden="true" />
        </button>
      </header>

      <div className="documents-preview-toolbar">
        <div className="documents-preview-actions">
          {spec.download_url?.trim() ? (
            <button
              type="button"
              className="documents-preview-link-btn"
              disabled={downloading}
              onClick={() => void handleDownload()}
            >
              {downloading ? 'Downloading…' : 'Download'}
            </button>
          ) : null}
          {onOpenChat ? (
            <button type="button" className="documents-preview-link-btn" onClick={() => onOpenChat(doc.chat_id)}>
              <ExternalLink size={14} aria-hidden="true" />
              Open in chat
            </button>
          ) : null}
        </div>
      </div>

      <div className="documents-preview-body documents-artifact-preview-body">
        {spec.kind === 'proposal_preview' ? (
          <p className="documents-preview-empty">
            Proposal preview opens in the original chat session. Use Open in chat to continue editing.
          </p>
        ) : sidePanel ? (
          <ArtifactPanelContent spec={spec} onClose={onClose} />
        ) : (
          <p className="documents-preview-empty">
            Download this generated file or open the session to view it in context.
          </p>
        )}
      </div>
    </div>
  )
}

export function DocumentsView({ onOpenChat, scopedAgentId }: Props) {
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [source, setSource] = useState<DocumentSourceType | 'all'>('all')
  const [parseStatus, setParseStatus] = useState('')
  const [mimeType, setMimeType] = useState('')
  const [agentId, setAgentId] = useState('')
  const [agents, setAgents] = useState<Agent[]>([])
  const [selected, setSelected] = useState<DocumentItem | null>(null)
  const [previewWidth, setPreviewWidth] = useState<number | null>(() => readStoredPreviewWidth())
  const [searchOpen, setSearchOpen] = useState(false)
  const searchInputRef = useRef<HTMLInputElement>(null)

  const splitRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(searchInput.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [searchInput])

  const showAttachmentFilters = source === 'all' || source === 'attachment'

  const effectiveAgentId = scopedAgentId ?? agentId

  const filters = useMemo(
    () => ({
      q: debouncedQuery || undefined,
      parse_status: showAttachmentFilters && parseStatus ? parseStatus : undefined,
      mime_type: showAttachmentFilters && mimeType ? mimeType : undefined,
      agent_id: effectiveAgentId || undefined,
      source,
      limit: 100,
      offset: 0,
    }),
    [effectiveAgentId, debouncedQuery, mimeType, parseStatus, showAttachmentFilters, source],
  )

  useEffect(() => {
    if (scopedAgentId) return
    void (async () => {
      try {
        const rows = await api.listAgents()
        setAgents(rows)
      } catch {
        setAgents([])
      }
    })()
  }, [scopedAgentId])

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.listDocuments(filters)
      setDocuments(result.items)
      setTotal(result.total)
      setSelected((current) => {
        if (!current) return null
        return result.items.find((item) => documentsMatch(item, current)) ?? null
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load documents'
      setError(
        message === 'Not Found'
          ? 'Documents API not found — restart the backend to load the new routes.'
          : message,
      )
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (previewWidth == null) return
    try {
      localStorage.setItem(STORAGE_KEY, String(Math.round(previewWidth)))
    } catch {
      /* ignore */
    }
  }, [previewWidth])

  const clampPreviewWidth = useCallback((next: number) => {
    const split = splitRef.current
    if (!split) return Math.max(MIN_PREVIEW_WIDTH, next)
    const totalWidth = split.getBoundingClientRect().width
    const max = Math.max(MIN_PREVIEW_WIDTH, totalWidth * MAX_PREVIEW_RATIO)
    const maxByList = totalWidth - MIN_LIST_WIDTH - RESIZE_HANDLE_WIDTH
    return Math.min(Math.max(next, MIN_PREVIEW_WIDTH), max, maxByList)
  }, [])

  const ensurePreviewWidth = useCallback(() => {
    setPreviewWidth((current) => {
      if (current != null) return clampPreviewWidth(current)
      const split = splitRef.current
      if (!split) return 480
      const half = (split.getBoundingClientRect().width - RESIZE_HANDLE_WIDTH) / 2
      return clampPreviewWidth(half)
    })
  }, [clampPreviewWidth])

  const handleSelect = (doc: DocumentItem) => {
    setSelected(doc)
    ensurePreviewWidth()
  }

  const onResizePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!selected) return
    event.preventDefault()
    dragRef.current = { startX: event.clientX, startWidth: previewWidth ?? MIN_PREVIEW_WIDTH }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const onResizePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragRef.current) return
    const delta = dragRef.current.startX - event.clientX
    setPreviewWidth(clampPreviewWidth(dragRef.current.startWidth + delta))
  }

  const onResizePointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragRef.current) return
    dragRef.current = null
    event.currentTarget.releasePointerCapture(event.pointerId)
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && selected) {
        setSelected(null)
      }
    }
    window.document.addEventListener('keydown', onKeyDown)
    return () => window.document.removeEventListener('keydown', onKeyDown)
  }, [selected])

  const handleOpenChat = (chatId: string) => {
    onOpenChat?.(chatId)
  }

  const toggleSearch = () => {
    setSearchOpen((open) => {
      const next = !open
      if (next) {
        window.setTimeout(() => searchInputRef.current?.focus(), 0)
      } else {
        setSearchInput('')
      }
      return next
    })
  }

  const sourcePill = (value: DocumentSourceType | 'all', label: string) => (
    <button
      key={value}
      type="button"
      className={`artifacts-source-pill${source === value ? ' artifacts-source-pill-active' : ''}`}
      onClick={() => setSource(value)}
    >
      {label}
    </button>
  )

  return (
    <div className={`documents-view${scopedAgentId ? ' documents-view-agent-scoped' : ''}`}>
      <header className="documents-view-header">
        <div>
          <h1 className="documents-view-title">{scopedAgentId ? 'Artifacts' : 'Chat Documents'}</h1>
          {!scopedAgentId ? (
            <p className="documents-view-subtitle">
              Uploads and generated artifacts across sessions.
            </p>
          ) : null}
        </div>
      </header>

      <div ref={splitRef} className="documents-view-split">
        <div className={`documents-view-list-pane${selected ? ' documents-view-list-pane-split' : ''}`}>
          {scopedAgentId ? (
            <div className="artifacts-toolbar">
              <div className="artifacts-source-pills">
                {sourcePill('all', 'All')}
                {sourcePill('artifact', 'Generated')}
                {sourcePill('attachment', 'Attachment')}
              </div>
              <div className="artifacts-toolbar-end">
                {searchOpen ? (
                  <label className="documents-filter-search artifacts-search-inline">
                    <Search size={14} aria-hidden="true" />
                    <input
                      ref={searchInputRef}
                      type="search"
                      value={searchInput}
                      placeholder="Search by file name…"
                      onChange={(event) => setSearchInput(event.target.value)}
                    />
                    <button
                      type="button"
                      className="artifacts-search-close"
                      aria-label="Clear search"
                      onClick={() => {
                        setSearchInput('')
                        setSearchOpen(false)
                      }}
                    >
                      <X size={14} aria-hidden="true" />
                    </button>
                  </label>
                ) : null}
                <button
                  type="button"
                  className={`artifacts-search-toggle${searchOpen ? ' artifacts-search-toggle-active' : ''}`}
                  aria-label={searchOpen ? 'Close search' : 'Search artifacts'}
                  aria-expanded={searchOpen}
                  onClick={toggleSearch}
                >
                  <Search size={16} strokeWidth={1.75} aria-hidden="true" />
                </button>
              </div>
            </div>
          ) : null}
          {!scopedAgentId ? (
            <div className="documents-view-filters">
              <label className="documents-filter-search">
                <Search size={14} aria-hidden="true" />
                <input
                  type="search"
                  value={searchInput}
                  placeholder="Search name…"
                  onChange={(event) => setSearchInput(event.target.value)}
                />
              </label>
              <select
                className="documents-filter-select"
                value={agentId}
                aria-label="Filter by agent"
                onChange={(event) => setAgentId(event.target.value)}
              >
                <option value="">All agents</option>
                {agents.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
              <select
                className="documents-filter-select"
                value={source}
                aria-label="Filter by source"
                onChange={(event) => setSource(event.target.value as DocumentSourceType | 'all')}
              >
                {SOURCE_FILTER_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              {showAttachmentFilters ? (
                <select
                  className="documents-filter-select"
                  value={parseStatus}
                  aria-label="Filter by parse status"
                  onChange={(event) => setParseStatus(event.target.value)}
                >
                  {PARSE_STATUS_OPTIONS.map((option) => (
                    <option key={option.value || 'all-status'} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : null}
              {showAttachmentFilters ? (
                <select
                  className="documents-filter-select"
                  value={mimeType}
                  aria-label="Filter by file type"
                  onChange={(event) => setMimeType(event.target.value)}
                >
                  {MIME_FILTER_OPTIONS.map((option) => (
                    <option key={option.value || 'all-types'} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : null}
            </div>
          ) : null}

          {error ? <div className="documents-drawer-error">{error}</div> : null}

          <div className="documents-view-list-scroll">
            {loading ? (
              <div className="documents-drawer-loading">
                <LoadingSpinner />
              </div>
            ) : documents.length === 0 ? (
              <p className="documents-drawer-empty">No documents match your filters.</p>
            ) : scopedAgentId ? (
              <ul className="artifacts-card-list">
                {documents.map((doc) => (
                  <li key={documentRowKey(doc)}>
                    <button
                      type="button"
                      className={`artifacts-card${selected && documentsMatch(selected, doc) ? ' artifacts-card-selected' : ''}`}
                      onClick={() => handleSelect(doc)}
                    >
                      <span className="artifacts-card-icon" aria-hidden="true">
                        <DocumentFileIcon doc={doc} />
                      </span>
                      <span className="artifacts-card-body">
                        <span className="artifacts-card-filename" title={doc.filename}>
                          {doc.filename}
                        </span>
                        <span className="artifacts-card-session" title={doc.chat_id}>
                          {sessionLabel(doc)}
                          <span className="artifacts-card-session-id">{doc.chat_id}</span>
                        </span>
                      </span>
                      <span className="artifacts-card-date">
                        {doc.created_at ? formatAttachmentTimestamp(doc.created_at) : '—'}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <>
                <p className="documents-drawer-count">
                  {total === documents.length
                    ? `${total} document${total === 1 ? '' : 's'}`
                    : `${documents.length} of ${total}`}
                </p>
                <div
                  className={`documents-table${selected ? ' documents-table-preview-open' : ''}${
                    scopedAgentId ? ' documents-table-agent-scoped' : ''
                  }`}
                >
                  <div className="documents-table-head" aria-hidden="true">
                    {!scopedAgentId ? (
                      <span className="documents-col documents-col-agent">Agent</span>
                    ) : null}
                    <span className="documents-col documents-col-session">Session</span>
                    <span className="documents-col documents-col-source">Source</span>
                    <span className="documents-col documents-col-file">File</span>
                    <span className="documents-col documents-col-size">Size</span>
                    <span className="documents-col documents-col-date">Date</span>
                    {!selected ? (
                      <span className="documents-col documents-col-status">Status</span>
                    ) : null}
                  </div>
                  <ul className="documents-table-list">
                    {documents.map((doc) => (
                      <li key={documentRowKey(doc)}>
                        <button
                          type="button"
                          className={`documents-table-row${selected && documentsMatch(selected, doc) ? ' documents-table-row-selected' : ''}`}
                          onClick={() => handleSelect(doc)}
                        >
                          {!scopedAgentId ? (
                            <span className="documents-col documents-col-agent">
                              <span className="documents-col-agent-name" title={agentLabel(doc)}>
                                {agentLabel(doc)}
                              </span>
                              {doc.agent_slug ? (
                                <span className="documents-col-agent-slug" title={doc.agent_slug}>
                                  {doc.agent_slug}
                                </span>
                              ) : null}
                            </span>
                          ) : null}
                          <span className="documents-col documents-col-session">
                            <span className="documents-col-session-name" title={sessionLabel(doc)}>
                              {sessionLabel(doc)}
                            </span>
                            <span className="documents-col-session-id" title={doc.chat_id}>
                              {doc.chat_id}
                            </span>
                          </span>
                          <span className="documents-col documents-col-source">
                            {documentSourceBadge(doc) ? (
                              <span className={`documents-source-badge documents-source-badge-${documentSourceBadge(doc)}`}>
                                {documentSourceBadge(doc)}
                              </span>
                            ) : (
                              <span className="documents-col-empty">—</span>
                            )}
                          </span>
                          <span className="documents-col documents-col-file">
                            <span className="documents-col-file-icon" aria-hidden="true">
                              <DocumentFileIcon doc={doc} />
                            </span>
                            <span className="documents-col-file-name" title={doc.filename}>
                              {doc.filename}
                            </span>
                          </span>
                          <span className="documents-col documents-col-size">
                            {formatDocumentSize(doc)}
                          </span>
                          <span className="documents-col documents-col-date">
                            {doc.created_at ? formatAttachmentTimestamp(doc.created_at) : '—'}
                          </span>
                          {!selected ? (
                            <span className="documents-col documents-col-status">
                              {documentStatusBadges(doc).map((badge) => (
                                <span
                                  key={badge}
                                  className={
                                    !isArtifactDocument(doc) &&
                                    badge === parseStatusDisplayLabel(doc as Parameters<typeof parseStatusDisplayLabel>[0])
                                      ? parseStatusClass(doc.parse_status ?? undefined)
                                      : 'documents-status-badge documents-status-badge-extra'
                                  }
                                >
                                  {badge}
                                </span>
                              ))}
                            </span>
                          ) : null}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              </>
            )}
          </div>
        </div>

        {selected && previewWidth != null ? (
          <>
            <div
              className="documents-view-resize-handle"
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize preview panel"
              style={{ width: RESIZE_HANDLE_WIDTH }}
              onPointerDown={onResizePointerDown}
              onPointerMove={onResizePointerMove}
              onPointerUp={onResizePointerUp}
              onPointerCancel={onResizePointerUp}
            />
            <div className="documents-view-preview-pane" style={{ width: previewWidth }}>
              {isArtifactDocument(selected) ? (
                <ArtifactDocumentPreviewPane
                  document={selected}
                  onClose={() => setSelected(null)}
                  onOpenChat={onOpenChat ? handleOpenChat : undefined}
                />
              ) : (
                <DocumentPreviewPane
                  document={selected}
                  onClose={() => setSelected(null)}
                  onOpenChat={onOpenChat ? handleOpenChat : undefined}
                />
              )}
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
