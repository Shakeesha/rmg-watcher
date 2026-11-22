// Unified touch and hardware-button focus/view controller.

import { writable } from 'svelte/store'
import type { View } from './types'

export const VIEWS: View[] = ['live', 'delays', 'connections', 'alerts']

export const viewLabels: Record<View, string> = {
  live: 'Live',
  delays: 'Delays',
  connections: 'Connections',
  alerts: 'Alerts',
}

export const activeView = writable<View>('live')

export function setView(view: View): void {
  activeView.set(view)
}

export function cycleView(direction: 1 | -1): void {
  activeView.update((current) => {
    const index = VIEWS.indexOf(current)
    return VIEWS[(index + direction + VIEWS.length) % VIEWS.length]
  })
}

function focusableElements(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('[data-nav]')).filter(
    (element) => element.offsetParent !== null && !element.hasAttribute('disabled'),
  )
}

export function focusNext(direction: 1 | -1): void {
  const elements = focusableElements()
  if (elements.length === 0) return

  const currentIndex = elements.indexOf(document.activeElement as HTMLElement)
  const nextIndex =
    currentIndex === -1
      ? direction === 1
        ? 0
        : elements.length - 1
      : (currentIndex + direction + elements.length) % elements.length

  elements[nextIndex]?.focus()
}

export function activateFocused(): void {
  if (document.activeElement instanceof HTMLElement) {
    document.activeElement.click()
  }
}

export function installNavigation(): () => void {
  const handler = (event: KeyboardEvent) => {
    switch (event.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        event.preventDefault()
        focusNext(1)
        break
      case 'ArrowLeft':
      case 'ArrowUp':
        event.preventDefault()
        focusNext(-1)
        break
      case 'Enter':
      case ' ':
        if (document.activeElement instanceof HTMLButtonElement) {
          return
        }
        event.preventDefault()
        activateFocused()
        break
      case 'PageDown':
        event.preventDefault()
        cycleView(1)
        break
      case 'PageUp':
        event.preventDefault()
        cycleView(-1)
        break
      case 'Escape':
        setView('live')
        break
    }
  }

  window.addEventListener('keydown', handler)
  return () => window.removeEventListener('keydown', handler)
}
