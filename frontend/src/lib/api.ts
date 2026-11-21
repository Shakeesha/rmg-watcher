// Typed fetch client for /api/health, /api/departures, and /api/metrics.

import type { Departure, HealthResponse, Metrics, Stop } from './types'

const API_BASE = '/api'

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: 'application/json' },
    signal,
  })

  if (!response.ok) {
    throw new Error(`API ${response.status}: ${response.statusText}`)
  }

  return (await response.json()) as T
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson<HealthResponse>('/health', signal)
}

export function fetchStops(signal?: AbortSignal): Promise<Stop[]> {
  return getJson<Stop[]>('/stops', signal)
}

export function fetchDepartures(
  stopId: string,
  signal?: AbortSignal,
  limit = 20,
): Promise<Departure[]> {
  const path = `/departures/${encodeURIComponent(stopId)}?limit=${limit}`
  return getJson<Departure[]>(path, signal)
}

export function fetchMetrics(signal?: AbortSignal): Promise<Metrics> {
  return getJson<Metrics>('/metrics', signal)
}
