import { Navigate, useSearchParams } from 'react-router-dom'

/** Legacy route — forwards to chat with the documents drawer open. */
export function DocumentsSettingsPage() {
  const [searchParams] = useSearchParams()
  const next = new URLSearchParams(searchParams)
  next.set('documents', '1')
  return <Navigate to={`/chat?${next.toString()}`} replace />
}
