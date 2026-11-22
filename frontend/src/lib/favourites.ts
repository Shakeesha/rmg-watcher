// Favourite connections persisted in the browser.

import type { FavouriteConnection } from './types'

const STORAGE_KEY = 'transit-kiosk-favourites'

export function loadFavourites(): FavouriteConnection[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (item): item is FavouriteConnection =>
        typeof item === 'object' &&
        item !== null &&
        typeof item.from === 'string' &&
        typeof item.to === 'string' &&
        typeof item.label === 'string',
    )
  } catch {
    return []
  }
}

export function saveFavourites(favourites: FavouriteConnection[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(favourites))
  } catch {
    // Storage can be unavailable in locked-down kiosk browsers.
  }
}
