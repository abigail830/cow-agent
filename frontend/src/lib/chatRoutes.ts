/** Agent-scoped workspace routes under `/chat/:agentId`. */

export type ChatWorkspaceView = 'chat' | 'documents' | 'integrations' | 'hub'

const LAST_AGENT_STORAGE_KEY = 'agent-platform:last-agent-id'

export function readLastAgentId(): string | null {
  try {
    return localStorage.getItem(LAST_AGENT_STORAGE_KEY)
  } catch {
    return null
  }
}

export function writeLastAgentId(agentId: string): void {
  try {
    localStorage.setItem(LAST_AGENT_STORAGE_KEY, agentId)
  } catch {
    /* ignore */
  }
}

export function agentChatPath(agentId: string): string {
  return `/chat/${encodeURIComponent(agentId)}`
}

export function agentDocumentsPath(agentId: string): string {
  return `${agentChatPath(agentId)}/documents`
}

export function agentIntegrationsPath(agentId: string): string {
  return `${agentChatPath(agentId)}/integrations`
}

export function agentHubPath(agentId: string): string {
  return `${agentChatPath(agentId)}/hub`
}

export const HUB_TARGET_CHAT_STORAGE_KEY = 'document-hub:target-chat-id'

export type ParsedChatRoute = {
  agentId: string | null
  view: ChatWorkspaceView
}

/** @deprecated Use parseChatRoute; kept for call sites that only need the view. */
export function chatWorkspaceView(pathname: string): ChatWorkspaceView {
  return parseChatRoute(pathname).view
}

/**
 * Parses `/chat/:agentId`, sub-routes, and legacy global `/chat`, `/chat/documents`, etc.
 */
export function parseChatRoute(pathname: string): ParsedChatRoute {
  const path = pathname.replace(/\/$/, '') || '/'

  if (path === '/chat/documents') {
    return { agentId: null, view: 'documents' }
  }
  if (path === '/chat/integrations') {
    return { agentId: null, view: 'integrations' }
  }
  if (path === '/chat/hub') {
    return { agentId: null, view: 'hub' }
  }
  if (path === '/chat') {
    return { agentId: null, view: 'chat' }
  }

  const match = path.match(/^\/chat\/([^/]+)(?:\/(documents|integrations|hub))?$/)
  if (!match) {
    return { agentId: null, view: 'chat' }
  }

  const agentId = decodeURIComponent(match[1])
  const sub = match[2]
  if (sub === 'documents') return { agentId, view: 'documents' }
  if (sub === 'integrations') return { agentId, view: 'integrations' }
  if (sub === 'hub') return { agentId, view: 'hub' }
  return { agentId, view: 'chat' }
}

/** Resolve legacy global workspace URLs to an agent-scoped path when possible. */
export function resolveLegacyChatPath(
  view: ChatWorkspaceView,
  agentId: string | null,
): string | null {
  const id = agentId ?? readLastAgentId()
  if (!id) return null
  if (view === 'documents') return agentDocumentsPath(id)
  if (view === 'integrations') return agentIntegrationsPath(id)
  if (view === 'hub') return agentHubPath(id)
  return agentChatPath(id)
}

/** @deprecated Use agentDocumentsPath(agentId) */
export const CHAT_DOCUMENTS_PATH = '/chat/documents'

/** @deprecated Use agentIntegrationsPath(agentId) */
export const CHAT_INTEGRATIONS_PATH = '/chat/integrations'

/** @deprecated Use agentChatPath(agentId) */
export const CHAT_HOME_PATH = '/chat'
