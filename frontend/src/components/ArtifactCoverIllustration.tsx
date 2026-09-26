import type { ReactNode } from 'react'
import type { ArtifactSpec } from '../types/artifact'

export type ArtifactCoverKind =
  | 'word'
  | 'slides'
  | 'web'
  | 'diagram'
  | 'pdf'
  | 'markdown'
  | 'audio'
  | 'generic'

export function resolveArtifactCoverKind(spec: ArtifactSpec): ArtifactCoverKind {
  const format = (spec.format || '').toLowerCase()
  const name = (spec.filename || '').toLowerCase()

  if (spec.kind === 'audio_transcript') return 'audio'
  if (spec.kind === 'diagram_svg' || format === 'svg') return 'diagram'
  if (spec.kind === 'slide_deck') {
    if (format === 'html' || name.endsWith('.html')) return 'web'
    return 'slides'
  }
  if (format === 'docx' || name.endsWith('.docx') || spec.kind === 'proposal_word') return 'word'
  if (format === 'pptx' || name.endsWith('.pptx')) return 'slides'
  if (format === 'html' || name.endsWith('.html')) return 'web'
  if (format === 'pdf' || name.endsWith('.pdf')) return 'pdf'
  if (format === 'markdown' || format === 'md' || name.endsWith('.md')) return 'markdown'
  if (spec.kind.startsWith('proposal_')) return 'word'
  return 'generic'
}

function WordCover() {
  return (
    <svg viewBox="0 0 180 112" aria-hidden="true">
      <path d="M34 28 103 17l39 22-68 12zM34 28v48l40 22V51M74 98l68-14V39" />
      <path className="cover-fill" d="m36 28 67-10 36 21-65 11z" />
      <path d="m49 38 42-7M54 47l31-5M51 61l13 7m19-4 39-8M83 73l38-8" />
      <circle cx="122" cy="28" r="8" />
      <path d="m116 28 5 4 8-10" />
    </svg>
  )
}

function SlidesCover() {
  return (
    <svg viewBox="0 0 180 112" aria-hidden="true">
      <path d="m29 34 111-10v62L29 76zM39 25l111 10v62L39 87z" />
      <rect className="cover-fill" x="48" y="41" width="93" height="49" />
      <path d="M57 52h34M57 60h21M57 77l13-12 10 7 15-16 32 25M112 49v17M106 55h13" />
    </svg>
  )
}

function WebCover() {
  return (
    <svg viewBox="0 0 180 112" aria-hidden="true">
      <path d="M22 23h136v72H22zM22 38h136" />
      <circle cx="32" cy="31" r="2" />
      <circle cx="40" cy="31" r="2" />
      <path className="cover-fill" d="M30 47h39v38H30z" />
      <path d="M78 49h64M78 58h48M78 72h23M108 72h34M78 82h64M42 65l8 7 12-15" />
    </svg>
  )
}

/** Flow / node graph — same line-art language as brand covers. */
function DiagramCover() {
  return (
    <svg viewBox="0 0 180 112" aria-hidden="true">
      <rect className="cover-fill" x="24" y="28" width="44" height="28" rx="4" />
      <rect x="112" y="22" width="44" height="28" rx="4" />
      <rect x="68" y="68" width="44" height="28" rx="4" />
      <path d="M68 42h44M134 50v18M90 68V56" />
      <circle cx="90" cy="56" r="3" />
      <path d="M34 42h-6M146 36h8" />
    </svg>
  )
}

function PdfCover() {
  return (
    <svg viewBox="0 0 180 112" aria-hidden="true">
      <path d="M48 18h62l28 28v52H48z" />
      <path d="M110 18v28h28" />
      <path className="cover-fill" d="M60 58h70v28H60z" />
      <path d="M68 68h28M68 76h40M120 68v16" />
    </svg>
  )
}

function MarkdownCover() {
  return (
    <svg viewBox="0 0 180 112" aria-hidden="true">
      <path d="M32 22h116v68H32z" />
      <path className="cover-fill" d="M42 34h40v44H42z" />
      <path d="M52 48v20l10-12 10 12V48M96 42h48M96 54h36M96 66h42M96 78h28" />
    </svg>
  )
}

/**
 * Transcript page + waveform panel — same document frame as MarkdownCover,
 * but left accent holds a smooth wave and top-right holds broadcast arcs.
 */
function AudioCover() {
  return (
    <svg viewBox="0 0 180 112" aria-hidden="true">
      <path d="M32 22h116v68H32z" />
      <path className="cover-fill" d="M42 34h40v44H42z" />
      <path d="M46 58c3-10 6 10 9 0s6 10 9 0 6 10 9 0 6-14 9 0" />
      <path d="M54 72h16" />
      <path d="M96 42h44M96 54h32M96 66h24M96 78h16" />
      <path d="M118 28a6 6 0 0 1 12 0M114 28a10 10 0 0 1 20 0M110 28a14 14 0 0 1 28 0" />
    </svg>
  )
}

function GenericCover() {
  return (
    <svg viewBox="0 0 180 112" aria-hidden="true">
      <path d="M52 20h56l28 28v52H52z" />
      <path d="M108 20v28h28" />
      <path className="cover-fill" d="M64 58h72v8H64z" />
      <path d="M64 74h48M64 86h36" />
    </svg>
  )
}

const COVER_BY_KIND: Record<ArtifactCoverKind, () => ReactNode> = {
  word: WordCover,
  slides: SlidesCover,
  web: WebCover,
  diagram: DiagramCover,
  pdf: PdfCover,
  markdown: MarkdownCover,
  audio: AudioCover,
  generic: GenericCover,
}

type Props = {
  kind: ArtifactCoverKind
  className?: string
}

export function ArtifactCoverIllustration({ kind, className = '' }: Props) {
  const Illustration = COVER_BY_KIND[kind]
  return (
    <div className={`artifact-cover artifact-${kind}${className ? ` ${className}` : ''}`} aria-hidden>
      <Illustration />
    </div>
  )
}
