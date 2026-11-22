// Shared formatting helpers for the kiosk UI.

import {
  METRES_PER_KILOMETRE,
  MINUTES_PER_HOUR,
  SECONDS_PER_MINUTE,
} from './constants'

const timeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

export function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return timeFormatter.format(date)
}

export function formatDurationSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  const rounded = Math.round(seconds)
  if (rounded < SECONDS_PER_MINUTE) return `${rounded}s`
  const minutes = Math.floor(rounded / SECONDS_PER_MINUTE)
  const rest = rounded % SECONDS_PER_MINUTE
  return rest === 0 ? `${minutes}m` : `${minutes}m ${rest}s`
}

export function formatDistance(metres: number | null): string {
  if (metres === null) return ''
  if (metres < METRES_PER_KILOMETRE) return `${metres} m`
  return `${(metres / METRES_PER_KILOMETRE).toFixed(1)} km`
}

export function formatRelativeAge(seconds: number | null): string {
  if (seconds === null) return 'not loaded yet'
  if (seconds < 10) return 'just now'
  if (seconds < SECONDS_PER_MINUTE) return `${seconds}s ago`
  const minutes = Math.floor(seconds / SECONDS_PER_MINUTE)
  if (minutes < MINUTES_PER_HOUR) return `${minutes}m ago`
  const hours = Math.floor(minutes / MINUTES_PER_HOUR)
  return `${hours}h ago`
}

export function routeLabel(route: string | null, mode: string): string {
  if (!route) return mode === 'walk' ? 'Walk' : mode.toUpperCase()
  if (route.startsWith('route-')) return route.slice('route-'.length)
  if (!route.includes(':')) return route
  return route.split(':').at(-1)?.replace(/^_+/, '') || mode.toUpperCase()
}

export function transportIcon(mode: string | null): string {
  const value = (mode ?? '').toLowerCase()
  if (value.includes('bus') || value.includes('coach')) return '🚌'
  if (value.includes('tram') || value.includes('light_rail')) return '🚊'
  if (value.includes('rail') || value.includes('train')) return '🚆'
  if (value.includes('subway') || value.includes('metro')) return '🚇'
  if (value.includes('ferry')) return '⛴️'
  return '•'
}

export function transportLabel(mode: string | null): string {
  const value = (mode ?? '').toLowerCase()
  if (value.includes('bus') || value.includes('coach')) return 'Bus'
  if (value.includes('tram') || value.includes('light_rail')) return 'Tram'
  if (value.includes('rail') || value.includes('train')) return 'Train'
  if (value.includes('subway') || value.includes('metro')) return 'Subway'
  if (value.includes('ferry')) return 'Ferry'
  return 'Transit'
}
