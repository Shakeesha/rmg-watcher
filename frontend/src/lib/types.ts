// TypeScript interfaces matching the FastAPI response schemas.

export type View = 'live' | 'delays' | 'transfers'

export interface HealthResponse {
  status: string
  database_ok: boolean
  mock_mode: boolean
  version: string
  stop_count: number
  event_count: number
  last_run_at: string | null
  last_run_status: string | null
}

export interface Stop {
  stop_id: string
  name: string
  latitude: number | null
  longitude: number | null
}

export interface Departure {
  trip_id: string
  route_id: string
  route_short_name: string
  stop_id: string
  stop_name: string
  scheduled_time: string
  expected_time: string | null
  delay_seconds: number | null
  delay_category: string
  status: string
}

export interface RouteDelay {
  route_id: string
  max_delay_seconds: number
}

export interface TransferRisk {
  stop_id: string
  inbound_route_id: string
  outbound_route_id: string
  scheduled_transfer_seconds: number
  projected_slack_seconds: number
  at_risk: boolean
}

export interface Metrics {
  total_events: number
  punctuality_rate: number
  median_delay_seconds: number | null
  p95_delay_seconds: number | null
  top_delayed_routes: RouteDelay[]
  transfer_risks: TransferRisk[]
}
