import type { AttachmentProcessingMode } from './attachmentMode'
import type { ChatAttachment } from '../types'
import { isAttachmentReferenceCompatible } from './attachmentCompat'

export type MentionTrigger = {
  start: number
  query: string
}

/** Detect `@query` being typed at the cursor (query may be empty). */
export function detectMentionTrigger(value: string, cursorPos: number): MentionTrigger | null {
  const before = value.slice(0, cursorPos)
  const match = before.match(/@([^\s@]*)$/)
  if (!match) return null
  return {
    start: cursorPos - match[0].length,
    query: match[1] ?? '',
  }
}

export function filterAttachmentsForMention(
  attachments: ChatAttachment[],
  query: string,
  mode: AttachmentProcessingMode,
  currentProvider: string,
): ChatAttachment[] {
  const normalized = query.trim().toLowerCase()
  return attachments.filter((att) => {
    if (!isAttachmentReferenceCompatible(att, mode, currentProvider).compatible) return false
    if (!normalized) return true
    return att.filename.toLowerCase().includes(normalized)
  })
}

export type InputMentionSegment =
  | { kind: 'text'; value: string }
  | { kind: 'mention'; value: string; attachment: ChatAttachment }

/** Split composer text into plain text and resolved `@filename` mention segments. */
export function segmentInputByMentions(
  text: string,
  attachments: ChatAttachment[],
): InputMentionSegment[] {
  if (!text) return []
  const byFilename = [...attachments].sort((a, b) => b.filename.length - a.filename.length)
  const segments: InputMentionSegment[] = []
  let index = 0
  while (index < text.length) {
    if (text[index] !== '@') {
      let end = index + 1
      while (end < text.length && text[end] !== '@') end += 1
      segments.push({ kind: 'text', value: text.slice(index, end) })
      index = end
      continue
    }
    let matched = false
    for (const att of byFilename) {
      const token = `@${att.filename}`
      if (text.slice(index, index + token.length) === token) {
        segments.push({ kind: 'mention', value: token, attachment: att })
        index += token.length
        matched = true
        break
      }
    }
    if (!matched) {
      segments.push({ kind: 'text', value: '@' })
      index += 1
    }
  }
  return segments
}

/** Resolve `@filename` tokens in message text to attachment IDs (longest filename first). */
export function parseAttachmentMentionIds(
  text: string,
  attachments: ChatAttachment[],
): string[] {
  if (!text || attachments.length === 0) return []
  const byFilename = [...attachments].sort((a, b) => b.filename.length - a.filename.length)
  const ids: string[] = []
  let index = 0
  while (index < text.length) {
    if (text[index] !== '@') {
      index += 1
      continue
    }
    let matched = false
    for (const att of byFilename) {
      const token = `@${att.filename}`
      if (text.slice(index, index + token.length) === token) {
        ids.push(att.id)
        index += token.length
        matched = true
        break
      }
    }
    if (!matched) index += 1
  }
  return [...new Set(ids)]
}

/** Remove `@filename` tokens already shown as attachment chips in the sent message UI. */
export function stripAttachmentMentionsFromText(
  text: string,
  attachments: Array<{ filename: string }>,
): string {
  if (!text || attachments.length === 0) return text
  const byFilename = [...attachments].sort((a, b) => b.filename.length - a.filename.length)
  let result = ''
  let index = 0
  while (index < text.length) {
    if (text[index] !== '@') {
      result += text[index]
      index += 1
      continue
    }
    let matched = false
    for (const att of byFilename) {
      const token = `@${att.filename}`
      if (text.slice(index, index + token.length) === token) {
        index += token.length
        matched = true
        break
      }
    }
    if (!matched) {
      result += text[index]
      index += 1
    }
  }
  return result.replace(/[ \t]+/g, ' ').trim()
}

export function insertMentionIntoText(
  value: string,
  cursorPos: number,
  mentionStart: number,
  filename: string,
): { nextValue: string; nextCursor: number } {
  const before = value.slice(0, mentionStart)
  const after = value.slice(cursorPos)
  const mention = `@${filename}`
  const nextValue = `${before}${mention}${after}`
  const nextCursor = before.length + mention.length
  return { nextValue, nextCursor }
}

export function formatAttachmentTimestamp(iso: string | null | undefined): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const min = String(date.getMinutes()).padStart(2, '0')
  return `${mm}/${dd} ${hh}:${min}`
}
