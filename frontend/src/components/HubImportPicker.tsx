import { useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { FileText, FolderOpen, X } from 'lucide-react'
import { api } from '../api/client'
import type { ChatDocumentImport, HubFolder, HubItem } from '../types/hub'
import {
  readStoredHubFolderId,
  storeHubFolderId,
} from '../lib/documentHubLayout'
import { documentParseListBadge } from '../lib/documentParseDisplay'
import { formatFileSize } from '../lib/formatBytes'
import { LoadingSpinner } from './LoadingSpinner'

type Props = {
  open: boolean
  chatId: string
  existingImports: ChatDocumentImport[]
  onClose: () => void
  onImported: (rows: ChatDocumentImport[]) => void
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

function pickInitialFolderId(folders: HubFolder[]): string | null {
  if (!folders.length) return null
  const stored = readStoredHubFolderId()
  if (stored && folders.some((f) => f.id === stored)) return stored
  return folders[0]?.id ?? null
}

export function HubImportPicker({
  open,
  chatId,
  existingImports,
  onClose,
  onImported,
}: Props) {
  const [folders, setFolders] = useState<HubFolder[]>([])
  const [folderId, setFolderId] = useState<string | null>(null)
  const [items, setItems] = useState<HubItem[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [loading, setLoading] = useState(false)
  const [itemsLoading, setItemsLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const importedHubIds = useMemo(() => {
    const ids = new Set<string>()
    for (const row of existingImports) {
      if (row.source === 'hub_item') ids.add(row.ref_id)
    }
    return ids
  }, [existingImports])

  const folderById = useMemo(() => new Map(folders.map((f) => [f.id, f])), [folders])

  const loadItems = useCallback(async (id: string) => {
    setItemsLoading(true)
    setError(null)
    try {
      const rows = await api.listHubItems(id)
      setItems(rows.filter((row) => row.item_kind !== 'audio_part'))
    } catch (e) {
      setItems([])
      setError(e instanceof Error ? e.message : 'Failed to load files')
    } finally {
      setItemsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    setSelectedIds(new Set())
    setError(null)
    setLoading(true)
    void (async () => {
      try {
        const rows = await api.listHubFolders()
        setFolders(rows)
        const initial = pickInitialFolderId(rows)
        setFolderId(initial)
        if (initial) {
          storeHubFolderId(initial)
          await loadItems(initial)
        } else {
          setItems([])
        }
      } catch (e) {
        setFolders([])
        setFolderId(null)
        setItems([])
        setError(e instanceof Error ? e.message : 'Failed to load folders')
      } finally {
        setLoading(false)
      }
    })()
  }, [loadItems, open])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = prevOverflow
    }
  }, [onClose, open])

  const toggleItem = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleFolderSelect = (id: string) => {
    storeHubFolderId(id)
    setFolderId(id)
    setSelectedIds(new Set())
    void loadItems(id)
  }

  async function handleImport() {
    const ids = [...selectedIds].filter((id) => !importedHubIds.has(id))
    if (!ids.length || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const rows = await api.importHubToChat(chatId, ids)
      onImported(rows)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  const newSelectionCount = [...selectedIds].filter((id) => !importedHubIds.has(id)).length

  const dialog = (
    <>
      <div className="hub-import-backdrop" role="presentation" onClick={onClose} />
      <div className="hub-import-dialog" role="dialog" aria-modal="true" aria-label="Import from Document Hub">
        <header className="hub-import-header">
          <div className="hub-import-title-wrap">
            <FolderOpen size={18} aria-hidden />
            <h2 className="hub-import-title">Import from Document Hub</h2>
          </div>
          <button type="button" className="hub-import-close" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </header>
        <p className="hub-import-desc">
          Add files to this chat&apos;s document library. After import, type <strong>@</strong> in the
          message box to reference parsed documents.
        </p>
        {error ? <p className="hub-import-error">{error}</p> : null}
        {loading ? (
          <div className="hub-import-loading hub-import-loading-block">
            <LoadingSpinner />
            <span>Loading your library…</span>
          </div>
        ) : folders.length === 0 ? (
          <div className="hub-import-empty-block">
            <p className="hub-import-empty">No folders yet.</p>
            <p className="hub-import-empty-hint">Upload documents in Document Hub first, then return here.</p>
          </div>
        ) : (
          <div className="hub-import-body">
            <aside className="hub-import-folders">
              <span className="hub-import-folders-label">Folders</span>
              <ul>
                {folders.map((folder) => {
                  const depth = folderDepth(folder, folderById)
                  const active = folderId === folder.id
                  return (
                    <li key={folder.id}>
                      <button
                        type="button"
                        className={`hub-import-folder-btn${active ? ' hub-import-folder-btn-active' : ''}`}
                        style={depth > 0 ? { paddingLeft: `${0.5 + depth * 0.55}rem` } : undefined}
                        onClick={() => handleFolderSelect(folder.id)}
                      >
                        {folder.name}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </aside>
            <div className="hub-import-items">
              {itemsLoading ? (
                <div className="hub-import-loading hub-import-loading-inline">
                  <LoadingSpinner size="sm" />
                </div>
              ) : items.length === 0 ? (
                <div className="hub-import-empty-block hub-import-empty-block-inline">
                  <p className="hub-import-empty">This folder has no files.</p>
                  <p className="hub-import-empty-hint">Choose another folder or upload in Document Hub.</p>
                </div>
              ) : (
                <ul className="hub-import-item-list">
                  {items.map((item) => {
                    const { label, badgeClass } = documentParseListBadge(item)
                    const already = importedHubIds.has(item.id)
                    const checked = already || selectedIds.has(item.id)
                    return (
                      <li key={item.id}>
                        <label
                          className={`hub-import-item-row${already ? ' hub-import-item-row-imported' : ''}`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={already || submitting}
                            onChange={() => toggleItem(item.id)}
                          />
                          <FileText size={14} className="hub-import-item-icon" aria-hidden />
                          <span className="hub-import-item-main">
                            <span className="hub-import-item-name" title={item.filename}>
                              {item.filename}
                            </span>
                            <span className="hub-import-item-meta">
                              {formatFileSize(item.size_bytes)}
                              {already ? ' · Already in chat' : ''}
                            </span>
                          </span>
                          <span className={`documents-status-badge ${badgeClass}`}>{label}</span>
                        </label>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </div>
        )}
        <footer className="hub-import-footer">
          <button type="button" className="integration-tile-btn integration-tile-btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="integration-tile-btn integration-tile-btn-primary"
            disabled={loading || submitting || newSelectionCount === 0}
            onClick={() => void handleImport()}
          >
            {submitting ? 'Importing…' : newSelectionCount > 0 ? `Import (${newSelectionCount})` : 'Import'}
          </button>
        </footer>
      </div>
    </>
  )

  return createPortal(dialog, document.body)
}
