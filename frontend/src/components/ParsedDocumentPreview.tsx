import { lazy, Suspense, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ExternalLink, FileText, X } from 'lucide-react'
import type { ParsedArtifactsAvailability } from '../types'
import type { ArtifactSpec } from '../types/artifact'
import {
  canPreviewOriginalMime,
  fetchParsedArtifactText,
  originalDocumentUrl,
  type ParsedDocumentRef,
  rewriteParsedMarkdown,
  resolveParsedMarkdownFigureSrc,
} from '../lib/documentArtifacts'
import { prettyJson } from '../lib/prettyJson'
import {
  layoutPreviewText,
  layoutTypeLabel,
  parsePageIndex,
  type PageIndexData,
} from '../lib/pageIndexPreview'
import type { ParsedFigureMeta } from '../lib/parsedFigureRefs'
import { LoadingSpinner } from './LoadingSpinner'
import { MarkdownContent } from './MarkdownContent'

const UDocArtifactViewer = lazy(async () => {
  const mod = await import('./UDocArtifactViewer')
  return { default: mod.UDocArtifactViewer }
})

export type ParsedDocumentPreviewTab = 'original' | 'parsed' | 'meta' | 'pageindex'

type Props = {
  documentRef: ParsedDocumentRef
  title: string
  mimeType: string
  artifacts: ParsedArtifactsAvailability
  onClose: () => void
  subtitle?: string | null
  toolbarActions?: ReactNode
  markdownBodyClassName?: string
  closeIcon?: ReactNode
}

function originalPreviewSpec(ref: ParsedDocumentRef, filename: string): ArtifactSpec {
  const documentId = ref.scope === 'chat' ? ref.documentId : ref.itemId
  const downloadPath =
    ref.scope === 'chat'
      ? `/chats/${ref.chatId}/attachments/${ref.documentId}/original`
      : `/document-hub/items/${ref.itemId}/original`
  return {
    kind: 'content_document',
    title: filename,
    format: 'pdf',
    content: '',
    filename,
    artifact_id: documentId,
    download_url: downloadPath,
  }
}

function OriginalDocumentPreview({
  documentRef,
  filename,
  mimeType,
}: {
  documentRef: ParsedDocumentRef
  filename: string
  mimeType: string
}) {
  const mime = mimeType.toLowerCase()
  const inlineUrl = originalDocumentUrl(documentRef, { inline: true })

  if (mime.startsWith('image/')) {
    return <img className="documents-preview-image" src={inlineUrl} alt={filename} />
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
          <UDocArtifactViewer spec={originalPreviewSpec(documentRef, filename)} />
        </Suspense>
      </div>
    )
  }

  return <iframe className="documents-preview-frame" src={inlineUrl} title={filename} />
}

function PageIndexStructuredView({ data }: { data: PageIndexData }) {
  const layouts = data.layouts ?? []
  return (
    <div className="documents-pageindex-view">
      <div className="documents-pageindex-summary">
        <span>
          {layouts.length} layout block{layouts.length === 1 ? '' : 's'}
        </span>
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

export function ParsedDocumentPreview({
  documentRef,
  title,
  mimeType,
  artifacts,
  onClose,
  subtitle,
  toolbarActions,
  markdownBodyClassName = 'markdown-body artifact-markdown-body documents-preview-markdown',
  closeIcon,
}: Props) {
  const hasPageIndex = artifacts.pageindex_json
  const [tab, setTab] = useState<ParsedDocumentPreviewTab>(() =>
    artifacts.content_md ? 'parsed' : 'original',
  )
  const [parsedContent, setParsedContent] = useState<string | null>(null)
  const [parsedFigureMeta, setParsedFigureMeta] = useState<ParsedFigureMeta | undefined>(undefined)
  const [metaContent, setMetaContent] = useState<string | null>(null)
  const [pageindexData, setPageindexData] = useState<PageIndexData | null>(null)
  const [pageindexRaw, setPageindexRaw] = useState<string | null>(null)
  const [pageindexView, setPageindexView] = useState<'structured' | 'raw'>('structured')
  const [parsedView, setParsedView] = useState<'rendered' | 'source'>('rendered')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const documentKey =
    documentRef.scope === 'chat'
      ? `chat:${documentRef.chatId}:${documentRef.documentId}`
      : `hub:${documentRef.itemId}`

  const downloadUrl = originalDocumentUrl(documentRef)
  const resolveFigureSrc = useCallback(
    (src: string | undefined) => resolveParsedMarkdownFigureSrc(src, documentRef, parsedFigureMeta),
    [documentRef, parsedFigureMeta],
  )
  const renderedParsedContent = useMemo(
    () =>
      parsedContent != null ? rewriteParsedMarkdown(parsedContent, documentRef, parsedFigureMeta) : null,
    [parsedContent, documentRef, parsedFigureMeta],
  )

  useEffect(() => {
    setTab(artifacts.content_md ? 'parsed' : 'original')
    setParsedContent(null)
    setParsedFigureMeta(undefined)
    setMetaContent(null)
    setPageindexData(null)
    setPageindexRaw(null)
    setParsedView('rendered')
    setError(null)
  }, [artifacts.content_md, artifacts.meta_json, artifacts.pageindex_json, documentKey])

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
          const text = await fetchParsedArtifactText(documentRef, 'content_md')
          if (!cancelled) setParsedContent(text)
          if (!cancelled && artifacts.meta_json) {
            try {
              const metaText = await fetchParsedArtifactText(documentRef, 'meta_json')
              if (!cancelled) {
                setParsedFigureMeta(JSON.parse(metaText) as ParsedFigureMeta)
              }
            } catch {
              if (!cancelled) setParsedFigureMeta(undefined)
            }
          } else if (!cancelled) {
            setParsedFigureMeta(undefined)
          }
        } else if (tab === 'meta') {
          const text = await fetchParsedArtifactText(documentRef, 'meta_json')
          if (!cancelled) setMetaContent(prettyJson(text))
        } else {
          const text = await fetchParsedArtifactText(documentRef, 'pageindex_json')
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
  }, [tab, artifacts.content_md, artifacts.meta_json, documentKey, hasPageIndex])

  const showOriginalPreview = tab === 'original' && canPreviewOriginalMime(mimeType)

  return (
    <div className="documents-preview-pane">
      <header className="documents-preview-header">
        <div className="documents-preview-heading">
          <h3 className="documents-preview-title" title={title}>
            {title}
          </h3>
          {subtitle ? <p className="documents-preview-meta documents-preview-gist">{subtitle}</p> : null}
        </div>
        <button type="button" className="documents-preview-close" onClick={onClose} aria-label="Close preview">
          {closeIcon ?? <X size={18} aria-hidden="true" />}
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
          {toolbarActions}
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
            <OriginalDocumentPreview documentRef={documentRef} filename={title} mimeType={mimeType} />
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
                  content={renderedParsedContent ?? ''}
                  className={markdownBodyClassName}
                  allowHtml
                  resolveImageSrc={resolveFigureSrc}
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
