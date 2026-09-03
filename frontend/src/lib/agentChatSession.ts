import type { ProposalPanelTab } from '../components/ProposalPanelShell'
import type { PendingAttachment } from './attachments'
import type { TurnSyncPhase } from './turnSync'
import type { ArtifactSpec } from '../types/artifact'
import type { ProposalPreview } from '../types/proposalPreview'
import type { FulfillmentForm } from '../types/fulfillmentForms'
import type { ChatSummary, Message } from '../types'

export type AgentChatSession = {
  agentId: string
  /** Whether loadChat has completed at least once for this agent. */
  initialized: boolean
  chatId: string | null
  messages: Message[]
  input: string
  pendingAttachments: PendingAttachment[]
  loading: boolean
  activeRunId: string | null
  chatSessionLoading: boolean
  chatHistory: ChatSummary[]
  chatHistoryLoading: boolean
  error: string | null
  turnSyncPhase: TurnSyncPhase | null
  proposalTurnSyncing: boolean
  expandedArtifact: ArtifactSpec | null
  proposalPanelCollapsed: boolean
  proposalPanelTab: ProposalPanelTab
  proposalPreview: ProposalPreview | null
  proposalPreviewLoading: boolean
  proposalPreviewError: string | null
  proposalState: Record<string, unknown> | null
  proposalStateFingerprint: string | null
  proposalStateLoading: boolean
  proposalStateError: string | null
  fulfillmentForms: FulfillmentForm[]
  fulfillmentFormsLoading: boolean
  fulfillmentFormsError: string | null
}

export function createEmptyAgentSession(agentId: string): AgentChatSession {
  return {
    agentId,
    initialized: false,
    chatId: null,
    messages: [],
    input: '',
    pendingAttachments: [],
    loading: false,
    activeRunId: null,
    chatSessionLoading: false,
    chatHistory: [],
    chatHistoryLoading: false,
    error: null,
    turnSyncPhase: null,
    proposalTurnSyncing: false,
    expandedArtifact: null,
    proposalPanelCollapsed: true,
    proposalPanelTab: 'preview',
    proposalPreview: null,
    proposalPreviewLoading: false,
    proposalPreviewError: null,
    proposalState: null,
    proposalStateFingerprint: null,
    proposalStateLoading: false,
    proposalStateError: null,
    fulfillmentForms: [],
    fulfillmentFormsLoading: false,
    fulfillmentFormsError: null,
  }
}

export function getAgentSession(
  sessions: Record<string, AgentChatSession>,
  agentId: string | null,
): AgentChatSession {
  if (!agentId) return createEmptyAgentSession('')
  return sessions[agentId] ?? createEmptyAgentSession(agentId)
}
