import type { ArtifactSpec } from '../types/artifact'
import { DiagramArtifactCard } from './DiagramArtifactCard'
import { SlideDeckArtifactCard } from './SlideDeckArtifactCard'
import { MarkdownContent } from './MarkdownContent'
import { isDiagramArtifact, isSlideDeckArtifact } from '../lib/artifactKinds'

type Props = {
  spec: ArtifactSpec
  expanded?: boolean
  createdAt?: string | null
  onExpand?: (spec: ArtifactSpec) => void
}

const PREVIEW_MAX_HEIGHT = 280

export function ArtifactBubble({ spec, expanded = false, createdAt, onExpand }: Props) {
  if (isDiagramArtifact(spec)) {
    return <DiagramArtifactCard spec={spec} expanded={expanded} onExpand={onExpand} />
  }

  if (isSlideDeckArtifact(spec)) {
    return (
      <SlideDeckArtifactCard
        spec={spec}
        expanded={expanded}
        createdAt={createdAt}
        onExpand={onExpand}
      />
    )
  }

  const isDocument = spec.kind === 'proposal_document'

  return (
    <div className={`viz-widget-frame artifact-widget-frame${expanded ? ' artifact-widget-frame-expanded' : ''}`}>
      <div className="viz-bubble-header">
        <h4 className="viz-bubble-title">{spec.title}</h4>
        <div className="viz-widget-toolbar">
          {isDocument && <span className="viz-bubble-badge">Download ready</span>}
        </div>
      </div>
      <div className="viz-widget-body">
        <div className="artifact-markdown-wrap" style={{ maxHeight: PREVIEW_MAX_HEIGHT }}>
          <MarkdownContent
            content={spec.content}
            className="markdown-body artifact-markdown-body"
            allowHtml
          />
        </div>
      </div>
    </div>
  )
}
