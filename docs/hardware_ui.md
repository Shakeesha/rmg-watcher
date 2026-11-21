# Hardware UI

The kiosk UI is built for small landscape displays such as 800×480 and
1024×600. It is served by FastAPI from the static Vite bundle, so the Pi needs
no Node.js runtime after deployment.

## Layout

- **Top bar** — product mark and three view buttons: Live, Delays, Transfers.
- **Stop selector** — shown only in the Live view; remembers the last selected
  stop in local storage and defaults to `luisenplatz` when available.
- **Status banner** — connection, stale-data, database, pipeline, and mock-mode
  state. It refreshes its relative timestamp every 10 seconds.
- **Content area** — one view at a time with no page-level scrolling; long
  lists scroll inside the view.

## Views

| View | Content |
| --- | --- |
| Live | Next departures for the selected stop with expected time, scheduled time, countdown, and delay badge. |
| Delays | Punctuality, median delay, 95th-percentile delay, and the most delayed lines. |
| Transfers | Connection pairs ranked by projected slack, with at-risk connections highlighted. |

## Touch targets and focus

- All interactive controls are at least 64×64 px, except compact stop chips
  which are 52 px tall inside a 68 px bar.
- Every focusable control uses the global `:focus-visible` ring.
- Colour is never the only signal: status text and badges accompany the
  green/amber/red accents.

## Keyboard and hardware buttons

`frontend/src/lib/navigation.ts` installs one key handler for both a USB
keyboard and the optional GPIO-to-key bridge:

| Key | Action |
| --- | --- |
| Arrow keys | Move focus through controls marked `data-nav`. |
| Enter / Space | Activate the focused control. |
| PageDown | Next view. |
| PageUp | Previous view. |
| Escape | Return to the Live view. |

Buttons expose `data-nav` so the same handler works for touch targets and
physical buttons.

## Polling

The root component refreshes health, stops, metrics, and the selected stop's
departures every 15 seconds. The browser's online/offline events trigger an
immediate refresh when connectivity returns. Failed requests leave the last
known data visible and switch the status banner to an error state.

## GPIO bridge (optional)

`deploy/scripts/gpio_to_keys.py` creates a virtual keyboard with `evdev` and
uses `gpiozero` to watch five buttons. Wire each button between its BCM pin and
ground:

| BCM pin | Key | UI action |
| --- | --- | --- |
| 17 | Right | Focus the next control |
| 27 | Left | Focus the previous control |
| 22 | Enter | Activate the focused control |
| 23 | PageDown | Next view |
| 24 | PageUp | Previous view |

Install `python3-gpiozero` and `python3-evdev`, load the `uinput` module, and
grant the `input` group access to `/dev/uinput`. Then enable
`transit-gpio-nav.service`. See README.md for the exact commands.
