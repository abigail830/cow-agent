import type { ArtifactSpec } from '../types/artifact'
import { artifactCardSubtitle } from '../lib/artifactKinds'
import { DiagramArtifactActions } from './DiagramArtifactActions'

type Props = {
  spec: ArtifactSpec
  expanded?: boolean
  onExpand?: (spec: ArtifactSpec) => void
}

function DiagramIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <path d="M14 17h7" />
      <path d="M17.5 14v7" />
    </svg>
  )
}

export function DiagramArtifactCard({ spec, expanded = false, onExpand }: Props) {
  return (
    <div
      className={`artifact-inline-card diagram-artifact-card${expanded ? ' artifact-inline-card-expanded' : ''}`}
      aria-label={spec.title}
    >
      <div className="artifact-inline-card-icon diagram-artifact-icon" aria-hidden>
        <DiagramIcon />
      </div>
      <div className="artifact-inline-card-main">
        <h4 className="artifact-inline-card-title" title={spec.title}>
          {spec.title}
        </h4>
        <p className="artifact-inline-card-subtitle">{artifactCardSubtitle(spec)}</p>
      </div>
      <DiagramArtifactActions
        spec={spec}
        variant="card"
        expanded={expanded}
        onExpand={onExpand}
      />
    </div>
  )
}
