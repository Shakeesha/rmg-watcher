// Typed fetch client for /api/health, /api/departures, and /api/metrics.

import type {
  Connection,
  Departure,
  HealthResponse,
  Metrics,
  NearbyStop,
  Stop,
} from './types'

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

export function fetchNearbyStops(
  stopId: string,
  signal?: AbortSignal,
  radius = 1000,
): Promise<NearbyStop[]> {
  const path = `/stops/nearby/${encodeURIComponent(stopId)}?radius=${radius}`
  return getJson<NearbyStop[]>(path, signal)
}

export function fetchLiveDepartures(
  stopId: string,
  signal?: AbortSignal,
  limit = 20,
): Promise<Departure[]> {
  const path = `/departures/live/${encodeURIComponent(stopId)}?limit=${limit}`
  return getJson<Departure[]>(path, signal)
}

export function fetchConnections(
  fromStop: string,
  toStop: string,
  signal?: AbortSignal,
  limit = 3,
): Promise<Connection[]> {
  const query = new URLSearchParams({
    from: fromStop,
    to: toStop,
    limit: String(limit),
  })
  return getJson<Connection[]>(`/connections?${query.toString()}`, signal)
}

export function fetchMetrics(signal?: AbortSignal): Promise<Metrics> {
  return getJson<Metrics>('/metrics', signal)
}
