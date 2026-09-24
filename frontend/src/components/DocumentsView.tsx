import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import { ExternalLink, FileImage, FileText, Search, Sparkles, Workflow, X } from 'lucide-react'
import { api } from '../api/client'
import { LoadingSpinner } from './LoadingSpinner'
import { MarkdownContent } from './MarkdownContent'
import { ArtifactPanelContent } from './ArtifactPanelHost'
import { formatAttachmentTimestamp } from '../lib/attachmentMentions'
import { parseStatusDisplayLabel } from '../lib/attachmentParseProgress'
import { artifactCardSubtitle, isSidePanelArtifact } from '../lib/artifactKinds'
import { downloadArtifactFile } from '../lib/artifactDownload'
import { attachmentOriginalUrl } from '../lib/documentUrls'
import {
  layoutPreviewText,
  layoutTypeLabel,
  parsePageIndex,
  type PageIndexData,
} from '../lib/pageIndexPreview'
import type { ArtifactSpec } from '../types/artifact'
import type { Agent, AttachmentParseStatus, DocumentItem, DocumentSourceType } from '../types'

const UDocArtifactViewer = lazy(async () => {
  const mod = await import('./UDocArtifactViewer')
  return { default: mod.UDocArtifactViewer }
})

type Props = {
  onClose: () => void
  onOpenChat?: (chatId: string) => void
}

type PreviewTab = 'original' | 'parsed' | 'meta' | 'pageindex'

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

const ARTIFACT_KIND_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All kinds' },
  { value: 'diagram_svg', label: 'Diagrams' },
  { value: 'slide_deck', label: 'Slides' },
  { value: 'content_document', label: 'Documents' },
  { value: 'proposal_preview', label: 'Proposal preview' },
  { value: 'proposal_document', label: 'Proposal export' },
  { value: 'proposal_word', label: 'Proposal Word' },
]

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

function agentLabel(doc: DocumentItem): string {
  return doc.agent_name?.trim() || 'Unknown agent'
}

function sessionLabel(doc: DocumentItem): string {
  return doc.chat_title?.trim() || 'Untitled session'
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

function attachmentPreviewSpec(doc: DocumentItem): ArtifactSpec {
  return {
    kind: 'content_document',
    title: doc.filename,
    format: 'pdf',
    content: '',
    filename: doc.filename,
    artifact_id: doc.id,
    download_url: `/chats/${doc.chat_id}/attachments/${doc.id}/original`,
  }
}

function AttachmentOriginalPreview({ doc }: { doc: DocumentItem }) {
  const mime = (doc.mime_type ?? '').toLowerCase()
  const inlineUrl = attachmentOriginalUrl(doc.chat_id, doc.id, { inline: true })

  if (mime.startsWith('image/')) {
    return <img className="documents-preview-image" src={inlineUrl} alt={doc.filename} />
  }

  if (mime === 'application/pdf') {
    return (
      <div className="documents-preview-udoc">
        <Suspense
          fallback={
            <div className="documents-preview-loading">
              <LoadingSpinner />
            </div>
          }
        >
          <UDocArtifactViewer spec={attachmentPreviewSpec(doc)} />
        </Suspense>
      </div>
    )
  }

  return <iframe className="documents-preview-frame" src={inlineUrl} title={doc.filename} />
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
    content_md: doc.has_parsed_content,
    meta_json: false,
    pageindex_json: false,
  }
  const hasPageIndex = artifacts.pageindex_json

  const [tab, setTab] = useState<PreviewTab>(() =>
    artifacts.content_md ? 'parsed' : 'original',
  )
  const [parsedContent, setParsedContent] = useState<string | null>(null)
  const [metaContent, setMetaContent] = useState<string | null>(null)
  const [pageindexData, setPageindexData] = useState<PageIndexData | null>(null)
  const [pageindexRaw, setPageindexRaw] = useState<string | null>(null)
  const [pageindexView, setPageindexView] = useState<'structured' | 'raw'>('structured')
  const [parsedView, setParsedView] = useState<'rendered' | 'source'>('rendered')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const downloadUrl = attachmentOriginalUrl(doc.chat_id, doc.id)

  useEffect(() => {
    setTab(artifacts.content_md ? 'parsed' : 'original')
    setParsedContent(null)
    setMetaContent(null)
    setPageindexData(null)
    setPageindexRaw(null)
    setParsedView('rendered')
    setError(null)
  }, [artifacts.content_md, doc.id])

  useEffect(() => {
    if (tab !== 'parsed' && tab !== 'meta' && tab !== 'pageindex') return
    if (tab === 'parsed' && !artifacts.content_md) return
    if (tab === 'meta' && !artifacts.meta_json) return
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
          if (!cancelled) setMetaContent(prettyJson(text))
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
  }, [tab, artifacts.content_md, artifacts.meta_json, doc.chat_id, doc.id, hasPageIndex])

  const showOriginalPreview = tab === 'original' && canPreviewOriginal(doc.mime_type ?? '')

  return (
    <div className="documents-preview-pane">
      <header className="documents-preview-header">
        <div className="documents-preview-heading">
          <h3 className="documents-preview-title">{doc.filename}</h3>
          <p className="documents-preview-meta">
            {agentLabel(doc)} · {sessionLabel(doc)} · {formatDocumentSize(doc)} ·{' '}
            {parseStatusDisplayLabel(doc as Parameters<typeof parseStatusDisplayLabel>[0])}
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
            disabled={!artifacts.content_md}
            className={`documents-preview-tab${tab === 'parsed' ? ' documents-preview-tab-active' : ''}`}
            onClick={() => setTab('parsed')}
          >
            Parsed
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'meta'}
            disabled={!artifacts.meta_json}
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
            <button type="button" className="documents-preview-link-btn" onClick={() => onOpenChat(doc.chat_id)}>
              Open session
            </button>
          ) : null}
          <a className="documents-preview-link-btn" href={downloadUrl} target="_blank" rel="noreferrer">
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
            <AttachmentOriginalPreview doc={doc} />
          ) : (
            <div className="documents-preview-placeholder">
              <FileText size={28} aria-hidden="true" />
              <p>Inline preview is not available for this file type.</p>
              <a className="documents-preview-download" href={downloadUrl} target="_blank" rel="noreferrer">
                Download original
              </a>
            </div>
          )
        ) : tab === 'parsed' ? (
          parsedContent != null ? (
            <>
              <div className="documents-pageindex-toggle" role="tablist" aria-label="Parsed content view">
                <button
                  type="button"
                  role="tab"
                  aria-selected={parsedView === 'rendered'}
                  className={`documents-pageindex-toggle-btn${
                    parsedView === 'rendered' ? ' documents-pageindex-toggle-btn-active' : ''
                  }`}
                  onClick={() => setParsedView('rendered')}
                >
                  Rendered
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={parsedView === 'source'}
                  className={`documents-pageindex-toggle-btn${
                    parsedView === 'source' ? ' documents-pageindex-toggle-btn-active' : ''
                  }`}
                  onClick={() => setParsedView('source')}
                >
                  Source
                </button>
              </div>
              {parsedView === 'rendered' ? (
                <MarkdownContent
                  content={parsedContent}
                  className="markdown-body artifact-markdown-body documents-preview-markdown"
                  allowHtml
                />
              ) : (
                <pre className="documents-preview-text">{parsedContent}</pre>
              )}
            </>
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
    </div>
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

export function DocumentsView({ onClose, onOpenChat }: Props) {
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [source, setSource] = useState<DocumentSourceType | 'all'>('all')
  const [parseStatus, setParseStatus] = useState('')
  const [mimeType, setMimeType] = useState('')
  const [artifactKind, setArtifactKind] = useState('')
  const [agentId, setAgentId] = useState('')
  const [agents, setAgents] = useState<Agent[]>([])
  const [selected, setSelected] = useState<DocumentItem | null>(null)
  const [previewWidth, setPreviewWidth] = useState<number | null>(() => readStoredPreviewWidth())

  const splitRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(searchInput.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [searchInput])

  const showAttachmentFilters = source === 'all' || source === 'attachment'
  const showArtifactFilters = source === 'all' || source === 'artifact'

  const filters = useMemo(
    () => ({
      q: debouncedQuery || undefined,
      parse_status: showAttachmentFilters && parseStatus ? parseStatus : undefined,
      mime_type: showAttachmentFilters && mimeType ? mimeType : undefined,
      artifact_kind: showArtifactFilters && artifactKind ? artifactKind : undefined,
      agent_id: agentId || undefined,
      source,
      limit: 100,
      offset: 0,
    }),
    [agentId, artifactKind, debouncedQuery, mimeType, parseStatus, showArtifactFilters, showAttachmentFilters, source],
  )

  useEffect(() => {
    void (async () => {
      try {
        const rows = await api.listAgents()
        setAgents(rows)
      } catch {
        setAgents([])
      }
    })()
  }, [])

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
      if (event.key === 'Escape') {
        if (selected) setSelected(null)
        else onClose()
      }
    }
    window.document.addEventListener('keydown', onKeyDown)
    return () => window.document.removeEventListener('keydown', onKeyDown)
  }, [onClose, selected])

  const handleOpenChat = (chatId: string) => {
    onClose()
    onOpenChat?.(chatId)
  }

  return (
    <div className="documents-view">
      <header className="documents-view-header">
        <div>
          <h1 className="documents-view-title">Chat Documents</h1>
          <p className="documents-view-subtitle">Uploads and generated artifacts across sessions.</p>
        </div>
        <button type="button" className="documents-view-close" onClick={onClose} aria-label="Back to chat">
          <X size={18} aria-hidden="true" />
        </button>
      </header>

      <div ref={splitRef} className="documents-view-split">
        <div className={`documents-view-list-pane${selected ? ' documents-view-list-pane-split' : ''}`}>
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
            {showArtifactFilters ? (
              <select
                className="documents-filter-select"
                value={artifactKind}
                aria-label="Filter by artifact kind"
                onChange={(event) => setArtifactKind(event.target.value)}
              >
                {ARTIFACT_KIND_OPTIONS.map((option) => (
                  <option key={option.value || 'all-kinds'} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : null}
          </div>

          {error ? <div className="documents-drawer-error">{error}</div> : null}

          <div className="documents-view-list-scroll">
            {loading ? (
              <div className="documents-drawer-loading">
                <LoadingSpinner />
              </div>
            ) : documents.length === 0 ? (
              <p className="documents-drawer-empty">No documents match your filters.</p>
            ) : (
              <>
                <p className="documents-drawer-count">
                  {total === documents.length
                    ? `${total} document${total === 1 ? '' : 's'}`
                    : `${documents.length} of ${total}`}
                </p>
                <div className="documents-table">
                  <div className="documents-table-head" aria-hidden="true">
                    <span className="documents-col documents-col-agent">Agent</span>
                    <span className="documents-col documents-col-session">Session</span>
                    <span className="documents-col documents-col-source">Source</span>
                    <span className="documents-col documents-col-file">File</span>
                    <span className="documents-col documents-col-size">Size</span>
                    <span className="documents-col documents-col-date">Date</span>
                    <span className="documents-col documents-col-status">Status</span>
                  </div>
                  <ul className="documents-table-list">
                    {documents.map((doc) => (
                      <li key={documentRowKey(doc)}>
                        <button
                          type="button"
                          className={`documents-table-row${selected && documentsMatch(selected, doc) ? ' documents-table-row-selected' : ''}`}
                          onClick={() => handleSelect(doc)}
                        >
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
