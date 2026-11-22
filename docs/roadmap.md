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
- Accessibility information, seat reservation, and ticket purchase.
- Station information and on-site facilities.

### HEAG mobilo

- Local trip planning, live vehicle positions, and a map view.
- **Störungsmelder** service alerts filterable by line and date.
- Tickets: Deutschlandticket, Schülerticket, Jobticket.
- Barrier-free travel information.
- AirLiner airport connection and regional tram extensions.
- Construction/project notices.

## Proposed features

| Priority | Feature | Notes |
| --- | --- | --- |
| 1 | **Service alerts view** | Reuse HEAG's "Aktuelle Meldungen" with line/date filters. Cache once per hour; render as a compact list in a new view. |
| 1 | **Platform/track display** | MOTIS `place.track` already exists in stoptimes; show it beside each departure. |
| 1 | **Favourite connections** | Store from/to pairs in local storage; one tap re-runs a cached connection search. |
| 2 | **Date/time picker for connections** | Add "depart at" input instead of always searching from now. Reuse the 15-minute cache bucket. |
| 2 | **Disruption-aware transfer risk** | Join service alerts to affected route IDs before scoring transfer slack. |
| 2 | **Vehicle position map** | Use `GET /api/v6/map/trips` for the bounding box; cache frames every 60 s. Heavy — coordinate with Transitous first. |
| 3 | **Accessibility filter** | Surface `wheelchairAccessible` and `bikesAllowed` from MOTIS stop times. |
| 3 | **Offline timetable cache** | Store static GTFS for the watched stops so the UI still shows scheduled times during outages. |
| 3 | **Ticket link-out** | Deep-link to DB/HEAG ticket apps; do not handle payments on the kiosk. |
| 4 | **Push-style alerts** | Promote cancellations and severe delays into the status banner. |

## Constraints

- No feature may introduce uncapped polling. All new endpoints must use the
  disk cache and the existing daily request counters.
- Ticket purchase, account login, and personal data are out of scope for a
  shared kiosk.
- Anything using `/plan`, `/one-to-many`, or `/one-to-all` must stay under the
  Transitous resource policy; see <https://transitous.org/api/>.
