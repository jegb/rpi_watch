# RPi Watch Backlog

## Planned Next

### Metric Rotation And Animation

- make transition timing configurable with duration, frame count, easing, and speed fast enough to read as intentional motion
- keep animation rendering inside the existing PIL/SPI pipeline instead of introducing a heavy external framework

### Derived Metrics Adoption

- add config for metric source selection per visual:
  raw vs `*_avg_24h` vs `*_day_avg`

### Derived Metrics And Historical Views

- add a daily-average sparkline mode sourced from station-side aggregate history
- decide whether to fetch daily history from:
  - station HTTP API (`/api/daily-averages`)
  - or a new MQTT history snapshot payload
- decide layout-by-layout when to show:
  - raw trailing readings from the local store
  - current-day average
  - multi-day daily averages

### Theme And Color Controls

- support theme-level palettes for transitions and layouts
- support per-item color overrides for individual rotated metrics
- allow animated transitions to inherit either the shared theme or item-specific colors
