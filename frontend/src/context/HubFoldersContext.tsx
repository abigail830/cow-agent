import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../api/client'
import type { HubFolder } from '../types/hub'

type HubFoldersContextValue = {
  folders: HubFolder[]
  rootFolders: HubFolder[]
  loading: boolean
  refresh: () => Promise<HubFolder[]>
  createFolder: (name: string) => Promise<HubFolder>
  deleteFolder: (folderId: string, folderName: string) => Promise<HubFolder[]>
}

const HubFoldersContext = createContext<HubFoldersContextValue | null>(null)

export function HubFoldersProvider({ children }: { children: ReactNode }) {
  const [folders, setFolders] = useState<HubFolder[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await api.listHubFolders()
      setFolders(rows)
      return rows
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const rootFolders = useMemo(
    () =>
      folders
        .filter((f) => f.parent_id == null)
        .slice()
        .sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name)),
    [folders],
  )

  const createFolder = useCallback(
    async (name: string) => {
      const created = await api.createHubFolder({ name: name.trim(), parent_id: null })
      await refresh()
      return created
    },
    [refresh],
  )

  const deleteFolder = useCallback(
    async (folderId: string, folderName: string) => {
      await api.deleteHubFolder(folderId, folderName)
      return refresh()
    },
    [refresh],
  )

  const value = useMemo(
    () => ({
      folders,
      rootFolders,
      loading,
      refresh,
      createFolder,
      deleteFolder,
    }),
    [createFolder, deleteFolder, folders, loading, refresh, rootFolders],
  )

  return <HubFoldersContext.Provider value={value}>{children}</HubFoldersContext.Provider>
}

export function useHubFolders(): HubFoldersContextValue {
  const ctx = useContext(HubFoldersContext)
  if (!ctx) {
    throw new Error('useHubFolders must be used within HubFoldersProvider')
  }
  return ctx
}
