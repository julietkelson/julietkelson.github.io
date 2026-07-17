# Listening Trend Y-Axis & Hover Scrubber Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a labeled y-axis and a hover scrubber (vertical guide + dots + value tooltip) to the daily energy/valence trend chart in the `/music/` listening banner.

**Architecture:** The two polylines stay inside the existing stretched SVG (`preserveAspectRatio="none"`). Every new element — y-axis labels, midline, scrubber guide, dots, tooltip — is HTML/CSS positioned by percentage over a `position: relative` plot wrapper, so nothing distorts under non-uniform scaling. All rendering is JS in `renderTrend`; no HTML-include or Python changes.

**Tech Stack:** Vanilla JS (`assets/js/now-playing.js`), SCSS (`_sass/_now-playing.scss`), Jekyll build.

## Global Constraints

- No third-party JS/chart libraries — hand-built, matching the existing bars/lines.
- No changes to `scripts/aggregate.py` or the `aggregates.json` data shape; consume the existing `daily_series` (`{date, energy, valence, plays}`, values 0–1).
- No new color tokens — reuse `--fn-amber`, `--fn-ochre`, `--fn-ink2`, `--fn-dot`, `--fn-paper`, `--fn-paperDk` (all present in `_sass/_tokens.scss`).
- The chart stays `aria-hidden="true"`; the scrubber adds no focusable elements.
- The `np__trend` block stays hidden when `daily_series` has fewer than 2 points (existing behavior).
- No JS test runner exists in this repo. Verification is `jekyll build` + browser eyeball, then discard the locally regenerated `data/aggregates.json` before committing (the GitHub Action regenerates it on its own schedule).

**Note on the working tree:** `_sass/_tokens.scss` and `_sass/_now-playing.scss` already carry an uncommitted change adding `--fn-ochre` and switching the valence line/legend swatch to it. That change is part of this same visual work and is committed together in Task 3.

---

## File Structure

- `assets/js/now-playing.js` — `renderTrend()` rewritten to emit the y-axis + plot-wrapper DOM and wire pointer handlers; new pure helper `nearestIndex()`.
- `_sass/_now-playing.scss` — new rules for `.np__trend-chart` grid, y-axis, plot wrapper, midline, cursor/guide/dots/tooltip; one edit to `.np__trend-svg` height.
- No change to `_includes/now-playing.html` (the `[data-np-trend]` container already exists).

---

## Task 1: Y-axis, plot wrapper, and midline

Restructure `renderTrend`'s DOM into a `[y-axis][plot]` grid with the polylines inside a positioned plot wrapper, and style the axis + midline. No scrubber yet — deliverable is a correctly scaled, labeled static chart.

**Files:**
- Modify: `assets/js/now-playing.js` (`renderTrend`, lines ~28–62)
- Modify: `_sass/_now-playing.scss` (add rules after `.np__trend-line--valence`, ~line 180; edit `.np__trend-svg`, ~line 166)

**Interfaces:**
- Consumes: `series` = `data.daily_series`, an array of `{date, energy, valence, plays}`.
- Produces: DOM with `.np__trend-chart` > (`.np__trend-yaxis`, `.np__trend-plot[data-np-plot]` > (`svg.np__trend-svg`, `.np__trend-midline`)). Task 2 appends the cursor group inside `.np__trend-plot` and reads `[data-np-plot]`.

- [ ] **Step 1: Rewrite `renderTrend` markup**

Replace the whole `renderTrend` function body's `container.innerHTML = ...` block (keep the guard clauses and the `W/H/n/x/y/path` helpers above it) so the markup becomes:

```js
    container.innerHTML = `
      <div class="np__trend-legend">
        <span class="np__trend-key np__trend-key--energy">ENERGY</span>
        <span class="np__trend-key np__trend-key--valence">VALENCE</span>
      </div>
      <div class="np__trend-chart">
        <div class="np__trend-yaxis" aria-hidden="true">
          <span>1</span><span>0.5</span><span>0</span>
        </div>
        <div class="np__trend-plot" data-np-plot>
          <svg class="np__trend-svg" viewBox="0 0 ${W} ${H}"
               preserveAspectRatio="none" aria-hidden="true">
            <polyline class="np__trend-line np__trend-line--valence"
                      vector-effect="non-scaling-stroke" points="${path('valence')}" />
            <polyline class="np__trend-line np__trend-line--energy"
                      vector-effect="non-scaling-stroke" points="${path('energy')}" />
          </svg>
          <div class="np__trend-midline" aria-hidden="true"></div>
        </div>
      </div>
      <div class="np__trend-dates">
        <span>${shortDate(pts[0].date)}</span>
        <span>${shortDate(pts[n - 1].date)}</span>
      </div>
    `;
```

- [ ] **Step 2: Edit the SVG height rule**

In `_sass/_now-playing.scss`, change the existing `.np__trend-svg` block so the SVG fills the plot wrapper:

```scss
.np__trend-svg {
  display: block;
  width: 100%;
  height: 100%;
}
```

- [ ] **Step 3: Add chart grid, y-axis, plot, and midline rules**

Add after the `.np__trend-line--valence { stroke: var(--fn-ochre); }` rule:

```scss
.np__trend-chart {
  display: grid;
  grid-template-columns: 26px 1fr;
  column-gap: 6px;
}

.np__trend-yaxis {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
  font-family: var(--fn-mono);
  font-size: 10px;
  line-height: 1;
  color: var(--fn-ink2);
}

.np__trend-plot {
  position: relative;
  height: 64px;
}

.np__trend-midline {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  background: var(--fn-dot);
  pointer-events: none;
}
```

- [ ] **Step 4: Offset the dates row to sit under the plot**

Update the existing `.np__trend-dates` rule to add a left offset equal to the gutter + gap (26 + 6 = 32px):

```scss
.np__trend-dates {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  padding-left: 32px;
  font-family: var(--fn-mono);
  font-size: 10px;
  color: var(--fn-ink2);
}
```

- [ ] **Step 5: Regenerate local data and build**

Generate a local `aggregates.json` that includes `daily_series`, then build:

```bash
cd scripts && python3 -c "import json; from aggregate import aggregate; h=json.load(open('../data/history.json')); json.dump(aggregate(h), open('../data/aggregates.json','w'), indent=2)" && cd ..
bundle exec jekyll build
```

Expected: build succeeds with no Liquid/SCSS errors.

- [ ] **Step 6: Eyeball the axis**

```bash
bundle exec jekyll serve
```

View `/music/`. Expected: the trend chart shows `1 / 0.5 / 0` labels down the left, a faint hairline at the vertical middle, the two lines drawn in the plot area to the right of the labels, and the start/end dates aligned under the plot (not under the labels). No console errors.

- [ ] **Step 7: Commit**

```bash
git add assets/js/now-playing.js _sass/_now-playing.scss
git commit -m "Add y-axis and midline to listening trend chart"
```

(Leave `data/aggregates.json` uncommitted — it is discarded in Task 3.)

---

## Task 2: Hover scrubber

Add the `nearestIndex` helper, the cursor group DOM, the pointer handlers, and the cursor/guide/dot/tooltip styling. Deliverable: hovering the plot snaps a guide + dots to the nearest day and shows a value tooltip that flips near the right edge.

**Files:**
- Modify: `assets/js/now-playing.js` (add `nearestIndex`; extend `renderTrend`)
- Modify: `_sass/_now-playing.scss` (add cursor/guide/dot/tooltip rules)

**Interfaces:**
- Consumes: `[data-np-plot]` and the `pts` array (`{date, energy, valence}`) from Task 1.
- Produces: no downstream consumers.

- [ ] **Step 1: Add the `nearestIndex` helper**

In `assets/js/now-playing.js`, add near the other top-level helpers (after `shortDate`):

```js
  function nearestIndex(frac, n) {
    const i = Math.round(frac * (n - 1));
    return Math.max(0, Math.min(n - 1, i));
  }
```

- [ ] **Step 2: Add the cursor group to the plot markup**

In `renderTrend`, inside `.np__trend-plot` and immediately after the `.np__trend-midline` div, add the cursor group:

```html
          <div class="np__trend-cursor" data-np-cursor hidden aria-hidden="true">
            <div class="np__trend-guide"></div>
            <div class="np__trend-dot np__trend-dot--energy"></div>
            <div class="np__trend-dot np__trend-dot--valence"></div>
            <div class="np__trend-tip"></div>
          </div>
```

- [ ] **Step 3: Add percent helpers and wire the handlers**

At the top of `renderTrend`, alongside the existing `x`/`y` helpers, add percent versions:

```js
    const xPct = (i) => (i / (n - 1)) * 100;
    const yPct = (v) => (1 - Math.max(0, Math.min(1, v))) * 100;
```

Then, after the `container.innerHTML = ...` assignment (at the end of `renderTrend`), add:

```js
    const plot = container.querySelector('[data-np-plot]');
    const cursor = container.querySelector('[data-np-cursor]');
    const guide = cursor.querySelector('.np__trend-guide');
    const dotE = cursor.querySelector('.np__trend-dot--energy');
    const dotV = cursor.querySelector('.np__trend-dot--valence');
    const tip = cursor.querySelector('.np__trend-tip');

    function moveTo(clientX) {
      const rect = plot.getBoundingClientRect();
      if (!rect.width) return;
      const frac = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      const i = nearestIndex(frac, n);
      const px = xPct(i);
      cursor.hidden = false;
      guide.style.left = px + '%';
      dotE.style.left = px + '%';
      dotE.style.top = yPct(pts[i].energy) + '%';
      dotV.style.left = px + '%';
      dotV.style.top = yPct(pts[i].valence) + '%';
      tip.style.left = px + '%';
      tip.classList.toggle('np__trend-tip--flip', frac > 0.5);
      tip.innerHTML = `
        <div class="np__trend-tip-date">${shortDate(pts[i].date)}</div>
        <div class="np__trend-tip-row">
          <span class="np__trend-tip-swatch np__trend-tip-swatch--energy"></span>
          ENERGY <b>${fmt(pts[i].energy)}</b>
        </div>
        <div class="np__trend-tip-row">
          <span class="np__trend-tip-swatch np__trend-tip-swatch--valence"></span>
          VALENCE <b>${fmt(pts[i].valence)}</b>
        </div>`;
    }

    plot.addEventListener('pointermove', (e) => moveTo(e.clientX));
    plot.addEventListener('pointerleave', () => { cursor.hidden = true; });
```

- [ ] **Step 4: Style the cursor, guide, dots, and tooltip**

Add to `_sass/_now-playing.scss` after the `.np__trend-midline` rule:

```scss
.np__trend-cursor {
  position: absolute;
  inset: 0;
  pointer-events: none;

  &[hidden] { display: none; }
}

.np__trend-guide {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--fn-ink2);
  opacity: 0.35;
  transform: translateX(-0.5px);
}

.np__trend-dot {
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  transform: translate(-50%, -50%);
}

.np__trend-dot--energy { background: var(--fn-amber); }
.np__trend-dot--valence { background: var(--fn-ochre); }

.np__trend-tip {
  position: absolute;
  top: 2px;
  transform: translateX(6px);
  padding: 4px 6px;
  background: var(--fn-paper);
  border: 1px solid var(--fn-paperDk);
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(26, 20, 16, 0.12);
  font-family: var(--fn-mono);
  font-size: 10px;
  line-height: 1.5;
  color: var(--fn-ink2);
  white-space: nowrap;
}

.np__trend-tip--flip { transform: translateX(calc(-100% - 6px)); }

.np__trend-tip-date {
  font-weight: 600;
  margin-bottom: 2px;
}

.np__trend-tip-row {
  display: flex;
  align-items: center;
}

.np__trend-tip-row b { margin-left: 5px; }

.np__trend-tip-swatch {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 5px;
}

.np__trend-tip-swatch--energy { background: var(--fn-amber); }
.np__trend-tip-swatch--valence { background: var(--fn-ochre); }
```

- [ ] **Step 5: Build and eyeball the scrubber**

```bash
bundle exec jekyll build && bundle exec jekyll serve
```

View `/music/` and move the pointer across the chart. Expected: a vertical guide snaps day-to-day; an amber dot and an ochre dot sit on the two lines at that day; a tooltip shows the `M/D` date and both values with matching color swatches. Near the right edge the tooltip flips to the left of the guide and never clips. Moving the pointer off the plot hides the guide/dots/tooltip. No console errors.

- [ ] **Step 6: Commit**

```bash
git add assets/js/now-playing.js _sass/_now-playing.scss
git commit -m "Add hover scrubber to listening trend chart"
```

---

## Task 3: Final verification and cleanup

Fold in the pending `--fn-ochre` token change, confirm a clean build, and discard the local data regeneration.

**Files:**
- Commit: `_sass/_tokens.scss` (already-modified `--fn-ochre` token)
- Discard: `data/aggregates.json`

- [ ] **Step 1: Confirm a clean build**

```bash
bundle exec jekyll build
```

Expected: succeeds with no Liquid/SCSS errors.

- [ ] **Step 2: Commit the pending color token**

The `--fn-ochre` token addition in `_sass/_tokens.scss` was modified before this work and underpins the valence color used throughout the chart. Commit it:

```bash
git add _sass/_tokens.scss
git commit -m "Add ochre accent token for trend valence line"
```

- [ ] **Step 3: Discard the local data regeneration**

```bash
git checkout data/aggregates.json
```

- [ ] **Step 4: Confirm a clean tree**

```bash
git status
```

Expected: `working tree clean` (aside from any untracked Jekyll build artifacts already ignored). The four new commits (y-axis, scrubber, color token, plus the earlier chart commit) are ahead of `origin/master`.

---

## Self-Review

- **Spec coverage:** Overlay approach (core decision) → Tasks 1–2 build all new elements as HTML/CSS over `.np__trend-plot`. Y-axis labels + midline → Task 1. Scrubber (guide, dots, tooltip, `nearestIndex`, flip near edge, hide on leave) → Task 2. No data/Python change, `aria-hidden` retained, <2-point hide → preserved (guards untouched). Verification + discard local data → Task 3. All covered.
- **Placeholder scan:** none — every code step carries complete code.
- **Type consistency:** `nearestIndex(frac, n)`, `xPct(i)`, `yPct(v)`, `[data-np-plot]`, `[data-np-cursor]`, and the `.np__trend-*` class names match between the JS handler and the SCSS/markup across tasks.
