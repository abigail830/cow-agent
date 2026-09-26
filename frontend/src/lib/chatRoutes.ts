/** Workspace sub-routes under the chat shell (sidebar + main). */
export const CHAT_HOME_PATH = '/chat'
export const CHAT_DOCUMENTS_PATH = '/chat/documents'
export const CHAT_INTEGRATIONS_PATH = '/chat/integrations'

export type ChatWorkspaceView = 'chat' | 'documents' | 'integrations'

export function chatWorkspaceView(pathname: string): ChatWorkspaceView {
  if (pathname === CHAT_DOCUMENTS_PATH || pathname.endsWith('/chat/documents')) {
    return 'documents'
  }
  if (pathname === CHAT_INTEGRATIONS_PATH || pathname.endsWith('/chat/integrations')) {
    return 'integrations'
  }
  return 'chat'
}
