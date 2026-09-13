import type { ArtifactSpec } from '../types/artifact'
import { DiagramArtifactCard } from './DiagramArtifactCard'
import { SlideDeckArtifactCard } from './SlideDeckArtifactCard'
import { InlineDownloadArtifactCard } from './InlineDownloadArtifactCard'
import {
  isContentDocumentArtifact,
  isDiagramArtifact,
  isInlineDownloadArtifact,
  isSlideDeckArtifact,
} from '../lib/artifactKinds'

type Props = {
  spec: ArtifactSpec
  expanded?: boolean
  onExpand?: (spec: ArtifactSpec) => void
}

export function ArtifactBubble({ spec, expanded = false, onExpand }: Props) {
  if (isDiagramArtifact(spec)) {
    return <DiagramArtifactCard spec={spec} expanded={expanded} onExpand={onExpand} />
  }

  if (isSlideDeckArtifact(spec)) {
    return <SlideDeckArtifactCard spec={spec} expanded={expanded} onExpand={onExpand} />
  }

  if (isContentDocumentArtifact(spec) || isInlineDownloadArtifact(spec)) {
    return <InlineDownloadArtifactCard spec={spec} />
  }

  if (spec.kind === 'proposal_preview') {
    return <InlineDownloadArtifactCard spec={spec} showDownload={false} />
  }

  return <InlineDownloadArtifactCard spec={spec} />
}
