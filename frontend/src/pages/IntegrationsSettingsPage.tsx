import { Navigate, useSearchParams } from 'react-router-dom'
import { CHAT_INTEGRATIONS_PATH } from '../lib/chatRoutes'

/** OAuth callback landing — canonical URL is `/chat/integrations`. */
export function IntegrationsSettingsPage() {
  const [searchParams] = useSearchParams()
  const qs = searchParams.toString()
  return <Navigate to={qs ? `${CHAT_INTEGRATIONS_PATH}?${qs}` : CHAT_INTEGRATIONS_PATH} replace />
}
