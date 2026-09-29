import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useHubFolders } from '../context/HubFoldersContext'
import { readStoredHubFolderId } from '../lib/documentHubLayout'

type Props = {
  hubOpen: boolean
}

/** When entering Document Hub, ensure URL has a valid ?folder= id. */
export function HubFolderRouteSync({ hubOpen }: Props) {
  const [searchParams, setSearchParams] = useSearchParams()
  const { rootFolders, loading } = useHubFolders()

  useEffect(() => {
    if (!hubOpen || loading) return
    const current = searchParams.get('folder')
    if (current && rootFolders.some((f) => f.id === current)) return

    const stored = readStoredHubFolderId()
    const pick =
      stored && rootFolders.some((f) => f.id === stored) ? stored : (rootFolders[0]?.id ?? null)

    if (!pick) {
      if (current) setSearchParams({}, { replace: true })
      return
    }
    if (pick !== current) {
      setSearchParams({ folder: pick }, { replace: true })
    }
  }, [hubOpen, loading, rootFolders, searchParams, setSearchParams])

  return null
}
