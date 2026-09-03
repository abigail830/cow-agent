const PREFIX = 'agent-platform:chat:'

export function getStoredChatId(agentId: string): string | null {
  return localStorage.getItem(`${PREFIX}${agentId}`)
}

export function setStoredChatId(agentId: string, chatId: string): void {
  localStorage.setItem(`${PREFIX}${agentId}`, chatId)
}

export function clearStoredChatId(agentId: string): void {
  localStorage.removeItem(`${PREFIX}${agentId}`)
}
