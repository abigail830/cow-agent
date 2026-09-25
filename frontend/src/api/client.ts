import type {
  Agent,
  Chat,
  ChatAttachment,
  DocumentListResult,
  ChatForkResult,
  ChatSummary,
  ChatTimeline,
  ContextUsage,
  KnowledgeBaseListResult,
  MemoryDocument,
  Message,
  ModelOption,
  StreamEvent,
  User,
  IntegrationStatus,
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
    if (text) {
      try {
        const parsed = JSON.parse(text) as { detail?: unknown }
        if (typeof parsed.detail === 'string') {
          throw new Error(parsed.detail)
        }
      } catch (error) {
        if (error instanceof Error && error.message !== text) {
          throw error
        }
      }
      throw new Error(text)
    }
    throw new Error(res.statusText)
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
  listIntegrations: () => request<IntegrationStatus[]>('/integrations'),
  connectIntegration: (provider: string) =>
    request<{ authorize_url: string }>(`/integrations/${encodeURIComponent(provider)}/connect`, {
      method: 'POST',
    }),
  disconnectIntegration: (provider: string) =>
    request<{ disconnected: boolean }>(`/integrations/${encodeURIComponent(provider)}/disconnect`, {
      method: 'POST',
    }),
  saveIntegrationCredentials: (provider: string, apiKey: string) =>
    request<{ connected: boolean; account_label?: string | null }>(
      `/integrations/${encodeURIComponent(provider)}/credentials`,
      {
        method: 'PUT',
        body: JSON.stringify({ api_key: apiKey }),
      },
    ),
  getCurrentUser: () => request<User>('/auth/me'),
  listAgents: () => request<Agent[]>('/agents'),
  getAgent: (id: string) => request<Agent>(`/agents/${id}`),
  listModels: () => request<ModelOption[]>('/models'),
  patchAgentModelSelection: (agentId: string, modelId: string) =>
    request<Agent>(`/agents/${agentId}/model-selection`, {
      method: 'PATCH',
      body: JSON.stringify({ model_id: modelId }),
    }),
  listAgentKnowledgeBases: (agentId: string) =>
    request<KnowledgeBaseListResult>(`/agents/${encodeURIComponent(agentId)}/knowledge-bases`),
  getAgentKbPreferences: (agentId: string) =>
    request<{ disabled_kb_ids: string[] }>(`/agents/${encodeURIComponent(agentId)}/kb-preferences`),
  putAgentKbPreferences: (agentId: string, disabledKbIds: string[]) =>
    request<{ disabled_kb_ids: string[] }>(`/agents/${encodeURIComponent(agentId)}/kb-preferences`, {
      method: 'PUT',
      body: JSON.stringify({ disabled_kb_ids: disabledKbIds }),
    }),

  listChats: (agentId: string) =>
    request<ChatSummary[]>(`/chats?agent_id=${encodeURIComponent(agentId)}`),
  createChat: (agentId: string) =>
    request<Chat>('/chats', {
      method: 'POST',
      body: JSON.stringify({ agent_id: agentId }),
    }),
  warmupChat: (chatId: string) =>
    request<void>(`/chats/${encodeURIComponent(chatId)}/warmup`, {
      method: 'POST',
    }),
  forkChat: (chatId: string) =>
    request<ChatForkResult>(`/chats/${encodeURIComponent(chatId)}/fork`, {
      method: 'POST',
    }),
  deleteChat: (chatId: string) =>
    request<void>(`/chats/${encodeURIComponent(chatId)}`, {
      method: 'DELETE',
    }),
  listMessages: (chatId: string) => request<Message[]>(`/chats/${chatId}/messages`),
  listTimeline: (chatId: string) => request<ChatTimeline>(`/chats/${chatId}/timeline`),
  getContextUsage: (chatId: string) =>
    request<ContextUsage>(`/chats/${encodeURIComponent(chatId)}/context-usage`),

  getAttachmentConfig: () =>
    request<AttachmentLimits>('/config/attachments').catch(() => DEFAULT_ATTACHMENT_LIMITS),

  listChatAttachments: (chatId: string) =>
    request<ChatAttachment[]>(`/chats/${chatId}/attachments`),

  deleteChatAttachment: async (chatId: string, attachmentId: string): Promise<void> => {
    const res = await fetch(`${API}/chats/${chatId}/attachments/${attachmentId}`, {
      ...defaultFetchInit,
      method: 'DELETE',
    })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(text || res.statusText)
    }
  },

  retryAttachmentParse: (chatId: string, attachmentId: string) =>
    request<ChatAttachment>(`/chats/${chatId}/attachments/${attachmentId}/parse/retry`, {
      method: 'POST',
    }),

  getAudioCaptureUploadConfig: (chatId: string) =>
    request<{
      mode: 'blob' | 'multipart'
      max_total_bytes: number
      blob_upload_url?: string | null
      blob_access?: string | null
    }>(`/chats/${chatId}/captures/upload-config`),

  submitAudioCaptureMultipart: async (chatId: string, files: File[], title?: string | null) => {
    const form = new FormData()
    for (const file of files) {
      form.append('files', file)
    }
    if (title?.trim()) form.append('title', title.trim())
    const res = await fetch(`${API}/chats/${chatId}/captures`, {
      ...defaultFetchInit,
      method: 'POST',
      body: form,
    })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(text || res.statusText)
    }
    return res.json()
  },

  submitAudioCapture: async (chatId: string, files: File[], title?: string | null) => {
    const config = await api.getAudioCaptureUploadConfig(chatId)
    if (config.mode === 'multipart') {
      return api.submitAudioCaptureMultipart(chatId, files, title)
    }

    const { upload } = await import('@vercel/blob/client')
    const access = config.blob_access === 'public' ? 'public' : 'private'
    const handleUploadUrl = config.blob_upload_url?.startsWith('http')
      ? config.blob_upload_url
      : `${API}${config.blob_upload_url ?? `/chats/${chatId}/captures/blob-upload`}`

    const parts: Array<{
      attachment_id: string
      sort_order: number
      filename: string
      mime_type: string
      size_bytes: number
    }> = []

    for (let sortOrder = 0; sortOrder < files.length; sortOrder += 1) {
      const file = files[sortOrder]
      if (!file) continue
      const attachmentId = crypto.randomUUID()
      const pathname = `chat-attachments/${chatId}/${attachmentId}`
      await upload(pathname, file, {
        access,
        handleUploadUrl,
        clientPayload: JSON.stringify({ chat_id: chatId, attachment_id: attachmentId }),
        contentType: file.type || 'application/octet-stream',
        multipart: file.size > 5 * 1024 * 1024,
      })
      parts.push({
        attachment_id: attachmentId,
        sort_order: sortOrder,
        filename: file.name,
        mime_type: file.type || 'application/octet-stream',
        size_bytes: file.size,
      })
    }

    return request(`/chats/${chatId}/captures/submit`, {
      method: 'POST',
      body: JSON.stringify({
        title: title?.trim() || null,
        parts,
      }),
    })
  },

  uploadChatAttachment: async (
    chatId: string,
    file: File,
  ): Promise<ChatAttachment> => {
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

  listDocuments: (params?: {
    q?: string
    parse_status?: string
    mime_type?: string
    agent_id?: string
    source?: 'all' | 'attachment' | 'artifact'
    artifact_kind?: string
    limit?: number
    offset?: number
  }) => {
    const search = new URLSearchParams()
    if (params?.q?.trim()) search.set('q', params.q.trim())
    if (params?.parse_status) search.set('parse_status', params.parse_status)
    if (params?.mime_type) search.set('mime_type', params.mime_type)
    if (params?.agent_id) search.set('agent_id', params.agent_id)
    if (params?.source) search.set('source', params.source)
    if (params?.artifact_kind) search.set('artifact_kind', params.artifact_kind)
    if (params?.limit != null) search.set('limit', String(params.limit))
    if (params?.offset != null) search.set('offset', String(params.offset))
    const query = search.toString()
    return request<DocumentListResult>(`/documents${query ? `?${query}` : ''}`)
  },

  fetchAttachmentParsedText: async (
    chatId: string,
    attachmentId: string,
    artifactKey: 'content_md' | 'meta_json' | 'pageindex_json',
  ): Promise<string> => {
    const res = await fetch(`${API}/chats/${chatId}/attachments/${attachmentId}/parsed/${artifactKey}`, {
      ...defaultFetchInit,
    })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(text || res.statusText)
    }
    return res.text()
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
    body: JSON.stringify({
      content,
      attachment_ids: attachmentIds,
    }),
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
