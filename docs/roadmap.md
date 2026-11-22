# Roadmap

Planned work, informed by the feature sets of the **DB Navigator** app and the
**HEAG mobilo** app. The kiosk remains a lightweight, touch-only device: every
feature below must fit the 720×1280 portrait display and the Transitous usage
policy.

## Reference features

### DB Navigator

- Journey planning with live delays, cancellations, and platform changes.
- Saved/favourite connections and recent searches.
- Disruption messages with alternative routes.
- Timetable lookups and line/route maps.
- Station information and on-site facilities.

### HEAG mobilo

- Local trip planning, live vehicle positions, and a map view.
- **Störungsmelder** service alerts filterable by line and date.
- AirLiner airport connection and regional tram extensions.
- Construction/project notices.

## Implemented

- Nearby stop search, mode icons, and a local schematic map without tiles
- Departures/Arrivals toggle via MOTIS `arriveBy`
- Favourite connections with one-tap replay
- Date/time picker with departure/arrival mode and quick chips
- Route bars, platforms, operator, and expandable intermediate stops
- Service alerts from cached MOTIS stop-time alerts

## Remaining features

| Priority | Feature | Notes |
| --- | --- | --- |
| 2 | **Disruption-aware transfer risk** | Join service alerts to affected route IDs before scoring transfer slack. |
| 3 | **Accessibility filter** | Surface `wheelchairAccessible` from MOTIS stop times. |
| 3 | **Offline timetable cache** | Store static GTFS for suggested stops so scheduled times survive outages. |
| 4 | **Push-style alerts** | Promote cancellations and severe delays into the status banner. |

Out of scope: ticket purchase, account login, personal profiles, bike/scooter
booking, and external map tiles.

## Constraints

- No feature may introduce uncapped polling. All new endpoints must use the
  disk cache and the existing daily request counters.
- Ticket purchase, account login, and personal data are out of scope for a
  shared kiosk.
- Anything using `/plan`, `/one-to-many`, or `/one-to-all` must stay under the
  Transitous resource policy; see <https://transitous.org/api/>.
