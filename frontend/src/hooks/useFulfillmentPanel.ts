import { useCallback, useEffect, useRef } from 'react'
import { api } from '../api/client'
import { formatApiError } from '../lib/apiErrorMessage'
import { parseFulfillmentForms } from '../lib/fulfillmentForms'
import type { AgentChatSession } from '../lib/agentChatSession'
import type { FulfillmentForm } from '../types/fulfillmentForms'
import type { ActiveStream } from '../lib/streamRegistry'

type PatchSession = (
  agentId: string,
  patch: Partial<AgentChatSession> | ((session: AgentChatSession) => Partial<AgentChatSession>),
) => void

type UseFulfillmentPanelArgs = {
  selectedId: string | null
  chatId: string | null
  isYlWorker2: boolean
  chatSessionLoading: boolean
  patchSession: PatchSession
}

export function useFulfillmentPanel({
  selectedId,
  chatId,
  isYlWorker2,
  chatSessionLoading,
  patchSession,
}: UseFulfillmentPanelArgs) {
  const fetchKeyRef = useRef<string | null>(null)
  const fetchGenRef = useRef(new Map<string, number>())

  const fetchForms = useCallback(
    async (agentId: string, id: string) => {
      const generation = (fetchGenRef.current.get(agentId) ?? 0) + 1
      fetchGenRef.current.set(agentId, generation)
      patchSession(agentId, {
        fulfillmentFormsLoading: true,
        fulfillmentFormsError: null,
      })
      try {
        const payload = await api.getFulfillmentForms(id)
        if (generation !== fetchGenRef.current.get(agentId)) return
        const forms = parseFulfillmentForms(payload.forms)
        patchSession(agentId, (prev) => {
          if (prev.chatId !== id) return {}
          if (payload.chat_id && payload.chat_id !== id) return {}
          return {
            fulfillmentForms: forms,
            fulfillmentFormsLoading: false,
          }
        })
      } catch (e) {
        if (generation !== fetchGenRef.current.get(agentId)) return
        patchSession(agentId, (prev) => {
          if (prev.chatId !== id) return {}
          return {
            fulfillmentFormsError: formatApiError(e, '加载补录单表单失败'),
            fulfillmentFormsLoading: false,
          }
        })
      } finally {
        if (generation === fetchGenRef.current.get(agentId)) {
          patchSession(agentId, { fulfillmentFormsLoading: false })
        }
      }
    },
    [patchSession],
  )

  useEffect(() => {
    if (!isYlWorker2 || !selectedId) {
      fetchKeyRef.current = null
      return
    }
    if (!chatId || chatSessionLoading) return

    const fetchKey = `${selectedId}:${chatId}`
    if (fetchKeyRef.current === fetchKey) return
    fetchKeyRef.current = fetchKey

    void fetchForms(selectedId, chatId)
  }, [isYlWorker2, selectedId, chatId, chatSessionLoading, fetchForms])

  const setForms = useCallback(
    (forms: FulfillmentForm[]) => {
      if (!selectedId) return
      patchSession(selectedId, { fulfillmentForms: forms })
    },
    [patchSession, selectedId],
  )

  const resetFetchKey = useCallback(() => {
    fetchKeyRef.current = null
  }, [])

  const newChatPatch = useCallback(
    (): Partial<AgentChatSession> => ({
      fulfillmentForms: [],
      fulfillmentFormsError: null,
    }),
    [],
  )

  const handleStreamToolResult = useCallback(
    (
      toolName: string,
      resultRaw: unknown,
      ylWorker: boolean,
      agentId: string,
      activeChatId: string,
      patchStreamSession: (updates: Partial<AgentChatSession>) => void,
      handle: ActiveStream,
    ) => {
      if (toolName !== 'propose_fulfillment_forms' || !ylWorker) return false
      const forms =
        resultRaw && typeof resultRaw === 'object' && !Array.isArray(resultRaw)
          ? parseFulfillmentForms((resultRaw as Record<string, unknown>).forms)
          : []
      if (forms.length > 0) {
        handle.fulfillmentFormsFromStream = true
        patchStreamSession({ fulfillmentForms: forms })
      }
      void fetchForms(agentId, activeChatId)
      return true
    },
    [fetchForms],
  )

  const afterStreamTurn = useCallback(
    async (handle: ActiveStream, agentId: string, activeChatId: string) => {
      if (handle.isYlWorker2 && handle.fulfillmentFormsFromStream) {
        await fetchForms(agentId, activeChatId)
      }
    },
    [fetchForms],
  )

  return {
    fetchForms,
    setForms,
    resetFetchKey,
    newChatPatch,
    handleStreamToolResult,
    afterStreamTurn,
  }
}
