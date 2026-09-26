type Props = {
  agentName: string
  agentDescription: string | null
}

export function ChatStandbyPanel({ agentName, agentDescription }: Props) {
  return (
    <div className="chat-standby-panel">
      <div className="chat-standby-inner">
        <h2 className="chat-standby-greeting">Hi, I&apos;m {agentName}</h2>
        {agentDescription ? (
          <p className="chat-standby-description">{agentDescription}</p>
        ) : (
          <p className="chat-standby-description">What would you like to work on?</p>
        )}
      </div>
    </div>
  )
}
