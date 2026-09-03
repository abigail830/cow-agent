import type { Agent } from '../types'

export function formatAgentLabel(agent: Agent): string {
  return agent.name.trim() || agent.slug || agent.id
}
