import { useCallback, useEffect, useRef, useState, type ChangeEvent, type ClipboardEvent } from 'react'
import { api, streamChat } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { AgentIcon } from '../components/AgentIcon'
import { ChatHistoryPanel } from '../components/ChatHistoryPanel'
import { MemoryPanel } from '../components/MemoryPanel'
import { ProposalLivePanel } from '../components/ProposalLivePanel'
import { ProposalPanelShell, readProposalPanelWidth, type ProposalPanelTab } from '../components/ProposalPanelShell'
import { ProposalStatePanel } from '../components/ProposalStatePanel'
import { useFulfillmentPanel } from '../hooks/useFulfillmentPanel'
import { ChatHistoryIcon } from '../components/ChatHistoryIcon'
import { ChatMessageList } from '../components/ChatMessageList'
import { ArtifactPanelHost } from '../components/ArtifactPanelHost'
import { useArtifactPanel } from '../hooks/useArtifactPanel'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { PanelLoadingState } from '../components/PanelLoadingState'
import { NewChatIcon } from '../components/NewChatIcon'
import { SidebarToggleIcon } from '../components/SidebarToggleIcon'
import { SidebarUserMenu } from '../components/SidebarUserMenu'
import { formatAgentLabel } from '../lib/agentLabel'
import {
  getAgentSession,
  type AgentChatSession,
} from '../lib/agentChatSession'
import { getStoredChatId, setStoredChatId } from '../lib/chatStorage'
import { StreamRegistry } from '../lib/streamRegistry'
import {
  DEFAULT_ATTACHMENT_LIMITS,
  SUPPORTED_ATTACHMENT_ACCEPT,
  SUPPORTED_ATTACHMENT_LABEL,
  validatePendingAttachments,
  pendingAttachmentFilename,
  pendingAttachmentId,
  pendingAttachmentSize,
  pendingAttachmentsForValidation,
  formatAttachmentLimitMb,
  readPastedAttachmentFiles,
  type AttachmentLimits,
  type PendingAttachment,
} from '../lib/attachments'
import { formatApiError } from '../lib/apiErrorMessage'
import { formatUserFacingError } from '../lib/userFacingError'
import {
  applyStreamArtifact,
  applyStreamReasoning,
  applyStreamText,
  applyStreamToolCall,
  applyStreamToolResult,
  applyStreamViz,
  finalizeStreamLocalMessages,
  finalizeStreamReasoning,
  mergeMessagesFromApi,
} from '../lib/messageActivity'
import { turnSyncStatusLabel } from '../lib/turnSync'
import type { ArtifactSpec } from '../types/artifact'
import type { VizSpec } from '../types/viz'
import type { ProposalPreview } from '../types/proposalPreview'
import type { ProposalDraftResponse } from '../types/proposalDraft'
import type { Agent, ChatSummary, Message } from '../types'

const SIDEBAR_COLLAPSED_KEY = 'agent-platform:sidebar-collapsed'
const PROPOSAL_COMPOSER_SLUG = 'proposal-composer'
const YL_WORKER2_SLUG = 'yl-worker2'

function pickMostRecentChatId(rows: ChatSummary[]): string | null {
  if (rows.length === 0) return null
  const sorted = [...rows].sort((a, b) => {
    const aTime = a.updated_at ?? a.created_at ?? ''
    const bTime = b.updated_at ?? b.created_at ?? ''
    return bTime.localeCompare(aTime)
  })
  return sorted[0]?.id ?? null
}

function parseProposalExportWord(raw: unknown): ProposalPreview['export'] {
  if (!raw || typeof raw !== 'object') return undefined
  const wordRaw = (raw as { word?: unknown }).word
  if (!wordRaw || typeof wordRaw !== 'object') return undefined
  const word = wordRaw as Record<string, unknown>
  return {
    word: {
      available: Boolean(word.available),
      reason: typeof word.reason === 'string' ? word.reason : null,
      template_file: typeof word.template_file === 'string' ? word.template_file : null,
    },
  }
}

function parseProposalPreview(data: Record<string, unknown>): ProposalPreview | null {
  if (typeof data.state_fingerprint !== 'string' || typeof data.title !== 'string') {
    return null
  }
  const completenessRaw = data.completeness
  const completeness =
    completenessRaw && typeof completenessRaw === 'object'
      ? {
          missing_required: Array.isArray((completenessRaw as ProposalPreview['completeness']).missing_required)
            ? ((completenessRaw as ProposalPreview['completeness']).missing_required as string[])
            : [],
          ready_to_preview: Boolean((completenessRaw as ProposalPreview['completeness']).ready_to_preview),
          ready_to_generate: Boolean((completenessRaw as ProposalPreview['completeness']).ready_to_generate),
        }
      : { missing_required: [], ready_to_preview: false, ready_to_generate: false }

  return {
    chat_id: typeof data.chat_id === 'string' ? data.chat_id : undefined,
    status: (data.status as ProposalPreview['status']) || 'empty',
    title: data.title,
    markdown: typeof data.markdown === 'string' ? data.markdown : '',
    filename: typeof data.filename === 'string' ? data.filename : 'proposal.md',
    state_fingerprint: data.state_fingerprint,
    message: typeof data.message === 'string' ? data.message : null,
    completeness,
    export: parseProposalExportWord(data.export),
  }
}

function shouldReplaceProposalPreview(
  prev: ProposalPreview | null,
  next: ProposalPreview,
): boolean {
  if (!prev) return true
  if (
    next.chat_id &&
    prev.chat_id &&
    next.chat_id !== prev.chat_id
  ) {
    return true
  }
  if (prev.markdown && !next.markdown && (next.status === 'empty' || next.status === 'blocked')) {
    return false
  }
  if (next.state_fingerprint !== prev.state_fingerprint) return true
  if (next.markdown !== prev.markdown) return true
  if (next.markdown && !prev.markdown) return true
  return !prev.markdown
}

function parseToolResultObject(result: unknown): Record<string, unknown> | null {
  if (result && typeof result === 'object' && !Array.isArray(result)) {
    return result as Record<string, unknown>
  }
  if (typeof result !== 'string') return null
  try {
    const parsed: unknown = JSON.parse(result)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null
  } catch {
    return null
  }
}

function readSidebarCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1'
  } catch {
    return false
  }
}

function formatAttachmentSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

export function ChatPage() {
  const { user, logout } = useAuth()
  const [agents, setAgents] = useState<Agent[]>([])
  const [agentsLoading, setAgentsLoading] = useState(true)
  const [agentsError, setAgentsError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<Record<string, AgentChatSession>>({})
  const [attachmentUploading, setAttachmentUploading] = useState(false)
  const [attachmentLimits, setAttachmentLimits] = useState<AttachmentLimits>(DEFAULT_ATTACHMENT_LIMITS)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(readSidebarCollapsed)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [memoryOpen, setMemoryOpen] = useState(false)
  const [proposalPanelWidth, setProposalPanelWidth] = useState(readProposalPanelWidth)
  const streamRegistryRef = useRef(new StreamRegistry())
  const reloadInFlightRef = useRef(new Map<string, Promise<void>>())
  const proposalPreviewFetchGenRef = useRef(new Map<string, number>())
  const proposalStateFetchGenRef = useRef(new Map<string, number>())
  const proposalPanelTabRef = useRef(new Map<string, ProposalPanelTab>())
  const [memoryRefreshKey, setMemoryRefreshKey] = useState(0)
  const messagesScrollRef = useRef<HTMLDivElement>(null)
  const pinToBottomRef = useRef(true)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const openChatLoadGenRef = useRef(new Map<string, number>())
  const chatLoadTasksRef = useRef(new Map<string, Promise<void>>())
  const sessionsRef = useRef(sessions)
  const proposalFetchKeyRef = useRef<string | null>(null)
  sessionsRef.current = sessions

  const patchSession = useCallback(
    (
      agentId: string,
      patch:
        | Partial<AgentChatSession>
        | ((session: AgentChatSession) => Partial<AgentChatSession>),
    ) => {
      setSessions((prev) => {
        const current = getAgentSession(prev, agentId)
        const updates = typeof patch === 'function' ? patch(current) : patch
        return { ...prev, [agentId]: { ...current, ...updates } }
      })
    },
    [],
  )

  const session = getAgentSession(sessions, selectedId)
  const {
    chatId,
    messages,
    input,
    pendingAttachments,
    loading,
    error,
    chatHistory,
    chatHistoryLoading,
    chatSessionLoading,
    activeRunId,
    turnSyncPhase,
    proposalTurnSyncing,
    expandedArtifact,
    proposalPanelCollapsed,
    proposalPanelTab,
    proposalPreview,
    proposalPreviewLoading,
    proposalPreviewError,
    proposalState,
    proposalStateFingerprint,
    proposalStateLoading,
    proposalStateError,
    fulfillmentForms,
    fulfillmentFormsLoading,
    fulfillmentFormsError,
  } = session

  const SCROLL_PIN_THRESHOLD_PX = 80

  const updateScrollPin = useCallback(() => {
    const el = messagesScrollRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    pinToBottomRef.current = distanceFromBottom <= SCROLL_PIN_THRESHOLD_PX
  }, [])

  const scrollToBottomIfPinned = useCallback(() => {
    const el = messagesScrollRef.current
    if (!el || !pinToBottomRef.current) return
    el.scrollTop = el.scrollHeight
  }, [])

  const turnSyncHint = turnSyncStatusLabel(turnSyncPhase)

  const selected = agents.find((a) => a.id === selectedId) ?? null
  const isProposalComposer = selected?.slug === PROPOSAL_COMPOSER_SLUG
  const isYlWorker2 = selected?.slug === YL_WORKER2_SLUG
  const showChat = !agentsLoading && selected != null

  const fulfillment = useFulfillmentPanel({
    selectedId,
    chatId,
    isYlWorker2,
    chatSessionLoading,
    patchSession,
  })

  useEffect(() => {
    if (selectedId) {
      proposalPanelTabRef.current.set(selectedId, proposalPanelTab)
    }
  }, [selectedId, proposalPanelTab])

  const invalidateProposalPanelFetches = useCallback((agentId: string) => {
    proposalPreviewFetchGenRef.current.set(agentId, (proposalPreviewFetchGenRef.current.get(agentId) ?? 0) + 1)
    proposalStateFetchGenRef.current.set(agentId, (proposalStateFetchGenRef.current.get(agentId) ?? 0) + 1)
  }, [])

  const fetchProposalPreview = useCallback(async (agentId: string, id: string) => {
    const generation = (proposalPreviewFetchGenRef.current.get(agentId) ?? 0) + 1
    proposalPreviewFetchGenRef.current.set(agentId, generation)
    patchSession(agentId, {
      proposalPreviewLoading: true,
      proposalPreviewError: null,
    })
    try {
      const preview = await api.getProposalPreview(id, true)
      if (generation !== proposalPreviewFetchGenRef.current.get(agentId)) return
      patchSession(agentId, (prev) => {
        if (prev.chatId !== id) return {}
        if (preview.chat_id && preview.chat_id !== id) return {}
        return {
          proposalPreview: shouldReplaceProposalPreview(prev.proposalPreview, preview)
            ? preview
            : prev.proposalPreview,
          proposalPreviewLoading: false,
        }
      })
    } catch (e) {
      if (generation !== proposalPreviewFetchGenRef.current.get(agentId)) return
      patchSession(agentId, (prev) => {
        if (prev.chatId !== id) return {}
        return {
          proposalPreviewError: e instanceof Error ? e.message : 'Failed to load proposal preview',
          proposalPreviewLoading: false,
        }
      })
    } finally {
      if (generation === proposalPreviewFetchGenRef.current.get(agentId)) {
        patchSession(agentId, { proposalPreviewLoading: false })
      }
    }
  }, [patchSession])

  const fetchProposalState = useCallback(async (agentId: string, id: string) => {
    const generation = (proposalStateFetchGenRef.current.get(agentId) ?? 0) + 1
    proposalStateFetchGenRef.current.set(agentId, generation)
    patchSession(agentId, {
      proposalStateLoading: true,
      proposalStateError: null,
    })
    try {
      const payload: ProposalDraftResponse = await api.getProposalDraft(id)
      if (generation !== proposalStateFetchGenRef.current.get(agentId)) return
      patchSession(agentId, (prev) => {
        if (prev.chatId !== id) return {}
        if (payload.chat_id && payload.chat_id !== id) return {}
        return {
          proposalState: payload.draft,
          proposalStateFingerprint: payload.state_fingerprint,
          proposalStateLoading: false,
        }
      })
    } catch (e) {
      if (generation !== proposalStateFetchGenRef.current.get(agentId)) return
      patchSession(agentId, (prev) => {
        if (prev.chatId !== id) return {}
        return {
          proposalStateError: formatApiError(e, 'Failed to load proposal draft'),
          proposalStateLoading: false,
        }
      })
    } finally {
      if (generation === proposalStateFetchGenRef.current.get(agentId)) {
        patchSession(agentId, { proposalStateLoading: false })
      }
    }
  }, [patchSession])

  const applyProposalPreview = useCallback((
    agentId: string,
    preview: ProposalPreview,
    forChatId: string,
  ) => {
    proposalPreviewFetchGenRef.current.set(
      agentId,
      (proposalPreviewFetchGenRef.current.get(agentId) ?? 0) + 1,
    )
    patchSession(agentId, (prev) => {
      if (prev.chatId !== forChatId) return {}
      if (preview.chat_id && preview.chat_id !== forChatId) return {}
      return {
        proposalPreview: shouldReplaceProposalPreview(prev.proposalPreview, preview)
          ? preview
          : prev.proposalPreview,
        proposalPreviewLoading: false,
        proposalPreviewError: null,
        proposalTurnSyncing: false,
        turnSyncPhase: null,
        proposalPanelCollapsed: preview.markdown ? false : prev.proposalPanelCollapsed,
      }
    })
  }, [patchSession])

  useEffect(() => {
    void api.getAttachmentConfig().then(setAttachmentLimits)
  }, [])

  const collapseProposalPanel = useCallback(() => {
    if (!selectedId) return
    patchSession(selectedId, { proposalPanelCollapsed: true })
  }, [patchSession, selectedId])

  const expandProposalPanel = useCallback(
    (tab: ProposalPanelTab = 'preview') => {
      if (!selectedId || !chatId) return
      patchSession(selectedId, { proposalPanelCollapsed: false, proposalPanelTab: tab })
      if (tab === 'preview') void fetchProposalPreview(selectedId, chatId)
      if (tab === 'state') void fetchProposalState(selectedId, chatId)
    },
    [chatId, fetchProposalPreview, fetchProposalState, patchSession, selectedId],
  )

  const handleProposalPanelTabChange = useCallback(
    (tab: ProposalPanelTab) => {
      if (!selectedId || !chatId) return
      patchSession(selectedId, { proposalPanelTab: tab })
      if (tab === 'preview') void fetchProposalPreview(selectedId, chatId)
      if (tab === 'state') void fetchProposalState(selectedId, chatId)
    },
    [chatId, fetchProposalPreview, fetchProposalState, patchSession, selectedId],
  )

  const closeOverlayPanels = useCallback(() => {
    setHistoryOpen(false)
    setMemoryOpen(false)
  }, [])

  const {
    handleExpandArtifact,
    closeArtifactPanel,
    panelWidth: artifactPanelWidth,
    setPanelWidth: setArtifactPanelWidth,
    sidePanelOpen,
  } = useArtifactPanel({
    selectedId,
    agentSlug: selected?.slug,
    expandedArtifact,
    patchSession,
    onExpandProposalPanel: () => expandProposalPanel(),
    onCloseOverlayPanels: closeOverlayPanels,
  })

  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev
      try {
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, next ? '1' : '0')
      } catch {
        /* ignore */
      }
      return next
    })
  }

  const refreshChatHistory = useCallback(async (agentId: string) => {
    patchSession(agentId, { chatHistoryLoading: true })
    try {
      const rows = await api.listChats(agentId)
      patchSession(agentId, { chatHistory: rows, chatHistoryLoading: false })
    } catch {
      patchSession(agentId, { chatHistory: [], chatHistoryLoading: false })
    }
  }, [patchSession])

  const resetProposalPanel = useCallback((agentId: string) => {
    invalidateProposalPanelFetches(agentId)
    patchSession(agentId, {
      proposalPreview: null,
      proposalPreviewError: null,
      proposalState: null,
      proposalStateFingerprint: null,
      proposalStateError: null,
    })
  }, [invalidateProposalPanelFetches, patchSession])

  const enterDraftMode = useCallback((agentId: string) => {
    patchSession(agentId, {
      chatId: null,
      messages: [],
      input: '',
      pendingAttachments: [],
      error: null,
      expandedArtifact: null,
      chatSessionLoading: false,
      initialized: true,
    })
    resetProposalPanel(agentId)
  }, [patchSession, resetProposalPanel])

  const ensureChatId = useCallback(async (agentId: string): Promise<string> => {
    const current = getAgentSession(sessionsRef.current, agentId)
    if (current.chatId) return current.chatId
    const chat = await api.createChat(agentId)
    setStoredChatId(agentId, chat.id)
    streamRegistryRef.current.bindChat(chat.id, agentId)
    patchSession(agentId, { chatId: chat.id, initialized: true })
    await refreshChatHistory(agentId)
    return chat.id
  }, [patchSession, refreshChatHistory])

  const openChatById = useCallback(async (agentId: string, id: string) => {
    const loadGen = (openChatLoadGenRef.current.get(agentId) ?? 0) + 1
    openChatLoadGenRef.current.set(agentId, loadGen)

    setSessions((prev) => {
      const current = getAgentSession(prev, agentId)
      if (current.chatId && current.chatId !== id) {
        streamRegistryRef.current.abort(current.chatId)
      }
      return {
        ...prev,
        [agentId]: {
          ...current,
          error: null,
          chatSessionLoading: true,
          messages: current.chatId === id ? current.messages : [],
        },
      }
    })
    resetProposalPanel(agentId)
    try {
      const rows = await api.listMessages(id)
      if (loadGen !== openChatLoadGenRef.current.get(agentId)) return
      patchSession(agentId, {
        messages: rows,
        chatId: id,
        input: '',
        pendingAttachments: [],
        expandedArtifact: null,
        chatSessionLoading: false,
        initialized: true,
        error: null,
      })
      setStoredChatId(agentId, id)
      streamRegistryRef.current.bindChat(id, agentId)
    } catch (e) {
      if (loadGen !== openChatLoadGenRef.current.get(agentId)) return
      patchSession(agentId, {
        chatSessionLoading: false,
        error: e instanceof Error ? e.message : 'Failed to load conversation',
      })
      throw e
    }
  }, [resetProposalPanel, patchSession])

  const createAndOpenChat = useCallback(
    async (agentId: string) => {
      const chat = await api.createChat(agentId)
      await openChatById(agentId, chat.id)
      await refreshChatHistory(agentId)
      return chat.id
    },
    [openChatById, refreshChatHistory],
  )

  const loadChat = useCallback(
    async (agentId: string) => {
      patchSession(agentId, { error: null })
      let rows: ChatSummary[] = []
      patchSession(agentId, { chatHistoryLoading: true })
      try {
        rows = await api.listChats(agentId)
        patchSession(agentId, { chatHistory: rows, chatHistoryLoading: false })
      } catch {
        patchSession(agentId, { chatHistory: [], chatHistoryLoading: false })
        rows = []
      }

      try {
        const storedChatId = getStoredChatId(agentId)
        if (storedChatId && rows.some((row) => row.id === storedChatId)) {
          await openChatById(agentId, storedChatId)
          return
        }
        const recentChatId = pickMostRecentChatId(rows)
        if (recentChatId) {
          await openChatById(agentId, recentChatId)
          return
        }
        await createAndOpenChat(agentId)
      } catch (e) {
        enterDraftMode(agentId)
        patchSession(agentId, {
          error: e instanceof Error ? e.message : 'Failed to load conversation',
        })
      }
    },
    [createAndOpenChat, enterDraftMode, openChatById, patchSession],
  )

  const ensureAgentChatLoaded = useCallback(
    async (agentId: string) => {
      if (getAgentSession(sessionsRef.current, agentId).initialized) return

      const inFlight = chatLoadTasksRef.current.get(agentId)
      if (inFlight) {
        await inFlight
        return
      }

      patchSession(agentId, { chatSessionLoading: true, error: null })
      const task = (async () => {
        try {
          await loadChat(agentId)
        } finally {
          chatLoadTasksRef.current.delete(agentId)
          patchSession(agentId, (prev) => {
            if (prev.initialized) return {}
            return { chatSessionLoading: false }
          })
        }
      })()
      chatLoadTasksRef.current.set(agentId, task)
      await task
    },
    [loadChat, patchSession],
  )

  const selectAgent = useCallback(
    async (agent: Agent) => {
      setSelectedId(agent.id)
      setHistoryOpen(false)
      try {
        await ensureAgentChatLoaded(agent.id)
      } catch (e) {
        patchSession(agent.id, {
          chatSessionLoading: false,
          error: e instanceof Error ? e.message : 'Failed to load conversation',
        })
      }
    },
    [ensureAgentChatLoaded, patchSession],
  )

  const loadAgents = useCallback(async (options?: { autoSelect?: boolean }) => {
    setAgentsLoading(true)
    setAgentsError(null)
    try {
      const rows = await api.listAgents()
      setAgents(rows)
      if (rows.length > 0 && options?.autoSelect) {
        setSelectedId(rows[0].id)
        await ensureAgentChatLoaded(rows[0].id)
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to load agents'
      setAgents([])
      setAgentsError(message)
    } finally {
      setAgentsLoading(false)
    }
  }, [ensureAgentChatLoaded])

  useEffect(() => {
    void loadAgents({ autoSelect: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only bootstrap
  }, [])

  useEffect(() => {
    if (!isProposalComposer || !selectedId) {
      proposalFetchKeyRef.current = null
      return
    }
    if (!chatId || chatSessionLoading) return

    const fetchKey = `${selectedId}:${chatId}`
    if (proposalFetchKeyRef.current === fetchKey) return
    proposalFetchKeyRef.current = fetchKey

    patchSession(selectedId, { proposalPanelCollapsed: false })
    invalidateProposalPanelFetches(selectedId)
    void fetchProposalPreview(selectedId, chatId)
    const tab = proposalPanelTabRef.current.get(selectedId) ?? 'preview'
    if (tab === 'state') {
      void fetchProposalState(selectedId, chatId)
    }
  }, [
    isProposalComposer,
    selectedId,
    chatId,
    chatSessionLoading,
    fetchProposalPreview,
    fetchProposalState,
    invalidateProposalPanelFetches,
    patchSession,
  ])

  useEffect(() => {
    scrollToBottomIfPinned()
  }, [messages, scrollToBottomIfPinned])

  const reloadMessagesAfterStream = useCallback(
    async (agentId: string, id: string) => {
      const task = (async () => {
        const rows = await api.listMessages(id)
        patchSession(agentId, (prev) => ({
          messages: mergeMessagesFromApi(rows, prev.messages),
        }))
        await refreshChatHistory(agentId)
      })()
      reloadInFlightRef.current.set(id, task)
      try {
        await task
      } finally {
        if (reloadInFlightRef.current.get(id) === task) {
          reloadInFlightRef.current.delete(id)
        }
      }
    },
    [patchSession, refreshChatHistory],
  )

  const setInputForSelected = (value: string) => {
    if (!selectedId) return
    patchSession(selectedId, { input: value })
  }

  const removePendingAttachment = (attachmentId: string) => {
    if (!selectedId) return
    patchSession(selectedId, (prev) => ({
      pendingAttachments: prev.pendingAttachments.filter(
        (item) => pendingAttachmentId(item) !== attachmentId,
      ),
    }))
  }

  const handleAttachmentPick = () => {
    if (
      loading ||
      chatSessionLoading ||
      attachmentUploading ||
      pendingAttachments.length >= attachmentLimits.max_files_per_message
    ) {
      return
    }
    fileInputRef.current?.click()
  }

  const addPendingAttachmentFile = useCallback(
    async (file: File): Promise<boolean> => {
      if (!selectedId) return false
      if (loading || chatSessionLoading || attachmentUploading) return false

      const session = getAgentSession(sessionsRef.current, selectedId)
      const limitError = validatePendingAttachments(
        pendingAttachmentsForValidation(session.pendingAttachments),
        file.size,
        attachmentLimits,
      )
      if (limitError) {
        patchSession(selectedId, { error: limitError })
        return false
      }

      if (!session.chatId) {
        patchSession(selectedId, (prev) => ({
          pendingAttachments: [
            ...prev.pendingAttachments,
            {
              kind: 'local',
              localId: `local-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
              file,
            },
          ],
        }))
        return true
      }

      setAttachmentUploading(true)
      patchSession(selectedId, { error: null })
      try {
        const uploaded = await api.uploadChatAttachment(session.chatId, file)
        patchSession(selectedId, (prev) => ({
          pendingAttachments: [...prev.pendingAttachments, { kind: 'uploaded', attachment: uploaded }],
        }))
        return true
      } catch (e) {
        patchSession(selectedId, {
          error: formatApiError(e, 'Failed to upload attachment'),
        })
        return false
      } finally {
        setAttachmentUploading(false)
      }
    },
    [
      selectedId,
      loading,
      chatSessionLoading,
      attachmentUploading,
      attachmentLimits,
      patchSession,
    ],
  )

  const handleAttachmentSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    await addPendingAttachmentFile(file)
  }

  const handleComposerPaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = readPastedAttachmentFiles(event.clipboardData)
    if (files.length === 0) return
    event.preventDefault()
    void (async () => {
      for (const file of files) {
        const added = await addPendingAttachmentFile(file)
        if (!added) break
      }
    })()
  }

  const resolveAttachmentIds = useCallback(
    async (activeChatId: string, items: PendingAttachment[]): Promise<string[]> => {
      const ids: string[] = []
      for (const item of items) {
        if (item.kind === 'uploaded') {
          ids.push(item.attachment.id)
          continue
        }
        const uploaded = await api.uploadChatAttachment(activeChatId, item.file)
        ids.push(uploaded.id)
      }
      return ids
    },
    [],
  )

  const stopStreaming = async () => {
    if (!selectedId || !chatId) return
    const stream = streamRegistryRef.current.get(chatId)
    const runId = stream?.runId ?? activeRunId

    streamRegistryRef.current.abort(chatId)

    if (runId) {
      try {
        await api.cancelRun(runId)
      } catch {
        /* idempotent */
      }
    }

    try {
      await reloadMessagesAfterStream(selectedId, chatId)
    } finally {
      patchSession(selectedId, {
        loading: false,
        proposalTurnSyncing: false,
        turnSyncPhase: null,
        activeRunId: null,
      })
    }
  }

  const send = async () => {
    if (!selectedId || loading) return
    const agentId = selectedId
    const agentSlug = agents.find((a) => a.id === agentId)?.slug
    const composer = agentSlug === PROPOSAL_COMPOSER_SLUG
    const ylWorker = agentSlug === YL_WORKER2_SLUG
    const currentSession = getAgentSession(sessionsRef.current, agentId)
    const text = currentSession.input.trim()
    const sentAttachments = [...currentSession.pendingAttachments]
    if (!text && sentAttachments.length === 0) return

    patchSession(agentId, {
      input: '',
      pendingAttachments: [],
      loading: true,
      proposalTurnSyncing: false,
      turnSyncPhase: null,
      error: null,
    })
    pinToBottomRef.current = true

    let activeChatId: string
    try {
      activeChatId = await ensureChatId(agentId)
    } catch (e) {
      patchSession(agentId, {
        loading: false,
        error: e instanceof Error ? e.message : 'Failed to start conversation',
      })
      return
    }

    streamRegistryRef.current.bindChat(activeChatId, agentId)
    const reloadInFlight = reloadInFlightRef.current.get(activeChatId)
    if (reloadInFlight) {
      try {
        await reloadInFlight
      } catch {
        /* reload may fail; still attempt send */
      }
    }

    streamRegistryRef.current.abort(activeChatId)

    // Clear transient streaming messages (tool calls, partial text) left over from the
    // aborted previous turn.  When a turn is aborted its finishTurnAfterStream never
    // runs, so local-* messages never get flushed by the DB reload.  If we leave them
    // in place the new optimistic user message gets a sequence that lands in the
    // middle of the stale local messages, making the new bubble appear above the
    // AI's previous (partial) response.
    patchSession(agentId, (prev) => ({
      messages: prev.messages.filter(
        (msg) => !msg.metadata?.local || (msg.id.startsWith('tmp-') && msg.role === 'user'),
      ),
    }))

    let attachmentIds: string[] = []
    try {
      attachmentIds = await resolveAttachmentIds(activeChatId, sentAttachments)
    } catch (e) {
      patchSession(agentId, {
        loading: false,
        error: formatApiError(e, 'Failed to upload attachments'),
      })
      return
    }

    patchSession(agentId, (prev) => {
      const nextSequence = prev.messages.reduce((max, row) => Math.max(max, row.sequence), 0) + 1
      const optimistic: Message = {
        id: `tmp-${Date.now()}`,
        chat_id: activeChatId,
        role: 'user',
        message_type: 'text',
        content: text,
        metadata:
          sentAttachments.length > 0
            ? {
                attachments: sentAttachments.map((item) => ({
                  id: pendingAttachmentId(item),
                  filename: pendingAttachmentFilename(item),
                  mime_type:
                    item.kind === 'local'
                      ? item.file.type || 'application/octet-stream'
                      : item.attachment.mime_type,
                  size_bytes: pendingAttachmentSize(item),
                  provider: item.kind === 'uploaded' ? item.attachment.provider : '',
                  provider_file_id:
                    item.kind === 'uploaded' ? item.attachment.provider_file_id : '',
                })),
              }
            : {},
        parent_id: null,
        sequence: nextSequence,
        created_at: new Date().toISOString(),
      }
      return { messages: [...prev.messages, optimistic] }
    })

    const generation = streamRegistryRef.current.nextGeneration(activeChatId)
    const abortController = new AbortController()
    const streamHandle = {
      chatId: activeChatId,
      agentId,
      generation,
      abortController,
      segmentText: '',
      reasoningSegment: '',
      runId: null as string | null,
      streamIdleSeen: false,
      reloadedAfterStream: false,
      previewFreshFromStream: false,
      isProposalComposer: composer,
      isYlWorker2: ylWorker,
      fulfillmentFormsFromStream: false,
    }
    streamRegistryRef.current.set(activeChatId, streamHandle)

    patchSession(agentId, { activeRunId: null })

    const patchStreamSession = (
      updates: Partial<AgentChatSession> | ((prev: AgentChatSession) => Partial<AgentChatSession>),
    ) => {
      if (!streamRegistryRef.current.isActive(activeChatId, generation)) return
      patchSession(agentId, (prev) => {
        if (prev.chatId !== activeChatId) return {}
        const nextUpdates = typeof updates === 'function' ? updates(prev) : updates
        return nextUpdates
      })
    }

    const finishTurnAfterStream = async () => {
      const handle = streamRegistryRef.current.get(activeChatId)
      if (!handle || handle.generation !== generation || handle.reloadedAfterStream) return
      handle.reloadedAfterStream = true
      try {
        if (!handle.streamIdleSeen) {
          patchStreamSession({
            loading: false,
            activeRunId: null,
            turnSyncPhase: 'saving-messages',
            proposalTurnSyncing: composer,
          })
          patchStreamSession((prev) => ({
            messages: finalizeStreamLocalMessages(prev.messages),
          }))
        }
        patchStreamSession({ turnSyncPhase: 'saving-messages' })
        await reloadMessagesAfterStream(agentId, activeChatId)
        if (composer && !handle.previewFreshFromStream) {
          patchStreamSession({ turnSyncPhase: 'updating-preview' })
          await fetchProposalPreview(agentId, activeChatId)
        }
        const tab = proposalPanelTabRef.current.get(agentId) ?? 'preview'
        if (composer && tab === 'state') {
          patchStreamSession({ turnSyncPhase: 'refreshing-draft' })
          await fetchProposalState(agentId, activeChatId)
        }
        await fulfillment.afterStreamTurn(handle, agentId, activeChatId)
      } finally {
        if (streamRegistryRef.current.isActive(activeChatId, generation)) {
          patchStreamSession({
            turnSyncPhase: null,
            proposalTurnSyncing: false,
            loading: false,
            activeRunId: null,
          })
        }
      }
    }

    try {
      await streamChat(
        activeChatId,
        text,
        (ev) => {
          if (!streamRegistryRef.current.isActive(activeChatId, generation)) return

          const handle = streamRegistryRef.current.get(activeChatId)!

          if (ev.event === 'memory_updated') {
            setMemoryRefreshKey((k) => k + 1)
          }
          if (ev.event === 'run_started' && ev.data.run_id != null) {
            const id = String(ev.data.run_id)
            handle.runId = id
            patchStreamSession({ activeRunId: id })
          }
          if (ev.event === 'text' && typeof ev.data.text === 'string') {
            const chunk = ev.data.text
            if (
              handle.segmentText === '' ||
              (chunk.length >= handle.segmentText.length && chunk.startsWith(handle.segmentText))
            ) {
              handle.segmentText = chunk
            } else if (chunk) {
              handle.segmentText += chunk
            }
            patchStreamSession((prev) => ({
              messages: applyStreamText(prev.messages, activeChatId, handle.segmentText),
            }))
          }
          if (ev.event === 'reasoning_done') {
            handle.reasoningSegment = ''
            patchStreamSession((prev) => ({
              messages: finalizeStreamReasoning(prev.messages),
            }))
          }
          if (ev.event === 'viz' && ev.data.spec && typeof ev.data.spec === 'object') {
            const spec = ev.data.spec as VizSpec
            patchStreamSession((prev) => ({
              messages: applyStreamViz(prev.messages, activeChatId, spec),
            }))
          }
          if (ev.event === 'artifact' && ev.data.spec && typeof ev.data.spec === 'object') {
            const spec = ev.data.spec as ArtifactSpec
            patchStreamSession((prev) => ({
              messages: applyStreamArtifact(prev.messages, activeChatId, spec),
            }))
          }
          if (ev.event === 'proposal_updated') {
            const preview = parseProposalPreview(ev.data)
            if (preview) {
              handle.previewFreshFromStream = true
              applyProposalPreview(agentId, preview, activeChatId)
            }
            const tab = proposalPanelTabRef.current.get(agentId) ?? 'preview'
            if (tab === 'state') {
              void fetchProposalState(agentId, activeChatId)
            }
          }
          const proposalDraftWriteTools = new Set([
            'initialize_proposal_draft',
            'patch_proposal_draft',
            'add_package_to_proposal_draft',
            'add_service_to_proposal_draft',
            'enable_proposal_draft_section',
          ])
          if (
            ev.event === 'tool_result' &&
            proposalDraftWriteTools.has(String(ev.data?.tool_name || '')) &&
            composer
          ) {
            const result = parseToolResultObject(ev.data?.result)
            if (result) {
              const draft = result.draft
              if (draft && typeof draft === 'object' && !Array.isArray(draft)) {
                patchStreamSession({ proposalState: draft as Record<string, unknown> })
              }
            }
            const tab = proposalPanelTabRef.current.get(agentId) ?? 'preview'
            if (tab === 'state') {
              void fetchProposalState(agentId, activeChatId)
            }
          }
          if (ev.event === 'reasoning' && typeof ev.data.text === 'string') {
            const chunk = ev.data.text
            if (
              handle.reasoningSegment === '' ||
              (chunk.length >= handle.reasoningSegment.length &&
                chunk.startsWith(handle.reasoningSegment))
            ) {
              handle.reasoningSegment = chunk
            } else if (chunk) {
              handle.reasoningSegment += chunk
            }
            patchStreamSession((prev) => ({
              messages: applyStreamReasoning(
                prev.messages,
                activeChatId,
                handle.reasoningSegment,
              ),
            }))
          }
          if (ev.event === 'tool_call' && ev.data) {
            handle.segmentText = ''
            patchStreamSession((prev) => ({
              messages: applyStreamToolCall(prev.messages, activeChatId, ev.data),
            }))
          }
          if (ev.event === 'tool_result' && ev.data) {
            fulfillment.handleStreamToolResult(
              String(ev.data?.tool_name || ''),
              parseToolResultObject(ev.data?.result),
              ylWorker,
              agentId,
              activeChatId,
              patchStreamSession,
              handle,
            )
            handle.segmentText = ''
            patchStreamSession((prev) => ({
              messages: applyStreamToolResult(prev.messages, activeChatId, ev.data),
            }))
          }
          if (ev.event === 'stream_idle') {
            handle.streamIdleSeen = true
            patchStreamSession((prev) => ({
              loading: false,
              activeRunId: null,
              turnSyncPhase: 'saving-messages',
              proposalTurnSyncing: composer,
              messages: finalizeStreamLocalMessages(prev.messages),
            }))
          }
          if (ev.event === 'error') {
            throw new Error(formatUserFacingError(ev.data.error ?? ev.data, 'stream error'))
          }
        },
        abortController.signal,
        attachmentIds,
      )

      if (!streamRegistryRef.current.isActive(activeChatId, generation)) return
      await finishTurnAfterStream()
    } catch (e) {
      if (!streamRegistryRef.current.isActive(activeChatId, generation)) return
      if (e instanceof Error && e.name === 'AbortError') return
      patchSession(agentId, {
        error: formatUserFacingError(e, 'Failed to send message'),
        proposalTurnSyncing: false,
        turnSyncPhase: null,
        loading: false,
        activeRunId: null,
      })
      try {
        await reloadMessagesAfterStream(agentId, activeChatId)
      } catch {
        /* ignore reload failure */
      }
    } finally {
      if (streamRegistryRef.current.get(activeChatId)?.generation === generation) {
        streamRegistryRef.current.delete(activeChatId)
      }
    }
  }

  const startNewChat = async () => {
    if (!selectedId || loading || chatSessionLoading) return
    setHistoryOpen(false)
    proposalFetchKeyRef.current = null
    fulfillment.resetFetchKey()
    patchSession(selectedId, { error: null })
    try {
      await createAndOpenChat(selectedId)
      patchSession(selectedId, {
        proposalPanelTab: 'preview',
        proposalPanelCollapsed: isProposalComposer ? false : true,
        ...fulfillment.newChatPatch(),
      })
    } catch (e) {
      patchSession(selectedId, {
        error: e instanceof Error ? e.message : 'Failed to start new conversation',
      })
    }
  }

  const openHistoryChat = async (id: string) => {
    if (!selectedId || chatSessionLoading) return
    const current = getAgentSession(sessionsRef.current, selectedId)
    if (current.loading && current.chatId === id) return
    setHistoryOpen(false)
    proposalFetchKeyRef.current = null
    fulfillment.resetFetchKey()
    try {
      await openChatById(selectedId, id)
    } catch (e) {
      patchSession(selectedId, {
        error: e instanceof Error ? e.message : 'Failed to load conversation',
      })
    }
  }

  useEffect(() => {
    return () => {
      streamRegistryRef.current.abortAll()
    }
  }, [])

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      <aside
        className={`agent-sidebar flex shrink-0 flex-col border-r border-border bg-surface-raised ${
          sidebarCollapsed ? 'agent-sidebar-collapsed' : ''
        }`}
      >
        <div
          className={`sidebar-brand-wrap${sidebarCollapsed ? ' sidebar-brand-wrap-collapsed' : ''}`}
        >
          <h1
            className="sidebar-brand"
            aria-label="Agent Team"
            title={sidebarCollapsed ? 'Agent Team' : undefined}
          >
            <img src="/cow.png" alt="" className="sidebar-brand-icon" />
            {!sidebarCollapsed && (
              <>
                <span className="sidebar-brand-agent">Agent</span>{' '}
                <span className="sidebar-brand-team">Team</span>
              </>
            )}
          </h1>
        </div>

        {!sidebarCollapsed && (
          <div className="px-4 pb-0.5 pt-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-subtle">
              Agents
            </p>
          </div>
        )}

        <ul
          className={`min-h-0 flex-1 overflow-y-auto pb-2 ${sidebarCollapsed ? 'px-1.5 pt-2' : 'px-2'}`}
        >
          {agentsLoading && !sidebarCollapsed && (
            <li className="px-2 py-3 text-[11px] text-muted">Loading…</li>
          )}
          {agentsError && !sidebarCollapsed && (
            <li className="space-y-2 px-2 py-3">
              <p className="text-[11px] leading-relaxed text-brand-700">
                Failed to load agents: {agentsError}
              </p>
              <p className="text-[10px] text-muted">
                Make sure the backend is running (http://127.0.0.1:8000)
              </p>
              <button
                type="button"
                className="btn btn-secondary text-[10px]"
                onClick={() => void loadAgents({ autoSelect: true })}
              >
                Retry
              </button>
            </li>
          )}
          {!agentsLoading && !agentsError && agents.length === 0 && !sidebarCollapsed && (
            <li className="px-2 py-3 text-[11px] leading-relaxed text-muted">
              No agents found. Add a directory and profile.yaml under backend/agents/, then restart
              the backend.
            </li>
          )}
          {!agentsLoading &&
            agents.map((agent) => {
            const active = agent.id === selectedId
            const agentSession = getAgentSession(sessions, agent.id)
            const agentBusy = agentSession.loading
            return (
              <li key={agent.id}>
                <button
                  type="button"
                  onClick={() => void selectAgent(agent)}
                  title={sidebarCollapsed ? formatAgentLabel(agent) : undefined}
                  className={`agent-nav-item ${active ? 'agent-nav-item-active' : ''} ${
                    sidebarCollapsed ? 'agent-nav-item-collapsed' : ''
                  }${agentBusy ? ' agent-nav-item-busy' : ''}`}
                >
                  <AgentIcon className="h-[18px] w-[18px] shrink-0" />
                  {!sidebarCollapsed && (
                    <span className="agent-nav-label">{formatAgentLabel(agent)}</span>
                  )}
                  {agentBusy && (
                    <span className="agent-nav-busy-dot" aria-hidden title="Responding…" />
                  )}
                </button>
              </li>
            )
          })}
        </ul>

        <div className="agent-sidebar-footer">
          <SidebarUserMenu user={user} collapsed={sidebarCollapsed} onLogout={logout} />
          <button
            type="button"
            className="agent-sidebar-toggle-btn"
            onClick={toggleSidebar}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={sidebarCollapsed ? 'Expand' : 'Collapse'}
          >
            <SidebarToggleIcon collapsed={sidebarCollapsed} />
          </button>
        </div>
      </aside>

      <section className="chat-main flex min-w-0 flex-1 flex-col">
        {showChat && selected ? (
          <div className={`chat-main-layout${isProposalComposer ? ' chat-main-layout-proposal' : ''}`}>
            <div className="chat-main-inner">
            <div className="chat-header">
              <div className="chat-header-brand">
                <AgentIcon className="chat-header-icon h-[18px] w-[18px] shrink-0" />
                <h1 className="chat-header-title">{selected.name}</h1>
              </div>
              <div className="chat-header-actions">
                <div className="chat-header-action-wrap">
                  <button
                    type="button"
                    className={`chat-header-btn${chatSessionLoading ? ' chat-header-btn-busy' : ''}`}
                    aria-label="New Chat"
                    aria-busy={chatSessionLoading}
                    disabled={loading || chatSessionLoading}
                    onClick={() => void startNewChat()}
                  >
                    <NewChatIcon className="chat-header-action-icon" />
                  </button>
                  <span className="chat-header-tooltip">New Chat</span>
                </div>
                <div className="chat-header-action-wrap">
                  <button
                    type="button"
                    className={`chat-header-btn ${memoryOpen ? 'chat-header-btn-active' : ''}`}
                    aria-label="Memory"
                    aria-expanded={memoryOpen}
                    onClick={() => {
                      setMemoryOpen((open) => {
                        const next = !open
                        if (next) {
                          setHistoryOpen(false)
                        }
                        return next
                      })
                    }}
                  >
                    <img src="/alzheimer.png" alt="" className="chat-header-action-icon chat-header-memory-icon" />
                  </button>
                  <span className="chat-header-tooltip">Memory</span>
                </div>
                <div className="chat-header-action-wrap">
                  <button
                    type="button"
                    className={`chat-header-btn ${historyOpen ? 'chat-header-btn-active' : ''}`}
                    aria-label="Chat History"
                    aria-expanded={historyOpen}
                    onClick={() => {
                      setHistoryOpen((open) => {
                        const next = !open
                        if (next) {
                          setMemoryOpen(false)
                          if (selectedId) void refreshChatHistory(selectedId)
                        }
                        return next
                      })
                    }}
                  >
                    <ChatHistoryIcon className="chat-header-action-icon" />
                  </button>
                  <span className="chat-header-tooltip">Chat History</span>
                </div>
              </div>
            </div>

            <div className="chat-body-frame">
              <div className="chat-body-white">
                <div
                  ref={messagesScrollRef}
                  className="chat-messages-scroll"
                  onScroll={updateScrollPin}
                >
                  <div className="chat-content-column">
                    {chatSessionLoading ? (
                      <PanelLoadingState message="Loading conversation…" />
                    ) : (
                      <>
                        {messages.length === 0 && (
                          <div className="chat-messages-empty">
                            Send a message to start a conversation
                          </div>
                        )}
                        <ChatMessageList
                          messages={messages}
                          loading={loading}
                          turnSyncHint={turnSyncHint}
                          proposalPanelOpen={isProposalComposer && !proposalPanelCollapsed}
                          expandedArtifactId={expandedArtifact?.artifact_id ?? null}
                          onExpandArtifact={handleExpandArtifact}
                          fulfillmentChatId={isYlWorker2 ? chatId : null}
                          fulfillmentForms={isYlWorker2 ? fulfillmentForms : []}
                          fulfillmentFormsLoading={isYlWorker2 ? fulfillmentFormsLoading : false}
                          fulfillmentFormsError={isYlWorker2 ? fulfillmentFormsError : null}
                          onFulfillmentFormsChange={isYlWorker2 ? fulfillment.setForms : undefined}
                        />
                      </>
                    )}
                  </div>
                </div>

                {error && (
                  <p className="chat-error-bar text-center text-[11px] text-brand-700">
                    <span className="chat-content-column inline-block">
                      {formatUserFacingError(error)}
                    </span>
                  </p>
                )}

                <div className="chat-composer-wrap">
                  <div className="chat-content-column">
                    <div className="chat-composer">
                      <input
                        ref={fileInputRef}
                        type="file"
                        className="hidden"
                        accept={SUPPORTED_ATTACHMENT_ACCEPT}
                        onChange={(e) => void handleAttachmentSelected(e)}
                      />
                      {pendingAttachments.length > 0 && (
                        <div className="chat-composer-attachments">
                          {pendingAttachments.map((item) => (
                            <span
                              key={pendingAttachmentId(item)}
                              className="chat-composer-attachment-chip"
                            >
                              <span className="chat-composer-attachment-name">
                                {pendingAttachmentFilename(item)}
                              </span>
                              <span className="chat-composer-attachment-size">
                                {formatAttachmentSize(pendingAttachmentSize(item))}
                              </span>
                              <button
                                type="button"
                                className="chat-composer-attachment-remove"
                                onClick={() => removePendingAttachment(pendingAttachmentId(item))}
                                disabled={loading || attachmentUploading}
                                aria-label={`Remove ${pendingAttachmentFilename(item)}`}
                              >
                                ×
                              </button>
                            </span>
                          ))}
                        </div>
                      )}
                      <textarea
                        value={input}
                        onChange={(e) => setInputForSelected(e.target.value)}
                        onPaste={(e) => handleComposerPaste(e)}
                        onKeyDown={(e) => {
                          if (e.nativeEvent.isComposing || e.keyCode === 229) {
                            return
                          }
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault()
                            if (!loading && !chatSessionLoading) void send()
                          }
                        }}
                        placeholder="question"
                        className="chat-composer-textarea"
                        disabled={loading || chatSessionLoading}
                      />
                      <div className="chat-composer-footer">
                        <button
                          type="button"
                          className={`chat-composer-add${attachmentUploading ? ' chat-composer-add-uploading' : ''}`}
                          disabled={
                            loading ||
                            chatSessionLoading ||
                            attachmentUploading ||
                            pendingAttachments.length >= attachmentLimits.max_files_per_message
                          }
                          onClick={handleAttachmentPick}
                          aria-busy={attachmentUploading}
                          aria-label={attachmentUploading ? 'Uploading attachment' : 'Add attachment'}
                          title={
                            attachmentUploading
                              ? 'Uploading…'
                              : pendingAttachments.length >= attachmentLimits.max_files_per_message
                                ? `Maximum ${attachmentLimits.max_files_per_message} files per message`
                                : `Attach file or paste image (${SUPPORTED_ATTACHMENT_LABEL}, max ${attachmentLimits.max_files_per_message} files / ${formatAttachmentLimitMb(attachmentLimits.max_total_bytes_per_message)} MB total)`
                          }
                        >
                          {attachmentUploading ? <LoadingSpinner size="sm" /> : '+'}
                        </button>
                        <button
                          type="button"
                          onClick={() => (loading ? void stopStreaming() : void send())}
                          disabled={
                            chatSessionLoading ||
                            (!loading && !input.trim() && pendingAttachments.length === 0)
                          }
                          className={`chat-send-btn${loading ? ' chat-send-btn-stop' : ''}`}
                          aria-label={loading ? 'Stop generating' : 'Send'}
                          title={loading ? 'Stop' : 'Send'}
                        >
                          {loading ? (
                            <svg
                              width="16"
                              height="16"
                              viewBox="0 0 24 24"
                              fill="currentColor"
                              aria-hidden
                            >
                              <rect x="5" y="5" width="14" height="14" rx="2" />
                            </svg>
                          ) : (
                            <svg
                              width="16"
                              height="16"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2.25"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              aria-hidden
                            >
                              <path d="M12 19V5" />
                              <path d="m5 12 7-7 7 7" />
                            </svg>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            </div>

            {isProposalComposer && (
              <ProposalPanelShell
                open={!proposalPanelCollapsed}
                width={proposalPanelWidth}
                activeTab={proposalPanelTab}
                syncing={proposalTurnSyncing}
                onTabChange={handleProposalPanelTabChange}
                onWidthChange={setProposalPanelWidth}
                onExpand={expandProposalPanel}
              >
                {proposalPanelTab === 'preview' ? (
                  <ProposalLivePanel
                    chatId={chatId}
                    open
                    embedded
                    preview={proposalPreview}
                    loading={proposalPreviewLoading || chatSessionLoading}
                    syncing={proposalTurnSyncing}
                    error={proposalPreviewError}
                    onCollapse={collapseProposalPanel}
                    onRefresh={() => {
                      if (selectedId && chatId) void fetchProposalPreview(selectedId, chatId)
                    }}
                  />
                ) : (
                  <ProposalStatePanel
                    open
                    embedded
                    state={proposalState}
                    fingerprint={proposalStateFingerprint}
                    loading={proposalStateLoading || chatSessionLoading}
                    syncing={proposalTurnSyncing}
                    error={proposalStateError}
                    onCollapse={collapseProposalPanel}
                    onRefresh={() => {
                      if (selectedId && chatId) void fetchProposalState(selectedId, chatId)
                    }}
                  />
                )}
              </ProposalPanelShell>
            )}

            <ArtifactPanelHost
              open={sidePanelOpen}
              spec={expandedArtifact}
              width={artifactPanelWidth}
              onWidthChange={setArtifactPanelWidth}
              onClose={closeArtifactPanel}
            />

            <MemoryPanel
              open={memoryOpen}
              agents={agents}
              activeAgentId={selected.id}
              refreshKey={memoryRefreshKey}
              onClose={() => setMemoryOpen(false)}
            />
            <ChatHistoryPanel
              open={historyOpen}
              chats={chatHistory}
              activeChatId={chatId}
              loading={chatHistoryLoading}
              onClose={() => setHistoryOpen(false)}
              onSelect={(id) => void openHistoryChat(id)}
            />
          </div>
        ) : (
          <div className="chat-main-placeholder">
            {agentsLoading ? (
              <LoadingSpinner size="lg" />
            ) : (
              <>
                <p className="chat-main-placeholder-title">Select an agent to start chatting</p>
                <p className="chat-main-placeholder-subtitle">
                  Agents are loaded from backend/agents/ profiles
                </p>
              </>
            )}
          </div>
        )}
      </section>
    </div>
  )
}
