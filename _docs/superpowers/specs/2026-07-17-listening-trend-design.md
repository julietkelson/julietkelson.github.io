# Listening Trend — Design

**Date:** 2026-07-17
**Feature:** A "change over time" element below the bar graph in the "In my ears"
listening banner (`/music/`), showing daily energy and valence across the
30-day window.

## Goal

The banner currently shows the *averaged shape* of the last 30 days of Spotify
plays (energy/upbeat/valence/acoustic/instrumental bars). Add a small element
directly below the bars that shows how the listening has *changed over time* —
a two-line trend of daily **energy** and **valence** across the same 30-day
window.

## Decisions (from brainstorming)

- **Metric:** Energy + valence, overlaid as two lines on one chart.
- **Granularity:** Raw daily means — one point per calendar day (UTC), no
  smoothing. Accepted tradeoff: jagged with few plays/day; if too noisy, a
  later change can swap daily means for a rolling window using the same
  pipeline.
- **Rendering:** Hand-built inline SVG (Approach A). No chart library — keeps
  the site dependency-free and matches the existing hand-built bars.
- **Y-axis:** Fixed 0–1 scale, consistent with the bar axis.
- **Placement:** Between the bars (`np__body`) and the genre/meta footer.

## Data pipeline — `scripts/aggregate.py`

Add a `daily_series` array to the aggregates output. After filtering `history`
to the 30-day window (existing logic), bucket the `recent` plays by the UTC
calendar date of `logged_at`. For each day that has at least one play carrying
`audio_features`, emit:

```json
{ "date": "2026-07-14", "energy": 0.61, "valence": 0.48, "plays": 4 }
```

- `energy` / `valence`: mean over that day's plays that have features, rounded
  to 4 decimals (same rounding as `audio_features_mean`).
- `plays`: total plays logged that day (including any without features), for
  context/possible future use.
- Days with zero plays are **omitted** (not zero-filled). The rendered line
  spans across the gap.
- Days whose plays **all lack features** are omitted (consistent with the
  existing "with features" rule for the bars).
- `daily_series` is sorted by `date` ascending.
- In the `calibrating` state (no plays carry features), the aggregate returns
  early as it does today; `daily_series` is not required there. Consumers treat
  an absent series as empty.

New top-level key on `aggregates.json`: `daily_series`.

## Rendering — `assets/js/now-playing.js` + `_includes/now-playing.html`

**HTML include:** add a container between `np__body` and `np__rule`:

```html
<div class="np__trend" data-np-trend><!-- filled by JS --></div>
```

**JS (`render`)**: read `data.daily_series` (default to `[]` if absent) and
build an inline SVG:

- `viewBox="0 0 100 64"` (or similar), `preserveAspectRatio="none"` for the
  drawing area, rendered responsive to container width via CSS.
- x = evenly spaced by index across the days present (`i / (n - 1) * width`).
- y = `(1 - value) * height` on a **fixed 0–1 scale**.
- Two `<polyline fill="none">`: energy stroked in `--fn-amber`; valence in a
  muted second palette tone (chosen at implementation to read distinctly on the
  cream background — candidates: `--fn-ink2` or an existing green var).
- A thin mono legend row `ENERGY · VALENCE`, each with a small color swatch.
- First and last date labels under the ends (e.g. `7/7 … 7/17`).
- **Hide the whole `np__trend` block when `daily_series` has fewer than 2
  points** — a line needs at least two points.

The block re-renders on each poll alongside the bars, gated by the existing
`generated_at` change check.

## Styling — `_sass/_now-playing.scss`

- `.np__trend`: small top margin, sits above `.np__rule`.
- `.np__trend-legend`: reuse the existing mono micro-label style (as
  `.np__bar-label`: `--fn-mono`, ~10.5px, uppercase, `--fn-ink2`).
- SVG polylines: `fill: none`, `stroke-width` ~1.5, `stroke-linejoin: round`,
  `stroke-linecap: round`.
- No new color tokens beyond the one valence stroke (reuse an existing var).

## Edge cases

- `daily_series` with 0 or 1 points → block hidden.
- Day with plays but none carrying features → day omitted.
- Stale `aggregates.json` from before this pipeline ships (no `daily_series`
  key) → JS treats absent as `[]`, block hidden, no crash.
- `calibrating` state → block hidden (series empty/absent).

## Testing — `scripts/test_aggregate.py`

Add tests for the new `daily_series`:

1. Same-day plays are grouped and their features averaged into one point.
2. Points are sorted by date ascending.
3. A day with zero plays does not appear (gap, not zero-fill).
4. A day whose plays all lack features does not appear.
5. `plays` count per day is correct (counts feature-less plays too).

Existing tests continue to pass unchanged.

## Out of scope

- Smoothing / rolling averages (possible later swap).
- Auto-scaled y-axis.
- Interactivity (tooltips, hover), axis gridlines beyond the fixed scale.
- Any third metric or a third line.
