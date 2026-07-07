# Now Playing — Aggregated Listening Banner on `/music/`

Date: 2026-06-28
Status: Approved (design phase)
Source handoff: `Live "Now Playing" Music Visualization` (provided by user, 2026-06-28)

## Goal

Add an aggregated read of recent Spotify listening to the existing `/music/`
page as a banner above the three band cards. The banner summarizes the rolling
last 50 plays as labeled audio-feature bar meters, the top 5 genres in the
window, and a small metadata eyebrow. A horizontal playhead line sweeps across
the bar group at the average BPM of the window.

This is **display-only**. No model training, no commercial use, no external
publishing.

## Scope

In scope (MVP):
- Cron-driven collection of Spotify currently-playing as the data source.
- Per-track genre + audio-feature lookup (ReccoBeats → SoundStat fallback).
- Rolling history file capped at 500 plays / 30 days.
- Precomputed `aggregates.json` for the page.
- New `_includes/now-playing.html` rendered above the bands on `/music/`.
- Front-end JS that fetches `aggregates.json` on load, polls every 60s.
- Playhead sweep animation at average BPM.
- `CALIBRATING` empty state when history is empty or all-null.

Out of scope (explicitly):
- A live "what's playing right now" card on the page.
- Real-time / websockets / SSE.
- A backend server. GitHub Actions writes JSON; the static page reads it.
- Spotify's deprecated `/v1/audio-features`, `/v1/audio-analysis`, `popularity`
  field, or the removed batch `GET /v1/artists?ids=` endpoint.
- Phase-2 history visualization (energy×valence scatter, genre drift over
  time). Out of MVP but the `history.json` artifact supports it later without
  backfill.

## Architecture

```
GitHub Actions cron (*/5)
  -> refresh Spotify access token
  -> GET /v1/me/player/currently-playing
  -> (200) GET /v1/artists/{id} per artist        (genres)
  -> (200) ReccoBeats two-step                    (features; cache hit short-circuits)
        miss/429/error -> SoundStat fallback
        miss          -> features: null
  -> append to history.json (deduped)
  -> recompute aggregates.json (rolling last 50 plays)
  -> commit + push iff any artifact changed

Static page (/music/)
  -> fetches data/aggregates.json on load + every 60s (cache-busted)
  -> renders eyebrow, six bar meters, top-5 genre chips
  -> playhead line sweeps at average BPM
```

The page reads only `aggregates.json` in the MVP. `now-playing.json` is
written each run for internal continuity but is not consumed by the front end.

## Front-end design

Placement: at the top of `_layouts/music.html`, above `<div class="music-bands">`,
via `{% include now-playing.html %}`.

Visual structure (desktop; stacks on mobile):

```
LAST 50 PLAYS · 24 ARTISTS · AVG 118 BPM         ← mono eyebrow, ink2
──────────────────────────────────────────────  ← fn-rule
ENERGY         ▇▇▇▇▇▇▇░░░░░░░░░░  0.62
DANCEABILITY   ▇▇▇▇▇░░░░░░░░░░░░  0.48
VALENCE        ▇▇▇▇░░░░░░░░░░░░░  0.41
ACOUSTICNESS   ▇▇▇▇▇▇▇▇▇▇▇▇░░░░░  0.71
INSTRUMENTAL   ▇▇░░░░░░░░░░░░░░░  0.18
SPEECHINESS    ▇░░░░░░░░░░░░░░░░  0.09
──────────────────────────────────────────────
folk · indie folk · americana · alt country · slowcore
```

- Six audio features: `energy, danceability, valence, acousticness,
  instrumentalness, speechiness`. Liveness and loudness are deliberately not
  shown (loudness is dB-scaled; liveness is rarely interesting).
- Tempo lives as the eyebrow number (`AVG 118 BPM`) and as the sweep speed.
  It is not a bar.
- Bar fills: thin solid amber on a panel background, label mono-uppercase in
  ink2, numeric mean right-aligned, fixed-width number column.
- Genre chips: top 5 by play count, dot-separated, lowercase, mono.
- Playhead: a single thin vertical line (~1px, ink2 at low opacity) overlaid
  on the bar group, translating left → right over a period of
  `60 / averageBpm` seconds, infinite loop. CSS `animation` driven by a
  `--bpm` custom property set from `aggregates.json` by the script. Animation
  honors `prefers-reduced-motion: reduce` (line is hidden).
- Empty state: eyebrow + a single mono `CALIBRATING` label, no bars, no chips,
  no sweep.

Styling lives in a new `_sass/_now-playing.scss` that uses the existing FN
design tokens (`--fn-ink`, `--fn-ink2`, `--fn-amber`, `--fn-rule`,
`--fn-panel`, `--fn-mono`, `--fn-sans`). The partial is `@import`ed by the
main sass file alongside the other page partials.

Front-end JS (`assets/js/now-playing.js`):
- Fetch `/data/aggregates.json?t=${Date.now()}` on `DOMContentLoaded`.
- Render the bars/chips/eyebrow into the include's container.
- Set `--bpm` on the container element.
- Poll every 60s (cache-busted each time). Stop polling when the tab is
  hidden (`document.hidden`) and resume on visibility change to be gentle on
  the user's CPU.
- No external libraries.

## File layout

New:
```
scripts/
  now_playing.py
  get_refresh_token.py        # one-time local helper; never runs in CI
.github/workflows/
  now-playing.yml             # */5 cron + workflow_dispatch
data/
  now-playing.json
  history.json
  aggregates.json
  features-cache.json
_includes/
  now-playing.html
_sass/
  _now-playing.scss
assets/js/
  now-playing.js
```

Modified:
- `_layouts/music.html` — `{% include now-playing.html %}` above the bands.
- Whichever sass file `@import`s the partials — add `@import 'now-playing';`.
- `README.md` — append a setup section (refresh-token flow, required secrets).
- `.gitignore` — confirm `.env` (or equivalent) stays ignored.

GitHub Actions secrets required:
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REFRESH_TOKEN`
- `SOUNDSTAT_API_KEY` (optional; enables fallback)

## Data contracts

### `data/now-playing.json` (internal snapshot)
```jsonc
{
  "fetched_at": "2026-06-28T15:00:14Z",
  "is_playing": true,
  "currently_playing_type": "track",
  "track": {
    "id": "spotify-track-id",
    "name": "Track Name",
    "artists": [{"id": "...", "name": "..."}],
    "album": {"name": "...", "release_date": "2021-04-30", "image": "https://..."},
    "duration_ms": 215000,
    "progress_ms": 64000,
    "explicit": false,
    "external_urls": {"spotify": "https://open.spotify.com/track/..."}
  },
  "genres": ["indie folk", "folk"],
  "audio_features": {
    "energy": 0.34, "danceability": 0.41, "valence": 0.23,
    "acousticness": 0.78, "instrumentalness": 0.02, "speechiness": 0.04,
    "tempo": 96.2, "liveness": 0.12, "loudness": -10.4,
    "source": "reccobeats"
  }
}
```
Idle variant:
```jsonc
{ "fetched_at": "...", "is_playing": false, "track": null }
```

### `data/history.json` (rolling list)
Array of play entries, oldest first. Cap = first hit between 500 entries or
30 days. Each entry:
```jsonc
{
  "logged_at": "2026-06-28T15:00:14Z",
  "track_id": "spotify-track-id",
  "name": "Track Name",
  "artists": ["Artist Name"],
  "genres": ["indie folk", "folk"],
  "audio_features": { /* same shape as above, or null */ }
}
```
Dedupe rule: append iff
- `history` is empty, OR
- current `track_id` ≠ last entry's `track_id`, OR
- current `track_id` == last entry's `track_id` AND `now − last.logged_at > 20 min`
  (handles the rare case where the same song genuinely plays twice in a row
  far apart, while collapsing the same song held across consecutive cron
  runs into one entry).

### `data/aggregates.json` (what the page reads)
```jsonc
{
  "generated_at": "2026-06-28T15:00:14Z",
  "window": { "plays_used": 50, "plays_with_features": 47 },
  "totals": { "plays": 50, "unique_artists": 24 },
  "audio_features_mean": {
    "energy": 0.62, "danceability": 0.48, "valence": 0.41,
    "acousticness": 0.71, "instrumentalness": 0.18, "speechiness": 0.09
  },
  "tempo_mean_bpm": 118.4,
  "top_genres": [
    {"name": "folk", "count": 14},
    {"name": "indie folk", "count": 11},
    {"name": "americana", "count": 7},
    {"name": "alt country", "count": 5},
    {"name": "slowcore", "count": 4}
  ]
}
```
Empty/calibrating variant (history is empty or every feature is null):
```jsonc
{
  "generated_at": "...",
  "state": "calibrating",
  "window": {"plays_used": 0, "plays_with_features": 0}
}
```

### `data/features-cache.json` (per-track cache)
```jsonc
{
  "spotify-track-id-hit": {
    "cached_at": "2026-06-28T15:00:14Z",
    "features": {
      "energy": 0.34, "danceability": 0.41, "valence": 0.23,
      "acousticness": 0.78, "instrumentalness": 0.02, "speechiness": 0.04,
      "tempo": 96.2, "liveness": 0.12, "loudness": -10.4,
      "source": "reccobeats"
    }
  },
  "spotify-track-id-miss": {
    "cached_at": "2026-06-28T15:00:14Z",
    "features": null
  }
}
```
Successful entries are cached indefinitely (a track's features don't change).
Miss entries (both APIs returned nothing) are cached as `features: null` with
a 30-day TTL so genuinely missing tracks get retried later, and removed from
the cache on expiry. The cache file is committed to git so it survives across
runs.

## Aggregation rules

Computed over the most recent 50 entries in `history.json` (or fewer if
history is shorter).

- `audio_features_mean[k]` = arithmetic mean of `entry.audio_features[k]`
  across entries where `audio_features` is non-null. Plays with `null` features
  are excluded from the mean (not zeroed).
- `tempo_mean_bpm` = arithmetic mean of `tempo` over the same subset.
- `top_genres` = count of each genre string across all 50 entries (a play
  with N genres contributes 1 to each), sorted descending, top 5. Ties broken
  by alphabetical.
- `totals.plays` = number of entries in the window (≤ 50).
- `totals.unique_artists` = distinct count across all entries' `artists` lists.
- `window.plays_with_features` = how many of the 50 had non-null features.

If `plays_with_features == 0`, write the calibrating variant.

## Error handling

- **Spotify token refresh failure** → log to stderr, exit non-zero, no commit.
  Workflow run goes red so the failure is visible.
- **Spotify `204 No Content`** → no current track, but still recompute and
  write `aggregates.json` so the page keeps showing your last 50 plays.
  Commit only if `aggregates.json` (or `now-playing.json`) changed.
- **`currently_playing_type` ≠ `"track"`** (podcast/episode) → log the entry
  to history with `name = episode.name` (when present), `artists: []`,
  `genres: []`, and `audio_features: null`. Skip the per-artist and feature
  lookups. Counts toward `totals.plays`, contributes nothing to
  `unique_artists`, `top_genres`, or the feature means.
- **ReccoBeats `429` / connection error / 5xx** → catch, fall through to
  SoundStat if `SOUNDSTAT_API_KEY` is set, else write `features: null`.
- **ReccoBeats miss (no UUID for that Spotify track id)** → try SoundStat,
  else `features: null`.
- **SoundStat error or no key** → `features: null`.
- **Empty history or all-null features** → write the `state: "calibrating"`
  aggregates variant.
- **Concurrency** → workflow `concurrency: { group: now-playing,
  cancel-in-progress: true }` so two runs can't race on the push.
- **Secrets** → never written into any file under `data/`. The script only
  reads them from environment variables and never logs their values.

## Testing approach

- **Local dry run.** `scripts/now_playing.py --dry-run` runs the full
  pipeline against real Spotify credentials, prints what it would write, and
  performs no file writes and no git commit. Manual sanity before turning the
  cron on.
- **Aggregation unit test.** `scripts/test_aggregate.py` (no network)
  exercises the aggregation function against a hand-crafted history fixture
  that includes: a play with null features, a non-track episode entry, a
  duplicate track id collapsed across runs, and a genre tie. Asserts the
  expected `aggregates.json` shape and values.
- **Front-end check.** With a hand-crafted `data/aggregates.json`,
  `bundle exec jekyll serve` and load `http://localhost:4000/music/`.
  Confirm: bars render, eyebrow shows the metadata line, genres render, the
  sweep animates at the BPM, `prefers-reduced-motion: reduce` hides the
  sweep, and the `CALIBRATING` state renders when `state === "calibrating"`.
- **CI implicit acceptance.** Once the cron is live, a successful run that
  commits a populated `aggregates.json` for a real play satisfies acceptance
  criteria 1, 3, and 5 from the original handoff.

## GitHub Actions workflow

`.github/workflows/now-playing.yml`:

- Trigger: `schedule: cron: '*/5 * * * *'` and `workflow_dispatch`.
- `permissions: contents: write` so the run can push.
- `concurrency: { group: now-playing, cancel-in-progress: true }`.
- Steps: `actions/checkout`, `actions/setup-python@v5` (Python 3.11),
  `pip install requests`, run `python scripts/now_playing.py`, then
  `git add data/ && git diff --cached --quiet || git commit -m 'chore: update
  now-playing' && git push`.
- Secrets pulled into the env: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`,
  `SPOTIFY_REFRESH_TOKEN`, `SOUNDSTAT_API_KEY`.

Cost: this repo is public, so Actions minutes are unlimited. Even on a
private repo, `*/5` × ~20s per run ≈ ~50 min/month, well inside the 2,000
min free tier.

## One-time setup (documented in README)

1. Create a Spotify app at developer.spotify.com (requires the owner to have
   Spotify Premium; verify the dashboard allows new app creation before
   building further).
2. Set redirect URI `http://127.0.0.1:3000`.
3. Run `python scripts/get_refresh_token.py` locally. The helper opens the
   Authorization Code flow with scope `user-read-currently-playing`, captures
   the code on a one-shot local server, exchanges it for tokens, and prints
   the refresh token. Never runs in CI.
4. Add the four secrets (3 required + SoundStat optional) to repo Settings
   → Secrets and variables → Actions.
5. Trigger the workflow manually once via `workflow_dispatch` to confirm
   the first commit lands.

## Acceptance criteria (mapped from the handoff)

1. A scheduled run with a track playing writes `now-playing.json` with track
   metadata, at least one genre when available, and audio features from
   ReccoBeats or SoundStat (or explicit null). **Met by the cron pipeline.**
2. A run with nothing playing writes a valid idle `now-playing.json` and
   recomputes `aggregates.json` from existing history; exits 0.
   **Met by the 204 handling.**
3. The same track playing across consecutive runs is logged to history
   exactly once and does not re-call the feature APIs (cache hit).
   **Met by the dedupe rule + features cache.**
4. The static page renders the aggregated view and updates without manual
   refresh, with a clean `CALIBRATING` state when history is empty.
   **Met by the front-end fetch + poll.** (Note: per the user's direction,
   the page shows an aggregated view rather than the live currently-playing
   card from the original handoff.)
5. No secret values appear in committed files or the built page.
   **Met by env-only secret access + write boundaries.**
6. The repo README documents the one-time refresh-token setup and the
   required GitHub secrets. **Met by the README section.**

## Deviations from the original handoff (acknowledged)

- The page renders an **aggregated view** (rolling last 50 plays) instead of
  a live currently-playing card. User-directed change during design.
- The original `now-playing.json` is still written each run but is **not
  consumed by the front end** in the MVP. It remains in the data flow for
  internal continuity and potential future use.
- The original Phase 2 history visualization is still future work; the
  `history.json` artifact will support it without backfill.
