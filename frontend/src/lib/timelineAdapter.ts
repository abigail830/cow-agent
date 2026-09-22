import type { ChatRun, ChatTimeline, MafMessageBody, Message, TimelineItem } from '../types'
import {
  isAttachmentMaterializationText,
  platformAttachments,
  splitUserPromptText,
} from './userMessageDisplay'
import { getUiWidget } from './uiWidgets/registry'

/** DB chat_messages.sequence → UI sub-order (must match backend timeline_projection). */
export const TIMELINE_SEQUENCE_SCALE = 100

const SEQUENCE_SCALE = TIMELINE_SEQUENCE_SCALE

function displaySequence(base: number, index: number): number {
  return base * SEQUENCE_SCALE + index
}

function mafContentType(content: Record<string, unknown>): string {
  return typeof content.type === 'string' ? content.type : ''
}

function expandUserMafMessage(item: Extract<TimelineItem, { kind: 'message' }>, chatId: string): Message[] {
  const body = item.message
  const contents = Array.isArray(body.contents) ? body.contents : []
  const attachments = platformAttachments(body.additional_properties)
  let prompt = ''

  for (const raw of contents) {
    if (!raw || typeof raw !== 'object') continue
    const content = raw as Record<string, unknown>
    const type = mafContentType(content)
    if (type !== 'text') continue
    const text = typeof content.text === 'string' ? content.text : ''
    if (isAttachmentMaterializationText(text)) continue
    const visible = splitUserPromptText(text)
    if (visible) {
      prompt = visible
      break
    }
  }

  return [
    {
      id: item.id,
      chat_id: chatId,
      role: 'user',
      message_type: 'text',
      content: prompt,
      metadata: attachments.length > 0 ? { attachments } : {},
      parent_id: null,
      sequence: displaySequence(item.sequence, 0),
      created_at: item.created_at ?? null,
    },
  ]
}

function expandMafMessage(item: Extract<TimelineItem, { kind: 'message' }>, chatId: string): Message[] {
  const body = item.message
  const role = typeof body.role === 'string' ? body.role : 'assistant'
  if (role === 'user') {
    return expandUserMafMessage(item, chatId)
  }
  const contents = Array.isArray(body.contents) ? body.contents : []
  const createdAt = item.created_at ?? null
  const rows: Message[] = []

  contents.forEach((raw, index) => {
    if (!raw || typeof raw !== 'object') return
    const content = raw as Record<string, unknown>
    const type = mafContentType(content)

    if (type === 'text_reasoning') {
      rows.push({
        id: `${item.id}:${index}`,
        chat_id: chatId,
        role: 'assistant',
        message_type: 'reasoning',
        content: typeof content.text === 'string' ? content.text : '',
        metadata: {},
        parent_id: item.id,
        sequence: displaySequence(item.sequence, index),
        created_at: createdAt,
      })
      return
    }

    if (type === 'function_call') {
      rows.push({
        id: `${item.id}:${index}`,
        chat_id: chatId,
        role: 'assistant',
        message_type: 'tool_call',
        content: null,
        metadata: {
          call_id: content.call_id ?? null,
          tool_name: content.name ?? 'unknown',
          arguments: content.arguments ?? {},
        },
        parent_id: item.id,
        sequence: displaySequence(item.sequence, index),
        created_at: createdAt,
      })
      return
    }

    if (type === 'function_result') {
      const result = content.result
      rows.push({
        id: `${item.id}:${index}`,
        chat_id: chatId,
        role: 'tool',
        message_type: 'tool_result',
        content: typeof result === 'string' ? result : result == null ? null : JSON.stringify(result),
        metadata: {
          call_id: content.call_id ?? null,
          result,
        },
        parent_id: item.id,
        sequence: displaySequence(item.sequence, index),
        created_at: createdAt,
      })
      return
    }

    const text = typeof content.text === 'string' ? content.text : ''
    rows.push({
      id: `${item.id}:${index}`,
      chat_id: chatId,
      role,
      message_type: 'text',
      content: text,
      metadata: {},
      parent_id: item.id,
      sequence: displaySequence(item.sequence, index),
      created_at: createdAt,
    })
  })

  if (rows.length === 0) {
    rows.push({
      id: item.id,
      chat_id: chatId,
      role,
      message_type: 'text',
      content: '',
      metadata: {},
      parent_id: null,
      sequence: displaySequence(item.sequence, 0),
      created_at: createdAt,
    })
  }

  return rows
}

function annotationToMessage(
  item: Extract<TimelineItem, { kind: 'ui_annotation' }>,
  chatId: string,
): Message | null {
  const widget = getUiWidget(item.annotation.kind)
  const display = item.annotation.display ?? {}
  const title =
    (typeof display.title === 'string' && display.title) ||
    (typeof display.spec === 'object' &&
      display.spec !== null &&
      typeof (display.spec as Record<string, unknown>).title === 'string' &&
      String((display.spec as Record<string, unknown>).title)) ||
    item.annotation.ref

  const messageType =
    item.annotation.kind === 'viz' ||
    item.annotation.kind === 'artifact' ||
    item.annotation.kind === 'fulfillment'
      ? item.annotation.kind
      : item.annotation.kind

  if (widget?.toMessage) {
    return widget.toMessage({ item, chatId })
  }

  const metadata: Record<string, unknown> =
    item.annotation.kind === 'viz' || item.annotation.kind === 'artifact'
      ? { spec: display.spec ?? display }
      : { ...display, ref: item.annotation.ref }

  return {
    id: item.id,
    chat_id: chatId,
    role: 'assistant',
    message_type: messageType,
    content: title,
    metadata,
    parent_id: item.annotation.anchor_message_id ?? null,
    sequence: displaySequence(item.sequence, 0),
    created_at: item.created_at ?? null,
  }
}

function runMarkerMessage(run: ChatRun, chatId: string, sequence: number): Message | null {
  if (run.status === 'cancelled') {
    return {
      id: `run-cancel-${run.id}`,
      chat_id: chatId,
      role: 'user',
      message_type: 'run_cancelled',
      content: '[User cancelled the assistant response here.]',
      metadata: { run_id: run.id, cancelled_by: 'user' },
      parent_id: null,
      sequence,
      created_at: run.finished_at ?? run.started_at ?? null,
    }
  }
  if (run.status === 'failed' && run.error) {
    return {
      id: `run-error-${run.id}`,
      chat_id: chatId,
      role: 'assistant',
      message_type: 'error',
      content: run.error,
      metadata: { run_id: run.id },
      parent_id: null,
      sequence,
      created_at: run.finished_at ?? run.started_at ?? null,
    }
  }
  return null
}

export function timelineToMessages(timeline: ChatTimeline): Message[] {
  const chatId = timeline.chat_id
  const rows: Message[] = []
  for (const item of timeline.items) {
    if (item.kind === 'message') {
      rows.push(...expandMafMessage(item, chatId))
      continue
    }
    const annotationRow = annotationToMessage(item, chatId)
    if (annotationRow) rows.push(annotationRow)
  }

  for (const run of timeline.runs ?? []) {
    if (!run.user_message_id) continue
    const userItem = timeline.items.find(
      (entry) => entry.kind === 'message' && entry.id === run.user_message_id,
    )
    if (!userItem || userItem.kind !== 'message') continue
    const turnId = userItem.turn_id
    const turnMessageIds = new Set(
      timeline.items
        .filter((entry) => entry.kind === 'message' && entry.turn_id === turnId)
        .map((entry) => (entry.kind === 'message' ? entry.id : '')),
    )
    const annotationIds = new Set(
      timeline.items
        .filter((entry) => entry.kind === 'ui_annotation' && entry.turn_id === turnId)
        .map((entry) => (entry.kind === 'ui_annotation' ? entry.id : '')),
    )
    const turnRows = rows.filter(
      (row) =>
        turnMessageIds.has(row.id) ||
        (row.parent_id != null && turnMessageIds.has(row.parent_id)) ||
        annotationIds.has(row.id),
    )
    const turnMax =
      turnRows.length > 0 ? Math.max(...turnRows.map((row) => row.sequence)) : displaySequence(userItem.sequence, 0)
    const marker = runMarkerMessage(run, chatId, turnMax + 1)
    if (marker) rows.push(marker)
  }

  return rows.sort((a, b) => a.sequence - b.sequence)
}

export type { MafMessageBody }
