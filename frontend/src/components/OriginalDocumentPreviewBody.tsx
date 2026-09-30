import type { ArtifactSpec } from '../types/artifact'
import { isUdocSupportedDocument } from '../lib/udocPreview'
import { UdocDocumentViewerPane } from './UdocDocumentViewerPane'

type Props = {
  spec: ArtifactSpec
  filename: string
  mimeType?: string | null
  format?: string | null
  /** Required for plain-text originals (udoc does not render text/*). */
  inlineTextUrl?: string | null
}

/** Hub/Documents Original tab body: udoc for supported binaries, iframe for text/*. */
export function OriginalDocumentPreviewBody({
  spec,
  filename,
  mimeType,
  format,
  inlineTextUrl,
}: Props) {
  if (isUdocSupportedDocument(filename, mimeType, format)) {
    return <UdocDocumentViewerPane spec={spec} containerClassName="documents-preview-udoc" />
  }

  const mime = (mimeType ?? '').trim().toLowerCase()
  if (mime.startsWith('text/') && inlineTextUrl) {
    return <iframe className="documents-preview-frame" src={inlineTextUrl} title={filename} />
  }

  return null
}
