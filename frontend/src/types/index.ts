export interface User {
  id: string
  email: string
  name: string | null
}

export interface Agent {
  id: string
  slug: string | null
  name: string
  description: string | null
  model_provider: string
  model_name: string
}

export interface Chat {
  id: string
  user_id: string
  agent_id: string
  title: string | null
}

export interface ChatSummary {
  id: string
  agent_id: string
  title: string | null
  created_at: string | null
  updated_at: string | null
}

export interface ChatAttachment {
  id: string
  chat_id: string
  filename: string
  mime_type: string
  size_bytes: number
  provider: string
  provider_file_id: string
  created_at: string | null
}

export interface MessageAttachmentMeta {
  id: string
  filename: string
  mime_type: string
  size_bytes: number
  provider: string
  provider_file_id: string
}

export interface Message {
  id: string
  chat_id: string
  role: string
  message_type: string
  content: string | null
  metadata: Record<string, unknown>
  parent_id: string | null
  sequence: number
  created_at: string | null
}

export interface StreamEvent {
  event: string
  data: Record<string, unknown>
}

export interface MemoryBullet {
  prefix: string
  text: string
  line: string
  kind: string
}

export interface MemoryDocument {
  scope: string
  agent_id: string | null
  content: string
  revision: number
  bullets: MemoryBullet[]
  updated_at: string | null
}
