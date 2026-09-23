import { API_V1 } from './apiBase'
import type { ChatAttachment } from '../types'

export type AttachmentParseUpdatedEvent = {
  type: 'attachment.parse_updated'
  attachment_id: string
  chat_id?: string
  parse_status?: ChatAttachment['parse_status']
  parse_pipeline_id?: string | null
  parse_job_id?: string | null
  parse_error_message?: string | null
  parse_progress?: ChatAttachment['parse_progress']
}

export function subscribeChatAttachmentParseEvents(
  chatId: string,
  onEvent: (event: AttachmentParseUpdatedEvent) => void,
  options?: { onConnectionChange?: (connected: boolean) => void },
): () => void {
  const url = `${API_V1}/chats/${chatId}/attachment-events`
  const es = new EventSource(url, { withCredentials: true })

  const handler = (message: MessageEvent<string>) => {
    try {
      const data = JSON.parse(message.data) as AttachmentParseUpdatedEvent
      onEvent(data)
    } catch {
      /* ignore malformed */
    }
  }

  es.addEventListener('attachment.parse_updated', handler as EventListener)
  es.onopen = () => options?.onConnectionChange?.(true)
  es.onerror = () => {
    options?.onConnectionChange?.(false)
  }

  return () => {
    es.removeEventListener('attachment.parse_updated', handler as EventListener)
    options?.onConnectionChange?.(false)
    es.close()
  }
}

export function patchAttachmentFromParseEvent(
  attachments: ChatAttachment[],
  event: AttachmentParseUpdatedEvent,
): ChatAttachment[] {
  const id = event.attachment_id
  if (!id) return attachments
  let found = false
  const next = attachments.map((row) => {
    if (row.id !== id) return row
    found = true
    return {
      ...row,
      parse_status: event.parse_status ?? row.parse_status,
      parse_pipeline_id: event.parse_pipeline_id ?? row.parse_pipeline_id,
      parse_job_id: event.parse_job_id ?? row.parse_job_id,
      parse_error_message: event.parse_error_message ?? row.parse_error_message,
      parse_progress: event.parse_progress ?? row.parse_progress,
    }
  })
  return found ? next : attachments
}
