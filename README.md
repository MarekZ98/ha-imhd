# iMHD Departures

Home Assistant custom integration with live public transport departures from [imhd.sk](https://imhd.sk)
for several stops of any iMHD city, plus a bundled Lovelace card `custom:imhd-departures-card`.
Departures are pushed live over the iMHD board socket (one connection per stop). Live boards exist only for
selected cities; a stop iMHD refuses shows the status `unavailable`.

## Install

- **HACS:** HACS → Integrations → ⋮ → Custom repositories → add `https://github.com/MarekZ98/ha-imhd`
  (category *Integration*), install **iMHD Departures**, restart Home Assistant.
- **Manual:** copy `custom_components/imhd` into your `config/custom_components/` folder and restart.

The card is served by the integration and loaded on every dashboard automatically (no resource to add).

## Configure

1. Settings → Devices & services → Add integration → **iMHD Departures**.
2. Either paste a board link from imhd.sk (open *Online zastávková tabuľa*, choose stops, copy the URL, e.g.
   `https://imhd.sk/ba/online-zastavkova-tabula?st=83;270`) and name each stop,
   or pick the city, search a stop by name and choose it.
3. One entry per city (max 8 stops). Adding stops of a configured city extends that entry.

Options (Configure): add stops by link or search, edit a stop (name, walk time in minutes, line filter such as
`30, N33` — empty = all lines), remove stops.

Walk time = minutes from home to the stop (set by hand, no GPS). The card uses it twice: departures you cannot catch
(minutes < walk time) are dimmed or hidden, and a line + direction that leaves from several of your stops is shown
only from the stop with the shortest walk (`nearest_only`). Stops with the same walk time (also all 0) all stay.

## Entity

One sensor per stop, e.g. `sensor.imhd_hodzovo_namestie`: state = time of the next departure (timestamp).
Attributes: `departures` (up to 10: `line`, `mode`, `destination`, `departs_at`, `scheduled_at`, `realtime`,
`delay_min`, `platform`, `platform_label`, `color`, `text_color`), `status` (`live` / `connecting` / `unavailable`), `last_live`, `stop_id`, `stop_name`,
`city`, `walk_min`, `lines`.
Departures are shown only while the board is live (a push younger than 2 minutes).
`platform_label` (the letter shown at the stop, e.g. `A`) and the line colors come from imhd.sk, refreshed daily.

## Card

```yaml
type: custom:imhd-departures-card
title: MHD                  # optional, default "MHD"
subtitle: stihneš len tie, čo sú tu  # optional, short text on the right of the title (merged)
layout: merged              # merged (default) | stack | columns (stops side by side)
rows: 6                     # merged: total rows (default 6); stack/columns: per stop (default 3)
clock_after: 60             # from this many minutes on show the clock time ("00:47") instead of "N min"
language: sk                # optional: sk | en (default: the Home Assistant language)
hide_missed: false          # true = hide departures you cannot catch (minutes < walk_min)
nearest_only: true          # merged: a line + direction from several stops only from the one with the shortest walk
show_walk: true             # merged: "4 min pešo" on the second line (stops with a walk time > 0)
badge: line                 # line (iMHD / mode colors, default) | neutral (theme colors)
entities:
  - sensor.imhd_hodzovo_namestie
  - entity: sensor.imhd_kamenne_namestie
    name: Kamenné nám.      # optional (default: the stop name)
    rows: 4                 # optional, stack/columns only
```

`merged` shows one list of the departures of all stops, sorted by time; under each destination it names the stop
and the platform (`nást. 2`), the walk time (`4 min pešo`), plus the delay or `podľa CP` for timetable-only rows.
With `nearest_only` the same line to the same terminus (e.g. N21 → Hlavná stanica from two stops) is listed only from
the closer stop; the list still fills up to `rows`. A stop that is not live gets
one status line under the list. Tap a row for the stop sensor's details. `stack` / `columns` show one block per stop.

Styling: set these CSS variables in a theme or on a parent card (defaults in brackets):
`--imhd-card-padding` (16px), `--imhd-title-size` (20px), `--imhd-title-weight` (500), `--imhd-subtitle-size` (13px),
`--imhd-dot-size` (8px), `--imhd-live-color` (#66BB6A), `--imhd-list-gap` (8px), `--imhd-row-gap` (14px),
`--imhd-badge-height` (36px), `--imhd-badge-radius` (10px), `--imhd-badge-size` (17px),
`--imhd-badge-background` / `--imhd-badge-color` (neutral badges; theme secondary background / primary text),
`--imhd-dest-size` (17px), `--imhd-dest-weight` (400), `--imhd-sub-size` (13px), `--imhd-delay-color` (#FB8C00),
`--imhd-minutes-size` (30px), `--imhd-minutes-weight` (200).

The card sources are in `card/` (`npm install`, `npx vite build` writes `custom_components/imhd/frontend/`).
