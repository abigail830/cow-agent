import type { ArtifactSpec } from '../types/artifact'
import { UDocArtifactViewer } from './UDocArtifactViewer'

type Props = {
  spec: ArtifactSpec
  /** Wrapper around the viewer (e.g. documents-preview-udoc). Omit for artifact side panel. */
  containerClassName?: string
  initialPage?: number | null
}

/** Shared udoc mount (eager — WASM init is warmed via warmUdocClient). */
export function UdocDocumentViewerPane({
  spec,
  containerClassName,
  initialPage = null,
}: Props) {
  const viewer = <UDocArtifactViewer spec={spec} initialPage={initialPage} />

  if (containerClassName) {
    return <div className={containerClassName}>{viewer}</div>
  }

  return viewer
}
