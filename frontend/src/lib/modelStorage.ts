const PREFIX = 'agent-platform:model:'

export function getStoredModelId(agentId: string): string | null {
  return localStorage.getItem(`${PREFIX}${agentId}`)
}

export function setStoredModelId(agentId: string, modelId: string): void {
  localStorage.setItem(`${PREFIX}${agentId}`, modelId)
}

export function clearStoredModelId(agentId: string): void {
  localStorage.removeItem(`${PREFIX}${agentId}`)
}
