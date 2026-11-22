// Shared numeric constants for the kiosk UI.

export const MILLISECONDS_PER_SECOND = 1000
export const SECONDS_PER_MINUTE = 60
export const MILLISECONDS_PER_MINUTE = SECONDS_PER_MINUTE * MILLISECONDS_PER_SECOND
export const MINUTES_PER_HOUR = 60

export const FAVOURITE_LABEL_SEPARATOR = ' → '
export const STATUS_CANCELLED = 'cancelled'
export const METRES_PER_KILOMETRE = 1000

export const DEFAULT_DEPARTURE_LIMIT = 20
export const DEFAULT_CONNECTION_LIMIT = 3
export const DEFAULT_NEARBY_RADIUS_M = 1000

export const AUTOCOMPLETE_DEBOUNCE_MS = 250
export const GEOLOCATION_TIMEOUT_MS = 5000
export const GEOLOCATION_MAX_AGE_MS = 300_000

export const QUICK_OFFSET_FIFTEEN_MIN = 15
export const QUICK_OFFSET_ONE_HOUR_MIN = MINUTES_PER_HOUR

// Local schematic map geometry (SVG viewBox units).
export const MAP_MARGIN_X = 30
export const MAP_PLOT_SIZE = 260
export const MAP_BASELINE_Y = 290
export const MAP_TOP_Y = 30
export const MAP_RIGHT_X = 290
export const MAP_VIEWBOX_SIZE = 320
export const MIN_COORD_SPAN = 0.0005
export const MAX_MAP_STOPS = 12
