/** Strip internal model/client exceptions accidentally streamed as assistant text. */

const LEAK_MARKERS = [
  'service failed to complete the prompt',
  'OpenAICompatibleReasoningClient',
  '<class \'app.platform.llm',
] as const

export function splitAssistantStreamLeak(text: string): { display: string; leakedError: string | null } {
  const trimmed = text.trim()
  if (!trimmed) return { display: text, leakedError: null }

  let cutAt = trimmed.length
  for (const marker of LEAK_MARKERS) {
    const idx = trimmed.indexOf(marker)
    if (idx >= 0) cutAt = Math.min(cutAt, idx)
  }
  if (cutAt === trimmed.length) {
    const parenIdx = trimmed.indexOf('(*<class')
    if (parenIdx >= 0) cutAt = parenIdx
  }
  if (cutAt >= trimmed.length) return { display: text, leakedError: null }

  const display = trimmed.slice(0, cutAt).trimEnd()
  const leakedError = trimmed.slice(cutAt).trim()
  return { display, leakedError: leakedError || null }
}
