export type ActiveStream = {
  chatId: string
  agentId: string
  generation: number
  abortController: AbortController
  segmentText: string
  reasoningSegment: string
  runId: string | null
  streamIdleSeen: boolean
  reloadedAfterStream: boolean
  previewFreshFromStream: boolean
  isProposalComposer: boolean
  isYlWorker2: boolean
  fulfillmentFormsFromStream: boolean
}

export class StreamRegistry {
  private readonly _streams = new Map<string, ActiveStream>()
  private readonly _chatToAgent = new Map<string, string>()
  private readonly _generations = new Map<string, number>()

  bindChat(chatId: string, agentId: string): void {
    this._chatToAgent.set(chatId.trim().toLowerCase(), agentId)
  }

  agentForChat(chatId: string): string | undefined {
    return this._chatToAgent.get(chatId.trim().toLowerCase())
  }

  private _key(chatId: string): string {
    return chatId.trim().toLowerCase()
  }

  nextGeneration(chatId: string): number {
    const key = this._key(chatId)
    const next = (this._generations.get(key) ?? 0) + 1
    this._generations.set(key, next)
    return next
  }

  get(chatId: string): ActiveStream | undefined {
    return this._streams.get(this._key(chatId))
  }

  set(chatId: string, stream: ActiveStream): void {
    this._streams.set(this._key(chatId), stream)
  }

  delete(chatId: string): void {
    this._streams.delete(this._key(chatId))
  }

  abort(chatId: string): void {
    this._streams.get(this._key(chatId))?.abortController.abort()
  }

  abortAll(): void {
    for (const stream of this._streams.values()) {
      stream.abortController.abort()
    }
    this._streams.clear()
  }

  isActive(chatId: string, generation: number): boolean {
    const stream = this._streams.get(this._key(chatId))
    return stream != null && stream.generation === generation
  }
}
