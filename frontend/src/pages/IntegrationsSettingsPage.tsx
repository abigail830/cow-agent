import { Navigate, useSearchParams } from 'react-router-dom'

/** Legacy OAuth callback route — forwards to chat with the integrations view open. */
export function IntegrationsSettingsPage() {
  const [searchParams] = useSearchParams()
  const next = new URLSearchParams(searchParams)
  next.set('integrations', '1')
  return <Navigate to={`/chat?${next.toString()}`} replace />
}
