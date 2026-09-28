import type { Agent } from '../types'

const PREFIX = 'agent-platform:nav-agent:'

export function stashNavAgent(agent: Agent): void {
  try {
    sessionStorage.setItem(`${PREFIX}${agent.id}`, JSON.stringify(agent))
  } catch {
    /* ignore */
  }
}

export function readNavAgent(agentId: string): Agent | null {
  try {
    const raw = sessionStorage.getItem(`${PREFIX}${agentId}`)
    if (!raw) return null
    return JSON.parse(raw) as Agent
  } catch {
    return null
  }
}

export function mergeAgentIntoList(agents: Agent[], incoming: Agent): Agent[] {
  const index = agents.findIndex((item) => item.id === incoming.id)
  if (index < 0) return [...agents, incoming]
  return agents.map((item, i) => (i === index ? { ...item, ...incoming } : item))
}
