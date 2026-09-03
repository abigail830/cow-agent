export type TurnSyncPhase = 'saving-messages' | 'updating-preview' | 'refreshing-draft'

export function turnSyncStatusLabel(phase: TurnSyncPhase | null): string | null {
  if (!phase) return null
  switch (phase) {
    case 'saving-messages':
      return 'Saving conversation…'
    case 'updating-preview':
      return 'Updating proposal preview…'
    case 'refreshing-draft':
      return 'Refreshing draft…'
    default:
      return null
  }
}
