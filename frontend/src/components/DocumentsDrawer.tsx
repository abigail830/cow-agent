import { useCallback, useEffect, useMemo, useState } from 'react'
import { ExternalLink, FileText, Search, X } from 'lucide-react'
import { api } from '../api/client'
import { LoadingSpinner } from './LoadingSpinner'
import { formatAttachmentTimestamp } from '../lib/attachmentMentions'
import { parseStatusDisplayLabel } from '../lib/attachmentParseProgress'
import { attachmentOriginalUrl } from '../lib/documentUrls'
import {
  layoutPreviewText,
  layoutTypeLabel,
  parsePageIndex,
  type PageIndexData,
} from '../lib/pageIndexPreview'
import type { AttachmentParseStatus, DocumentItem } from '../types'

type Props = {
  open: boolean
  onClose: () => void
  onOpenChat?: (chatId: string) => void
}

type PreviewTab = 'original' | 'parsed' | 'meta' | 'pageindex'

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

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

function sessionLabel(doc: DocumentItem): string {
  return doc.chat_title?.trim() || 'Untitled session'
}

function parseStatusClass(status: AttachmentParseStatus | undefined): string {
  return `documents-row-status documents-row-status-${status ?? 'ready'}`
}

function canPreviewOriginal(mimeType: string): boolean {
  const mime = mimeType.toLowerCase()
  return mime.startsWith('image/') || mime === 'application/pdf' || mime.startsWith('text/')
}

function prettyJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

function PageIndexStructuredView({ data }: { data: PageIndexData }) {
  const layouts = data.layouts ?? []
  return (
    <div className="documents-pageindex-view">
      <div className="documents-pageindex-summary">
        <span>{layouts.length} layout block{layouts.length === 1 ? '' : 's'}</span>
        {data.external_job_id ? (
          <span className="documents-pageindex-job">Job {data.external_job_id}</span>
        ) : null}
      </div>
      {layouts.length === 0 ? (
        <p className="documents-preview-empty">Page index file is empty.</p>
      ) : (
        <ol className="documents-pageindex-list">
          {layouts.map((layout, index) => (
            <li key={index} className="documents-pageindex-item">
              <div className="documents-pageindex-item-head">
                <span className="documents-pageindex-item-index">#{index + 1}</span>
                <span className="documents-pageindex-item-type">{layoutTypeLabel(layout)}</span>
              </div>
              <pre className="documents-pageindex-item-body">{layoutPreviewText(layout)}</pre>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function DocumentPreviewPanel({
  document: doc,
  onClose,
  onOpenChat,
}: {
  document: DocumentItem
  onClose: () => void
  onOpenChat?: (chatId: string) => void
}) {
  const [tab, setTab] = useState<PreviewTab>(() =>
    doc.has_parsed_content ? 'parsed' : 'original',
  )
  const [parsedContent, setParsedContent] = useState<string | null>(null)
  const [metaContent, setMetaContent] = useState<string | null>(null)
  const [pageindexData, setPageindexData] = useState<PageIndexData | null>(null)
  const [pageindexRaw, setPageindexRaw] = useState<string | null>(null)
  const [hasPageIndex, setHasPageIndex] = useState(false)
  const [pageindexView, setPageindexView] = useState<'structured' | 'raw'>('structured')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const originalUrl = attachmentOriginalUrl(doc.chat_id, doc.id)

  useEffect(() => {
    if (!doc.has_parsed_content) {
      setHasPageIndex(false)
      return
    }

    let cancelled = false
    void (async () => {
      try {
        const text = await api.fetchAttachmentParsedText(doc.chat_id, doc.id, 'meta_json')
        if (cancelled) return
        try {
          const meta = JSON.parse(text) as { pageindex_path?: string | null }
          setHasPageIndex(Boolean(meta.pageindex_path))
        } catch {
          setHasPageIndex(false)
        }
      } catch {
        if (!cancelled) setHasPageIndex(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [doc.chat_id, doc.has_parsed_content, doc.id])

  useEffect(() => {
    if (tab !== 'parsed' && tab !== 'meta' && tab !== 'pageindex') return
    if (!doc.has_parsed_content) return
    if (tab === 'pageindex' && !hasPageIndex) return

    let cancelled = false
    setLoading(true)
    setError(null)

    void (async () => {
      try {
        if (tab === 'parsed') {
          const text = await api.fetchAttachmentParsedText(doc.chat_id, doc.id, 'content_md')
          if (!cancelled) setParsedContent(text)
        } else if (tab === 'meta') {
          const text = await api.fetchAttachmentParsedText(doc.chat_id, doc.id, 'meta_json')
          if (!cancelled) {
            try {
              setMetaContent(JSON.stringify(JSON.parse(text), null, 2))
            } catch {
              setMetaContent(text)
            }
          }
        } else {
          const text = await api.fetchAttachmentParsedText(doc.chat_id, doc.id, 'pageindex_json')
          if (!cancelled) {
            setPageindexRaw(text)
            setPageindexData(parsePageIndex(text))
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load preview')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [tab, doc.chat_id, doc.has_parsed_content, doc.id, hasPageIndex])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.document.addEventListener('keydown', onKeyDown)
    return () => window.document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const showOriginalPreview = tab === 'original' && canPreviewOriginal(doc.mime_type)

  return (
    <>
      <div className="documents-preview-backdrop" role="presentation" onClick={onClose} />
      <aside
        className="documents-preview-panel"
        role="dialog"
        aria-modal="true"
        aria-label={`Preview ${doc.filename}`}
      >
        <header className="documents-preview-header">
          <div className="documents-preview-heading">
            <h3 className="documents-preview-title">{doc.filename}</h3>
            <p className="documents-preview-meta">
              {sessionLabel(doc)} · {formatFileSize(doc.size_bytes)} ·{' '}
              {parseStatusDisplayLabel(doc)}
            </p>
          </div>
          <button type="button" className="documents-preview-close" onClick={onClose} aria-label="Close preview">
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        <div className="documents-preview-toolbar">
          <div className="documents-preview-tabs" role="tablist" aria-label="Preview mode">
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'original'}
              className={`documents-preview-tab${tab === 'original' ? ' documents-preview-tab-active' : ''}`}
              onClick={() => setTab('original')}
            >
              Original
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'parsed'}
              disabled={!doc.has_parsed_content}
              className={`documents-preview-tab${tab === 'parsed' ? ' documents-preview-tab-active' : ''}`}
              onClick={() => setTab('parsed')}
            >
              Parsed
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'meta'}
              disabled={!doc.has_parsed_content}
              className={`documents-preview-tab${tab === 'meta' ? ' documents-preview-tab-active' : ''}`}
              onClick={() => setTab('meta')}
            >
              Meta
            </button>
            {hasPageIndex ? (
              <button
                type="button"
                role="tab"
                aria-selected={tab === 'pageindex'}
                className={`documents-preview-tab${tab === 'pageindex' ? ' documents-preview-tab-active' : ''}`}
                onClick={() => setTab('pageindex')}
              >
                Page Index
              </button>
            ) : null}
          </div>
          <div className="documents-preview-actions">
            {onOpenChat ? (
              <button
                type="button"
                className="documents-preview-link-btn"
                onClick={() => onOpenChat(doc.chat_id)}
              >
                Open session
              </button>
            ) : null}
            <a
              className="documents-preview-link-btn"
              href={originalUrl}
              target="_blank"
              rel="noreferrer"
            >
              Download
              <ExternalLink size={12} aria-hidden="true" />
            </a>
          </div>
        </div>

        <div className="documents-preview-body">
          {loading ? (
            <div className="documents-preview-loading">
              <LoadingSpinner />
            </div>
          ) : error ? (
            <p className="documents-preview-error">{error}</p>
          ) : tab === 'original' ? (
            showOriginalPreview ? (
              doc.mime_type.toLowerCase().startsWith('image/') ? (
                <img className="documents-preview-image" src={originalUrl} alt={doc.filename} />
              ) : (
                <iframe className="documents-preview-frame" src={originalUrl} title={doc.filename} />
              )
            ) : (
              <div className="documents-preview-placeholder">
                <FileText size={28} aria-hidden="true" />
                <p>Inline preview is not available for this file type.</p>
                <a className="documents-preview-download" href={originalUrl} target="_blank" rel="noreferrer">
                  Download original
                </a>
              </div>
            )
          ) : tab === 'parsed' ? (
            parsedContent != null ? (
              <pre className="documents-preview-text">{parsedContent}</pre>
            ) : (
              <p className="documents-preview-empty">No parsed content.</p>
            )
          ) : tab === 'pageindex' ? (
            pageindexData || pageindexRaw ? (
              <>
                <div className="documents-pageindex-toggle" role="tablist" aria-label="Page index view">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={pageindexView === 'structured'}
                    className={`documents-pageindex-toggle-btn${
                      pageindexView === 'structured' ? ' documents-pageindex-toggle-btn-active' : ''
                    }`}
                    onClick={() => setPageindexView('structured')}
                  >
                    Structured
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={pageindexView === 'raw'}
                    className={`documents-pageindex-toggle-btn${
                      pageindexView === 'raw' ? ' documents-pageindex-toggle-btn-active' : ''
                    }`}
                    onClick={() => setPageindexView('raw')}
                  >
                    Raw JSON
                  </button>
                </div>
                {pageindexView === 'structured' && pageindexData ? (
                  <PageIndexStructuredView data={pageindexData} />
                ) : (
                  <pre className="documents-preview-text">{pageindexRaw != null ? prettyJson(pageindexRaw) : ''}</pre>
                )}
              </>
            ) : (
              <p className="documents-preview-empty">No page index available.</p>
            )
          ) : metaContent != null ? (
            <pre className="documents-preview-text">{metaContent}</pre>
          ) : (
            <p className="documents-preview-empty">No parse metadata.</p>
          )}
        </div>
      </aside>
    </>
  )
}

export function DocumentsDrawer({ open, onClose, onOpenChat }: Props) {
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [parseStatus, setParseStatus] = useState('')
  const [mimeType, setMimeType] = useState('')
  const [selected, setSelected] = useState<DocumentItem | null>(null)

  useEffect(() => {
    if (!open) return
    const timer = window.setTimeout(() => setDebouncedQuery(searchInput.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [open, searchInput])

  const filters = useMemo(
    () => ({
      q: debouncedQuery || undefined,
      parse_status: parseStatus || undefined,
      mime_type: mimeType || undefined,
      limit: 100,
      offset: 0,
    }),
    [debouncedQuery, mimeType, parseStatus],
  )

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.listDocuments(filters)
      setDocuments(result.items)
      setTotal(result.total)
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
    if (!open) return
    void refresh()
  }, [open, refresh])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !selected) onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose, selected])

  useEffect(() => {
    if (!open) {
      setSelected(null)
      setSearchInput('')
      setDebouncedQuery('')
      setParseStatus('')
      setMimeType('')
    }
  }, [open])

  const handleOpenChat = (chatId: string) => {
    setSelected(null)
    onClose()
    onOpenChat?.(chatId)
  }

  return (
    <>
      <aside className={`documents-drawer ${open ? 'documents-drawer-open' : ''}`} aria-hidden={!open}>
        <div className="documents-drawer-inner">
          <div className="documents-drawer-header">
            <div>
              <h2 className="documents-drawer-title">Documents</h2>
              <p className="documents-drawer-subtitle">Attachments and parse results across sessions.</p>
            </div>
            <button type="button" className="documents-drawer-close" onClick={onClose} aria-label="Close documents">
              <X size={18} aria-hidden="true" />
            </button>
          </div>

          <div className="documents-drawer-filters">
            <label className="documents-filter-search">
              <Search size={14} aria-hidden="true" />
              <input
                type="search"
                value={searchInput}
                placeholder="Search filename…"
                onChange={(event) => setSearchInput(event.target.value)}
              />
            </label>
            <div className="documents-filter-row">
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
            </div>
          </div>

          {error ? <div className="documents-drawer-error">{error}</div> : null}

          <div className="documents-drawer-scroll">
            {loading ? (
              <div className="documents-drawer-loading">
                <LoadingSpinner />
              </div>
            ) : documents.length === 0 ? (
              <p className="documents-drawer-empty">No documents match your filters.</p>
            ) : (
              <>
                <p className="documents-drawer-count">
                  {total === documents.length ? `${total} document${total === 1 ? '' : 's'}` : `${documents.length} of ${total}`}
                </p>
                <ul className="documents-drawer-list">
                  {documents.map((doc) => (
                    <li key={doc.id}>
                      <button
                        type="button"
                        className="documents-row"
                        onClick={() => setSelected(doc)}
                      >
                        <span className="documents-row-icon" aria-hidden="true">
                          <FileText size={16} />
                        </span>
                        <span className="documents-row-copy">
                          <span className="documents-row-name">{doc.filename}</span>
                          <span className="documents-row-meta">
                            {sessionLabel(doc)} · {formatFileSize(doc.size_bytes)}
                            {doc.created_at ? ` · ${formatAttachmentTimestamp(doc.created_at)}` : ''}
                          </span>
                          <span className={parseStatusClass(doc.parse_status)}>
                            {parseStatusDisplayLabel(doc)}
                            {doc.has_parsed_content ? ' · parsed' : ''}
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </div>
      </aside>

      {selected ? (
        <DocumentPreviewPanel
          document={selected}
          onClose={() => setSelected(null)}
          onOpenChat={onOpenChat ? handleOpenChat : undefined}
        />
      ) : null}
    </>
  )
}
