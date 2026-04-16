# RPi Watch Backlog

## Planned Next

### Ring And Layout Polish
- verify whether any remaining ring stride artifacts are panel/camera limitations or still need renderer tuning
- if needed, increase supersampling or move the ring fill to a tighter annular mask pass
- keep cap treatment consistent:
  outer ends rounded, internal joins clean, marker not overpowering the ring
- keep the ring radius visually constant across the sweep
- continue reducing text/component overlap as layouts get denser

### Metric Rotation And Animation

- make transition timing configurable with duration, frame count, easing, and speed fast enough to read as intentional motion
- keep animation rendering inside the existing PIL/SPI pipeline instead of introducing a heavy external framework

### Derived Metrics Adoption

- use station-side rolling 24-hour averages already present on MQTT
  (`pm_2_5_avg_24h`, `pm_10_0_avg_24h`) as the preferred PM guidance reference
- keep a clear split between:
  - live reading shown as the large number
  - 24-hour average used for PM color index / risk banding
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
