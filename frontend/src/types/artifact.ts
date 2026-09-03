export type ArtifactKind =
  | 'proposal_preview'
  | 'proposal_document'
  | 'proposal_word'
  | 'diagram_svg'
  | 'slide_deck'
export type ArtifactFormat = 'markdown' | 'docx' | 'svg' | 'slidev' | 'html' | 'pdf'

export type ArtifactSpec = {
  kind: ArtifactKind
  title: string
  format: ArtifactFormat
  content: string
  filename: string
  artifact_id: string
  download_url?: string | null
  png_download_url?: string | null
  png_filename?: string | null
  pdf_download_url?: string | null
  pdf_filename?: string | null
  preview_url?: string | null
  preview_truncated?: boolean
  source?: string | null
}
