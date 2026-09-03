import type { Message } from '../types'
import type { ArtifactSpec } from '../types/artifact'
import type { VizSpec } from '../types/viz'
import { isProposalArtifact } from './artifactKinds'

export type ActivityEntry = {
  id: string
  kind: 'reasoning' | 'tool' | 'mcp' | 'skill'
  title: string
  detail: string
  request?: string
  response?: string
  status: 'running' | 'done' | 'error' | 'cancelled'
}

export type ChatBlock =
  | { kind: 'bubble'; message: Message }
  | { kind: 'process'; id: string; item: ActivityEntry }
  | { kind: 'viz'; id: string; spec: VizSpec }
  | { kind: 'artifact'; id: string; spec: ArtifactSpec; createdAt?: string | null }

function parseArtifactSpec(metadata: Record<string, unknown> | undefined): ArtifactSpec | null {
  const raw = metadata?.spec
  if (!raw || typeof raw !== 'object') return null
  const spec = raw as ArtifactSpec
  if (!spec.kind || !spec.title) return null
  if (!spec.content && !spec.download_url && !spec.preview_url && !spec.source) return null
  return spec
}

function parseVizSpec(metadata: Record<string, unknown> | undefined): VizSpec | null {
  const raw = metadata?.spec
  if (!raw || typeof raw !== 'object') return null
  const spec = raw as VizSpec
  if (!spec.kind || !spec.title) return null
  return spec
}

const REASONING_TITLE = 'Reasoning'

function formatDetail(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (
      (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
      (trimmed.startsWith('[') && trimmed.endsWith(']'))
    ) {
      try {
        return JSON.stringify(JSON.parse(trimmed), null, 2)
      } catch {
        return value
      }
    }
    return value
  }
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function toolNameFromMessage(message: Message): string {
  const meta = message.metadata ?? {}
  const name = meta.tool_name ?? meta.name
  return name != null && String(name).trim() ? String(name).trim() : 'unknown'
}

function inferKind(messageType: string): ActivityEntry['kind'] {
  if (messageType.startsWith('skill_')) return 'skill'
  if (messageType === 'mcp_call' || messageType === 'mcp_result') return 'mcp'
  return 'tool'
}

const READ_ONLY_SKILL_TOOLS = new Set(['load_skill', 'read_skill_resource'])

function parseToolArguments(value: unknown): Record<string, unknown> {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return {}
    try {
      const parsed = JSON.parse(trimmed) as unknown
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>
      }
    } catch {
      return { raw: trimmed }
    }
  }
  return {}
}

function formatSkillToolRequest(argumentsValue: unknown): string | null {
  const obj = parseToolArguments(argumentsValue)
  const skill = obj.skill_name ?? obj.name
  if (typeof skill === 'string' && skill.trim()) return skill.trim()
  return null
}

function resultLooksLikeError(result: unknown, toolName?: string): boolean {
  if (result == null) return false

  const tool = (toolName ?? '').trim()
  if (READ_ONLY_SKILL_TOOLS.has(tool)) {
    if (typeof result === 'object') {
      const obj = result as Record<string, unknown>
      if (typeof obj.error === 'string' && obj.error.trim()) return true
      if (obj.status === 'error') return true
      return false
    }
    if (typeof result === 'string') {
      const trimmed = result.trim()
      if (!trimmed) return false
      // Successful loads return SKILL.md (YAML frontmatter or long markdown body).
      if (trimmed.startsWith('---') || trimmed.length > 400) return false
      const lower = trimmed.toLowerCase()
      return (
        lower.startsWith('error') ||
        lower.includes('not found') ||
        lower.includes('not allowed')
      )
    }
    return false
  }

  if (typeof result === 'string') {
    const trimmed = result.trim()
    if (!trimmed) return false
    const lower = trimmed.toLowerCase()
    if (lower.includes('not allowed')) return true
    if (lower.includes('parsing failed')) return true
    // Long tool payloads often mention "error" in docs or JSON examples.
    if (trimmed.length > 400) {
      return lower.startsWith('error') || lower.startsWith('{"error"')
    }
    return lower.includes('error')
  }
  if (typeof result === 'object') {
    const obj = result as Record<string, unknown>
    if (obj.ok === false) return true
    if (typeof obj.error === 'string' && obj.error.trim()) return true
    if (obj.status === 'error') return true
  }
  return false
}

function formatCompactDetail(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return ''
    if (
      (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
      (trimmed.startsWith('[') && trimmed.endsWith(']'))
    ) {
      try {
        return JSON.stringify(JSON.parse(trimmed))
      } catch {
        return trimmed
      }
    }
    return trimmed
  }
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function hasToolRequest(value: string | undefined): boolean {
  if (!value) return false
  const trimmed = value.trim()
  return Boolean(trimmed) && trimmed !== '(empty)' && trimmed !== '{}'
}

function formatToolRequest(value: unknown): string {
  const skillRequest = formatSkillToolRequest(value)
  if (skillRequest) return skillRequest
  if (value == null) return ''
  if (typeof value === 'string') {
    return formatCompactDetail(value)
  }
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>
    if (Object.keys(obj).length === 0) return ''
    if (Object.keys(obj).length === 1 && typeof obj.raw === 'string' && obj.raw.trim()) {
      return formatCompactDetail(obj.raw)
    }
    if (typeof obj._memory_preview === 'string' && obj._memory_preview.trim()) {
      return obj._memory_preview.trim()
    }
    return formatCompactDetail(obj)
  }
  return formatCompactDetail(value)
}

function formatToolResponse(value: unknown): string {
  return formatCompactDetail(value)
}

function pickToolRequest(existing?: string, incoming?: string): string | undefined {
  for (const candidate of [incoming, existing]) {
    if (hasToolRequest(candidate)) return candidate
  }
  return undefined
}

function entryIdForMessage(message: Message): string {
  const type = message.message_type
  if (type === 'reasoning') return message.id
  const callId = message.metadata?.call_id
  if (callId != null && String(callId).trim()) return String(callId)
  return message.id
}

export function isActivityMessage(message: Message): boolean {
  const type = message.message_type
  if (type === 'cancelled' && message.metadata?.original_type === 'text') {
    return false
  }
  return (
    type === 'reasoning' ||
    type === 'cancelled' ||
    type === 'tool_call' ||
    type === 'tool_result' ||
    type === 'mcp_call' ||
    type === 'mcp_result' ||
    type.startsWith('skill_')
  )
}

export function messageToActivityEntry(message: Message): ActivityEntry {
  const type = message.message_type
  const meta = message.metadata ?? {}
  const entryId = entryIdForMessage(message)

  if (type === 'reasoning') {
    return {
      id: entryId,
      kind: 'reasoning',
      title: REASONING_TITLE,
      detail: message.content ?? '',
      status: 'done',
    }
  }

  if (type === 'cancelled') {
    const original = meta.original_type === 'reasoning' ? REASONING_TITLE : 'Partial response'
    return {
      id: entryId,
      kind: 'reasoning',
      title: `[Cancelled] ${original}`,
      detail: message.content ?? '',
      status: 'cancelled',
    }
  }

  const toolName = toolNameFromMessage(message)
  const kind = inferKind(type)

  if (type.startsWith('skill_')) {
    return {
      id: entryId,
      kind,
      title: toolName,
      detail: message.content ?? formatDetail(meta),
      status: 'done',
    }
  }

  if (type === 'tool_call' || type === 'mcp_call') {
    const request = formatToolRequest(meta.arguments ?? meta)
    return {
      id: entryId,
      kind,
      title: toolName,
      request: hasToolRequest(request) ? request : undefined,
      detail: request,
      status: 'running',
    }
  }

  const result = meta.result ?? message.content
  const request = formatToolRequest(meta.arguments)
  const response = formatToolResponse(result)
  return {
    id: entryId,
    kind,
    title: toolName,
    request: hasToolRequest(request) ? request : undefined,
    response: response || undefined,
    detail: response,
    status: resultLooksLikeError(result, toolName) ? 'error' : 'done',
  }
}

function findProcessBlockIndex(blocks: ChatBlock[], entryId: string): number {
  for (let i = blocks.length - 1; i >= 0; i -= 1) {
    const block = blocks[i]
    if (block.kind === 'process' && block.id === entryId) {
      return i
    }
  }
  return -1
}

function mergeActivityPair(existing: ActivityEntry, incoming: ActivityEntry): ActivityEntry {
  const request = pickToolRequest(existing.request, incoming.request)
  const response = incoming.response ?? existing.response

  if (incoming.status === 'running') {
    return {
      ...existing,
      title: existing.title !== 'unknown' ? existing.title : incoming.title,
      request,
      response,
      detail: response ?? request ?? existing.detail,
      status: 'running',
    }
  }

  const nextResponse = incoming.response ?? formatToolResponse(incoming.detail) ?? response
  return {
    ...existing,
    title: existing.title !== 'unknown' ? existing.title : incoming.title,
    request,
    response: nextResponse || undefined,
    detail: nextResponse ?? existing.detail,
    status: incoming.status,
  }
}

function mergeProcessBlock(blocks: ChatBlock[], entry: ActivityEntry): void {
  const idx = findProcessBlockIndex(blocks, entry.id)
  if (idx >= 0) {
    const block = blocks[idx]
    if (block.kind === 'process') {
      blocks[idx] = {
        kind: 'process',
        id: entry.id,
        item: mergeActivityPair(block.item, entry),
      }
    }
    return
  }
  blocks.push({ kind: 'process', id: entry.id, item: entry })
}

export const LOCAL_STREAM_TEXT_ID = 'local-stream-text'
export const LOCAL_STREAM_REASONING_ID = 'local-stream-reasoning'

function nextSequence(messages: Message[]): number {
  return messages.reduce((max, row) => Math.max(max, row.sequence), 0) + 1
}

function removeMessageById(messages: Message[], id: string): Message[] {
  return messages.filter((message) => message.id !== id)
}

function upsertMessage(messages: Message[], message: Message): Message[] {
  const index = messages.findIndex((row) => row.id === message.id)
  if (index < 0) return [...messages, message]
  const next = [...messages]
  next[index] = message
  return next
}

function commitLocalStreamText(messages: Message[]): Message[] {
  const existing = messages.find((message) => message.id === LOCAL_STREAM_TEXT_ID)
  if (!existing) return messages
  const content = existing.content ?? ''
  if (!content.trim()) {
    return removeMessageById(messages, LOCAL_STREAM_TEXT_ID)
  }
  const committed: Message = {
    ...existing,
    id: `local-text-${existing.sequence}-${Date.now()}`,
    metadata: localMetadata({ streaming: false }),
  }
  return [...removeMessageById(messages, LOCAL_STREAM_TEXT_ID), committed]
}

/** Freeze the current reasoning segment so the next segment gets its own process card. */
function commitLocalStreamReasoning(messages: Message[]): Message[] {
  const existing = messages.find((message) => message.id === LOCAL_STREAM_REASONING_ID)
  if (!existing) return messages
  const content = existing.content ?? ''
  if (!content.trim()) {
    return removeMessageById(messages, LOCAL_STREAM_REASONING_ID)
  }
  const committed: Message = {
    ...existing,
    id: `local-reasoning-${existing.sequence}-${Date.now()}`,
    metadata: localMetadata({ streaming: false }),
  }
  return [...removeMessageById(messages, LOCAL_STREAM_REASONING_ID), committed]
}

function localMetadata(extra: Record<string, unknown> = {}): Record<string, unknown> {
  return { local: true, ...extra }
}

function attachmentIds(metadata: Record<string, unknown> | undefined): string[] {
  const raw = metadata?.attachments
  if (!Array.isArray(raw)) return []
  return raw
    .map((item) => (item && typeof item === 'object' ? String((item as { id?: unknown }).id ?? '') : ''))
    .filter(Boolean)
    .sort()
}

function userMessageConfirmed(persisted: Message[], optimistic: Message): boolean {
  const content = (optimistic.content ?? '').trim()
  const optimisticAttachmentIds = attachmentIds(optimistic.metadata)
  return persisted.some((row) => {
    if (row.role !== 'user') return false
    if ((row.content ?? '').trim() !== content) return false
    const persistedAttachmentIds = attachmentIds(row.metadata)
    if (optimisticAttachmentIds.length !== persistedAttachmentIds.length) return false
    return optimisticAttachmentIds.every((id, index) => id === persistedAttachmentIds[index])
  })
}

/** Replace in-memory timeline with persisted rows; keep only unconfirmed optimistic user sends. */
export function mergeMessagesFromApi(persisted: Message[], local: Message[]): Message[] {
  const merged = new Map(persisted.map((message) => [message.id, message]))
  let maxSequence = persisted.reduce((max, row) => Math.max(max, row.sequence), 0)

  for (const message of local) {
    if (!message.id.startsWith('tmp-') || message.role !== 'user' || message.message_type !== 'text') {
      continue
    }
    const content = (message.content ?? '').trim()
    const hasAttachments = attachmentIds(message.metadata).length > 0
    if (!content && !hasAttachments) continue
    if (!userMessageConfirmed(persisted, message)) {
      maxSequence += 1
      merged.set(message.id, { ...message, sequence: maxSequence })
    }
  }

  return Array.from(merged.values()).sort((a, b) => a.sequence - b.sequence)
}

export function applyStreamText(messages: Message[], chatId: string, text: string): Message[] {
  if (!text.trim()) return messages
  const existing = messages.find((message) => message.id === LOCAL_STREAM_TEXT_ID)
  const message: Message = existing
    ? {
        ...existing,
        content: text,
        metadata: localMetadata({ streaming: true }),
      }
    : {
        id: LOCAL_STREAM_TEXT_ID,
        chat_id: chatId,
        role: 'assistant',
        message_type: 'text',
        content: text,
        metadata: localMetadata({ streaming: true }),
        parent_id: null,
        sequence: nextSequence(messages),
        created_at: new Date().toISOString(),
      }
  return upsertMessage(messages, message)
}

export function applyStreamReasoning(messages: Message[], chatId: string, text: string): Message[] {
  if (!text.trim()) return messages
  const existing = messages.find((message) => message.id === LOCAL_STREAM_REASONING_ID)
  const message: Message = existing
    ? {
        ...existing,
        content: text,
        metadata: localMetadata({ streaming: true }),
      }
    : {
        id: LOCAL_STREAM_REASONING_ID,
        chat_id: chatId,
        role: 'assistant',
        message_type: 'reasoning',
        content: text,
        metadata: localMetadata({ streaming: true }),
        parent_id: null,
        sequence: nextSequence(messages),
        created_at: new Date().toISOString(),
      }
  return upsertMessage(messages, message)
}

export function finalizeStreamReasoning(messages: Message[]): Message[] {
  return commitLocalStreamReasoning(messages)
}

export function applyStreamToolCall(
  messages: Message[],
  chatId: string,
  data: Record<string, unknown>,
): Message[] {
  let next = commitLocalStreamText(commitLocalStreamReasoning(messages))
  const callId = String(data.call_id ?? `call-${Date.now()}`)
  const toolName = String(data.tool_name ?? '').trim() || 'unknown'
  const message: Message = {
    id: `local-call-${callId}`,
    chat_id: chatId,
    role: 'assistant',
    message_type: 'tool_call',
    content: null,
    metadata: localMetadata({
      call_id: callId,
      tool_name: toolName,
      arguments: data.arguments ?? {},
    }),
    parent_id: null,
    sequence: nextSequence(next),
    created_at: new Date().toISOString(),
  }
  return upsertMessage(next, message)
}

export function applyStreamToolResult(
  messages: Message[],
  chatId: string,
  data: Record<string, unknown>,
): Message[] {
  let next = commitLocalStreamText(commitLocalStreamReasoning(messages))
  const callId = String(data.call_id ?? `result-${Date.now()}`)
  const toolName = String(data.tool_name ?? '').trim() || 'unknown'
  const result = data.result
  const response = formatToolResponse(result)
  const message: Message = {
    id: `local-result-${callId}`,
    chat_id: chatId,
    role: 'tool',
    message_type: 'tool_result',
    content: response || null,
    metadata: localMetadata({
      call_id: callId,
      tool_name: toolName,
      arguments: data.arguments ?? {},
      result,
    }),
    parent_id: null,
    sequence: nextSequence(next),
    created_at: new Date().toISOString(),
  }
  return upsertMessage(next, message)
}

export function applyStreamViz(messages: Message[], chatId: string, spec: VizSpec): Message[] {
  const next = commitLocalStreamText(commitLocalStreamReasoning(messages))
  return [
    ...next,
    {
      id: `local-viz-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      chat_id: chatId,
      role: 'assistant',
      message_type: 'viz',
      content: spec.title,
      metadata: localMetadata({ spec }),
      parent_id: null,
      sequence: nextSequence(next),
      created_at: new Date().toISOString(),
    },
  ]
}

export function applyStreamArtifact(
  messages: Message[],
  chatId: string,
  spec: ArtifactSpec,
): Message[] {
  const next = commitLocalStreamText(commitLocalStreamReasoning(messages))
  return [
    ...next,
    {
      id: `local-artifact-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      chat_id: chatId,
      role: 'assistant',
      message_type: 'artifact',
      content: spec.title,
      metadata: localMetadata({ spec }),
      parent_id: null,
      sequence: nextSequence(next),
      created_at: new Date().toISOString(),
    },
  ]
}

export function groupMessages(messages: Message[], options?: { streaming?: boolean }): ChatBlock[] {
  const blocks: ChatBlock[] = []

  for (const message of messages) {
    if (isActivityMessage(message)) {
      mergeProcessBlock(blocks, messageToActivityEntry(message))
      continue
    }
    if (message.message_type === 'viz') {
      const spec = parseVizSpec(message.metadata)
      if (spec) {
        blocks.push({ kind: 'viz', id: message.id, spec })
        continue
      }
    }
    if (message.message_type === 'artifact') {
      const spec = parseArtifactSpec(message.metadata)
      if (spec) {
        // Proposal/word downloads are linked in assistant text — skip duplicate inline cards.
        if (!(isProposalArtifact(spec) && spec.download_url)) {
          blocks.push({ kind: 'artifact', id: message.id, spec, createdAt: message.created_at })
        }
        continue
      }
    }
    blocks.push({ kind: 'bubble', message })
  }

  // While streaming, keep tool_call rows in "running" so the header spinner shows.
  // After the turn finishes, collapse orphaned running tools (e.g. reload mid-call),
  // but only when no tool_result merged into the same process block.
  if (!options?.streaming) {
    for (const block of blocks) {
      if (
        block.kind === 'process' &&
        block.item.status === 'running' &&
        block.item.kind !== 'reasoning' &&
        !block.item.response?.trim()
      ) {
        block.item = { ...block.item, status: 'done' }
      }
    }
  }

  return blocks
}

/** Show a breathing dot when the run is active but nothing is visibly streaming yet. */
export function shouldShowPendingIndicator(loading: boolean, messages: Message[]): boolean {
  if (!loading) return false

  let lastUserIndex = -1
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message.role === 'user' && message.message_type === 'text') {
      lastUserIndex = index
      break
    }
  }

  const turnMessages = messages.slice(lastUserIndex + 1)
  if (turnMessages.length === 0) return true

  for (const message of turnMessages) {
    if (message.message_type === 'text' && (message.content?.trim() ?? '').length > 0) {
      return false
    }
    if (message.message_type === 'reasoning' && (message.content?.trim() ?? '').length > 0) {
      return false
    }
    if (
      message.message_type === 'tool_call' ||
      message.message_type === 'tool_result' ||
      message.message_type === 'mcp_call' ||
      message.message_type === 'mcp_result'
    ) {
      return false
    }
    if (message.message_type === 'viz' || message.message_type === 'artifact') {
      return false
    }
  }

  return true
}

/** Clear streaming markers on optimistic local rows once the model stream finishes. */
export function finalizeStreamLocalMessages(messages: Message[]): Message[] {
  return messages.map((message) => {
    if (message.metadata?.streaming !== true) return message
    return {
      ...message,
      metadata: { ...message.metadata, streaming: false },
    }
  })
}

