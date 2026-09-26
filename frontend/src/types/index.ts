export interface User {
  id: string
  email: string
  name: string | null
}

export interface IntegrationStatus {
  provider: string
  display_name: string
  description: string
  auth_kind: 'oauth' | 'api_key'
  configured: boolean
  connected: boolean
  account_label?: string | null
  token_valid: boolean
}

export interface Agent {
  id: string
  slug: string | null
  name: string
  description: string | null
  model_provider: string
  model_name: string
  default_model_id: string | null
  selected_model_id: string | null
  supports_kb_scope?: boolean
}

export interface KnowledgeBaseItem {
  id: string
  name: string
  description?: string | null
  type?: string | null
  item_count?: number | null
  is_configured?: boolean | null
  enabled: boolean
}

export interface KnowledgeBaseListResult {
  connected: boolean
  items: KnowledgeBaseItem[]
  disabled_kb_ids: string[]
  message?: string | null
}

export interface ModelOption {
  id: string
  label: string
  provider: string
  supports_attachments: boolean
  available?: boolean
}

export interface ContextUsage {
  tokens: number
  budget_tokens: number
  percent: number
}

export interface Chat {
  id: string
  user_id: string
  agent_id: string
  title: string | null
}

export interface ChatForkResult extends Chat {
  forked_from: {
    chat_id: string
    title: string | null
  }
}

export interface ChatSummary {
  id: string
  agent_id: string
  title: string | null
  created_at: string | null
  updated_at: string | null
}

export type AttachmentParseStatus = 'pending' | 'running' | 'ready' | 'failed' | 'skipped'

export interface ParseStageSnapshot {
  stage_id?: string | null
  status?: string | null
  started_at?: string | null
  finished_at?: string | null
}

export interface AttachmentParseProgress {
  current_stage?: string | null
  message?: string | null
  stages?: ParseStageSnapshot[] | null
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
  parse_status?: AttachmentParseStatus
  parse_pipeline_id?: string | null
  parse_job_id?: string | null
  parse_error_message?: string | null
  parse_progress?: AttachmentParseProgress | null
  attachment_role?: string | null
  capture_id?: string | null
}

export interface ParsedArtifactsAvailability {
  content_md: boolean
  meta_json: boolean
  pageindex_json: boolean
}

export type DocumentSourceType = 'attachment' | 'artifact'

export interface DocumentItem {
  source_type: DocumentSourceType
  id: string
  chat_id: string
  filename: string
  created_at: string | null
  agent_id: string
  agent_name: string
  agent_slug: string | null
  chat_title: string | null
  mime_type?: string | null
  size_bytes?: number | null
  provider?: string | null
  provider_file_id?: string | null
  parse_status?: AttachmentParseStatus | null
  parse_pipeline_id?: string | null
  parse_job_id?: string | null
  parse_error_message?: string | null
  parse_progress?: AttachmentParseProgress | null
  has_parsed_content?: boolean
  parsed_artifacts?: ParsedArtifactsAvailability
  gist?: string | null
  artifact_id?: string | null
  artifact_kind?: string | null
  artifact_format?: string | null
  artifact_spec?: import('./artifact').ArtifactSpec | null
}

export interface DocumentListResult {
  items: DocumentItem[]
  total: number
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

export interface MafMessageBody {
  type?: string
  role?: string
  message_id?: string
  contents?: Array<Record<string, unknown>>
  additional_properties?: Record<string, unknown>
}

export interface TimelineMessageItem {
  kind: 'message'
  id: string
  sequence: number
  turn_id: string
  message: MafMessageBody
  created_at: string | null
}

export interface TimelineAnnotationItem {
  kind: 'ui_annotation'
  id: string
  sequence: number
  turn_id: string
  annotation: {
    kind: string
    ref: string
    display: Record<string, unknown>
    anchor_message_id?: string | null
  }
  created_at: string | null
}

export type TimelineItem = TimelineMessageItem | TimelineAnnotationItem

export interface ChatRun {
  id: string
  status: string
  error: string | null
  user_message_id: string | null
  model_id: string | null
  started_at: string | null
  finished_at: string | null
}

export interface ChatTimeline {
  chat_id: string
  items: TimelineItem[]
  runs: ChatRun[]
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
