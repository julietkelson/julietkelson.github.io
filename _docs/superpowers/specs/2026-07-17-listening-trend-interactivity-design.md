# Listening Trend — Y-Axis & Hover Scrubber — Design

**Date:** 2026-07-17
**Feature:** Add a labeled y-axis and a hover scrubber to the daily
energy/valence trend chart in the "In my ears" listening banner (`/music/`).

## Goal

The trend chart currently renders two bare polylines (energy + valence) with
only the first/last dates labeled and no vertical scale. Add:

1. **A y-axis** — `1 / 0.5 / 0` labels down the left with one faint midline, so
   the lines read against a scale.
2. **A hover scrubber** — moving across the chart snaps a vertical guide to the
   nearest day and shows that day's date + energy/valence values in a tooltip.

Both are purely additive; no data pipeline changes.

## Decisions (from brainstorming)

- **Hover behavior:** Scrubber + values. A vertical guide snaps to the nearest
  day; a tooltip shows `M/D` plus each series' value with a colored swatch.
  Chosen over line-emphasis-only (adds no info) and per-point dots (cluttered at
  ~30 points).
- **Y-axis:** Labels (`1` / `0.5` / `0`) plus one hairline gridline at 0.5.
  Chosen over labels-only (no visual reference) and full gridlines (busy in a
  small ambient banner).
- **No data changes:** Uses the existing `daily_series` (`{date, energy,
  valence, plays}`, 0–1 scale). `scripts/aggregate.py` is untouched.

## Core technical decision: overlay, not in-SVG

The chart SVG uses `preserveAspectRatio="none"`, so its coordinate system
stretches non-uniformly with container width. Anything drawn *inside* the SVG
distorts: `<text>` stretches horizontally and `<circle>` becomes an ellipse.

Therefore the two polylines stay in the SVG, but **every new element — y-axis
labels, midline, scrubber guide, dots, and tooltip — is HTML/CSS positioned by
percentage** over a `position: relative` wrapper. Positions come straight from
the data with no distortion:

- `x = i / (n - 1) × 100%` (left offset of day `i`)
- `y = (1 − value) × 100%` (top offset of a value on the fixed 0–1 scale)

## Structure — `assets/js/now-playing.js` (`renderTrend`)

`renderTrend` builds this DOM (legend and dates rows are largely as today):

```
.np__trend
  .np__trend-legend                    ENERGY · VALENCE  (unchanged)
  .np__trend-chart                     grid: [yaxis ~24px] [plot 1fr]
    .np__trend-yaxis                    spans "1" / "0.5" / "0"
    .np__trend-plot                     position: relative
      svg.np__trend-svg                 the two polylines (unchanged markup)
      .np__trend-midline                hairline at top:50%
      .np__trend-cursor[hidden]         JS-positioned scrubber group:
        .np__trend-guide                  vertical line at left:x%
        .np__trend-dot--energy            dot at (x%, y%)
        .np__trend-dot--valence           dot at (x%, y%)
        .np__trend-tip                     tooltip: date + 2 value rows
  .np__trend-dates                      start/end dates, offset under the plot
```

The block still re-renders on each poll, gated by the existing `generated_at`
change check. When `daily_series` has fewer than 2 points the whole `np__trend`
block stays hidden (existing behavior, unchanged).

## Scrubber interaction

- **Helper:** `nearestIndex(frac, n)` → `Math.round(frac × (n - 1))`, clamped to
  `[0, n-1]`. Pure function; easy to reason about.
- **Listeners** on `.np__trend-plot`: `pointermove` and `pointerleave`.
- **On `pointermove`:** compute `frac` from `(clientX − rect.left) / rect.width`
  (clamped 0–1), get `i = nearestIndex(frac, n)`, then:
  - Unhide `.np__trend-cursor`.
  - Position `.np__trend-guide` at `left: x(i)%`.
  - Position `.np__trend-dot--energy` / `--valence` at `left: x(i)%`,
    `top: (1 − value) × 100%`.
  - Fill `.np__trend-tip`: `M/D` header + one row per series (swatch + label +
    2-decimal value). Position the tip near the guide; **flip it to the left of
    the guide when `frac > 0.5`** so it never clips the right edge.
- **On `pointerleave`:** hide `.np__trend-cursor`.
- **Hidden by default.** No hover on touch, so mobile simply sees the static
  chart with its new axis — a pure progressive enhancement.

State: the current `pts` array is captured in the `pointermove` closure (or
stored on the plot element) so the handler can read values by index without
re-parsing the DOM.

## Y-axis & styling — `_sass/_now-playing.scss`

- `.np__trend-chart`: CSS grid, `grid-template-columns: [gutter] 1fr` (gutter
  ~24px). Replaces the SVG being full-bleed.
- `.np__trend-yaxis`: flex column, `justify-content: space-between`, mono
  ~10px `--fn-ink2`, right-aligned, full plot height. Labels top-to-bottom:
  `1`, `0.5`, `0`.
- `.np__trend-midline`: absolutely positioned, `top: 50%`, `height: 1px`,
  `background: var(--fn-dot)` (the existing faint dot-grid token, for texture
  consistency).
- `.np__trend-dates`: add a left offset equal to the gutter width so `7/1 … 7/17`
  align under the plot, not the axis labels.
- `.np__trend-guide`: 1px vertical line, `--fn-ink2` at low opacity.
- `.np__trend-dot--energy` / `--valence`: ~5px round dots in `--fn-amber` /
  `--fn-ochre` (matching the line colors), `transform: translate(-50%, -50%)`
  so they center on the point.
- `.np__trend-tip`: small card — cream/`--fn-paper` background, subtle border,
  mono text, `pointer-events: none` so it never eats the pointer. Positioned
  absolutely within `.np__trend-plot`.
- `.np__trend-cursor[hidden]`: `display: none`.

No new color tokens — reuses `--fn-amber`, `--fn-ochre` (added in the
uncommitted color tweak), `--fn-ink2`, `--fn-dot`, `--fn-paper`.

## Edge cases

- **< 2 points:** whole block hidden (existing).
- **Pointer near either edge:** `frac` clamped to `[0,1]`; tip flips side past
  the midpoint so it never clips.
- **Touch / no-hover:** cursor stays hidden; static chart + axis only.
- **Days omitted (gaps):** the scrubber snaps to the *rendered* points (index
  space), consistent with how the line is drawn; it does not invent missing
  days.
- **Energy ≈ valence on a day:** dots overlap; acceptable.
- **Stale `aggregates.json` without `daily_series`:** absent → `[]` → block
  hidden, no crash (existing).

## Accessibility

The chart keeps `aria-hidden="true"`. The scrubber is a decorative visual
enhancement of already-averaged data; it introduces no new keyboard/AT surface
and no new focusable elements. Out of scope: a keyboard-navigable data table
equivalent.

## Testing

No JS test runner exists in this repo (tests are Python for `aggregate.py`, and
this change touches no Python). Verification mirrors the original trend chart's
plan:

1. Regenerate a local `aggregates.json` with `daily_series` from real history.
2. `bundle exec jekyll build` — succeeds with no Liquid/SCSS errors.
3. `bundle exec jekyll serve`, view `/music/`: confirm the y-axis labels +
   midline render, and hovering the plot snaps the guide/dots and shows a
   correct tooltip that flips near the right edge.
4. `git checkout data/aggregates.json` — discard the local data copy before
   commit (the GitHub Action regenerates it on its schedule).

## Out of scope

- Any change to `scripts/aggregate.py` or the data shape.
- Smoothing / rolling averages, auto-scaled y-axis, per-point dot markers.
- A third metric/line, or a keyboard/AT-accessible data-table equivalent.
- Animated transitions on the scrubber.
