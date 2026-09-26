import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type ClipboardEvent,
  type DragEvent,
} from 'react'
import { Mic, Paperclip } from 'lucide-react'
import { ContextUsageIndicator } from '../components/ContextUsageIndicator'
import { KbScopePopover } from '../components/KbScopePopover'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, streamChat } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { AgentIcon } from '../components/AgentIcon'
import { ChatHistoryPanel } from '../components/ChatHistoryPanel'
import { DocumentsView } from '../components/DocumentsView'
import { IntegrationsView } from '../components/IntegrationsView'
import { MemoryPanel } from '../components/MemoryPanel'
import { ProposalLivePanel } from '../components/ProposalLivePanel'
import { ProposalPanelShell, readProposalPanelWidth, type ProposalPanelTab } from '../components/ProposalPanelShell'
import { ProposalStatePanel } from '../components/ProposalStatePanel'
import { useFulfillmentPanel } from '../hooks/useFulfillmentPanel'
import { ChatHistoryIcon } from '../components/ChatHistoryIcon'
import { ChatMessageList } from '../components/ChatMessageList'
import { ArtifactPanelHost } from '../components/ArtifactPanelHost'
import { useArtifactPanel } from '../hooks/useArtifactPanel'
import { AttachmentMentionPopup } from '../components/AttachmentMentionPopup'
import { ComposerMentionInput } from '../components/ComposerMentionInput'
import { AttachmentParseDrawer } from '../components/AttachmentParseDrawer'
import { TranscribeAudioPanel } from '../components/TranscribeAudioPanel'
import { ComposerStagedChips } from '../components/ComposerStagedChips'
import {
  clearForkBanner,
  readForkBanner,
  writeForkBanner,
  type ForkBannerState,
} from '../lib/forkBanner'
import { ModelSelect } from '../components/ModelSelect'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { PanelLoadingState } from '../components/PanelLoadingState'
import { ChatStandbyPanel } from '../components/ChatStandbyPanel'
import { NewChatIcon } from '../components/NewChatIcon'
import { SidebarToggleIcon } from '../components/SidebarToggleIcon'
import { SidebarUtilityNav } from '../components/SidebarUtilityNav'
import { SidebarUserMenu } from '../components/SidebarUserMenu'
import { formatAgentLabel } from '../lib/agentLabel'
import {
  getAgentSession,
  type AgentChatSession,
} from '../lib/agentChatSession'
import { clearStoredChatId, getStoredChatId, setStoredChatId } from '../lib/chatStorage'
import { getStoredModelId, setStoredModelId } from '../lib/modelStorage'
import { StreamRegistry } from '../lib/streamRegistry'
import {
  DEFAULT_ATTACHMENT_LIMITS,
  SUPPORTED_ATTACHMENT_ACCEPT,
  readPastedAttachmentFiles,
  type AttachmentLimits,
} from '../lib/attachments'
import {
  createPendingAttachment,
  isAttachmentParsing,
  isAttachmentReady,
  isPendingAttachmentId,
  mergeAttachmentIdsForSend,
  readyAttachments,
  type ChatAttachmentListItem,
  mergeChatAttachmentList,
  replacePendingAttachment,
} from '../lib/attachmentUpload'
import { ATTACHMENT_PARSE_POLL_MS } from '../lib/attachmentParseProgress'
import { isAttachmentReferenceCompatible } from '../lib/attachmentCompat'
import {
  detectMentionTrigger,
  filterAttachmentsForMention,
  insertMentionIntoText,
  parseAttachmentMentionIds,
  type MentionTrigger,
} from '../lib/attachmentMentions'
import { formatApiError } from '../lib/apiErrorMessage'
import { formatUserFacingError } from '../lib/userFacingError'
import {
  applyStreamArtifact,
  applyStreamReasoning,
  applyStreamText,
  applyStreamToolCall,
  applyStreamToolResult,
  applyStreamViz,
  applyDoneTurnMessages,
  finalizeStreamLocalMessages,
  isActiveStreamPlaceholder,
  finalizeStreamReasoning,
  mergeMessagesFromApi,
  parseDoneTurnMessages,
} from '../lib/messageActivity'
import { parseContextUsage } from '../lib/contextUsage'
import { timelineToMessages } from '../lib/timelineAdapter'
import { turnSyncStatusLabel } from '../lib/turnSync'
import type { ArtifactSpec } from '../types/artifact'
import type { VizSpec } from '../types/viz'
import type { ProposalPreview } from '../types/proposalPreview'
import type { ProposalDraftResponse } from '../types/proposalDraft'
import type { Agent, ChatAttachment, ChatSummary, Message, ModelOption } from '../types'

const SIDEBAR_COLLAPSED_KEY = 'agent-platform:sidebar-collapsed'
const PROPOSAL_COMPOSER_SLUG = 'proposal-composer'
const YL_WORKER2_SLUG = 'yl-worker2'
const AUDIO_CAPTURE_MAX_TOTAL_BYTES = 80 * 1024 * 1024
const AUDIO_CAPTURE_POLL_MS = 5000

function findStoredChatSummary(agentId: string, rows: ChatSummary[]): ChatSummary | null {
  const storedId = getStoredChatId(agentId)
  if (!storedId) return null
  return rows.find((row) => row.id === storedId) ?? null
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

export function ChatPage() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [agents, setAgents] = useState<Agent[]>([])
  const [agentsLoading, setAgentsLoading] = useState(true)
  const [agentsError, setAgentsError] = useState<string | null>(null)
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([])
  const [selectedModelByAgent, setSelectedModelByAgent] = useState<Record<string, string>>({})
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<Record<string, AgentChatSession>>({})
  const [attachmentLimits, setAttachmentLimits] = useState<AttachmentLimits>(DEFAULT_ATTACHMENT_LIMITS)
  const [chatAttachments, setChatAttachments] = useState<ChatAttachmentListItem[]>([])
  const [chatAttachmentsLoading, setChatAttachmentsLoading] = useState(false)
  const [parseDrawerAttachment, setParseDrawerAttachment] = useState<ChatAttachmentListItem | null>(null)
  const [transcribePanelOpen, setTranscribePanelOpen] = useState(false)
  const [captureSubmitting, setCaptureSubmitting] = useState(false)
  const [stagedAttachmentIds, setStagedAttachmentIds] = useState<string[]>([])
  const [composerDragOver, setComposerDragOver] = useState(false)
  const [mentionTrigger, setMentionTrigger] = useState<MentionTrigger | null>(null)
  const [mentionHighlightIndex, setMentionHighlightIndex] = useState(0)
  const composerMentionWrapRef = useRef<HTMLDivElement>(null)
  const mentionDismissedStartRef = useRef<number | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(readSidebarCollapsed)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [memoryOpen, setMemoryOpen] = useState(false)
  const [integrationsOpen, setIntegrationsOpen] = useState(() => searchParams.get('integrations') === '1')
  const [documentsOpen, setDocumentsOpen] = useState(() => searchParams.get('documents') === '1')
  const [proposalPanelWidth, setProposalPanelWidth] = useState(readProposalPanelWidth)
  const streamRegistryRef = useRef(new StreamRegistry())
  const reloadInFlightRef = useRef(new Map<string, Promise<void>>())
  const proposalPreviewFetchGenRef = useRef(new Map<string, number>())
  const proposalStateFetchGenRef = useRef(new Map<string, number>())
  const proposalPanelTabRef = useRef(new Map<string, ProposalPanelTab>())
  const [memoryRefreshKey, setMemoryRefreshKey] = useState(0)
  const [forkingChat, setForkingChat] = useState(false)
  const [deletingChatId, setDeletingChatId] = useState<string | null>(null)
  const [forkBannerByChatId, setForkBannerByChatId] = useState<Record<string, ForkBannerState>>({})
  const messagesScrollRef = useRef<HTMLDivElement>(null)
  const pinToBottomRef = useRef(true)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const chatAttachmentsRef = useRef<ChatAttachmentListItem[]>([])
  const stagedAttachmentIdsRef = useRef<string[]>([])
  const chatAttachmentsLoadGenRef = useRef(0)
  const prevChatIdRef = useRef<string | null>(null)
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

  const discardVisibleChatAttachments = useCallback(() => {
    chatAttachmentsLoadGenRef.current += 1
    setChatAttachments([])
    chatAttachmentsRef.current = []
    setChatAttachmentsLoading(false)
    setStagedAttachmentIds([])
    stagedAttachmentIdsRef.current = []
  }, [])

  const warmupTasksRef = useRef<Map<string, Promise<void>>>(new Map())

  const session = getAgentSession(sessions, selectedId)
  const {
    initialized: sessionInitialized,
    chatId,
    warmupStatus,
    messages,
    input,
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
    contextUsage,
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

  const turnSyncHint =
    turnSyncStatusLabel(turnSyncPhase) ??
    (loading && warmupStatus === 'connecting' ? 'Connecting tools…' : null)

  const selected = agents.find((a) => a.id === selectedId) ?? null
  const selectedModelId = selectedId ? selectedModelByAgent[selectedId] ?? null : null
  const isProposalComposer = selected?.slug === PROPOSAL_COMPOSER_SLUG
  const isYlWorker2 = selected?.slug === YL_WORKER2_SLUG
  const showChat = !agentsLoading && selected != null
  const isStandby = sessionInitialized && chatId === null && !chatSessionLoading
  const storedLastChat = useMemo(
    () => (selectedId ? findStoredChatSummary(selectedId, chatHistory) : null),
    [selectedId, chatHistory],
  )

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
    if (!id) return
    if (getAgentSession(sessionsRef.current, agentId).chatId !== id) return
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
    if (!id) return
    if (getAgentSession(sessionsRef.current, agentId).chatId !== id) return
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
    void api.listModels().then(setModelOptions).catch(() => setModelOptions([]))
  }, [])

  // Placeholder only until GET /agents returns authoritative selected_model_id.
  useEffect(() => {
    if (!selectedId) return
    const placeholder = getStoredModelId(selectedId)
    if (!placeholder) return
    setSelectedModelByAgent((prev) =>
      prev[selectedId] ? prev : { ...prev, [selectedId]: placeholder },
    )
  }, [selectedId])

  useEffect(() => {
    if (!selectedId || !selected) return
    const firstAvailable = modelOptions.find((option) => option.available !== false)?.id
    const serverModel =
      selected.selected_model_id ??
      selected.default_model_id ??
      firstAvailable ??
      modelOptions[0]?.id ??
      null
    if (!serverModel) return
    setSelectedModelByAgent((prev) =>
      prev[selectedId] === serverModel ? prev : { ...prev, [selectedId]: serverModel },
    )
    setStoredModelId(selectedId, serverModel)
  }, [modelOptions, selected, selectedId])

  const handleModelChange = useCallback(async (modelId: string) => {
    if (!selectedId) return
    setSelectedModelByAgent((prev) => ({ ...prev, [selectedId]: modelId }))
    setStoredModelId(selectedId, modelId)
    try {
      const updated = await api.patchAgentModelSelection(selectedId, modelId)
      setAgents((prev) =>
        prev.map((agent) => (agent.id === selectedId ? { ...agent, ...updated } : agent)),
      )
    } catch {
      /* optimistic UI remains; user can retry by changing model again */
    }
  }, [selectedId])

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
    setIntegrationsOpen(false)
    setDocumentsOpen(false)
  }, [])

  const openIntegrations = useCallback(() => {
    setIntegrationsOpen(true)
    setHistoryOpen(false)
    setMemoryOpen(false)
    setDocumentsOpen(false)
  }, [])

  const openDocuments = useCallback(() => {
    setDocumentsOpen(true)
    setHistoryOpen(false)
    setMemoryOpen(false)
    setIntegrationsOpen(false)
  }, [])

  useEffect(() => {
    if (searchParams.get('integrations') !== '1') return
    setIntegrationsOpen(true)
    setHistoryOpen(false)
    setMemoryOpen(false)
    setDocumentsOpen(false)
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('integrations')
        return next
      },
      { replace: true },
    )
  }, [searchParams, setSearchParams])

  useEffect(() => {
    if (searchParams.get('documents') !== '1') return
    setDocumentsOpen(true)
    setHistoryOpen(false)
    setMemoryOpen(false)
    setIntegrationsOpen(false)
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('documents')
        return next
      },
      { replace: true },
    )
  }, [searchParams, setSearchParams])

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

  const enterStandbyMode = useCallback((agentId: string) => {
    patchSession(agentId, {
      chatId: null,
      messages: [],
      input: '',
      pendingAttachments: [],
      error: null,
      expandedArtifact: null,
      chatSessionLoading: false,
      initialized: true,
      warmupStatus: 'idle',
    })
    discardVisibleChatAttachments()
    resetProposalPanel(agentId)
  }, [discardVisibleChatAttachments, patchSession, resetProposalPanel])

  const startChatWarmup = useCallback(
    (agentId: string, targetChatId: string) => {
      const existing = warmupTasksRef.current.get(targetChatId)
      if (existing) return existing

      patchSession(agentId, { warmupStatus: 'connecting' })
      const task = api
        .warmupChat(targetChatId)
        .then(() => {
          patchSession(agentId, (prev) =>
            prev.chatId === targetChatId ? { warmupStatus: 'ready' } : {},
          )
        })
        .catch(() => {
          patchSession(agentId, (prev) =>
            prev.chatId === targetChatId ? { warmupStatus: 'failed' } : {},
          )
        })
        .finally(() => {
          warmupTasksRef.current.delete(targetChatId)
        })

      warmupTasksRef.current.set(targetChatId, task)
      return task
    },
    [patchSession],
  )

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

    const current = getAgentSession(sessionsRef.current, agentId)
    if (current.chatId && current.chatId !== id) {
      streamRegistryRef.current.abort(current.chatId)
    }
    if (current.chatId !== id) {
      discardVisibleChatAttachments()
    }
    setSessions((prev) => {
      const session = getAgentSession(prev, agentId)
      return {
        ...prev,
        [agentId]: {
          ...session,
          error: null,
          chatSessionLoading: true,
          messages: session.chatId === id ? session.messages : [],
        },
      }
    })
    resetProposalPanel(agentId)
    try {
      const timeline = await api.listTimeline(id)
      const rows = timelineToMessages(timeline)
      if (loadGen !== openChatLoadGenRef.current.get(agentId)) return
      patchSession(agentId, {
        messages: rows,
        chatId: id,
        input: '',
        pendingAttachments: [],
        expandedArtifact: null,
        chatSessionLoading: false,
        initialized: true,
        warmupStatus: 'idle',
        error: null,
        contextUsage: null,
      })
      void api
        .getContextUsage(id)
        .then((usage) => {
          if (loadGen !== openChatLoadGenRef.current.get(agentId)) return
          patchSession(agentId, { contextUsage: usage })
        })
        .catch(() => {})
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
  }, [discardVisibleChatAttachments, resetProposalPanel, patchSession])

  const createAndOpenChat = useCallback(
    async (agentId: string) => {
      const current = getAgentSession(sessionsRef.current, agentId)
      if (current.chatId) {
        streamRegistryRef.current.abort(current.chatId)
      }
      setMentionTrigger(null)
      mentionDismissedStartRef.current = null
      discardVisibleChatAttachments()
      patchSession(agentId, {
        chatId: null,
        error: null,
        chatSessionLoading: true,
        messages: [],
        input: '',
        pendingAttachments: [],
        expandedArtifact: null,
      })
      resetProposalPanel(agentId)
      try {
        const chat = await api.createChat(agentId)
        setStoredChatId(agentId, chat.id)
        streamRegistryRef.current.bindChat(chat.id, agentId)
        patchSession(agentId, {
          chatId: chat.id,
          messages: [],
          chatSessionLoading: false,
          initialized: true,
          warmupStatus: 'idle',
          error: null,
          contextUsage: null,
        })
        void refreshChatHistory(agentId)
        return chat.id
      } catch (e) {
        patchSession(agentId, {
          chatSessionLoading: false,
          error: e instanceof Error ? e.message : 'Failed to start new conversation',
        })
        throw e
      }
    },
    [discardVisibleChatAttachments, patchSession, refreshChatHistory, resetProposalPanel],
  )

  const loadChat = useCallback(
    async (agentId: string) => {
      patchSession(agentId, { error: null, chatHistoryLoading: true })
      try {
        const rows = await api.listChats(agentId)
        patchSession(agentId, { chatHistory: rows, chatHistoryLoading: false })
      } catch {
        patchSession(agentId, { chatHistory: [], chatHistoryLoading: false })
      }
      enterStandbyMode(agentId)
    },
    [enterStandbyMode, patchSession],
  )

  const loadAgentStandby = useCallback(
    async (agentId: string) => {
      const inFlight = chatLoadTasksRef.current.get(agentId)
      if (inFlight) {
        await inFlight
        return
      }

      const current = getAgentSession(sessionsRef.current, agentId)
      if (current.chatId) {
        streamRegistryRef.current.abort(current.chatId)
      }

      patchSession(agentId, { chatSessionLoading: true, error: null })
      const task = (async () => {
        try {
          await loadChat(agentId)
        } finally {
          chatLoadTasksRef.current.delete(agentId)
        }
      })()
      chatLoadTasksRef.current.set(agentId, task)
      await task
    },
    [loadChat, patchSession],
  )

  const selectAgent = useCallback(
    async (agent: Agent) => {
      if (agent.id === selectedId) return

      if (selectedId) {
        const previous = getAgentSession(sessionsRef.current, selectedId)
        if (previous.chatId) {
          streamRegistryRef.current.abort(previous.chatId)
        }
      }

      patchSession(agent.id, { chatSessionLoading: true, error: null })
      setSelectedId(agent.id)
      setHistoryOpen(false)
      setDocumentsOpen(false)
      setIntegrationsOpen(false)
      try {
        await loadAgentStandby(agent.id)
      } catch (e) {
        patchSession(agent.id, {
          chatSessionLoading: false,
          error: e instanceof Error ? e.message : 'Failed to load conversation',
        })
      }
    },
    [loadAgentStandby, patchSession, selectedId],
  )

  const loadAgents = useCallback(async (options?: { autoSelect?: boolean }) => {
    setAgentsLoading(true)
    setAgentsError(null)
    try {
      const rows = await api.listAgents()
      setAgents(rows)
      if (rows.length > 0 && options?.autoSelect) {
        setSelectedId(rows[0].id)
        await loadAgentStandby(rows[0].id)
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to load agents'
      setAgents([])
      setAgentsError(message)
    } finally {
      setAgentsLoading(false)
    }
  }, [loadAgentStandby])

  useEffect(() => {
    void loadAgents({ autoSelect: false })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only bootstrap
  }, [])

  useEffect(() => {
    if (agentsLoading) return
    const agentParam = searchParams.get('agent')
    if (!agentParam) return

    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('agent')
        return next
      },
      { replace: true },
    )

    const agent = agents.find((item) => item.id === agentParam)
    if (agent) {
      void selectAgent(agent)
    }
  }, [agents, agentsLoading, searchParams, selectAgent, setSearchParams])

  useEffect(() => {
    if (!isProposalComposer || !selectedId || !chatId) {
      proposalFetchKeyRef.current = null
      return
    }
    if (chatSessionLoading) return

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
        const timeline = await api.listTimeline(id)
        const rows = timelineToMessages(timeline)
        patchSession(agentId, (prev) => ({
          messages: mergeMessagesFromApi(rows, prev.messages),
        }))
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
    [patchSession],
  )

  const loadChatAttachments = useCallback(
    async (activeChatId: string, options?: { silent?: boolean }) => {
      if (!activeChatId) return
      const sessionChatId = selectedId
        ? getAgentSession(sessionsRef.current, selectedId).chatId
        : null
      if (sessionChatId !== activeChatId) return
      const gen = ++chatAttachmentsLoadGenRef.current
      if (!options?.silent) {
        setChatAttachmentsLoading(true)
      }
      try {
        const rows = await api.listChatAttachments(activeChatId)
        if (gen !== chatAttachmentsLoadGenRef.current) return
        const latestChatId = selectedId
          ? getAgentSession(sessionsRef.current, selectedId).chatId
          : null
        if (latestChatId !== activeChatId) return
        setChatAttachments((prev) => {
          const next = mergeChatAttachmentList(prev, rows)
          chatAttachmentsRef.current = next
          return next
        })
      } catch (e) {
        if (gen !== chatAttachmentsLoadGenRef.current) return
        if (selectedId) {
          patchSession(selectedId, {
            error: formatApiError(e, 'Failed to load reference materials'),
          })
        }
      } finally {
        if (!options?.silent && gen === chatAttachmentsLoadGenRef.current) {
          setChatAttachmentsLoading(false)
        }
      }
    },
    [patchSession, selectedId],
  )

  useEffect(() => {
    chatAttachmentsRef.current = chatAttachments
  }, [chatAttachments])

  useEffect(() => {
    const prevChatId = prevChatIdRef.current
    prevChatIdRef.current = chatId ?? null
    setMentionTrigger(null)
    mentionDismissedStartRef.current = null
    if (!chatId) {
      setStagedAttachmentIds([])
      stagedAttachmentIdsRef.current = []
      discardVisibleChatAttachments()
      return
    }
    // Switching between two real chats: drop the previous library immediately.
    // Draft upload may set chatId from null → id; keep staged chips and in-flight rows.
    if (prevChatId && prevChatId !== chatId) {
      setStagedAttachmentIds([])
      stagedAttachmentIdsRef.current = []
      discardVisibleChatAttachments()
    }
    void loadChatAttachments(chatId)
  }, [chatId, discardVisibleChatAttachments, loadChatAttachments])

  const readyChatAttachments = useMemo(
    () => readyAttachments(chatAttachments),
    [chatAttachments],
  )

  useEffect(() => {
    stagedAttachmentIdsRef.current = stagedAttachmentIds
  }, [stagedAttachmentIds])

  const stagedAttachmentItems = useMemo(
    () =>
      stagedAttachmentIds
        .map((id) => chatAttachments.find((row) => row.id === id))
        .filter((row): row is ChatAttachmentListItem => row != null),
    [stagedAttachmentIds, chatAttachments],
  )

  const stagedUploading = stagedAttachmentItems.some(
    (row) => row.upload_status === 'uploading' || isPendingAttachmentId(row.id),
  )
  const stagedParsing = stagedAttachmentItems.some(isAttachmentParsing)
  const hasParsingAttachments = useMemo(
    () => chatAttachments.some(isAttachmentParsing),
    [chatAttachments],
  )
  const stagedReadyCount = stagedAttachmentItems.filter(isAttachmentReady).length
  const composerCanSend =
    !isStandby &&
    !loading &&
    !chatSessionLoading &&
    !stagedUploading &&
    !stagedParsing &&
    (input.trim().length > 0 || stagedReadyCount > 0)

  const parseDrawerNeedsPoll = useMemo(() => {
    if (!parseDrawerAttachment) return false
    const status = parseDrawerAttachment.parse_status ?? 'pending'
    return status === 'pending' || status === 'running'
  }, [parseDrawerAttachment])

  const shouldPollParseProgress = hasParsingAttachments || parseDrawerNeedsPoll

  const hasRunningAudioTranscript = useMemo(
    () =>
      messages.some((message) => {
        const spec = message.metadata?.spec
        if (!spec || typeof spec !== 'object') return false
        return (spec as ArtifactSpec).kind === 'audio_transcript' && (spec as ArtifactSpec).job_status === 'running'
      }),
    [messages],
  )

  useEffect(() => {
    if (!chatId || !selectedId || !hasRunningAudioTranscript) return
    const timer = window.setInterval(() => {
      void reloadMessagesAfterStream(selectedId, chatId)
      void loadChatAttachments(chatId, { silent: true })
    }, AUDIO_CAPTURE_POLL_MS)
    return () => window.clearInterval(timer)
  }, [chatId, hasRunningAudioTranscript, loadChatAttachments, reloadMessagesAfterStream, selectedId])

  useEffect(() => {
    if (!chatId || !shouldPollParseProgress) return
    void loadChatAttachments(chatId, { silent: true })
    const timer = window.setInterval(() => {
      void loadChatAttachments(chatId, { silent: true })
    }, ATTACHMENT_PARSE_POLL_MS)
    return () => window.clearInterval(timer)
  }, [chatId, loadChatAttachments, shouldPollParseProgress])

  useEffect(() => {
    setParseDrawerAttachment((current) => {
      if (!current) return current
      const fresh = chatAttachments.find((row) => row.id === current.id)
      if (!fresh) return current
      return { ...current, ...fresh }
    })
  }, [chatAttachments])

  const refreshMentionTrigger = useCallback(
    (value: string, cursorPos: number) => {
      const next = detectMentionTrigger(value, cursorPos, readyChatAttachments)
      if (next && mentionDismissedStartRef.current === next.start) {
        setMentionTrigger(null)
        return
      }
      if (!next || mentionDismissedStartRef.current !== next.start) {
        mentionDismissedStartRef.current = null
      }
      setMentionTrigger(next)
    },
    [readyChatAttachments],
  )

  const closeMentionPopup = useCallback(() => {
    setMentionTrigger((current) => {
      if (current) mentionDismissedStartRef.current = current.start
      return null
    })
  }, [])

  useEffect(() => {
    if (!selectedId) return
    const session = getAgentSession(sessionsRef.current, selectedId)
    const cursor = textareaRef.current?.selectionStart ?? session.input.length
    refreshMentionTrigger(session.input, cursor)
  }, [readyChatAttachments, refreshMentionTrigger, selectedId])

  const mentionFilteredAttachments = useMemo(() => {
    if (!mentionTrigger) return []
    return filterAttachmentsForMention(readyChatAttachments, mentionTrigger.query)
  }, [mentionTrigger, readyChatAttachments])

  useEffect(() => {
    if (!mentionTrigger) return
    setMentionHighlightIndex(0)
    if (chatId) {
      void loadChatAttachments(chatId, { silent: chatAttachmentsRef.current.length > 0 })
    }
  }, [chatId, loadChatAttachments, mentionTrigger?.start])

  useEffect(() => {
    setMentionHighlightIndex((index) => {
      if (mentionFilteredAttachments.length === 0) return 0
      return Math.min(index, mentionFilteredAttachments.length - 1)
    })
  }, [mentionFilteredAttachments.length])

  const updateMentionQuery = useCallback(
    (query: string) => {
      if (!selectedId || !mentionTrigger) return
      const session = getAgentSession(sessionsRef.current, selectedId)
      const textarea = textareaRef.current
      const cursor = textarea?.selectionStart ?? session.input.length
      const before = session.input.slice(0, mentionTrigger.start + 1)
      const after = session.input.slice(cursor)
      const nextValue = `${before}${query}${after}`
      const nextCursor = before.length + query.length
      patchSession(selectedId, { input: nextValue })
      setMentionTrigger({ start: mentionTrigger.start, query })
      requestAnimationFrame(() => {
        textarea?.focus()
        textarea?.setSelectionRange(nextCursor, nextCursor)
      })
    },
    [mentionTrigger, patchSession, selectedId],
  )

  const setInputForSelected = (value: string, cursorPos?: number) => {
    if (!selectedId) return
    patchSession(selectedId, { input: value })
    const pos = cursorPos ?? textareaRef.current?.selectionStart ?? value.length
    refreshMentionTrigger(value, pos)
  }

  const insertAttachmentMention = useCallback(
    (attachment: ChatAttachment) => {
      if (!selectedId) return
      const session = getAgentSession(sessionsRef.current, selectedId)
      const compat = isAttachmentReferenceCompatible(attachment)
      if (!compat.compatible) return

      const textarea = textareaRef.current
      const cursor = textarea?.selectionStart ?? session.input.length

      if (mentionTrigger) {
        const { nextValue, nextCursor } = insertMentionIntoText(
          session.input,
          cursor,
          mentionTrigger.start,
          attachment.filename,
        )
        patchSession(selectedId, { input: nextValue })
        mentionDismissedStartRef.current = null
        setMentionTrigger(null)
        requestAnimationFrame(() => {
          textarea?.focus()
          textarea?.setSelectionRange(nextCursor, nextCursor)
        })
      } else {
        const needsSpace = session.input.length > 0 && !/\s$/.test(session.input)
        const mention = `${needsSpace ? ' ' : ''}@${attachment.filename} `
        patchSession(selectedId, { input: `${session.input}${mention}` })
        mentionDismissedStartRef.current = null
        setMentionTrigger(null)
      }
      requestAnimationFrame(() => textarea?.focus())
    },
    [mentionTrigger, patchSession, selectedId],
  )

  const composerAttachmentAccept = SUPPORTED_ATTACHMENT_ACCEPT

  const patchChatAttachments = useCallback(
    (updater: (prev: ChatAttachmentListItem[]) => ChatAttachmentListItem[]) => {
      setChatAttachments((prev) => {
        const next = updater(prev)
        chatAttachmentsRef.current = next
        return next
      })
    },
    [],
  )

  const handleViewParsePipeline = useCallback(
    (attachmentId: string) => {
      const attachment = chatAttachments.find((row) => row.id === attachmentId)
      if (attachment) {
        setParseDrawerAttachment(attachment)
        return
      }
      if (!chatId) return
      setParseDrawerAttachment({
        id: attachmentId,
        chat_id: chatId,
        filename: 'Audio transcript',
        mime_type: 'text/markdown',
        size_bytes: 0,
        provider: 'platform',
        provider_file_id: attachmentId,
        created_at: null,
        parse_status: 'running',
      })
    },
    [chatAttachments, chatId],
  )

  const handleSubmitAudioCapture = useCallback(
    async (files: File[], title: string | null) => {
      if (!chatId || !selectedId) return
      setCaptureSubmitting(true)
      try {
        await api.submitAudioCapture(chatId, files, title)
        await reloadMessagesAfterStream(selectedId, chatId)
        await loadChatAttachments(chatId, { silent: true })
        patchSession(selectedId, { error: null })
      } finally {
        setCaptureSubmitting(false)
      }
    },
    [chatId, loadChatAttachments, patchSession, reloadMessagesAfterStream, selectedId],
  )

  const handleRetryAttachmentParse = useCallback(
    async (attachment: ChatAttachmentListItem) => {
      if (!chatId) return
      try {
        const updated = await api.retryAttachmentParse(chatId, attachment.id)
        patchChatAttachments((prev) =>
          mergeChatAttachmentList(
            prev,
            prev.some((row) => row.id === updated.id)
              ? prev.map((row) => (row.id === updated.id ? { ...row, ...updated } : row))
              : [updated, ...prev],
          ),
        )
        setParseDrawerAttachment((current) =>
          current?.id === updated.id ? { ...current, ...updated } : current,
        )
        patchSession(selectedId!, { error: null })
      } catch (e) {
        patchSession(selectedId!, {
          error: formatApiError(e, 'Failed to retry parse'),
        })
        throw e
      }
    },
    [chatId, patchChatAttachments, patchSession, selectedId],
  )

  const handleRetryAudioTranscript = useCallback(
    async ({
      attachmentId,
      captureId,
    }: {
      attachmentId: string
      captureId?: string | null
    }) => {
      if (!chatId || !selectedId) return
      try {
        if (captureId) {
          await api.retryAudioCapture(chatId, captureId)
        } else {
          const attachment = chatAttachments.find((row) => row.id === attachmentId)
          const target: ChatAttachmentListItem =
            attachment ??
            ({
              id: attachmentId,
              chat_id: chatId,
              filename: 'Audio transcript',
              mime_type: 'text/markdown',
              size_bytes: 0,
              provider: 'platform',
              provider_file_id: attachmentId,
              created_at: null,
              parse_status: 'failed',
            } satisfies ChatAttachmentListItem)
          await handleRetryAttachmentParse(target)
        }
        await reloadMessagesAfterStream(selectedId, chatId)
        await loadChatAttachments(chatId, { silent: true })
        patchSession(selectedId, { error: null })
      } catch (e) {
        patchSession(selectedId, {
          error: formatApiError(e, 'Failed to retry transcription'),
        })
        throw e
      }
    },
    [
      chatAttachments,
      chatId,
      handleRetryAttachmentParse,
      loadChatAttachments,
      patchSession,
      reloadMessagesAfterStream,
      selectedId,
    ],
  )

  const uploadToLibrary = useCallback(
    (file: File): void => {
      if (!selectedId) return
      if (loading || chatSessionLoading) return

      if (file.size > attachmentLimits.max_bytes_per_file) {
        patchSession(selectedId, {
          error: `Each file must be under ${attachmentLimits.max_bytes_per_file / (1024 * 1024)} MB`,
        })
        return
      }

      const pending = createPendingAttachment(file)
      patchChatAttachments((prev) => [pending, ...prev])
      setStagedAttachmentIds((prev) => {
        const next = [...prev, pending.id]
        stagedAttachmentIdsRef.current = next
        return next
      })
      patchSession(selectedId, { error: null })

      void (async () => {
        const pendingId = pending.id
        try {
          const activeChatId = await ensureChatId(selectedId)
          const uploaded = await api.uploadChatAttachment(activeChatId, file)
          const latestChatId = getAgentSession(sessionsRef.current, selectedId).chatId
          if (latestChatId !== activeChatId) {
            patchChatAttachments((prev) => prev.filter((row) => row.id !== pendingId))
            setStagedAttachmentIds((prev) => prev.filter((id) => id !== pendingId))
            return
          }
          patchChatAttachments((prev) => {
            if (!prev.some((row) => row.id === pendingId)) return prev
            return replacePendingAttachment(prev, pendingId, uploaded)
          })
          setStagedAttachmentIds((prev) => {
            const next = prev.map((id) => (id === pendingId ? uploaded.id : id))
            stagedAttachmentIdsRef.current = next
            return next
          })
        } catch (e) {
          patchChatAttachments((prev) => {
            if (!prev.some((row) => row.id === pendingId)) return prev
            return prev.map((row) =>
              row.id === pendingId ? { ...row, upload_status: 'failed' as const } : row,
            )
          })
          patchSession(selectedId, {
            error: formatApiError(e, 'Failed to upload attachment'),
          })
        }
      })()
    },
    [
      attachmentLimits.max_bytes_per_file,
      chatSessionLoading,
      ensureChatId,
      loading,
      patchChatAttachments,
      patchSession,
      selectedId,
    ],
  )

  const removeStagedAttachment = useCallback(
    (attachmentId: string) => {
      setStagedAttachmentIds((prev) => prev.filter((id) => id !== attachmentId))
      patchChatAttachments((prev) => {
        if (isPendingAttachmentId(attachmentId)) {
          return prev.filter((row) => row.id !== attachmentId)
        }
        return prev
      })
    },
    [patchChatAttachments],
  )

  const handleAttachFilesClick = () => {
    if (loading || chatSessionLoading) return
    fileInputRef.current?.click()
  }

  const handleComposerDragOver = (event: DragEvent<HTMLDivElement>) => {
    if (loading || chatSessionLoading) return
    if (!event.dataTransfer.types.includes('Files')) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
    setComposerDragOver(true)
  }

  const handleComposerDragLeave = (event: DragEvent<HTMLDivElement>) => {
    if (event.currentTarget.contains(event.relatedTarget as Node)) return
    setComposerDragOver(false)
  }

  const handleComposerDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setComposerDragOver(false)
    if (loading || chatSessionLoading) return
    const files = Array.from(event.dataTransfer.files ?? [])
    for (const file of files) {
      uploadToLibrary(file)
    }
  }

  const handleAttachmentSelected = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (files.length === 0) return
    for (const file of files) {
      uploadToLibrary(file)
    }
  }

  const handleComposerPaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = readPastedAttachmentFiles(event.clipboardData)
    if (files.length === 0) return
    event.preventDefault()
    for (const file of files) {
      uploadToLibrary(file)
    }
  }

  const handleComposerInputChange = (value: string) => {
    setInputForSelected(value)
  }

  const handleComposerSelectionChange = () => {
    if (!selectedId) return
    const session = getAgentSession(sessionsRef.current, selectedId)
    const cursor = textareaRef.current?.selectionStart ?? session.input.length
    refreshMentionTrigger(session.input, cursor)
  }

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
    const existingChatId = currentSession.chatId
    const text = currentSession.input.trim()
    const readyStagedIds = stagedAttachmentIdsRef.current.filter((id) => {
      const row = chatAttachmentsRef.current.find((item) => item.id === id)
      return row != null && isAttachmentReady(row)
    })
    if (!text && readyStagedIds.length === 0) return

    patchSession(agentId, {
      input: '',
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

    const pendingReload = reloadInFlightRef.current.get(activeChatId)
    if (pendingReload) {
      try {
        await pendingReload
      } catch {
        /* ignore reload failure */
      }
    }

    const previousStream = streamRegistryRef.current.get(activeChatId)
    streamRegistryRef.current.abort(activeChatId)

    if (
      previousStream?.streamIdleSeen &&
      !previousStream.reloadedAfterStream &&
      !previousStream.messagesSyncedFromDone
    ) {
      try {
        await reloadMessagesAfterStream(agentId, activeChatId)
        previousStream.reloadedAfterStream = true
      } catch {
        /* ignore reload failure */
      }
    }

    // Drop only active SSE placeholders from an aborted/incomplete stream.
    patchSession(agentId, (prev) => ({
      messages: prev.messages.filter((msg) => !isActiveStreamPlaceholder(msg)),
    }))

    let attachmentRows = readyAttachments(chatAttachmentsRef.current)
    if (
      existingChatId &&
      attachmentRows.length === 0 &&
      chatAttachmentsRef.current.length === 0 &&
      (stagedAttachmentIdsRef.current.length > 0 || text.includes('@'))
    ) {
      try {
        const rows = await api.listChatAttachments(activeChatId)
        const latestChatId = getAgentSession(sessionsRef.current, agentId).chatId
        if (latestChatId !== activeChatId) {
          patchSession(agentId, { loading: false })
          return
        }
        chatAttachmentsRef.current = rows
        setChatAttachments(rows)
        attachmentRows = rows
      } catch (e) {
        patchSession(agentId, {
          loading: false,
          error: formatApiError(e, 'Failed to load reference materials'),
        })
        return
      }
    } else {
      attachmentRows = readyAttachments(chatAttachmentsRef.current)
    }

    const stillUploadingStaged = stagedAttachmentIdsRef.current.some((id) => {
      const row = chatAttachmentsRef.current.find((item) => item.id === id)
      return row != null && (row.upload_status === 'uploading' || isPendingAttachmentId(row.id))
    })
    if (stillUploadingStaged) {
      patchSession(agentId, {
        loading: false,
        error: 'Wait for attachment uploads to finish before sending.',
      })
      return
    }

    const readyStagedIdsForSend = stagedAttachmentIdsRef.current.filter((id) => {
      const row = chatAttachmentsRef.current.find((item) => item.id === id)
      return row != null && isAttachmentReady(row)
    })
    const mentionIds = parseAttachmentMentionIds(text, attachmentRows)
    const attachmentIds = mergeAttachmentIdsForSend(readyStagedIdsForSend, mentionIds)
    if (attachmentIds.length > attachmentLimits.max_files_per_message) {
      patchSession(agentId, {
        loading: false,
        error: `At most ${attachmentLimits.max_files_per_message} attachments per message`,
      })
      return
    }

    for (const attachmentId of attachmentIds) {
      const att = attachmentRows.find((row) => row.id === attachmentId)
      if (!att) {
        patchSession(agentId, {
          loading: false,
          error: 'Referenced attachment was not found in this chat',
        })
        return
      }
      const compat = isAttachmentReferenceCompatible(att)
      if (!compat.compatible) {
        patchSession(agentId, {
          loading: false,
          error: compat.reason ?? 'Referenced attachment is not compatible with the current mode',
        })
        return
      }
    }

    patchSession(agentId, (prev) => {
      const nextSequence = prev.messages.reduce((max, row) => Math.max(max, row.sequence), 0) + 1
      const referenced = attachmentRows.filter((row) => attachmentIds.includes(row.id))
      const optimistic: Message = {
        id: `tmp-${Date.now()}`,
        chat_id: activeChatId,
        role: 'user',
        message_type: 'text',
        content: text,
        metadata:
          referenced.length > 0
            ? {
                attachments: referenced.map((item) => ({
                  id: item.id,
                  filename: item.filename,
                  mime_type: item.mime_type,
                  size_bytes: item.size_bytes,
                  provider: item.provider,
                  provider_file_id: item.provider_file_id,
                })),
              }
            : {},
        parent_id: null,
        sequence: nextSequence,
        created_at: new Date().toISOString(),
      }
      return { messages: [...prev.messages, optimistic] }
    })
    setStagedAttachmentIds([])
    stagedAttachmentIdsRef.current = []

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
      doneTurnMessages: null,
      turnStartDisplaySequence: null,
      messagesSyncedFromDone: false,
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
      if (!handle || handle.generation !== generation) return
      try {
        if (!handle.reloadedAfterStream) {
          handle.reloadedAfterStream = true
          if (!handle.messagesSyncedFromDone) {
            patchStreamSession((prev) => ({
              messages: finalizeStreamLocalMessages(prev.messages),
            }))
            await reloadMessagesAfterStream(agentId, activeChatId)
          }
        }

        const userTurnCount = getAgentSession(sessionsRef.current, agentId).messages.filter(
          (row) => row.role === 'user',
        ).length
        if (userTurnCount === 2) {
          window.setTimeout(() => {
            void refreshChatHistory(agentId)
          }, 800)
        }

        if (composer && !handle.previewFreshFromStream) {
          void fetchProposalPreview(agentId, activeChatId)
        }
        void fulfillment.afterStreamTurn(handle, agentId, activeChatId)
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
            const streamContextUsage = parseContextUsage(ev.data.context_usage)
            patchStreamSession((prev) => ({
              loading: false,
              activeRunId: null,
              messages: finalizeStreamLocalMessages(prev.messages),
              ...(streamContextUsage != null ? { contextUsage: streamContextUsage } : {}),
            }))
          }
          if (ev.event === 'done') {
            const doneMessages = parseDoneTurnMessages(ev.data.messages)
            const doneContextUsage = parseContextUsage(ev.data.context_usage)
            const turnStartDisplaySequence =
              typeof ev.data.turn_start_display_sequence === 'number'
                ? ev.data.turn_start_display_sequence
                : null
            if (doneMessages != null) {
              handle.doneTurnMessages = doneMessages
            }
            if (turnStartDisplaySequence != null) {
              handle.turnStartDisplaySequence = turnStartDisplaySequence
            }
            if (doneMessages != null && turnStartDisplaySequence != null) {
              handle.messagesSyncedFromDone = true
              handle.reloadedAfterStream = true
              patchStreamSession((prev) => ({
                messages: applyDoneTurnMessages(
                  prev.messages,
                  doneMessages,
                  turnStartDisplaySequence,
                ),
              }))
            }
            if (doneContextUsage != null) {
              patchStreamSession(() => ({
                contextUsage: doneContextUsage,
              }))
            }
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
      if (e instanceof Error && e.name === 'AbortError') {
        if (streamHandle.streamIdleSeen && !streamHandle.reloadedAfterStream) {
          try {
            await reloadMessagesAfterStream(agentId, activeChatId)
            streamHandle.reloadedAfterStream = true
          } catch {
            /* ignore reload failure */
          }
        }
        return
      }
      if (!streamRegistryRef.current.isActive(activeChatId, generation)) return
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
    try {
      const newChatId = await createAndOpenChat(selectedId)
      if (newChatId) {
        startChatWarmup(selectedId, newChatId)
      }
      patchSession(selectedId, {
        proposalPanelTab: 'preview',
        proposalPanelCollapsed: isProposalComposer ? false : true,
        ...fulfillment.newChatPatch(),
      })
    } catch {
      /* error patched in createAndOpenChat */
    }
  }

  const continueLastConversation = async () => {
    if (!selectedId || chatSessionLoading) return
    const storedId = getStoredChatId(selectedId)
    if (!storedId) return
    if (!chatHistory.some((row) => row.id === storedId)) return
    setHistoryOpen(false)
    setDocumentsOpen(false)
    proposalFetchKeyRef.current = null
    fulfillment.resetFetchKey()
    try {
      await openChatById(selectedId, storedId)
      startChatWarmup(selectedId, storedId)
    } catch (e) {
      patchSession(selectedId, {
        error: e instanceof Error ? e.message : 'Failed to load conversation',
      })
    }
  }

  const openHistoryChat = async (id: string) => {
    if (!selectedId || chatSessionLoading) return
    const current = getAgentSession(sessionsRef.current, selectedId)
    if (current.loading && current.chatId === id) return
    setHistoryOpen(false)
    setDocumentsOpen(false)
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
    if (!chatId) return
    const cached = readForkBanner(chatId)
    if (!cached) return
    setForkBannerByChatId((prev) => (prev[chatId] ? prev : { ...prev, [chatId]: cached }))
  }, [chatId])

  useEffect(() => {
    if (!chatId) return
    const banner = forkBannerByChatId[chatId]
    if (!banner) return
    if (messages.length <= banner.baselineMessageCount) return
    clearForkBanner(chatId)
    setForkBannerByChatId((prev) => {
      if (!prev[chatId]) return prev
      const next = { ...prev }
      delete next[chatId]
      return next
    })
  }, [chatId, messages.length, forkBannerByChatId])

  const handleForkChat = useCallback(async () => {
    if (!selectedId || !chatId || forkingChat || loading || chatSessionLoading) return
    setForkingChat(true)
    // Let the fork button paint its spinner before the network request.
    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => resolve())
      })
    })
    try {
      const forked = await api.forkChat(chatId)
      const banner: ForkBannerState = {
        sourceChatId: forked.forked_from.chat_id,
        sourceTitle: forked.forked_from.title || 'New Chat',
        baselineMessageCount: messages.length,
      }
      writeForkBanner(forked.id, banner)
      setForkBannerByChatId((prev) => ({ ...prev, [forked.id]: banner }))
      await openChatById(selectedId, forked.id)
      await refreshChatHistory(selectedId)
    } catch (e) {
      patchSession(selectedId, {
        error: e instanceof Error ? e.message : 'Failed to fork conversation',
      })
    } finally {
      setForkingChat(false)
    }
  }, [
    selectedId,
    chatId,
    forkingChat,
    loading,
    chatSessionLoading,
    messages.length,
    openChatById,
    refreshChatHistory,
    patchSession,
  ])

  const handleDeleteChat = useCallback(
    async (id: string) => {
      if (!selectedId || deletingChatId) return
      const current = getAgentSession(sessionsRef.current, selectedId)
      const wasActive = current.chatId === id
      if (wasActive) {
        streamRegistryRef.current.abort(id)
      }

      setDeletingChatId(id)
      try {
        await api.deleteChat(id)
      } catch (e) {
        patchSession(selectedId, {
          error: e instanceof Error ? e.message : 'Failed to delete conversation',
        })
        throw e
      } finally {
        setDeletingChatId(null)
      }

      clearForkBanner(id)
      setForkBannerByChatId((prev) => {
        if (!prev[id]) return prev
        const next = { ...prev }
        delete next[id]
        return next
      })

      const remaining = current.chatHistory.filter((row) => row.id !== id)
      patchSession(selectedId, { chatHistory: remaining })

      if (!wasActive) return

      fulfillment.resetFetchKey()
      proposalFetchKeyRef.current = null
      const storedId = getStoredChatId(selectedId)
      if (id === storedId) {
        clearStoredChatId(selectedId)
      }
      if (remaining.length > 0 && storedId && storedId !== id) {
        const stillStored = remaining.some((row) => row.id === storedId)
        if (stillStored) {
          await openChatById(selectedId, storedId)
          return
        }
      }
      enterStandbyMode(selectedId)
      patchSession(selectedId, fulfillment.newChatPatch())
    },
    [
      selectedId,
      deletingChatId,
      enterStandbyMode,
      fulfillment,
      openChatById,
      patchSession,
    ],
  )

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
          <button
            type="button"
            className="sidebar-brand sidebar-brand-btn"
            aria-label="Home"
            title={sidebarCollapsed ? 'Home' : undefined}
            onClick={() => navigate('/')}
          >
            <img src="/cow.png" alt="" className="sidebar-brand-icon" />
            {!sidebarCollapsed && (
              <>
                <span className="sidebar-brand-agent">Agent</span>{' '}
                <span className="sidebar-brand-team">Team</span>
              </>
            )}
          </button>
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
            const active = agent.id === selectedId && !documentsOpen && !integrationsOpen
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
                  <AgentIcon slug={agent.slug} className="h-6 w-6 shrink-0" />
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

        <SidebarUtilityNav
          collapsed={sidebarCollapsed}
          documentsOpen={documentsOpen}
          integrationsOpen={integrationsOpen}
          onOpenDocuments={openDocuments}
          onOpenIntegrations={openIntegrations}
        />

        <div className="agent-sidebar-footer">
          {!sidebarCollapsed ? (
            <SidebarUserMenu user={user} collapsed={sidebarCollapsed} onLogout={logout} />
          ) : null}
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
        {documentsOpen ? (
          <DocumentsView
            onClose={() => setDocumentsOpen(false)}
            onOpenChat={(id) => void openHistoryChat(id)}
          />
        ) : integrationsOpen ? (
          <IntegrationsView onClose={() => setIntegrationsOpen(false)} />
        ) : showChat && selected ? (
          <div className={`chat-main-layout${isProposalComposer ? ' chat-main-layout-proposal' : ''}`}>
            <div className="chat-main-inner">
            <div className="chat-header">
              <div className="chat-header-brand">
                <span className="chat-header-icon-slot" aria-hidden>
                  <AgentIcon slug={selected.slug} className="chat-header-icon" />
                </span>
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
                    ) : isStandby ? (
                      <ChatStandbyPanel
                        agentName={formatAgentLabel(selected)}
                        agentDescription={selected.description}
                        lastChat={storedLastChat}
                        busy={chatSessionLoading}
                        onNewConversation={() => void startNewChat()}
                        onContinueLast={() => void continueLastConversation()}
                      />
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
                          onViewParsePipeline={handleViewParsePipeline}
                          onRetryAudioTranscript={chatId ? handleRetryAudioTranscript : undefined}
                          fulfillmentChatId={isYlWorker2 ? chatId : null}
                          fulfillmentForms={isYlWorker2 ? fulfillmentForms : []}
                          fulfillmentFormsLoading={isYlWorker2 ? fulfillmentFormsLoading : false}
                          fulfillmentFormsError={isYlWorker2 ? fulfillmentFormsError : null}
                          onFulfillmentFormsChange={isYlWorker2 ? fulfillment.setForms : undefined}
                          onForkChat={chatId ? () => void handleForkChat() : undefined}
                          forkingChat={forkingChat}
                          forkBanner={chatId ? forkBannerByChatId[chatId] ?? null : null}
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

                {warmupStatus === 'connecting' && !isStandby ? (
                  <div className="chat-composer-warmup">
                    <div className="chat-content-column">
                      <p className="chat-warmup-status">Connecting tools…</p>
                    </div>
                  </div>
                ) : null}

                <div className="chat-composer-wrap">
                  <div className="chat-content-column">
                    {!isStandby && chatId ? (
                      <div className="chat-composer-tools">
                        <button
                          type="button"
                          className="chat-transcribe-audio-btn"
                          disabled={loading || chatSessionLoading || captureSubmitting}
                          onClick={() => setTranscribePanelOpen(true)}
                        >
                          <Mic size={14} aria-hidden />
                          <span>Transcribe audio</span>
                        </button>
                      </div>
                    ) : null}
                    <TranscribeAudioPanel
                      open={transcribePanelOpen}
                      maxTotalBytes={AUDIO_CAPTURE_MAX_TOTAL_BYTES}
                      submitting={captureSubmitting}
                      onClose={() => setTranscribePanelOpen(false)}
                      onSubmit={handleSubmitAudioCapture}
                    />
                    <div
                      className={`chat-composer${composerDragOver ? ' chat-composer-drag-over' : ''}${isStandby ? ' chat-composer-standby' : ''}`}
                      onDragOver={isStandby ? undefined : handleComposerDragOver}
                      onDragLeave={isStandby ? undefined : handleComposerDragLeave}
                      onDrop={isStandby ? undefined : handleComposerDrop}
                    >
                      <input
                        ref={fileInputRef}
                        type="file"
                        multiple
                        className="hidden"
                        accept={composerAttachmentAccept}
                        onChange={(e) => void handleAttachmentSelected(e)}
                      />
                      <ComposerStagedChips
                        attachments={stagedAttachmentItems}
                        onRemove={removeStagedAttachment}
                        onChipClick={(att) => setParseDrawerAttachment(att)}
                        disabled={loading || chatSessionLoading || isStandby}
                      />
                      <div ref={composerMentionWrapRef} className="chat-composer-mention-wrap">
                        <AttachmentMentionPopup
                          open={mentionTrigger !== null}
                          anchorRef={composerMentionWrapRef}
                          query={mentionTrigger?.query ?? ''}
                          attachments={mentionFilteredAttachments}
                          loading={chatAttachmentsLoading}
                          highlightIndex={mentionHighlightIndex}
                          onQueryChange={updateMentionQuery}
                          onHighlightChange={setMentionHighlightIndex}
                          onSelect={insertAttachmentMention}
                          onClose={closeMentionPopup}
                        />
                        <ComposerMentionInput
                          textareaRef={textareaRef}
                          value={input}
                          attachments={readyChatAttachments}
                          placeholder={
                            isStandby
                              ? 'Choose an option above to start'
                              : 'Message… (type @ to reference attachments)'
                          }
                          disabled={loading || chatSessionLoading || isStandby}
                          onChange={handleComposerInputChange}
                          onSelect={handleComposerSelectionChange}
                          onPaste={(e) => handleComposerPaste(e)}
                          onKeyDown={(e) => {
                            if (e.nativeEvent.isComposing || e.keyCode === 229) {
                              return
                            }
                            if (mentionTrigger) {
                              if (e.key === 'Escape') {
                                e.preventDefault()
                                closeMentionPopup()
                                return
                              }
                              if (mentionFilteredAttachments.length > 0) {
                                if (e.key === 'ArrowDown') {
                                  e.preventDefault()
                                  setMentionHighlightIndex((index) =>
                                    Math.min(index + 1, mentionFilteredAttachments.length - 1),
                                  )
                                  return
                                }
                                if (e.key === 'ArrowUp') {
                                  e.preventDefault()
                                  setMentionHighlightIndex((index) => Math.max(index - 1, 0))
                                  return
                                }
                                if (e.key === 'Enter' && !e.shiftKey) {
                                  e.preventDefault()
                                  insertAttachmentMention(
                                    mentionFilteredAttachments[mentionHighlightIndex],
                                  )
                                  return
                                }
                                if (e.key === 'Tab') {
                                  e.preventDefault()
                                  insertAttachmentMention(
                                    mentionFilteredAttachments[mentionHighlightIndex],
                                  )
                                  return
                                }
                              }
                            }
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault()
                              if (composerCanSend) void send()
                            }
                          }}
                        />
                      </div>
                      <div className="chat-composer-footer">
                        <div className="chat-composer-left">
                          <button
                            type="button"
                            className="chat-composer-attach-btn"
                            disabled={loading || chatSessionLoading || isStandby}
                            onClick={handleAttachFilesClick}
                            aria-label="Upload attachment"
                            title="Upload attachment"
                          >
                            <Paperclip size={16} strokeWidth={1.75} aria-hidden="true" />
                          </button>
                          {selected?.supports_kb_scope ? (
                            <KbScopePopover
                              agentId={selected.id}
                              disabled={loading || chatSessionLoading || isStandby}
                            />
                          ) : null}
                          <ContextUsageIndicator usage={contextUsage} />
                        </div>
                        <div className="chat-composer-actions">
                          <ModelSelect
                            value={selectedModelId}
                            options={modelOptions}
                            onChange={handleModelChange}
                            disabled={loading || chatSessionLoading || agentsLoading}
                          />
                          <button
                            type="button"
                            onClick={() => (loading ? void stopStreaming() : void send())}
                            disabled={loading ? chatSessionLoading : !composerCanSend}
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
            <AttachmentParseDrawer
              attachment={parseDrawerAttachment}
              onClose={() => setParseDrawerAttachment(null)}
              onRetry={chatId ? handleRetryAttachmentParse : undefined}
            />
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
              deletingChatId={deletingChatId}
              onClose={() => setHistoryOpen(false)}
              onSelect={(id) => void openHistoryChat(id)}
              onDelete={handleDeleteChat}
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
