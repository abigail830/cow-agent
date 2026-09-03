import type {
  Agent,
  Chat,
  ChatAttachment,
  ChatSummary,
  MemoryDocument,
  Message,
  StreamEvent,
  User,
} from '../types'
import type { AttachmentLimits } from '../lib/attachments'
import { DEFAULT_ATTACHMENT_LIMITS } from '../lib/attachments'
import type { ProposalExportResponse, ProposalPreview } from '../types/proposalPreview'
import type { ProposalDraftResponse } from '../types/proposalDraft'
import type {
  FulfillmentFormActionResponse,
  FulfillmentFormsResponse,
} from '../types/fulfillmentForms'
import { API_V1 } from '../lib/apiBase'

const API = API_V1

const defaultFetchInit: RequestInit = {
  credentials: 'include',
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...defaultFetchInit,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  authMe: () => request<User>('/auth/me'),
  login: (email: string, password: string) =>
    request<User>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  logout: () =>
    request<void>('/auth/logout', {
      method: 'POST',
    }),
  getCurrentUser: () => request<User>('/auth/me'),
  listAgents: () => request<Agent[]>('/agents'),
  getAgent: (id: string) => request<Agent>(`/agents/${id}`),

  listChats: (agentId: string) =>
    request<ChatSummary[]>(`/chats?agent_id=${encodeURIComponent(agentId)}`),
  createChat: (agentId: string) =>
    request<Chat>('/chats', {
      method: 'POST',
      body: JSON.stringify({ agent_id: agentId }),
    }),
  listMessages: (chatId: string) => request<Message[]>(`/chats/${chatId}/messages`),

  getAttachmentConfig: () =>
    request<AttachmentLimits>('/config/attachments').catch(() => DEFAULT_ATTACHMENT_LIMITS),

  uploadChatAttachment: async (chatId: string, file: File): Promise<ChatAttachment> => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${API}/chats/${chatId}/attachments`, {
      ...defaultFetchInit,
      method: 'POST',
      body: form,
    })
    if (!res.ok) {
      throw new Error(await res.text())
    }
    return res.json() as Promise<ChatAttachment>
  },

  getProposalPreview: (chatId: string, draft = true) =>
    request<ProposalPreview>(
      `/chats/${chatId}/proposal/preview?draft=${draft ? 'true' : 'false'}`,
    ),

  getProposalDraft: (chatId: string) =>
    request<ProposalDraftResponse>(`/chats/${chatId}/proposal/draft`),

  exportProposalWord: (chatId: string, force = false) =>
    request<ProposalExportResponse>(`/chats/${chatId}/proposal/export`, {
      method: 'POST',
      body: JSON.stringify({ format: 'docx', force }),
    }),

  getFulfillmentForms: (chatId: string) =>
    request<FulfillmentFormsResponse>(`/chats/${chatId}/fulfillment/forms`),

  patchFulfillmentForm: (chatId: string, formId: string, payload: Record<string, unknown>) =>
    request<FulfillmentFormActionResponse>(`/chats/${chatId}/fulfillment/forms/${formId}`, {
      method: 'PATCH',
      body: JSON.stringify({ payload }),
    }),

  confirmFulfillmentForm: (chatId: string, formId: string) =>
    request<FulfillmentFormActionResponse>(`/chats/${chatId}/fulfillment/forms/${formId}/confirm`, {
      method: 'POST',
    }),

  rejectFulfillmentForm: (chatId: string, formId: string) =>
    request<FulfillmentFormActionResponse>(`/chats/${chatId}/fulfillment/forms/${formId}/reject`, {
      method: 'POST',
    }),

  cancelRun: (runId: string) =>
    request<{ run_id: string; chat_id: string; status: string }>(`/runs/${runId}/cancel`, {
      method: 'POST',
    }),

  getUserMemory: () => request<MemoryDocument>('/memories/user'),
  getAgentMemory: (agentId: string) => request<MemoryDocument>(`/memories/agents/${agentId}`),
  replaceUserMemory: (content: string) =>
    request<MemoryDocument>('/memories/user', {
      method: 'PUT',
      body: JSON.stringify({ content }),
    }),
  replaceAgentMemory: (agentId: string, content: string) =>
    request<MemoryDocument>(`/memories/agents/${agentId}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    }),
  appendMemory: (body: {
    scope: string
    agent_id?: string
    lines: string[]
    is_constraint?: boolean
    source?: string
  }) =>
    request<MemoryDocument>('/memories/append', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  removeMemory: (body: {
    scope: string
    agent_id?: string
    match: string
    also_search_user?: boolean
  }) =>
    request<MemoryDocument>('/memories/remove', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}

export async function streamChat(
  chatId: string,
  content: string,
  onEvent: (ev: StreamEvent) => void,
  signal?: AbortSignal,
  attachmentIds: string[] = [],
): Promise<void> {
  const res = await fetch(`${API}/chats/${chatId}/stream`, {
    ...defaultFetchInit,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, attachment_ids: attachmentIds }),
    signal,
  })
  if (!res.ok || !res.body) {
    throw new Error(await res.text())
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      const lines = part.split('\n')
      let event = 'message'
      let data = ''
      for (const line of lines) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        if (line.startsWith('data:')) data = line.slice(5).trim()
      }
      if (data) {
        onEvent({ event, data: JSON.parse(data) as Record<string, unknown> })
      }
    }
  }
}
