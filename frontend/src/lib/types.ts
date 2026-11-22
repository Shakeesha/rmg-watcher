// TypeScript interfaces matching the FastAPI response schemas.

export type View = 'live' | 'delays' | 'connections' | 'alerts'

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
  mode: string | null
}

export interface NearbyStop extends Stop {
  distance_m: number | null
  mode: string | null
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
  mode: string | null
  wheelchair_accessible: boolean | null
}

export interface RouteDelay {
  route_id: string
  route_short_name: string | null
  max_delay_seconds: number
}

export interface TransferRisk {
  stop_id: string
  stop_name: string | null
  inbound_route_id: string
  outbound_route_id: string
  inbound_route_name: string | null
  outbound_route_name: string | null
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

export interface ConnectionStop {
  name: string
  arrival: string | null
  departure: string | null
  platform: string | null
}

export interface ConnectionLeg {
  mode: string
  route_id: string | null
  route: string | null
  route_color: string | null
  headsign: string | null
  operator: string | null
  from_name: string
  to_name: string
  from_platform: string | null
  to_platform: string | null
  departure: string
  arrival: string
  intermediate_stops: ConnectionStop[]
}

export interface Connection {
  departure: string
  arrival: string
  duration_minutes: number
  transfers: number
  legs: ConnectionLeg[]
}

export interface ServiceAlert {
  code: string
  header: string
  description: string
  severity: string
  url: string | null
  routes: string[]
  stop_id: string | null
}

export interface PlaceResult {
  id: string
  name: string
  latitude: number
  longitude: number
  type: string
  mode: string | null
}

export interface FavouriteConnection {
  from: string
  to: string
  label: string
}
