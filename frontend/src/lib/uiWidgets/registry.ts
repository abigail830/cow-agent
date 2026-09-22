import type { ReactNode } from 'react'
import type { Message, TimelineItem } from '../../types'

export type UiAnnotation = {
  kind: string
  ref: string
  display: Record<string, unknown>
  anchor_message_id?: string | null
}

export type UiWidgetProps = {
  annotation: UiAnnotation
}

export type UiWidget = {
  kind: string
  /** Optional: convert annotation timeline item to legacy Message for groupMessages. */
  toMessage?: (ctx: { item: Extract<TimelineItem, { kind: 'ui_annotation' }>; chatId: string }) => Message | null
  render?: (props: UiWidgetProps) => ReactNode
}

const widgets = new Map<string, UiWidget>()

export function registerUiWidget(widget: UiWidget): void {
  widgets.set(widget.kind, widget)
}

export function getUiWidget(kind: string): UiWidget | undefined {
  return widgets.get(kind)
}
