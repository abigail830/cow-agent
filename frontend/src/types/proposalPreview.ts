export type ProposalExportWordStatus = {
  available: boolean
  reason?: string | null
  template_file?: string | null
}

export type ProposalExportFormats = {
  word: ProposalExportWordStatus
}

export type ProposalPreviewStatus = 'ok' | 'empty' | 'blocked' | 'error'

export type ProposalCompleteness = {
  missing_required: string[]
  ready_to_preview: boolean
  ready_to_generate: boolean
}

export type ProposalPreview = {
  chat_id?: string
  status: ProposalPreviewStatus
  title: string
  markdown: string
  filename: string
  state_fingerprint: string
  message?: string | null
  completeness: ProposalCompleteness
  export?: ProposalExportFormats
}

export type ProposalExportResponse = {
  status: string
  format: 'docx'
  artifact_id: string
  filename: string
  download_url?: string | null
  title: string
  state_fingerprint: string
  missing_required?: string[]
}
