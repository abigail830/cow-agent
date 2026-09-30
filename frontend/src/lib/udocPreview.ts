import type { ArtifactKind, ArtifactSpec } from '../types/artifact'

/** Extensions aligned with @docmentis/udoc-viewer supported formats. */
const UDOC_EXTENSIONS = new Set([
  '.pdf',
  '.docx',
  '.pptx',
  '.xlsx',
  '.csv',
  '.svg',
  '.wmf',
  '.emf',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.webp',
  '.bmp',
  '.tif',
  '.tiff',
  '.ico',
  '.tga',
  '.ppm',
  '.pgm',
  '.pbm',
  '.hdr',
  '.exr',
  '.qoi',
])

const UDOC_EXACT_MIMES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/csv',
  'image/svg+xml',
])

/** When filename has no extension, infer from artifact format or MIME. */
const UDOC_FORMAT_TO_EXT: Record<string, string> = {
  pdf: '.pdf',
  docx: '.docx',
  pptx: '.pptx',
  xlsx: '.xlsx',
  csv: '.csv',
  svg: '.svg',
}

const UDOC_MIME_TO_EXT: Record<string, string> = {
  'application/pdf': '.pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
  'text/csv': '.csv',
  'image/svg+xml': '.svg',
}

/** Legacy OLE binaries — udoc only supports OOXML (.xlsx etc.), not .xls/.doc/.ppt. */
const LEGACY_OFFICE_EXTENSIONS = new Set(['.xls', '.doc', '.ppt'])

const UDOC_PREVIEW_ARTIFACT_KINDS = new Set<ArtifactKind>([
  'content_document',
  'proposal_word',
  'proposal_document',
])

const UDOC_FORMAT_BY_EXT: Record<string, ArtifactSpec['format']> = {
  '.pdf': 'pdf',
  '.docx': 'docx',
  '.pptx': 'pptx',
  '.md': 'markdown',
  '.markdown': 'markdown',
  '.svg': 'svg',
}

function fileExtension(filename: string): string {
  const lower = filename.trim().toLowerCase()
  const dot = lower.lastIndexOf('.')
  if (dot <= 0) return ''
  return lower.slice(dot)
}

/** Filename with synthetic extension when only format/MIME hints exist. */
export function effectiveFilenameForUdoc(
  filename: string,
  mimeType?: string | null,
  format?: string | null,
): string {
  const trimmed = filename.trim()
  if (fileExtension(trimmed)) return trimmed

  const fmt = (format ?? '').trim().toLowerCase()
  if (fmt && UDOC_FORMAT_TO_EXT[fmt]) {
    return `${trimmed}${UDOC_FORMAT_TO_EXT[fmt]}`
  }

  const mime = (mimeType ?? '').trim().toLowerCase()
  if (mime.startsWith('image/')) return `${trimmed || 'image'}.png`

  const fromMime = UDOC_MIME_TO_EXT[mime]
  if (fromMime) return `${trimmed || 'document'}${fromMime}`

  return trimmed
}

export function isMarkdownFilenameOrFormat(filename: string, format?: string | null): boolean {
  const fmt = (format ?? '').toLowerCase()
  if (fmt === 'markdown' || fmt === 'md') return true
  const ext = fileExtension(filename)
  return ext === '.md' || ext === '.markdown'
}

/** True when the original bytes should render in udoc (WASM viewer). */
export function isLegacyOfficeBinary(filename: string, mimeType?: string | null): boolean {
  const ext = fileExtension(filename)
  if (ext && LEGACY_OFFICE_EXTENSIONS.has(ext)) return true
  const mime = (mimeType ?? '').trim().toLowerCase()
  return mime === 'application/vnd.ms-excel' || mime === 'application/msword' || mime === 'application/vnd.ms-powerpoint'
}

export function isUdocSupportedDocument(
  filename: string,
  mimeType?: string | null,
  format?: string | null,
): boolean {
  if (isLegacyOfficeBinary(filename, mimeType)) return false
  const effective = effectiveFilenameForUdoc(filename, mimeType, format)
  const ext = fileExtension(effective)
  if (ext && UDOC_EXTENSIONS.has(ext)) return true

  const mime = (mimeType ?? '').trim().toLowerCase()
  if (!mime) return false
  if (UDOC_EXACT_MIMES.has(mime)) return true
  if (mime.startsWith('image/')) return true
  return false
}

/** Original tab in Document Hub / Documents: udoc or plain-text iframe. */
export function isOriginalInlinePreviewable(
  filename: string,
  mimeType?: string | null,
  format?: string | null,
): boolean {
  const mime = (mimeType ?? '').trim().toLowerCase()
  if (isUdocSupportedDocument(filename, mimeType, format)) return true
  return mime.startsWith('text/')
}

/** Chat / Documents artifact side panel — same udoc gate as Hub originals. */
export function isUdocPreviewableArtifact(spec: ArtifactSpec): boolean {
  if (!spec.download_url?.trim()) return false
  if (!UDOC_PREVIEW_ARTIFACT_KINDS.has(spec.kind)) return false
  if (isMarkdownFilenameOrFormat(spec.filename, spec.format)) return false
  return isUdocSupportedDocument(spec.filename, spec.mime_type, spec.format)
}

export function udocArtifactFormatFromFilename(
  filename: string,
  formatHint?: string | null,
): ArtifactSpec['format'] {
  const ext = fileExtension(effectiveFilenameForUdoc(filename, null, formatHint))
  if (ext && UDOC_FORMAT_BY_EXT[ext]) return UDOC_FORMAT_BY_EXT[ext]
  const fmt = (formatHint ?? '').toLowerCase()
  if (fmt === 'pdf' || fmt === 'docx' || fmt === 'pptx' || fmt === 'markdown' || fmt === 'svg') {
    return fmt as ArtifactSpec['format']
  }
  return 'pdf'
}

export function buildUdocArtifactSpec(params: {
  kind?: ArtifactSpec['kind']
  title: string
  filename: string
  artifactId: string
  downloadUrl: string
  format?: string | null
  mimeType?: string | null
}): ArtifactSpec {
  return {
    kind: params.kind ?? 'content_document',
    title: params.title,
    format: udocArtifactFormatFromFilename(params.filename, params.format),
    content: '',
    filename: params.filename,
    artifact_id: params.artifactId,
    download_url: params.downloadUrl,
    mime_type: params.mimeType ?? null,
  }
}
