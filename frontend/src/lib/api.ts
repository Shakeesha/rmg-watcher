// Typed fetch client for /api/health, /api/departures, and /api/metrics.

import type {
  Connection,
  Departure,
  HealthResponse,
  Metrics,
  NearbyStop,
  PlaceResult,
  ServiceAlert,
  Stop,
} from './types'
import {
  DEFAULT_CONNECTION_LIMIT,
  DEFAULT_DEPARTURE_LIMIT,
  DEFAULT_NEARBY_RADIUS_M,
} from './constants'

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
  limit = DEFAULT_DEPARTURE_LIMIT,
): Promise<Departure[]> {
  const path = `/departures/${encodeURIComponent(stopId)}?limit=${limit}`
  return getJson<Departure[]>(path, signal)
}

export function fetchNearbyStops(
  stopId: string,
  signal?: AbortSignal,
  radius = DEFAULT_NEARBY_RADIUS_M,
): Promise<NearbyStop[]> {
  const path = `/stops/nearby/${encodeURIComponent(stopId)}?radius=${radius}`
  return getJson<NearbyStop[]>(path, signal)
}

export function fetchLiveDepartures(
  stopId: string,
  signal?: AbortSignal,
  limit = DEFAULT_DEPARTURE_LIMIT,
  arriveBy = false,
): Promise<Departure[]> {
  const path = `/departures/live/${encodeURIComponent(stopId)}?limit=${limit}&arrive_by=${arriveBy}`
  return getJson<Departure[]>(path, signal)
}

export function fetchSuggestedStops(
  signal?: AbortSignal,
  lat?: number,
  lon?: number,
): Promise<NearbyStop[]> {
  const query = new URLSearchParams()
  if (lat !== undefined && lon !== undefined) {
    query.set('lat', String(lat))
    query.set('lon', String(lon))
  }
  const suffix = query.toString()
  return getJson<NearbyStop[]>(`/stops/suggested${suffix ? `?${suffix}` : ''}`, signal)
}

export function resolvePlace(id: string, signal?: AbortSignal): Promise<PlaceResult | null> {
  return getJson<PlaceResult | null>(
    `/places/resolve?id=${encodeURIComponent(id)}`,
    signal,
  )
}

export function fetchPlaces(
  query: string,
  signal?: AbortSignal,
): Promise<PlaceResult[]> {
  return getJson<PlaceResult[]>(
    `/places?q=${encodeURIComponent(query)}`,
    signal,
  )
}

export function fetchAlerts(signal?: AbortSignal): Promise<ServiceAlert[]> {
  return getJson<ServiceAlert[]>('/alerts', signal)
}

export function fetchConnections(
  fromStop: string,
  toStop: string,
  signal?: AbortSignal,
  limit = DEFAULT_CONNECTION_LIMIT,
  time?: string,
  arriveBy = false,
): Promise<Connection[]> {
  const query = new URLSearchParams({
    from: fromStop,
    to: toStop,
    limit: String(limit),
    arrive_by: String(arriveBy),
  })
  if (time) {
    const parsed = new Date(time)
    query.set(
      'time',
      Number.isNaN(parsed.getTime()) ? time : parsed.toISOString(),
    )
  }
  return getJson<Connection[]>(`/connections?${query.toString()}`, signal)
}

export function fetchMetrics(signal?: AbortSignal): Promise<Metrics> {
  return getJson<Metrics>('/metrics', signal)
}
