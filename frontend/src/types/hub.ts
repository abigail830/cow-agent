export type HubFolder = {
  id: string
  parent_id: string | null
  name: string
  sort_order: number
}

export type HubItem = {
  id: string
  folder_id: string
  item_kind: string
  filename: string
  mime_type: string
  size_bytes: number
  parse_status: string
  parse_pipeline_id?: string | null
  parse_job_id?: string | null
  parse_error_message?: string | null
  parse_stage_snapshot?: Record<string, unknown> | null
  content_hash?: string | null
  duplicate_of_existing?: boolean
  file_count?: number
  parsed_artifacts?: {
    content_md: boolean
    meta_json: boolean
    pageindex_json: boolean
  }
}

export type ChatDocumentImport = {
  id: string
  source: 'chat_attachment' | 'hub_item'
  ref_id: string
  filename?: string | null
  parse_status?: string | null
  imported_at?: string | null
}
