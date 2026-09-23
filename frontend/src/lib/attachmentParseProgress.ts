import type { AttachmentParseStatus, ChatAttachment } from '../types'

/** Primary parse status refresh interval (polling; works across multi-instance backend). */
export const ATTACHMENT_PARSE_POLL_MS = 3000

export const PARSE_STAGE_ORDER = [
  'fetch',
  'analyze',
  'parse_submit',
  'parse_wait',
  'parse_collect',
  'normalize',
  'write',
  'finalize',
] as const

export type ParseStageId = (typeof PARSE_STAGE_ORDER)[number]
export type ParseStageDisplayStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped'

export function effectiveParseStatus(attachment: ChatAttachment): AttachmentParseStatus {
  if (attachment.parse_status) return attachment.parse_status
  if (expectsParsePipeline(attachment) || likelyNeedsParse(attachment)) return 'pending'
  return 'ready'
}

export function expectsParsePipeline(attachment: ChatAttachment): boolean {
  return Boolean(attachment.parse_pipeline_id || attachment.parse_job_id)
}

export function likelyNeedsParse(attachment: ChatAttachment): boolean {
  if (expectsParsePipeline(attachment)) return true
  const mime = (attachment.mime_type ?? '').toLowerCase()
  const name = (attachment.filename ?? '').toLowerCase()
  if (mime === 'application/pdf') return true
  if (mime.startsWith('text/')) return true
  if (/\.(pdf|doc|docx|xls|xlsx|csv|tsv|md|markdown|txt)$/.test(name)) return true
  return false
}

export function isImageAttachment(attachment: ChatAttachment): boolean {
  const mime = (attachment.mime_type ?? '').toLowerCase()
  if (mime.startsWith('image/')) return true
  return /\.(png|jpe?g|gif|webp)$/i.test(attachment.filename ?? '')
}

/** True when upload finished without entering the GHA / parse-pipeline worker. */
export function parseNotRequired(attachment: ChatAttachment): boolean {
  const status = effectiveParseStatus(attachment)
  if (status === 'skipped') return true
  return status === 'ready' && !likelyNeedsParse(attachment)
}

export function parseStatusDisplayLabel(attachment: ChatAttachment): string {
  if (parseNotRequired(attachment)) return 'not required'
  return effectiveParseStatus(attachment)
}

export function parseNotRequiredDetail(attachment: ChatAttachment): string {
  if (isImageAttachment(attachment)) {
    return 'Sent to the model as vision input — no document parse pipeline.'
  }
  return 'Parse not required for this file type.'
}

export function hasStageTelemetry(attachment: ChatAttachment): boolean {
  const progress = attachment.parse_progress
  if (!progress) return false
  if (progress.current_stage) return true
  return (progress.stages?.length ?? 0) > 0
}

function stageIndex(stageId: ParseStageId): number {
  return PARSE_STAGE_ORDER.indexOf(stageId)
}

function normalizeStageStatus(raw: string | null | undefined): ParseStageDisplayStatus {
  const value = (raw ?? 'pending').toLowerCase()
  if (value === 'running' || value === 'in_progress') return 'running'
  if (value === 'succeeded' || value === 'success' || value === 'completed') return 'succeeded'
  if (value === 'failed' || value === 'error') return 'failed'
  if (value === 'skipped') return 'skipped'
  return 'pending'
}

function allStagesExplicitlySucceeded(stageMap: Map<string, ParseStageDisplayStatus>): boolean {
  return PARSE_STAGE_ORDER.every((stageId) => stageMap.get(stageId) === 'succeeded')
}

export function buildStageStatuses(
  attachment: ChatAttachment,
): Map<ParseStageId, ParseStageDisplayStatus> {
  const status = effectiveParseStatus(attachment)
  const stageMap = new Map<ParseStageId, ParseStageDisplayStatus>()
  const telemetry = new Map<string, ParseStageDisplayStatus>(
    (attachment.parse_progress?.stages ?? []).map((stage) => [
      stage.stage_id ?? '',
      normalizeStageStatus(stage.status),
    ]),
  )

  const currentStage = attachment.parse_progress?.current_stage as ParseStageId | null | undefined
  const currentIndex = currentStage ? stageIndex(currentStage) : -1

  for (const stageId of PARSE_STAGE_ORDER) {
    const index = stageIndex(stageId)
    const explicit = telemetry.get(stageId)
    if (explicit) {
      stageMap.set(stageId, explicit)
      continue
    }

    if (status === 'skipped') {
      stageMap.set(stageId, 'skipped')
      continue
    }

    if (status === 'ready' && !likelyNeedsParse(attachment)) {
      stageMap.set(stageId, 'skipped')
      continue
    }

    if (status === 'failed') {
      if (currentIndex >= 0) {
        stageMap.set(
          stageId,
          index < currentIndex ? 'succeeded' : index === currentIndex ? 'failed' : 'pending',
        )
      } else {
        stageMap.set(stageId, index === 0 ? 'failed' : 'pending')
      }
      continue
    }

    if (status === 'running') {
      if (currentIndex >= 0) {
        stageMap.set(
          stageId,
          index < currentIndex ? 'succeeded' : index === currentIndex ? 'running' : 'pending',
        )
      } else {
        stageMap.set(stageId, index === 0 ? 'running' : 'pending')
      }
      continue
    }

    if (status === 'pending') {
      stageMap.set(stageId, 'pending')
      continue
    }

    if (status === 'ready') {
      if (hasStageTelemetry(attachment) && allStagesExplicitlySucceeded(telemetry)) {
        stageMap.set(stageId, 'succeeded')
      } else {
        // Do not infer success without step-level telemetry.
        stageMap.set(stageId, 'pending')
      }
      continue
    }

    stageMap.set(stageId, 'pending')
  }

  return stageMap
}

export function parseProgressMessage(attachment: ChatAttachment): string | null {
  if (attachment.parse_progress?.message) return attachment.parse_progress.message

  const status = effectiveParseStatus(attachment)
  if (status === 'pending') return 'Queued — waiting for parse worker…'
  if (status === 'running') return 'Parse in progress…'
  if (status === 'failed') {
    return attachment.parse_error_message ?? 'Parse failed.'
  }
  if (parseNotRequired(attachment)) {
    return parseNotRequiredDetail(attachment)
  }
  if (status === 'ready') {
    if (hasStageTelemetry(attachment)) return 'Parse complete.'
    return 'Parse has not reported step progress yet.'
  }
  return null
}

export function parseProgressMessageTone(
  attachment: ChatAttachment,
): 'default' | 'warning' | 'error' {
  const status = effectiveParseStatus(attachment)
  if (status === 'failed') return 'error'
  if (status === 'ready' && likelyNeedsParse(attachment) && !hasStageTelemetry(attachment)) {
    return 'warning'
  }
  return 'default'
}
