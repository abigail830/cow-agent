import { Navigate, useSearchParams } from 'react-router-dom'
import { CHAT_DOCUMENTS_PATH } from '../lib/chatRoutes'

/** OAuth / bookmark compatibility — canonical URL is `/chat/documents`. */
export function DocumentsSettingsPage() {
  const [searchParams] = useSearchParams()
  const qs = searchParams.toString()
  return <Navigate to={qs ? `${CHAT_DOCUMENTS_PATH}?${qs}` : CHAT_DOCUMENTS_PATH} replace />
}
