// Shared numeric constants for the kiosk UI.

// Time and distance units
export const MILLISECONDS_PER_SECOND = 1000
export const SECONDS_PER_MINUTE = 60
export const MILLISECONDS_PER_MINUTE = SECONDS_PER_MINUTE * MILLISECONDS_PER_SECOND
export const MINUTES_PER_HOUR = 60
export const METRES_PER_KILOMETRE = 1000

// Labels and status values
export const FAVOURITE_LABEL_SEPARATOR = ' → '
export const STATUS_CANCELLED = 'cancelled'
export const DELAY_CATEGORY_SEVERE = 'severe'

// Default limits
export const DEFAULT_DEPARTURE_LIMIT = 20
export const DEFAULT_CONNECTION_LIMIT = 3
export const DEFAULT_NEARBY_RADIUS_M = 1000

// Autocomplete and geolocation
export const AUTOCOMPLETE_DEBOUNCE_MS = 250
export const GEOLOCATION_TIMEOUT_MS = 5000
export const GEOLOCATION_MAX_AGE_MS = 300_000

// Connection time chips
export const QUICK_OFFSET_FIFTEEN_MIN = 15
export const QUICK_OFFSET_ONE_HOUR_MIN = MINUTES_PER_HOUR

// Cached raster map geometry
export const MAX_MAP_STOPS = 12
export const MAP_ZOOM = 16
export const TILE_SIZE_PX = 256
export const TILE_GRID_RADIUS = 1
export const MAP_BOTTOM_SHEET_LIMIT = 3
