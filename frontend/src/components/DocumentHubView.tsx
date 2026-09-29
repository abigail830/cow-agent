import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import { api } from '../api/client'
import type { HubFolder, HubItem } from '../types/hub'
import { HUB_TARGET_CHAT_STORAGE_KEY } from '../lib/chatRoutes'
import {
  HUB_FOLDER_WIDTH_KEY,
  HUB_MAX_FOLDER_WIDTH,
  HUB_MAX_PREVIEW_RATIO,
  HUB_MIN_FOLDER_WIDTH,
  HUB_MIN_LIST_WIDTH,
  HUB_MIN_PREVIEW_WIDTH,
  HUB_PREVIEW_WIDTH_KEY,
  HUB_RESIZE_HANDLE_WIDTH,
  readStoredHubWidth,
  storeHubWidth,
} from '../lib/documentHubLayout'
import { ATTACHMENT_PARSE_POLL_MS } from '../lib/attachmentParseProgress'
import {
  hubItemPreviewReady,
  hubItemShowsParseDrawer,
  hubItemToAttachmentListItem,
} from '../lib/hubItemParse'
import { resolveHubParsedFigureSrc, rewriteHubParsedFigureRefs } from '../lib/parsedFigureRefs'
import { FileImage, FileText, FolderInput, Trash2, Workflow } from 'lucide-react'
import { AttachmentParseDrawer } from './AttachmentParseDrawer'
import { LoadingSpinner } from './LoadingSpinner'
import { MarkdownContent } from './MarkdownContent'

type PendingUpload = { id: string; filename: string }

function hubFileIsSvg(filename: string, mimeType: string): boolean {
  const name = filename.toLowerCase()
  if (name.endsWith('.svg')) return true
  return mimeType.toLowerCase() === 'image/svg+xml'
}

function hubFileIsRasterImage(filename: string, mimeType: string): boolean {
  if (hubFileIsSvg(filename, mimeType)) return false
  const mime = mimeType.toLowerCase()
  if (mime.startsWith('image/')) return true
  return /\.(png|jpe?g|gif|webp|bmp|ico|tiff?|heic|heif)$/.test(filename.toLowerCase())
}

function HubFileIcon({ filename, mimeType }: { filename: string; mimeType: string }) {
  if (hubFileIsSvg(filename, mimeType)) return <Workflow size={14} />
  if (hubFileIsRasterImage(filename, mimeType)) return <FileImage size={14} />
  return <FileText size={14} />
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function hubParseStatus(item: HubItem): { label: string; detail: string | null } {
  const status = item.parse_status ?? 'pending'
  if (status === 'uploading') return { label: 'Uploading', detail: null }
  if (status === 'ready' || status === 'skipped') return { label: 'Ready', detail: null }
  if (status === 'failed') {
    return { label: 'Failed', detail: item.parse_error_message ?? null }
  }
  const snap = item.parse_stage_snapshot
  const message =
    snap && typeof snap === 'object' && 'message' in snap ? String((snap as { message?: string }).message ?? '') : ''
  if (status === 'running') {
    return { label: 'Processing', detail: message || null }
  }
  if (status === 'pending') {
    return { label: 'Queued', detail: message || null }
  }
  return { label: status, detail: message || null }
}

function folderDepth(folder: HubFolder, byId: Map<string, HubFolder>): number {
  let depth = 0
  let parentId = folder.parent_id
  const seen = new Set<string>()
  while (parentId) {
    if (seen.has(parentId)) break
    seen.add(parentId)
    depth += 1
    parentId = byId.get(parentId)?.parent_id ?? null
  }
  return depth
}

function parseStatusBadgeClass(status: string | undefined): string {
  const key = status ?? 'pending'
  if (key === 'ready' || key === 'skipped') return 'documents-status-badge-ready'
  if (key === 'failed') return 'documents-status-badge-failed'
  if (key === 'running' || key === 'uploading') return 'documents-status-badge-running'
  return 'documents-status-badge-pending'
}

export function DocumentHubView() {
  const [folders, setFolders] = useState<HubFolder[]>([])
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [items, setItems] = useState<HubItem[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [pendingUploads, setPendingUploads] = useState<PendingUpload[]>([])
  const [error, setError] = useState<string | null>(null)
  const [selectedItem, setSelectedItem] = useState<HubItem | null>(null)
  const [previewTab, setPreviewTab] = useState<'original' | 'parsed'>('parsed')
  const [parsedContent, setParsedContent] = useState<string | null>(null)
  const [parsedLoading, setParsedLoading] = useState(false)
  const [parsedView, setParsedView] = useState<'rendered' | 'source'>('rendered')
  const [importNotice, setImportNotice] = useState<string | null>(null)
  const [parseDrawerItem, setParseDrawerItem] = useState<HubItem | null>(null)
  const [deletingItemIds, setDeletingItemIds] = useState<string[]>([])

  const [folderWidth, setFolderWidth] = useState(() => readStoredHubWidth(HUB_FOLDER_WIDTH_KEY, 200))
  const [previewWidth, setPreviewWidth] = useState<number | null>(() =>
    readStoredHubWidth(HUB_PREVIEW_WIDTH_KEY, 440),
  )

  const workspaceRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const uploadFolderIdRef = useRef<string | null>(null)
  const uploadInFlightRef = useRef(false)
  const [dragOver, setDragOver] = useState(false)
  const folderDragRef = useRef<{ startX: number; startWidth: number } | null>(null)
  const previewDragRef = useRef<{ startX: number; startWidth: number } | null>(null)

  const targetChatId = useMemo(() => {
    try {
      return sessionStorage.getItem(HUB_TARGET_CHAT_STORAGE_KEY)
    } catch {
      return null
    }
  }, [])

  const folderById = useMemo(() => new Map(folders.map((f) => [f.id, f])), [folders])

  const loadFolders = useCallback(async (): Promise<HubFolder[]> => {
    const rows = await api.listHubFolders()
    setFolders(rows)
    setSelectedFolderId((prev) => {
      if (prev && rows.some((f) => f.id === prev)) return prev
      return rows[0]?.id ?? null
    })
    return rows
  }, [])

  const loadItems = useCallback(async (folderId: string) => {
    const rows = await api.listHubItems(folderId)
    setItems(rows)
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const rows = await loadFolders()
      const folderId = selectedFolderId ?? rows[0]?.id ?? null
      if (folderId) await loadItems(folderId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load Document Hub')
    } finally {
      setLoading(false)
    }
  }, [loadFolders, loadItems, selectedFolderId])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      setLoading(true)
      setError(null)
      try {
        await loadFolders()
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load Document Hub')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [loadFolders])

  useEffect(() => {
    if (!selectedFolderId) {
      setItems([])
      return
    }
    void loadItems(selectedFolderId).catch((err) => {
      setError(err instanceof Error ? err.message : 'Failed to load files')
    })
  }, [loadItems, selectedFolderId])

  useEffect(() => {
    storeHubWidth(HUB_FOLDER_WIDTH_KEY, folderWidth)
  }, [folderWidth])

  useEffect(() => {
    if (previewWidth != null) storeHubWidth(HUB_PREVIEW_WIDTH_KEY, previewWidth)
  }, [previewWidth])

  const clampFolderWidth = useCallback((next: number) => {
    return Math.min(Math.max(next, HUB_MIN_FOLDER_WIDTH), HUB_MAX_FOLDER_WIDTH)
  }, [])

  const clampPreviewWidth = useCallback((next: number) => {
    const workspace = workspaceRef.current
    if (!workspace) return Math.max(HUB_MIN_PREVIEW_WIDTH, next)
    const total = workspace.getBoundingClientRect().width
    const max = Math.max(HUB_MIN_PREVIEW_WIDTH, total * HUB_MAX_PREVIEW_RATIO)
    const maxByList = total - folderWidth - HUB_MIN_LIST_WIDTH - HUB_RESIZE_HANDLE_WIDTH * 2
    return Math.min(Math.max(next, HUB_MIN_PREVIEW_WIDTH), max, maxByList)
  }, [folderWidth])

  const handleSelectItem = (item: HubItem) => {
    if (hubItemShowsParseDrawer(item)) {
      setSelectedItem(null)
      setParseDrawerItem(item)
      return
    }
    setParseDrawerItem(null)
    setSelectedItem(item)
    setPreviewTab('parsed')
    setParsedView('rendered')
    setPreviewWidth((current) => (current != null ? clampPreviewWidth(current) : clampPreviewWidth(440)))
  }

  const selectFolder = (folderId: string) => {
    setSelectedFolderId(folderId)
    setSelectedItem(null)
    setParseDrawerItem(null)
  }

  const onFolderResizeDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    folderDragRef.current = { startX: event.clientX, startWidth: folderWidth }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const onFolderResizeMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!folderDragRef.current) return
    const delta = event.clientX - folderDragRef.current.startX
    setFolderWidth(clampFolderWidth(folderDragRef.current.startWidth + delta))
  }

  const onFolderResizeUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!folderDragRef.current) return
    folderDragRef.current = null
    event.currentTarget.releasePointerCapture(event.pointerId)
  }

  const onPreviewResizeDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!selectedItem) return
    event.preventDefault()
    previewDragRef.current = { startX: event.clientX, startWidth: previewWidth ?? HUB_MIN_PREVIEW_WIDTH }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const onPreviewResizeMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!previewDragRef.current) return
    const delta = previewDragRef.current.startX - event.clientX
    setPreviewWidth(clampPreviewWidth(previewDragRef.current.startWidth + delta))
  }

  const onPreviewResizeUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!previewDragRef.current) return
    previewDragRef.current = null
    event.currentTarget.releasePointerCapture(event.pointerId)
  }

  useEffect(() => {
    if (!selectedItem || previewTab !== 'parsed' || !hubItemPreviewReady(selectedItem)) {
      setParsedContent(null)
      setParsedLoading(false)
      return
    }
    let cancelled = false
    setParsedLoading(true)
    setParsedContent(null)
    void api
      .fetchHubParsedText(selectedItem.id, 'content_md')
      .then((text) => {
        if (!cancelled) setParsedContent(text)
      })
      .catch(() => {
        if (!cancelled) setParsedContent(null)
      })
      .finally(() => {
        if (!cancelled) setParsedLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [previewTab, selectedItem])

  useEffect(() => {
    if (!parseDrawerItem) return
    const status = parseDrawerItem.parse_status ?? 'pending'
    if (status === 'ready' || status === 'skipped' || status === 'failed') return

    const timer = window.setInterval(() => {
      if (!selectedFolderId) return
      void loadItems(selectedFolderId).catch(() => {})
    }, ATTACHMENT_PARSE_POLL_MS)

    return () => window.clearInterval(timer)
  }, [loadItems, parseDrawerItem, selectedFolderId])

  useEffect(() => {
    if (!parseDrawerItem) return
    const updated = items.find((row) => row.id === parseDrawerItem.id)
    if (!updated) return
    const snap = JSON.stringify(updated.parse_stage_snapshot ?? null)
    const prevSnap = JSON.stringify(parseDrawerItem.parse_stage_snapshot ?? null)
    if (
      updated.parse_status !== parseDrawerItem.parse_status ||
      updated.parse_error_message !== parseDrawerItem.parse_error_message ||
      snap !== prevSnap
    ) {
      setParseDrawerItem(updated)
    }
  }, [items, parseDrawerItem])

  useEffect(() => {
    if (!selectedItem) return
    const updated = items.find((row) => row.id === selectedItem.id)
    if (!updated) {
      setSelectedItem(null)
      return
    }
    if (!hubItemPreviewReady(updated)) {
      setSelectedItem(null)
      setParseDrawerItem(updated)
    }
  }, [items, selectedItem])

  const parseDrawerAttachment = useMemo(
    () => (parseDrawerItem ? hubItemToAttachmentListItem(parseDrawerItem) : null),
    [parseDrawerItem],
  )

  const renderedParsedContent = useMemo(
    () =>
      selectedItem && parsedContent != null
        ? rewriteHubParsedFigureRefs(parsedContent, selectedItem.id)
        : null,
    [parsedContent, selectedItem],
  )

  const resolveHubFigureSrc = useCallback(
    (src: string | undefined) =>
      selectedItem ? resolveHubParsedFigureSrc(src, selectedItem.id) : src,
    [selectedItem],
  )

  const handleCreateFolder = async () => {
    const name = window.prompt('Folder name')
    if (!name?.trim()) return
    setError(null)
    try {
      const created = await api.createHubFolder({ name: name.trim(), parent_id: null })
      await loadFolders()
      setSelectedFolderId(created.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create folder')
    }
  }

  const handleDeleteFolder = async (folderId: string, folderName: string) => {
    if (!window.confirm(`Delete folder "${folderName}" and all contents? This cannot be undone.`)) return
    setError(null)
    try {
      const rows = await api.listHubFolders()
      const target = rows.find((f) => f.id === folderId)
      if (!target) {
        setError('That folder no longer exists. Refreshing the list.')
        await loadFolders()
        return
      }
      if (target.name !== folderName) {
        setError(
          `Folder list is out of sync (row says "${folderName}" but server has "${target.name}" for that id). Refresh and try again.`,
        )
        setFolders(rows)
        return
      }
      await api.deleteHubFolder(folderId, folderName)
      if (selectedFolderId === folderId) {
        setSelectedFolderId(null)
        setSelectedItem(null)
        setItems([])
      }
      await loadFolders()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete folder')
    }
  }

  const handleDeleteItem = async (item: HubItem) => {
    if (deletingItemIds.includes(item.id)) return
    if (!window.confirm(`Delete "${item.filename}"?`)) return
    setError(null)
    setDeletingItemIds((prev) => (prev.includes(item.id) ? prev : [...prev, item.id]))
    try {
      await api.deleteHubItem(item.id)
      if (selectedItem?.id === item.id) setSelectedItem(null)
      if (parseDrawerItem?.id === item.id) setParseDrawerItem(null)
      if (selectedFolderId) await loadItems(selectedFolderId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete item')
    } finally {
      setDeletingItemIds((prev) => prev.filter((id) => id !== item.id))
    }
  }

  const handleMoveItem = async (item: HubItem) => {
    const target = window.prompt(`Move to folder:\n${folders.map((f) => f.name).join(', ')}`)
    if (!target?.trim()) return
    const dest = folders.find((f) => f.name.toLowerCase() === target.trim().toLowerCase())
    if (!dest) {
      setError(`Folder not found: "${target.trim()}"`)
      return
    }
    setError(null)
    try {
      await api.moveHubItem(item.id, dest.id)
      if (selectedFolderId) await loadItems(selectedFolderId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to move item')
    }
  }

  const uploadFolderId = useMemo((): string | null => {
    if (selectedFolderId && folders.some((f) => f.id === selectedFolderId)) return selectedFolderId
    return folders[0]?.id ?? null
  }, [folders, selectedFolderId])

  uploadFolderIdRef.current = uploadFolderId

  const doUploadFiles = async (files: File[]) => {
    if (!files.length || uploadInFlightRef.current) return
    const folderId = uploadFolderIdRef.current
    if (!folderId) {
      setError('Select or create a folder before uploading.')
      return
    }
    uploadInFlightRef.current = true
    setSelectedFolderId((prev) => (prev === folderId ? prev : folderId))

    const placeholders = files.map((file) => ({ id: crypto.randomUUID(), filename: file.name }))
    setError(null)
    setImportNotice(null)
    setUploading(true)
    setPendingUploads(placeholders)
    try {
      for (let i = 0; i < files.length; i += 1) {
        const file = files[i]
        const row = await api.uploadHubItem(folderId, file)
        if (row.duplicate_of_existing) {
          setImportNotice(`"${file.name}" already exists in your library.`)
        }
        setPendingUploads((prev) => prev.filter((p) => p.id !== placeholders[i]?.id))
      }
      await loadItems(folderId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      uploadInFlightRef.current = false
      setUploading(false)
      setPendingUploads([])
    }
  }

  const handleUploadButtonClick = () => {
    if (uploadActive) return
    if (!uploadFolderIdRef.current) {
      setError('Select or create a folder before uploading.')
      return
    }
    fileInputRef.current?.click()
  }

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget
    const fileList = input.files
    if (!fileList?.length) return
    const picked = Array.from(fileList)
    input.value = ''
    void doUploadFiles(picked)
  }

  const handleListDragOver = (event: DragEvent<HTMLDivElement>) => {
    if (uploading || pendingUploads.length > 0 || !uploadFolderId) return
    if (!event.dataTransfer.types.includes('Files')) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
    setDragOver(true)
  }

  const handleListDragLeave = (event: DragEvent<HTMLDivElement>) => {
    if (event.currentTarget.contains(event.relatedTarget as Node)) return
    setDragOver(false)
  }

  const handleListDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragOver(false)
    if (uploading || pendingUploads.length > 0) return
    const dropped = event.dataTransfer.files
    if (!dropped?.length) return
    void doUploadFiles(Array.from(dropped))
  }

  const uploadActive = uploading || pendingUploads.length > 0

  const showEmptyCenter =
    !loading &&
    !uploadActive &&
    ((!selectedFolderId && folders.length === 0) ||
      ((selectedFolderId ?? folders[0]?.id) && items.length === 0))

  const emptyMessage = !selectedFolderId
    ? folders.length === 0
      ? 'Create a folder to start uploading files.'
      : 'Select a folder on the left.'
    : 'No files in this folder yet. Click Upload or drop files here.'

  return (
    <div className="document-hub-view documents-view documents-view-agent-scoped">
      <input
        ref={fileInputRef}
        type="file"
        multiple
        tabIndex={-1}
        aria-hidden
        className="document-hub-hidden-file-input"
        onChange={handleFileInputChange}
      />
      <header className="documents-view-header">
        <div>
          <h1 className="documents-view-title">Document Hub</h1>
          <p className="documents-view-subtitle">
            Personal document library. Import into a chat before @ mentions and retrieval tools can use a file.
            {targetChatId ? ' · Session linked for import' : ''}
          </p>
        </div>
      </header>

      {importNotice ? <div className="integrations-view-notice">{importNotice}</div> : null}
      {error ? <div className="integrations-view-error">{error}</div> : null}

      <div className="document-hub-workspace" ref={workspaceRef}>
        <aside className="document-hub-folder-pane" style={{ width: folderWidth }}>
          <div className="document-hub-sidebar-head">
            <span>Folders</span>
            <button type="button" className="document-hub-icon-btn" onClick={() => void handleCreateFolder()} title="New folder">
              +
            </button>
          </div>
          <ul className="document-hub-folder-list">
            {folders.map((folder) => {
              const depth = folderDepth(folder, folderById)
              const isSelected = selectedFolderId === folder.id
              return (
                <li key={folder.id} className="document-hub-folder-row">
                  <button
                    type="button"
                    className={`document-hub-folder-btn${isSelected ? ' document-hub-folder-btn-active' : ''}${depth > 0 ? ' document-hub-folder-btn-nested' : ''}`}
                    style={depth > 0 ? { paddingLeft: `${0.55 + depth * 0.65}rem` } : undefined}
                    onClick={() => selectFolder(folder.id)}
                  >
                    {folder.name}
                  </button>
                  <button
                    type="button"
                    className={`document-hub-folder-delete${isSelected ? ' document-hub-folder-delete-visible' : ''}`}
                    title={`Delete folder "${folder.name}"`}
                    aria-label={`Delete folder ${folder.name}`}
                    onPointerDown={(e) => e.stopPropagation()}
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      void handleDeleteFolder(folder.id, folder.name)
                    }}
                  >
                    <Trash2 size={14} strokeWidth={1.75} />
                  </button>
                </li>
              )
            })}
          </ul>
        </aside>

        <div
          className="documents-view-resize-handle"
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize folders panel"
          style={{ width: HUB_RESIZE_HANDLE_WIDTH }}
          onPointerDown={onFolderResizeDown}
          onPointerMove={onFolderResizeMove}
          onPointerUp={onFolderResizeUp}
          onPointerCancel={onFolderResizeUp}
        />

        <div
          className={`document-hub-list-pane${dragOver ? ' document-hub-list-pane-drag-over' : ''}`}
          onDragOver={handleListDragOver}
          onDragLeave={handleListDragLeave}
          onDrop={handleListDrop}
        >
          <div className="document-hub-toolbar">
            <button
              type="button"
              className="integration-tile-btn integration-tile-btn-primary"
              disabled={uploadActive}
              onClick={handleUploadButtonClick}
            >
              {uploading ? 'Uploading…' : 'Upload'}
            </button>
            <button
              type="button"
              className="integration-tile-btn integration-tile-btn-ghost"
              disabled={uploadActive}
              onClick={() => void refresh()}
            >
              Refresh
            </button>
            {uploadActive ? (
              <span className="document-hub-toolbar-status">
                <LoadingSpinner size="sm" /> Upload in progress…
              </span>
            ) : null}
          </div>

          {loading ? (
            <div className="document-hub-empty-center">
              <LoadingSpinner />
              <span>Loading…</span>
            </div>
          ) : uploadActive ? (
            <div className="document-hub-empty-center document-hub-upload-active">
              <LoadingSpinner size="md" />
              <p>Uploading {pendingUploads.length || 1} file(s)…</p>
              <ul className="document-hub-upload-names">
                {pendingUploads.map((p) => (
                  <li key={p.id}>{p.filename}</li>
                ))}
              </ul>
            </div>
          ) : showEmptyCenter ? (
            <div className="document-hub-empty-center">
              <p>{emptyMessage}</p>
            </div>
          ) : (
            <div className="document-hub-list-scroll">
              <ul className="document-hub-file-list">
                {pendingUploads.map((pending) => (
                  <li key={pending.id}>
                    <div className="document-hub-file-card document-hub-file-card-pending">
                      <span className="documents-col-file-icon document-hub-file-card-type-icon" aria-hidden>
                        <HubFileIcon filename={pending.filename} mimeType="" />
                      </span>
                      <div className="document-hub-file-card-main">
                        <div className="document-hub-file-card-title-row">
                          <span className="document-hub-file-name">{pending.filename}</span>
                          <span className="documents-status-badge documents-status-badge-running">Uploading</span>
                        </div>
                        <span className="document-hub-file-detail">Uploading…</span>
                      </div>
                    </div>
                  </li>
                ))}
                {items.map((item) => {
                  const { label, detail } = hubParseStatus(item)
                  const selected = selectedItem?.id === item.id
                  const isDeleting = deletingItemIds.includes(item.id)
                  return (
                    <li key={item.id}>
                      <div
                        className={`document-hub-file-card${selected ? ' document-hub-file-card-selected' : ''}${isDeleting ? ' document-hub-file-card-deleting' : ''}`}
                        role={isDeleting ? undefined : 'button'}
                        tabIndex={isDeleting ? -1 : 0}
                        aria-busy={isDeleting}
                        onClick={() => {
                          if (isDeleting) return
                          handleSelectItem(item)
                        }}
                        onKeyDown={(e) => {
                          if (isDeleting) return
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            handleSelectItem(item)
                          }
                        }}
                      >
                        <span className="documents-col-file-icon document-hub-file-card-type-icon" aria-hidden>
                          <HubFileIcon filename={item.filename} mimeType={item.mime_type} />
                        </span>
                        <div className="document-hub-file-card-main">
                          <div className="document-hub-file-card-title-row">
                            <span className="document-hub-file-name" title={item.filename}>
                              {item.filename}
                            </span>
                            <span
                              className={`documents-status-badge ${isDeleting ? 'documents-status-badge-running' : parseStatusBadgeClass(item.parse_status)}`}
                            >
                              {isDeleting ? 'Deleting' : label}
                            </span>
                          </div>
                          {isDeleting ? (
                            <span className="document-hub-file-detail">Removing file…</span>
                          ) : detail ? (
                            <span className="document-hub-file-detail" title={detail}>
                              {detail}
                            </span>
                          ) : (
                            <span className="document-hub-file-detail">{formatFileSize(item.size_bytes)}</span>
                          )}
                        </div>
                        {isDeleting ? (
                          <div className="document-hub-file-card-busy" aria-hidden>
                            <LoadingSpinner size="sm" />
                          </div>
                        ) : (
                          <div className="document-hub-file-card-icons">
                            <button
                              type="button"
                              className="document-hub-file-icon-btn"
                              title="Move to another folder"
                              aria-label={`Move ${item.filename}`}
                              onClick={(e) => {
                                e.stopPropagation()
                                void handleMoveItem(item)
                              }}
                            >
                              <FolderInput size={15} strokeWidth={1.75} />
                            </button>
                            <button
                              type="button"
                              className="document-hub-file-icon-btn document-hub-file-icon-btn-danger"
                              title="Delete file"
                              aria-label={`Delete ${item.filename}`}
                              onClick={(e) => {
                                e.stopPropagation()
                                void handleDeleteItem(item)
                              }}
                            >
                              <Trash2 size={15} strokeWidth={1.75} />
                            </button>
                          </div>
                        )}
                      </div>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}

          {uploading ? <div className="document-hub-upload-overlay" aria-hidden /> : null}
        </div>

        {selectedItem && hubItemPreviewReady(selectedItem) && previewWidth != null ? (
          <>
            <div
              className="documents-view-resize-handle"
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize preview panel"
              style={{ width: HUB_RESIZE_HANDLE_WIDTH }}
              onPointerDown={onPreviewResizeDown}
              onPointerMove={onPreviewResizeMove}
              onPointerUp={onPreviewResizeUp}
              onPointerCancel={onPreviewResizeUp}
            />
            <div className="documents-view-preview-pane document-hub-preview-pane" style={{ width: previewWidth }}>
              <div className="documents-preview-pane">
                <header className="documents-preview-header">
                  <h3 className="documents-preview-title" title={selectedItem.filename}>
                    {selectedItem.filename}
                  </h3>
                  <button type="button" className="documents-preview-close" onClick={() => setSelectedItem(null)} aria-label="Close preview">
                    ×
                  </button>
                </header>
                <div className="documents-preview-toolbar">
                  <div className="documents-preview-tabs">
                    <button
                      type="button"
                      className={`documents-preview-tab${previewTab === 'original' ? ' documents-preview-tab-active' : ''}`}
                      onClick={() => setPreviewTab('original')}
                    >
                      Original
                    </button>
                    <button
                      type="button"
                      className={`documents-preview-tab${previewTab === 'parsed' ? ' documents-preview-tab-active' : ''}`}
                      onClick={() => setPreviewTab('parsed')}
                    >
                      Parsed
                    </button>
                  </div>
                </div>
                <div className="documents-preview-body document-hub-preview-body">
                  <div className="document-hub-preview-surface">
                    {previewTab === 'original' ? (
                      <iframe
                        className="documents-preview-frame document-hub-preview-frame"
                        title={selectedItem.filename}
                        src={api.hubOriginalUrl(selectedItem.id)}
                      />
                    ) : parsedLoading ? (
                      <div className="document-hub-empty-center">
                        <LoadingSpinner />
                        <span>Loading parsed content…</span>
                      </div>
                    ) : parsedContent ? (
                      <>
                        <div className="documents-pageindex-toggle document-hub-parsed-toggle" role="tablist" aria-label="Parsed view">
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
                            className="markdown-body documents-preview-markdown document-hub-preview-markdown"
                            allowHtml
                            resolveImageSrc={resolveHubFigureSrc}
                          />
                        ) : (
                          <pre className="documents-preview-text document-hub-preview-text">{parsedContent}</pre>
                        )}
                      </>
                    ) : (
                      <p className="documents-preview-empty">No parsed content yet.</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </div>

      <AttachmentParseDrawer
        attachment={parseDrawerAttachment}
        onClose={() => setParseDrawerItem(null)}
        onRetry={
          parseDrawerItem
            ? async (att) => {
                const row = await api.retryHubItemParse(att.id)
                setParseDrawerItem(row)
                if (selectedFolderId) await loadItems(selectedFolderId)
              }
            : undefined
        }
      />
    </div>
  )
}
