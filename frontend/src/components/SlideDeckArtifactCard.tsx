import type { ArtifactSpec } from '../types/artifact'
import { SlideDeckArtifactActions } from './SlideDeckArtifactActions'

type Props = {
  spec: ArtifactSpec
  expanded?: boolean
  createdAt?: string | null
  onExpand?: (spec: ArtifactSpec) => void
}

function formatCreatedLabel(value: string | null | undefined): string | null {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `Created ${month}-${day} ${hours}:${minutes}`
}

export function SlideDeckArtifactCard({ spec, expanded = false, createdAt, onExpand }: Props) {
  const createdLabel = formatCreatedLabel(createdAt)

  return (
    <div
      className={`slide-deck-artifact-card${expanded ? ' slide-deck-artifact-card-expanded' : ''}`}
      aria-label={spec.title}
    >
      <div className="slide-deck-artifact-card-top">
        <div className="slide-deck-artifact-icon" aria-hidden>
          P
        </div>
        <div className="slide-deck-artifact-meta">
          <h4 className="slide-deck-artifact-title" title={spec.title}>
            {spec.title}
          </h4>
          {createdLabel ? <p className="slide-deck-artifact-created">{createdLabel}</p> : null}
        </div>
      </div>
      <SlideDeckArtifactActions
        spec={spec}
        variant="card"
        expanded={expanded}
        onExpand={onExpand}
      />
    </div>
  )
}
