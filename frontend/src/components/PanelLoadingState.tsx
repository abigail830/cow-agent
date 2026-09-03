import { LoadingSpinner } from './LoadingSpinner'

type Props = {
  message: string
  className?: string
}

export function PanelLoadingState({ message, className = '' }: Props) {
  return (
    <div
      className={`panel-loading-state${className ? ` ${className}` : ''}`}
      aria-live="polite"
      aria-label={message}
    >
      <LoadingSpinner size="lg" />
      <p className="panel-loading-caption">{message}</p>
    </div>
  )
}
