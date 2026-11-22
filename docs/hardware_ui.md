# Hardware UI

The kiosk is built for the attached **Raspberry Pi Touch Display 2 (5",
portrait)** at **720×1280**. It is a DSI display with a five-finger capacitive
touch panel; its power lead uses the GPIO header, so no GPIO pins are available
for navigation buttons. The UI is served by FastAPI from the static Vite bundle,
so the Pi needs no Node.js runtime after deployment.

## Layout

- **Top bar** — product mark and three touch buttons: Live, Delays, Transfers.
- **Stop selector** — shown only in the Live view; remembers the last selected
  stop in local storage and defaults to `luisenplatz` when available.
- **Status banner** — connection, stale-data, database, pipeline, and mock-mode
  state. It refreshes its relative timestamp every 10 seconds.
- **Content area** — one view at a time with no page-level scrolling; long
  lists scroll inside the view. The portrait height gives room for several rows.

## Views

| View | Content |
| --- | --- |
| Live | Search, suggested stops, a local schematic map, transport icons, and a departures/arrivals toggle with delay badges. |
| Delays | Punctuality, median delay, 95th-percentile delay, and the most delayed lines. |
| Transfers | Connection pairs ranked by projected slack, with at-risk connections highlighted. |
| Connections | From/To swap, date/time or quick chips, favourites, route bars, and expandable intermediate stops with platforms. |
| Alerts | Cached service alerts for nearby stops. |

## Touch targets and focus

- All interactive controls are at least 64×64 px, except compact stop chips
  which are 52 px tall inside a 68 px bar.
- Every focusable control uses the global `:focus-visible` ring, which also
  gives visual feedback after a tap.
- Colour is never the only signal: status text and badges accompany the
  green/amber/red accents.

## Input model

The device is operated by touch. `frontend/src/lib/navigation.ts` also keeps a
keyboard handler for development and debugging; it is not tied to any physical
buttons on the device.

| Key | Action (debug only) |
| --- | --- |
| Arrow keys | Move focus through controls marked `data-nav`. |
| Enter / Space | Activate the focused control. |
| PageDown | Next view. |
| PageUp | Previous view. |
| Escape | Return to the Live view. |

The three view buttons, stop chips, and any focused control are all reachable
with a finger. There is no GPIO navigation service in the deployment.

## Polling

The root component refreshes health, stops, metrics, and the selected stop's
departures every 15 seconds. The browser's online/offline events trigger an
immediate refresh when connectivity returns. Failed requests leave the last
known data visible and switch the status banner to an error state.
