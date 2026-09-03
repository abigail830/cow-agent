import { ProcessStepCard } from './ProcessStepCard'
import { MessageBubble } from './MessageBubble'
import { VizBubble } from './VizBubble'
import { ArtifactBubble } from './ArtifactBubble'
import { FulfillmentInlineBlock } from './fulfillment/FulfillmentInlineBlock'
import { groupMessages, shouldShowPendingIndicator, type ChatBlock } from '../lib/messageActivity'
import { isArtifactExpandedInSidePanel } from '../lib/artifactRegistry'
import { isProposalArtifact } from '../lib/artifactKinds'
import type { ArtifactSpec } from '../types/artifact'
import type { FulfillmentForm } from '../types/fulfillmentForms'
import type { Message } from '../types'

type Props = {
  messages: Message[]
  loading?: boolean
  turnSyncHint?: string | null
  proposalPanelOpen?: boolean
  expandedArtifactId?: string | null
  onExpandArtifact?: (spec: ArtifactSpec) => void
  fulfillmentChatId?: string | null
  fulfillmentForms?: FulfillmentForm[]
  fulfillmentFormsLoading?: boolean
  fulfillmentFormsError?: string | null
  onFulfillmentFormsChange?: (forms: FulfillmentForm[]) => void
}

function PendingIndicator({ hint }: { hint?: string | null }) {
  return (
    <div
      className="chat-pending-row"
      aria-live="polite"
      aria-label={hint ?? 'Assistant is working'}
    >
      <span className="chat-pending-dot" />
      {hint ? <span className="chat-pending-hint">{hint}</span> : null}
    </div>
  )
}

function isArtifactExpanded(
  spec: ArtifactSpec,
  proposalPanelOpen?: boolean,
  expandedArtifactId?: string | null,
): boolean {
  if (isArtifactExpandedInSidePanel(spec, expandedArtifactId)) return true
  if (proposalPanelOpen && isProposalArtifact(spec)) return true
  return false
}

function latestProposeFulfillmentBlockId(blocks: ChatBlock[]): string | null {
  for (let i = blocks.length - 1; i >= 0; i -= 1) {
    const block = blocks[i]
    if (block.kind === 'process' && block.item.title === 'propose_fulfillment_forms') {
      return block.id
    }
  }
  return null
}

function renderBlock(
  block: ChatBlock,
  proposalPanelOpen?: boolean,
  expandedArtifactId?: string | null,
  onExpandArtifact?: (spec: ArtifactSpec) => void,
) {
  if (block.kind === 'bubble') {
    return <MessageBubble message={block.message} />
  }
  if (block.kind === 'viz') {
    return (
      <div className="chat-viz-row">
        <VizBubble spec={block.spec} />
      </div>
    )
  }
  if (block.kind === 'artifact') {
    return (
      <div className="chat-artifact-row">
        <ArtifactBubble
          spec={block.spec}
          createdAt={block.createdAt}
          expanded={isArtifactExpanded(block.spec, proposalPanelOpen, expandedArtifactId)}
          onExpand={onExpandArtifact}
        />
      </div>
    )
  }
  return (
    <div className="chat-process-row">
      <ProcessStepCard item={block.item} />
    </div>
  )
}

export function ChatMessageList({
  messages,
  loading = false,
  turnSyncHint = null,
  proposalPanelOpen = false,
  expandedArtifactId = null,
  onExpandArtifact,
  fulfillmentChatId = null,
  fulfillmentForms = [],
  fulfillmentFormsLoading = false,
  fulfillmentFormsError = null,
  onFulfillmentFormsChange,
}: Props) {
  const blocks = groupMessages(messages, { streaming: loading })
  const showPending = shouldShowPendingIndicator(loading, messages)
  const showSyncStatus = Boolean(turnSyncHint)
  const proposeBlockId = latestProposeFulfillmentBlockId(blocks)
  const showInlineFulfillment =
    Boolean(fulfillmentChatId) &&
    Boolean(onFulfillmentFormsChange) &&
    (fulfillmentForms.length > 0 || fulfillmentFormsLoading || Boolean(fulfillmentFormsError))

  return (
    <div className="chat-timeline">
      {blocks.map((block, index) => {
        const key = block.kind === 'bubble' ? block.message.id : `${block.kind}-${block.id}-${index}`
        const node = renderBlock(block, proposalPanelOpen, expandedArtifactId, onExpandArtifact)

        const attachAfter =
          showInlineFulfillment &&
          proposeBlockId != null &&
          block.kind === 'process' &&
          block.id === proposeBlockId

        if (!attachAfter || !fulfillmentChatId || !onFulfillmentFormsChange) {
          return <div key={key}>{node}</div>
        }

        return (
          <div key={key} className="chat-process-with-fulfillment">
            {node}
            <div className="chat-fulfillment-row">
              <FulfillmentInlineBlock
                chatId={fulfillmentChatId}
                forms={fulfillmentForms}
                loading={fulfillmentFormsLoading}
                error={fulfillmentFormsError}
                onFormsChange={onFulfillmentFormsChange}
              />
            </div>
          </div>
        )
      })}

      {showInlineFulfillment &&
      proposeBlockId == null &&
      fulfillmentChatId &&
      onFulfillmentFormsChange ? (
        <div key="fulfillment-fallback" className="chat-fulfillment-row">
          <FulfillmentInlineBlock
            chatId={fulfillmentChatId}
            forms={fulfillmentForms}
            loading={fulfillmentFormsLoading}
            error={fulfillmentFormsError}
            onFormsChange={onFulfillmentFormsChange}
          />
        </div>
      ) : null}

      {(showPending || showSyncStatus) && (
        <PendingIndicator hint={showSyncStatus ? turnSyncHint : null} />
      )}
    </div>
  )
}
