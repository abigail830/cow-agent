import type { ArtifactSpec } from '../types/artifact'
import { DiagramArtifactCard } from './DiagramArtifactCard'
import { SlideDeckArtifactCard } from './SlideDeckArtifactCard'
import { InlineDownloadArtifactCard } from './InlineDownloadArtifactCard'
import {
  isAudioTranscriptArtifact,
  isContentDocumentArtifact,
  isDiagramArtifact,
  isInlineDownloadArtifact,
  isSlideDeckArtifact,
} from '../lib/artifactKinds'
import { AudioTranscriptArtifactCard } from './AudioTranscriptArtifactCard'

type Props = {
  spec: ArtifactSpec
  expanded?: boolean
  onExpand?: (spec: ArtifactSpec) => void
  onViewParsePipeline?: (attachmentId: string) => void
  onRetryAudioTranscript?: (attachmentId: string) => Promise<void>
}

export function ArtifactBubble({
  spec,
  expanded = false,
  onExpand,
  onViewParsePipeline,
  onRetryAudioTranscript,
}: Props) {
  if (isAudioTranscriptArtifact(spec)) {
    return (
      <AudioTranscriptArtifactCard
        spec={spec}
        expanded={expanded}
        onExpand={onExpand}
        onViewPipeline={onViewParsePipeline}
        onRetry={onRetryAudioTranscript}
      />
    )
  }
  if (isDiagramArtifact(spec)) {
    return <DiagramArtifactCard spec={spec} expanded={expanded} onExpand={onExpand} />
  }

  if (isSlideDeckArtifact(spec)) {
    return <SlideDeckArtifactCard spec={spec} expanded={expanded} onExpand={onExpand} />
  }

  if (isContentDocumentArtifact(spec) || isInlineDownloadArtifact(spec)) {
    return (
      <InlineDownloadArtifactCard
        spec={spec}
        expanded={expanded}
        onExpand={onExpand}
      />
    )
  }

  if (spec.kind === 'proposal_preview') {
    return <InlineDownloadArtifactCard spec={spec} showDownload={false} />
  }

  return <InlineDownloadArtifactCard spec={spec} />
}
