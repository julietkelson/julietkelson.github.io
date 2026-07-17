# Listening Trend Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-line (energy + valence) daily trend chart below the bars in the "In my ears" listening banner, showing change over the 30-day window.

**Architecture:** `aggregate.py` rolls the already-30-day-filtered play history into a new `daily_series` array (one point per day with plays) written to `aggregates.json`. `now-playing.js` reads that array and hand-builds an inline SVG with two polylines on a fixed 0–1 scale. Styling reuses existing mono/color tokens. No new dependencies.

**Tech Stack:** Python 3 (stdlib only), vanilla JS, Jekyll/Liquid include, SCSS.

## Global Constraints

- No third-party libraries — Python stdlib only in `scripts/`, zero JS dependencies (hand-built SVG).
- Fixed y-axis scale 0–1 (consistent with the existing bar axis). No auto-scaling.
- Raw daily means only — no smoothing/rolling averages.
- Feature-mean rounding: 4 decimals (matches existing `audio_features_mean`).
- Days bucketed by **UTC** calendar date of `logged_at`.
- Days with no feature-bearing plays are omitted from the series (never zero-filled).
- Trend block hidden when the series has fewer than 2 points.
- Reuse existing CSS custom properties (`--fn-amber`, `--fn-ink2`, `--fn-mono`); no new color tokens.

---

### Task 1: `daily_series` in the aggregate pipeline

**Files:**
- Modify: `scripts/aggregate.py` (add `_daily_series` helper; add `daily_series` key to the non-calibrating return)
- Test: `scripts/test_aggregate.py`

**Interfaces:**
- Consumes: existing `_parse_iso(str) -> datetime`, `_mean(list[float]) -> float`, and the `recent` list (already filtered to the 30-day window inside `aggregate`).
- Produces: `aggregate()` return dict gains `daily_series: list[dict]`, each `{ "date": "YYYY-MM-DD", "energy": float, "valence": float, "plays": int }`, sorted by `date` ascending. `_daily_series(recent: list[dict]) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

Add to `scripts/test_aggregate.py` (uses existing `entry`, `_days_ago`, `FEATURES_A`, `FEATURES_B` helpers):

```python
    def test_daily_series_groups_same_day_and_averages(self):
        day = _days_ago(2)  # same calendar day for both
        history = [
            entry("a", ["A"], ["folk"], FEATURES_A, when=day),
            entry("b", ["B"], ["folk"], FEATURES_B, when=day),
        ]
        series = aggregate(history)["daily_series"]
        self.assertEqual(len(series), 1)
        pt = series[0]
        # energy: mean(0.8, 0.4) = 0.6 ; valence: mean(0.5, 0.2) = 0.35
        self.assertAlmostEqual(pt["energy"], 0.6)
        self.assertAlmostEqual(pt["valence"], 0.35)
        self.assertEqual(pt["plays"], 2)

    def test_daily_series_sorted_ascending(self):
        history = [
            entry("new", ["A"], ["folk"], FEATURES_A, when=_days_ago(1)),
            entry("old", ["B"], ["folk"], FEATURES_B, when=_days_ago(5)),
        ]
        dates = [p["date"] for p in aggregate(history)["daily_series"]]
        self.assertEqual(dates, sorted(dates))

    def test_daily_series_omits_days_without_features(self):
        history = [
            entry("feat", ["A"], ["folk"], FEATURES_A, when=_days_ago(1)),
            entry("nofeat", ["B"], ["folk"], None, when=_days_ago(3)),
        ]
        series = aggregate(history)["daily_series"]
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]["plays"], 1)

    def test_daily_series_plays_counts_featureless_plays(self):
        day = _days_ago(2)
        history = [
            entry("feat", ["A"], ["folk"], FEATURES_A, when=day),
            entry("nofeat", ["B"], ["folk"], None, when=day),
        ]
        series = aggregate(history)["daily_series"]
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]["plays"], 2)  # counts the featureless play
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd scripts && python3 -m unittest test_aggregate -v`
Expected: the 4 new tests FAIL with `KeyError: 'daily_series'`.

- [ ] **Step 3: Implement `_daily_series` and wire it into the return**

In `scripts/aggregate.py`, add this helper above `def aggregate(`:

```python
def _daily_series(recent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, dict[str, Any]] = {}
    for e in recent:
        try:
            day = _parse_iso(e["logged_at"]).astimezone(
                dt.timezone.utc
            ).date().isoformat()
        except (KeyError, ValueError):
            continue
        bucket = by_day.setdefault(
            day, {"plays": 0, "energy": [], "valence": []}
        )
        bucket["plays"] += 1
        feats = e.get("audio_features")
        if feats:
            bucket["energy"].append(feats["energy"])
            bucket["valence"].append(feats["valence"])
    series = []
    for day in sorted(by_day):
        b = by_day[day]
        if not b["energy"]:
            continue
        series.append({
            "date": day,
            "energy": round(_mean(b["energy"]), 4),
            "valence": round(_mean(b["valence"]), 4),
            "plays": b["plays"],
        })
    return series
```

Then add the key to the final return dict in `aggregate()` (alongside `top_genres`):

```python
        "top_genres": top_genres,
        "daily_series": _daily_series(recent),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd scripts && python3 -m unittest test_aggregate -v`
Expected: all tests PASS (the 4 new ones plus the existing suite).

- [ ] **Step 5: Commit**

```bash
git add scripts/aggregate.py scripts/test_aggregate.py
git commit -m "Add daily_series to listening aggregate"
```

---

### Task 2: Render the trend chart in the widget

**Files:**
- Modify: `_includes/now-playing.html` (add trend container between `np__body` and `np__rule`)
- Modify: `assets/js/now-playing.js` (add `renderTrend`, call it from `render`, clear it in the calibrating branch)
- Modify: `_sass/_now-playing.scss` (add `.np__trend*` styles)

**Interfaces:**
- Consumes: `data.daily_series` from Task 1 (`list` of `{date, energy, valence, plays}`); absent/non-array treated as `[]`.
- Produces: rendered SVG inside `[data-np-trend]`; no exported symbols.

- [ ] **Step 1: Add the trend container to the include**

In `_includes/now-playing.html`, insert between the closing `</div>` of `np__body` and `<div class="np__rule"></div>`:

```html
  <div class="np__trend" data-np-trend hidden><!-- filled by JS --></div>
```

- [ ] **Step 2: Add the `renderTrend` helper to the JS**

In `assets/js/now-playing.js`, add this function above `function render(root, data) {`:

```js
  function shortDate(iso) {
    const [, m, d] = iso.split('-');
    return `${parseInt(m, 10)}/${parseInt(d, 10)}`;
  }

  function renderTrend(container, series) {
    if (!container) return;
    const pts = Array.isArray(series) ? series : [];
    if (pts.length < 2) {
      container.innerHTML = '';
      container.hidden = true;
      return;
    }
    container.hidden = false;

    const W = 100, H = 64;
    const n = pts.length;
    const x = (i) => (i / (n - 1)) * W;
    const y = (v) => (1 - Math.max(0, Math.min(1, v))) * H;
    const path = (key) =>
      pts.map((d, i) => `${x(i).toFixed(2)},${y(d[key]).toFixed(2)}`).join(' ');

    container.innerHTML = `
      <div class="np__trend-legend">
        <span class="np__trend-key np__trend-key--energy">ENERGY</span>
        <span class="np__trend-key np__trend-key--valence">VALENCE</span>
      </div>
      <svg class="np__trend-svg" viewBox="0 0 ${W} ${H}"
           preserveAspectRatio="none" aria-hidden="true">
        <polyline class="np__trend-line np__trend-line--valence"
                  vector-effect="non-scaling-stroke" points="${path('valence')}" />
        <polyline class="np__trend-line np__trend-line--energy"
                  vector-effect="non-scaling-stroke" points="${path('energy')}" />
      </svg>
      <div class="np__trend-dates">
        <span>${shortDate(pts[0].date)}</span>
        <span>${shortDate(pts[n - 1].date)}</span>
      </div>
    `;
  }
```

- [ ] **Step 3: Call `renderTrend` from `render`, and clear it when calibrating**

In `render()`, add the container lookup next to the others:

```js
    const meta = root.querySelector('[data-np-meta]');
    const trend = root.querySelector('[data-np-trend]');
```

In the `calibrating` branch, add a line to clear/hide it (next to `meta.textContent = '';`):

```js
      meta.textContent = '';
      if (trend) { trend.innerHTML = ''; trend.hidden = true; }
```

After the `meta.textContent = ...` line in the non-calibrating path, add:

```js
    renderTrend(trend, data.daily_series);
```

- [ ] **Step 4: Add the SCSS**

Append to `_sass/_now-playing.scss`:

```scss
.np__trend {
  margin-top: 18px;

  &[hidden] { display: none; }
}

.np__trend-legend {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}

.np__trend-key {
  font-family: var(--fn-mono);
  font-size: 10.5px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--fn-ink2);
  display: inline-flex;
  align-items: center;

  &::before {
    content: "";
    display: inline-block;
    width: 10px;
    height: 2px;
    margin-right: 6px;
  }
}

.np__trend-key--energy::before { background: var(--fn-amber); }
.np__trend-key--valence::before { background: var(--fn-ink2); }

.np__trend-svg {
  display: block;
  width: 100%;
  height: 64px;
}

.np__trend-line {
  fill: none;
  stroke-width: 1.5;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.np__trend-line--energy { stroke: var(--fn-amber); }
.np__trend-line--valence { stroke: var(--fn-ink2); }

.np__trend-dates {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-family: var(--fn-mono);
  font-size: 10px;
  color: var(--fn-ink2);
}
```

- [ ] **Step 5: Verify the build and the render locally**

Generate a local `aggregates.json` that includes `daily_series` from the real history, then build and eyeball:

```bash
cd scripts && python3 -c "import json; from aggregate import aggregate; h=json.load(open('../data/history.json')); json.dump(aggregate(h), open('../data/aggregates.json','w'), indent=2)" && cd ..
bundle exec jekyll build
```

Expected: build succeeds with no Liquid/SCSS errors, and `data/aggregates.json` now contains a `daily_series` array with ≥2 points.

Then serve and view `/music/`:

```bash
bundle exec jekyll serve
```

Expected: below the five bars, two thin lines (amber = energy, charcoal = valence) render with an `ENERGY · VALENCE` legend and `M/D` date labels at each end. Confirm the lines are legible and don't distort at the container width.

- [ ] **Step 6: Discard the local data regeneration**

The GitHub Action regenerates `data/aggregates.json` on its own schedule; don't commit the local copy.

```bash
git checkout data/aggregates.json
```

- [ ] **Step 7: Commit**

```bash
git add _includes/now-playing.html assets/js/now-playing.js _sass/_now-playing.scss
git commit -m "Render daily energy/valence trend chart in listening banner"
```

---

## Notes

- Valence stroke uses `--fn-ink2` (muted charcoal) to read distinctly against the amber energy line on the cream background. If it reads poorly once live, swap the `--valence` stroke/​swatch to another existing palette var — one-line change in the SCSS.
- If the raw-daily lines look too noisy in production, the smallest follow-up is smoothing inside `_daily_series` (rolling window) — no JS/SCSS change needed.
