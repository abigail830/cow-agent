import type { ArtifactSpec } from '../types/artifact'
import type { ChatAttachment, ChatAttachmentListItem, Message } from '../types'
import { isAudioTranscriptArtifact } from './artifactKinds'
import { attachmentParsedUrl } from './documentUrls'

function parsedContentUrl(chatId: string, attachmentId: string): string {
  return attachmentParsedUrl(chatId, attachmentId, 'content_md')
}

function stageSucceeded(status: string | null | undefined): boolean {
  const value = (status ?? '').toLowerCase()
  return value === 'succeeded' || value === 'success' || value === 'completed' || value === 'done'
}

/** Host row looks finished in pipeline UI but parse_status may still be `running`. */
export function audioTranscriptHostReady(host: ChatAttachment): boolean {
  if (host.parse_status === 'ready') return true
  if (host.parse_pipeline_id !== 'audio_transcription_standard') return false

  const message = host.parse_progress?.message ?? ''
  if (/succeeded/i.test(message)) return true

  const stages = host.parse_progress?.stages ?? []
  const finalize = stages.find((row) => row.stage_id === 'finalize')
  if (finalize && stageSucceeded(finalize.status)) return true

  return false
}

/** Align stale running transcript cards with attachment parse_status (host row). */
export function syncAudioTranscriptMessagesFromAttachments(
  messages: Message[],
  attachments: ChatAttachmentListItem[],
  chatId: string | null,
): Message[] {
  if (!chatId || attachments.length === 0) return messages

  const byId = new Map(attachments.map((row) => [row.id, row]))
  let changed = false

  const next = messages.map((message) => {
    const spec = message.metadata?.spec
    if (!spec || typeof spec !== 'object' || !isAudioTranscriptArtifact(spec as ArtifactSpec)) {
      return message
    }
    const typed = spec as ArtifactSpec
    if (typed.job_status !== 'running') return message

    const attachmentId = typed.attachment_id ?? typed.artifact_id
    if (!attachmentId) return message

    const host = byId.get(attachmentId)
    if (!host || !audioTranscriptHostReady(host)) return message

    changed = true
    const downloadUrl = parsedContentUrl(chatId, attachmentId)
    const updatedSpec: ArtifactSpec = {
      ...typed,
      job_status: 'ready',
      download_url: downloadUrl,
      preview_url: downloadUrl,
    }
    return {
      ...message,
      metadata: { ...message.metadata, spec: updatedSpec },
    }
  })

  return changed ? next : messages
}
