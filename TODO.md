# RPi Watch Backlog

## Planned Next

### Metric Rotation And Animation

- keep the current single-subscription metric rotation model and add visual transitions on top of it
- add slide-up transition where the current metric exits upward and the next metric enters from below
- make transition timing configurable with duration, frame count, and easing
- keep animation rendering inside the existing PIL/SPI pipeline instead of introducing a heavy external framework

### Theme And Color Controls

- support theme-level palettes for transitions and layouts
- support per-item color overrides for individual rotated metrics
- allow animated transitions to inherit either the shared theme or item-specific colors
