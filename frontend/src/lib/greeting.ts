import type { User } from '../types'

function timeOfDayGreeting(date = new Date()): string {
  const hour = date.getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

export function userFirstName(user: User): string {
  const name = user.name?.trim()
  if (name) return name.split(/\s+/)[0] ?? name
  const local = user.email.split('@')[0]?.trim()
  return local || 'there'
}

export function greetingForUser(user: User, date = new Date()): string {
  return `${timeOfDayGreeting(date)}, ${userFirstName(user)}`
}
