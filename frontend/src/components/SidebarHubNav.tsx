import { ChevronDown, ChevronRight, Folder, FolderOpen, Plus, Trash2 } from 'lucide-react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useCallback, useEffect, useState } from 'react'
import {
  agentHubPath,
  HUB_SIDEBAR_EXPANDED_KEY,
  HUB_TARGET_CHAT_STORAGE_KEY,
  parseChatRoute,
} from '../lib/chatRoutes'
import { readStoredHubFolderId, storeHubFolderId } from '../lib/documentHubLayout'
import { useHubFolders } from '../context/HubFoldersContext'

type Props = {
  collapsed: boolean
  agentId: string
  activeChatId?: string | null
}

function readHubExpanded(): boolean {
  try {
    return sessionStorage.getItem(HUB_SIDEBAR_EXPANDED_KEY) !== '0'
  } catch {
    return true
  }
}

function storeHubExpanded(expanded: boolean): void {
  try {
    sessionStorage.setItem(HUB_SIDEBAR_EXPANDED_KEY, expanded ? '1' : '0')
  } catch {
    /* ignore */
  }
}

export function SidebarHubNav({ collapsed, agentId, activeChatId }: Props) {
  const navigate = useNavigate()
  const location = useLocation()
  const { rootFolders, createFolder, deleteFolder } = useHubFolders()
  const { view } = parseChatRoute(location.pathname)
  const hubActive = view === 'hub'

  const [expanded, setExpanded] = useState(() => readHubExpanded())

  useEffect(() => {
    if (hubActive) {
      setExpanded(true)
      storeHubExpanded(true)
    }
  }, [hubActive])

  const selectedFolderId = useMemoFolderFromSearch(location.search)

  const toggleExpanded = useCallback(() => {
    setExpanded((prev) => {
      const next = !prev
      storeHubExpanded(next)
      return next
    })
  }, [])

  const openHubRoot = useCallback(() => {
    if (activeChatId) {
      try {
        sessionStorage.setItem(HUB_TARGET_CHAT_STORAGE_KEY, activeChatId)
      } catch {
        /* ignore */
      }
    }
    const stored = readStoredHubFolderId()
    const folderId =
      stored && rootFolders.some((f) => f.id === stored)
        ? stored
        : rootFolders[0]?.id ?? null
    navigate(agentHubPath(agentId, folderId))
  }, [activeChatId, agentId, navigate, rootFolders])

  const handleCreateFolder = useCallback(async () => {
    const name = window.prompt('New folder name')
    if (!name?.trim()) return
    try {
      const created = await createFolder(name)
      storeHubFolderId(created.id)
      navigate(agentHubPath(agentId, created.id))
      setExpanded(true)
      storeHubExpanded(true)
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Failed to create folder')
    }
  }, [agentId, createFolder, navigate])

  const handleDeleteFolder = useCallback(
    async (folderId: string, folderName: string, event: React.MouseEvent) => {
      event.preventDefault()
      event.stopPropagation()
      if (!window.confirm(`Delete folder "${folderName}" and all files inside?`)) return
      try {
        const rows = await deleteFolder(folderId, folderName)
        if (selectedFolderId === folderId) {
          const remaining = rows
            .filter((f) => f.parent_id == null)
            .sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name))
          navigate(agentHubPath(agentId, remaining[0]?.id ?? null))
        }
      } catch (err) {
        window.alert(err instanceof Error ? err.message : 'Failed to delete folder')
      }
    },
    [agentId, deleteFolder, navigate, selectedFolderId],
  )

  if (collapsed) {
    return (
      <li>
        <NavLink
          to={agentHubPath(agentId, selectedFolderId)}
          title="Document Hub"
          className={({ isActive }) =>
            `agent-nav-item agent-nav-item-collapsed${isActive ? ' agent-nav-item-active' : ''}`
          }
          onClick={() => {
            if (activeChatId) {
              try {
                sessionStorage.setItem(HUB_TARGET_CHAT_STORAGE_KEY, activeChatId)
              } catch {
                /* ignore */
              }
            }
          }}
        >
          <FolderOpen className="h-[1.375rem] w-[1.375rem] shrink-0" strokeWidth={1.75} aria-hidden />
        </NavLink>
      </li>
    )
  }

  return (
    <li className="agent-nav-hub-root">
      <div
        className={`agent-nav-hub-head${hubActive ? ' agent-nav-item-active' : ''}`}
      >
        <button type="button" className="agent-nav-hub-label" onClick={() => openHubRoot()}>
          <FolderOpen
            className="h-[1.375rem] w-[1.375rem] shrink-0"
            strokeWidth={1.75}
            aria-hidden
          />
          <span className="agent-nav-label">Document Hub</span>
        </button>
        <div className="agent-nav-hub-trailing">
          <button
            type="button"
            className="agent-nav-hub-add"
            title="New folder"
            aria-label="New folder under Document Hub"
            onClick={() => void handleCreateFolder()}
          >
            <Plus size={15} strokeWidth={2} aria-hidden />
          </button>
          <button
            type="button"
            className="agent-nav-hub-chevron"
            aria-expanded={expanded}
            aria-label={expanded ? 'Collapse Document Hub folders' : 'Expand Document Hub folders'}
            onClick={toggleExpanded}
          >
            {expanded ? (
              <ChevronDown size={16} strokeWidth={2} aria-hidden />
            ) : (
              <ChevronRight size={16} strokeWidth={2} aria-hidden />
            )}
          </button>
        </div>
      </div>
      {expanded ? (
        <ul className="agent-nav-hub-folders">
          {rootFolders.length === 0 ? (
            <li className="agent-nav-hub-folder-empty">No folders yet</li>
          ) : (
            rootFolders.map((folder) => {
              const isSelected = hubActive && selectedFolderId === folder.id
              return (
                <li key={folder.id}>
                  <NavLink
                    to={agentHubPath(agentId, folder.id)}
                    className={`agent-nav-hub-folder${isSelected ? ' agent-nav-hub-folder-active' : ''}`}
                    onClick={() => {
                      storeHubFolderId(folder.id)
                      if (activeChatId) {
                        try {
                          sessionStorage.setItem(HUB_TARGET_CHAT_STORAGE_KEY, activeChatId)
                        } catch {
                          /* ignore */
                        }
                      }
                    }}
                  >
                    <Folder size={15} strokeWidth={1.75} aria-hidden className="agent-nav-hub-folder-icon" />
                    <span className="agent-nav-hub-folder-name">{folder.name}</span>
                    <button
                      type="button"
                      className="agent-nav-hub-folder-delete"
                      title={`Delete folder ${folder.name}`}
                      aria-label={`Delete folder ${folder.name}`}
                      onClick={(e) => void handleDeleteFolder(folder.id, folder.name, e)}
                    >
                      <Trash2 size={13} strokeWidth={1.75} />
                    </button>
                  </NavLink>
                </li>
              )
            })
          )}
        </ul>
      ) : null}
    </li>
  )
}

function useMemoFolderFromSearch(search: string): string | null {
  try {
    return new URLSearchParams(search).get('folder')
  } catch {
    return null
  }
}
