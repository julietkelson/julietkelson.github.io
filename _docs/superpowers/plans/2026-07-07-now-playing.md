# Now Playing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the aggregated "Last 50 Plays" listening banner on `/music/`, backed by a cron-driven Python pipeline that collects Spotify currently-playing, enriches with genres + ReccoBeats audio features, and precomputes `aggregates.json` for the front end.

**Architecture:** A single Python 3.11 script (`scripts/now_playing.py`) runs every 5 minutes via GitHub Actions. It refreshes a Spotify access token, fetches currently-playing, enriches with per-artist genres (one call each — batch endpoint is gone) and per-track ReccoBeats audio features (cached), appends new plays to a rolling `history.json`, and precomputes `aggregates.json`. The static `/music/` page fetches `aggregates.json` on load + every 60s and renders six bar meters plus top-5 genre chips, with a horizontal playhead line sweeping across the bars at the average BPM.

**Tech Stack:** Python 3.11 (stdlib + `requests`), GitHub Actions, Jekyll (existing site), plain HTML/CSS/JS (no build step, no framework).

## Global Constraints

- **Working branch:** `now-playing`. Do not touch `master` until explicit merge.
- **Spec of record:** `_docs/superpowers/specs/2026-06-28-now-playing-design.md`. When this plan and the spec conflict, the spec wins — flag the conflict.
- **Python:** 3.11. Deps limited to stdlib + `requests`. No Spotipy or wrappers.
- **Spotify:** never call `/v1/audio-features`, `/v1/audio-analysis`, or `GET /v1/artists?ids=`. Never read `popularity`.
- **Genres:** fetch one artist at a time via `GET /v1/artists/{id}`.
- **Features:** ReccoBeats only in MVP. SoundStat integration is out of scope until we see gaps in real data.
- **Cache:** all feature lookups go through `data/features-cache.json` before hitting the network.
- **Cadence:** cron `*/5 * * * *`. Page polls `data/aggregates.json` every 60s (cache-busted).
- **Secrets:** `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REFRESH_TOKEN` in GitHub Actions secrets. Never written to any file under `data/`. Never logged.
- **Commits:** no `Co-Authored-By: Claude` lines (user preference in memory).
- **Motion:** playhead animation must honor `prefers-reduced-motion: reduce` by hiding the line.
- **Front-end:** no external JS/CSS libraries. Use existing FN sass tokens.
- **Design tokens available:** `--fn-ink`, `--fn-ink2`, `--fn-amber`, `--fn-forest`, `--fn-rule`, `--fn-panel`, `--fn-mono`, `--fn-sans`, `--fn-display`, `.fn-eyebrow`.
- **Empty state:** when history has zero plays with non-null features, `aggregates.json` uses `{ "state": "calibrating" }` and the front end renders the `CALIBRATING` label only.
- **Placement:** `_includes/now-playing.html` renders at the top of `_layouts/music.html`, above `<div class="music-bands">`.

---

## File Structure

Small focused files. Aggregation is a pure function so it can be tested without network.

**New scripts:**
- `scripts/now_playing.py` — orchestrator. CLI, history I/O, artifact writes, wires the other modules.
- `scripts/spotify_client.py` — Spotify token refresh, currently-playing, artist genres.
- `scripts/features_client.py` — ReccoBeats lookup, features cache read/write.
- `scripts/aggregate.py` — pure function: history → aggregates dict.
- `scripts/test_aggregate.py` — unit tests for `aggregate.py`. No network.

**New data artifacts (written by the script, committed by the workflow):**
- `data/now-playing.json`
- `data/history.json`
- `data/aggregates.json`
- `data/features-cache.json`

**New workflow:**
- `.github/workflows/now-playing.yml`

**New front-end:**
- `_includes/now-playing.html`
- `_sass/_now-playing.scss`
- `assets/js/now-playing.js`

**Modified:**
- `_layouts/music.html` — include the banner above the bands.
- `assets/css/main.scss` (or the entry sass file) — `@import 'now-playing';`.
- `_config.yml` — add `_docs` to `exclude` (belt-and-suspenders even though `_`-prefixed dirs are ignored by default).
- `README.md` — add a "Now playing setup" section.

---

## Task 1: Aggregation function (pure, TDD)

**Files:**
- Create: `scripts/aggregate.py`
- Test: `scripts/test_aggregate.py`

**Interfaces:**
- Consumes: nothing (pure).
- Produces: `aggregate(history: list[dict], window: int = 50) -> dict` returning either the populated aggregates dict or `{"state": "calibrating", "generated_at": ..., "window": {"plays_used": ..., "plays_with_features": 0}}`.

An entry in `history` looks like:
```python
{
    "logged_at": "2026-06-28T15:00:14Z",
    "track_id": "abc",
    "name": "Track Name",
    "artists": ["Artist"],
    "genres": ["indie folk", "folk"],
    "audio_features": {
        "energy": 0.34, "danceability": 0.41, "valence": 0.23,
        "acousticness": 0.78, "instrumentalness": 0.02, "speechiness": 0.04,
        "tempo": 96.2, "liveness": 0.12, "loudness": -10.4,
        "source": "reccobeats"
    }  # or None
}
```

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_aggregate.py
import datetime as dt
import unittest

from aggregate import aggregate

FEATURES_A = {
    "energy": 0.8, "danceability": 0.6, "valence": 0.5,
    "acousticness": 0.2, "instrumentalness": 0.0, "speechiness": 0.05,
    "tempo": 120.0, "liveness": 0.1, "loudness": -6.0, "source": "reccobeats",
}
FEATURES_B = {
    "energy": 0.4, "danceability": 0.3, "valence": 0.2,
    "acousticness": 0.9, "instrumentalness": 0.5, "speechiness": 0.03,
    "tempo": 90.0, "liveness": 0.2, "loudness": -12.0, "source": "reccobeats",
}


def entry(track_id, artists, genres, features, when="2026-06-28T15:00:00Z"):
    return {
        "logged_at": when,
        "track_id": track_id,
        "name": f"track {track_id}",
        "artists": artists,
        "genres": genres,
        "audio_features": features,
    }


class AggregateTest(unittest.TestCase):
    def test_empty_history_returns_calibrating(self):
        result = aggregate([])
        self.assertEqual(result["state"], "calibrating")
        self.assertEqual(result["window"]["plays_used"], 0)
        self.assertEqual(result["window"]["plays_with_features"], 0)

    def test_all_null_features_returns_calibrating(self):
        history = [entry("a", ["Artist"], ["folk"], None)]
        result = aggregate(history)
        self.assertEqual(result["state"], "calibrating")

    def test_means_only_over_non_null_features(self):
        history = [
            entry("a", ["A"], ["folk"], FEATURES_A),
            entry("b", ["B"], ["indie"], FEATURES_B),
            entry("c", ["C"], [], None),  # podcast/miss — excluded from mean
        ]
        result = aggregate(history)
        self.assertAlmostEqual(result["audio_features_mean"]["energy"], 0.6)
        self.assertAlmostEqual(result["audio_features_mean"]["valence"], 0.35)
        self.assertAlmostEqual(result["tempo_mean_bpm"], 105.0)
        self.assertEqual(result["window"]["plays_with_features"], 2)
        self.assertEqual(result["totals"]["plays"], 3)

    def test_top_genres_ranked_and_capped_at_five(self):
        history = [
            entry("a", ["A"], ["folk", "indie"], FEATURES_A),
            entry("b", ["B"], ["folk"], FEATURES_B),
            entry("c", ["C"], ["indie", "americana"], FEATURES_A),
            entry("d", ["D"], ["rock", "punk", "grunge", "metal"], FEATURES_B),
        ]
        result = aggregate(history)
        names = [g["name"] for g in result["top_genres"]]
        self.assertEqual(names[0], "folk")  # 2
        self.assertEqual(names[1], "indie")  # 2, alphabetical after folk
        self.assertLessEqual(len(result["top_genres"]), 5)

    def test_unique_artists_deduped(self):
        history = [
            entry("a", ["A", "B"], ["folk"], FEATURES_A),
            entry("b", ["B", "C"], ["folk"], FEATURES_B),
        ]
        result = aggregate(history)
        self.assertEqual(result["totals"]["unique_artists"], 3)

    def test_window_truncates_to_most_recent_n(self):
        history = [
            entry(str(i), [f"A{i}"], ["folk"], FEATURES_A) for i in range(60)
        ]
        result = aggregate(history, window=50)
        self.assertEqual(result["totals"]["plays"], 50)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests, watch them fail**

```bash
cd scripts && python3 -m unittest test_aggregate.py -v
```
Expected: `ModuleNotFoundError: No module named 'aggregate'` (before we create the module).

- [ ] **Step 3: Implement `aggregate.py`**

```python
# scripts/aggregate.py
"""Pure function: history entries -> aggregates dict."""

from __future__ import annotations

import datetime as dt
from collections import Counter
from typing import Any

FEATURE_KEYS = (
    "energy", "danceability", "valence",
    "acousticness", "instrumentalness", "speechiness",
)


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def aggregate(history: list[dict[str, Any]], window: int = 50) -> dict[str, Any]:
    recent = history[-window:] if window else list(history)
    with_features = [e for e in recent if e.get("audio_features")]

    if not with_features:
        return {
            "generated_at": _now_iso(),
            "state": "calibrating",
            "window": {"plays_used": len(recent), "plays_with_features": 0},
        }

    features_mean = {
        key: round(_mean([e["audio_features"][key] for e in with_features]), 4)
        for key in FEATURE_KEYS
    }
    tempo_mean = round(
        _mean([e["audio_features"]["tempo"] for e in with_features]), 2
    )

    genre_counts = Counter()
    for e in recent:
        for g in e.get("genres") or []:
            genre_counts[g] += 1
    top_genres = [
        {"name": name, "count": count}
        for name, count in sorted(
            genre_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )[:5]
    ]

    unique_artists: set[str] = set()
    for e in recent:
        for a in e.get("artists") or []:
            unique_artists.add(a)

    return {
        "generated_at": _now_iso(),
        "window": {
            "plays_used": len(recent),
            "plays_with_features": len(with_features),
        },
        "totals": {
            "plays": len(recent),
            "unique_artists": len(unique_artists),
        },
        "audio_features_mean": features_mean,
        "tempo_mean_bpm": tempo_mean,
        "top_genres": top_genres,
    }
```

- [ ] **Step 4: Run the tests, watch them pass**

```bash
cd scripts && python3 -m unittest test_aggregate.py -v
```
Expected: 6 tests, all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/aggregate.py scripts/test_aggregate.py
git commit -m "Add pure aggregation function with unit tests"
```

---

## Task 2: Spotify client (token refresh, currently-playing, genres)

**Files:**
- Create: `scripts/spotify_client.py`

**Interfaces:**
- Consumes: env vars `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REFRESH_TOKEN`.
- Produces:
  - `SpotifyClient(client_id, client_secret, refresh_token)` — constructor stores creds, refreshes access token lazily on first use.
  - `client.currently_playing() -> dict | None` — returns the raw JSON body on 200, `None` on 204. Raises `SpotifyError` on other errors.
  - `client.artist_genres(artist_ids: list[str]) -> list[str]` — one call per id, dedupes genres across artists in stable order.
- `SpotifyError(Exception)` for any non-2xx / non-204 response we can't handle.

- [ ] **Step 1: Implement the module**

```python
# scripts/spotify_client.py
"""Thin Spotify Web API client. Only the endpoints we still can use."""

from __future__ import annotations

import base64
from typing import Any

import requests

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_ROOT = "https://api.spotify.com/v1"
TIMEOUT_S = 10


class SpotifyError(Exception):
    pass


class SpotifyClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token: str | None = None

    def _refresh_access_token(self) -> None:
        basic = base64.b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            },
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=TIMEOUT_S,
        )
        if resp.status_code != 200:
            raise SpotifyError(
                f"token refresh failed: {resp.status_code} {resp.text[:200]}"
            )
        self._access_token = resp.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        if not self._access_token:
            self._refresh_access_token()
        return {"Authorization": f"Bearer {self._access_token}"}

    def currently_playing(self) -> dict[str, Any] | None:
        resp = requests.get(
            f"{API_ROOT}/me/player/currently-playing",
            headers=self._headers(),
            timeout=TIMEOUT_S,
        )
        if resp.status_code == 204:
            return None
        if resp.status_code == 401:
            self._refresh_access_token()
            resp = requests.get(
                f"{API_ROOT}/me/player/currently-playing",
                headers=self._headers(),
                timeout=TIMEOUT_S,
            )
        if resp.status_code == 204:
            return None
        if resp.status_code != 200:
            raise SpotifyError(
                f"currently-playing failed: {resp.status_code} {resp.text[:200]}"
            )
        return resp.json()

    def artist_genres(self, artist_ids: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for artist_id in artist_ids:
            resp = requests.get(
                f"{API_ROOT}/artists/{artist_id}",
                headers=self._headers(),
                timeout=TIMEOUT_S,
            )
            if resp.status_code == 401:
                self._refresh_access_token()
                resp = requests.get(
                    f"{API_ROOT}/artists/{artist_id}",
                    headers=self._headers(),
                    timeout=TIMEOUT_S,
                )
            if resp.status_code != 200:
                raise SpotifyError(
                    f"artist fetch failed for {artist_id}: {resp.status_code}"
                )
            for g in resp.json().get("genres", []):
                if g not in seen:
                    seen.add(g)
                    ordered.append(g)
        return ordered
```

- [ ] **Step 2: Smoke-test against real Spotify**

```bash
SPOTIFY_CLIENT_ID='...' SPOTIFY_CLIENT_SECRET='...' SPOTIFY_REFRESH_TOKEN='...' python3 -c "
from scripts.spotify_client import SpotifyClient
import os
c = SpotifyClient(os.environ['SPOTIFY_CLIENT_ID'], os.environ['SPOTIFY_CLIENT_SECRET'], os.environ['SPOTIFY_REFRESH_TOKEN'])
print('currently_playing:', c.currently_playing())
"
```

Expected: `None` if nothing is playing, or a dict with `item` and `is_playing` if you're actively listening. If it errors, fix before moving on.

- [ ] **Step 3: Commit**

```bash
git add scripts/spotify_client.py
git commit -m "Add Spotify Web API client with lazy token refresh"
```

---

## Task 3: Features client (ReccoBeats + cache)

**Files:**
- Create: `scripts/features_client.py`

**Interfaces:**
- Consumes: Spotify track id (string).
- Produces:
  - `FeaturesClient(cache_path: Path)` — loads existing cache from disk.
  - `client.get(spotify_track_id: str) -> dict | None` — returns features dict or `None`. Cache-first; on miss, calls ReccoBeats (id → UUID → features), writes result (hit or miss) back to cache. Never raises for ReccoBeats network errors; returns `None` instead.
  - `client.save()` — persists cache to disk.

Cache-on-disk shape:
```json
{
  "track_id": {
    "cached_at": "2026-06-28T15:00:14Z",
    "features": { ... } | null
  }
}
```

Miss entries expire after 30 days; hits are kept indefinitely.

- [ ] **Step 1: Implement the module**

```python
# scripts/features_client.py
"""ReccoBeats lookup with a committed on-disk cache."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
from typing import Any

import requests

RB_ROOT = "https://api.reccobeats.com/v1"
TIMEOUT_S = 10
MISS_TTL_DAYS = 30


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _now_iso() -> str:
    return _now().strftime("%Y-%m-%dT%H:%M:%SZ")


class FeaturesClient:
    def __init__(self, cache_path: pathlib.Path):
        self._cache_path = cache_path
        self._cache: dict[str, dict[str, Any]] = {}
        if cache_path.exists():
            try:
                self._cache = json.loads(cache_path.read_text())
            except json.JSONDecodeError:
                self._cache = {}
        self._prune_expired_misses()

    def _prune_expired_misses(self) -> None:
        cutoff = _now() - dt.timedelta(days=MISS_TTL_DAYS)
        for track_id in list(self._cache.keys()):
            entry = self._cache[track_id]
            if entry.get("features") is not None:
                continue
            try:
                cached_at = dt.datetime.strptime(
                    entry["cached_at"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=dt.timezone.utc)
            except (KeyError, ValueError):
                del self._cache[track_id]
                continue
            if cached_at < cutoff:
                del self._cache[track_id]

    def get(self, spotify_track_id: str) -> dict[str, Any] | None:
        if spotify_track_id in self._cache:
            return self._cache[spotify_track_id]["features"]

        features = self._reccobeats_lookup(spotify_track_id)
        self._cache[spotify_track_id] = {
            "cached_at": _now_iso(),
            "features": features,
        }
        return features

    def _reccobeats_lookup(self, spotify_track_id: str) -> dict[str, Any] | None:
        try:
            id_resp = requests.get(
                f"{RB_ROOT}/track",
                params={"ids": spotify_track_id},
                timeout=TIMEOUT_S,
            )
        except requests.RequestException:
            return None
        if id_resp.status_code != 200:
            return None
        body = id_resp.json()
        content = body.get("content") if isinstance(body, dict) else None
        if not content:
            return None
        rb_uuid = content[0].get("id")
        if not rb_uuid:
            return None

        try:
            feat_resp = requests.get(
                f"{RB_ROOT}/track/{rb_uuid}/audio-features",
                timeout=TIMEOUT_S,
            )
        except requests.RequestException:
            return None
        if feat_resp.status_code != 200:
            return None
        f = feat_resp.json()
        if not isinstance(f, dict):
            return None
        return {
            "energy": f.get("energy"),
            "danceability": f.get("danceability"),
            "valence": f.get("valence"),
            "acousticness": f.get("acousticness"),
            "instrumentalness": f.get("instrumentalness"),
            "speechiness": f.get("speechiness"),
            "tempo": f.get("tempo"),
            "liveness": f.get("liveness"),
            "loudness": f.get("loudness"),
            "source": "reccobeats",
        }

    def save(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(
            json.dumps(self._cache, indent=2, sort_keys=True) + "\n"
        )
```

- [ ] **Step 2: Smoke-test with a known track**

```bash
python3 -c "
from pathlib import Path
from scripts.features_client import FeaturesClient
c = FeaturesClient(Path('/tmp/features-cache-test.json'))
# Try a well-known track id: 'Kids' by MGMT
print(c.get('7pXexWjmyGWZY5FZfsRTS7'))
c.save()
"
```

Expected: a features dict with numeric values (energy, tempo, etc.). If it returns `None`, ReccoBeats didn't have the track — try a different id. Not an error unless *every* mainstream track returns `None`, in which case ReccoBeats is down and we stop.

- [ ] **Step 3: Commit**

```bash
git add scripts/features_client.py
git commit -m "Add ReccoBeats features client with on-disk cache"
```

---

## Task 4: Orchestrator (main script + CLI + history)

**Files:**
- Create: `scripts/now_playing.py`
- Modify: `data/` (create directory on first run)

**Interfaces:**
- Consumes: `SpotifyClient`, `FeaturesClient`, `aggregate`.
- Produces: CLI with:
  - `python3 scripts/now_playing.py` — full pipeline, writes artifacts.
  - `python3 scripts/now_playing.py --dry-run` — same but no writes, prints what would be written.

Dedupe rule (from spec): append iff history is empty, OR current `track_id` differs from last, OR current == last AND `now - last.logged_at > 20 min`.

History cap: keep entries where `now - logged_at <= 30 days`, then take last 500 by `logged_at`.

Non-track (podcast/episode) handling: log with `name = episode.name`, `artists: []`, `genres: []`, `audio_features: None`.

- [ ] **Step 1: Implement the orchestrator**

```python
# scripts/now_playing.py
"""Fetch currently-playing, enrich, append to history, write artifacts.

Usage:
    python3 scripts/now_playing.py [--dry-run]

Requires env vars: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET,
SPOTIFY_REFRESH_TOKEN.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
from typing import Any

from aggregate import aggregate
from features_client import FeaturesClient
from spotify_client import SpotifyClient, SpotifyError

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

HISTORY_PATH = DATA_DIR / "history.json"
NOW_PLAYING_PATH = DATA_DIR / "now-playing.json"
AGGREGATES_PATH = DATA_DIR / "aggregates.json"
FEATURES_CACHE_PATH = DATA_DIR / "features-cache.json"

DEDUPE_MINUTES = 20
HISTORY_MAX_ENTRIES = 500
HISTORY_MAX_DAYS = 30


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _now_iso() -> str:
    return _now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.timezone.utc
    )


def _load_json(path: pathlib.Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def _write_json(path: pathlib.Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _extract_snapshot(body: dict[str, Any]) -> dict[str, Any]:
    """Return the internal now-playing.json shape for a currently-playing body."""
    item = body.get("item") or {}
    play_type = body.get("currently_playing_type", "track")
    if play_type == "track":
        artists = [
            {"id": a.get("id"), "name": a.get("name")}
            for a in item.get("artists", [])
        ]
        album = item.get("album") or {}
        images = album.get("images") or []
        widest = max(images, key=lambda im: im.get("width", 0), default=None)
        track = {
            "id": item.get("id"),
            "name": item.get("name"),
            "artists": artists,
            "album": {
                "name": album.get("name"),
                "release_date": album.get("release_date"),
                "image": widest.get("url") if widest else None,
            },
            "duration_ms": item.get("duration_ms"),
            "progress_ms": body.get("progress_ms"),
            "explicit": item.get("explicit"),
            "external_urls": item.get("external_urls") or {},
        }
    else:
        track = {
            "id": item.get("id"),
            "name": item.get("name"),
            "artists": [],
            "album": {},
            "duration_ms": item.get("duration_ms"),
            "progress_ms": body.get("progress_ms"),
        }
    return {
        "fetched_at": _now_iso(),
        "is_playing": bool(body.get("is_playing")),
        "currently_playing_type": play_type,
        "track": track,
    }


def _history_entry(snapshot: dict[str, Any], genres: list[str],
                   features: dict[str, Any] | None) -> dict[str, Any]:
    track = snapshot["track"]
    return {
        "logged_at": _now_iso(),
        "track_id": track.get("id"),
        "name": track.get("name"),
        "artists": [a.get("name") for a in track.get("artists", [])],
        "genres": genres,
        "audio_features": features,
    }


def _should_append(history: list[dict[str, Any]], entry: dict[str, Any]) -> bool:
    if not history:
        return True
    last = history[-1]
    if entry["track_id"] != last.get("track_id"):
        return True
    try:
        last_when = _parse_iso(last["logged_at"])
    except (KeyError, ValueError):
        return True
    now_when = _parse_iso(entry["logged_at"])
    return (now_when - last_when).total_seconds() > DEDUPE_MINUTES * 60


def _cap_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cutoff = _now() - dt.timedelta(days=HISTORY_MAX_DAYS)
    kept = []
    for entry in history:
        try:
            when = _parse_iso(entry["logged_at"])
        except (KeyError, ValueError):
            continue
        if when >= cutoff:
            kept.append(entry)
    return kept[-HISTORY_MAX_ENTRIES:]


def run(dry_run: bool = False) -> int:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        print("Missing SPOTIFY_* env vars", file=sys.stderr)
        return 2

    spotify = SpotifyClient(client_id, client_secret, refresh_token)
    features_client = FeaturesClient(FEATURES_CACHE_PATH)
    history = _load_json(HISTORY_PATH, default=[])
    if not isinstance(history, list):
        history = []

    try:
        body = spotify.currently_playing()
    except SpotifyError as e:
        print(f"Spotify error: {e}", file=sys.stderr)
        return 1

    if body is None:
        now_playing = {
            "fetched_at": _now_iso(),
            "is_playing": False,
            "track": None,
        }
    else:
        snapshot = _extract_snapshot(body)
        now_playing = snapshot
        track = snapshot["track"]
        track_id = track.get("id")

        if snapshot["currently_playing_type"] == "track" and track_id:
            artist_ids = [
                a["id"] for a in track.get("artists", []) if a.get("id")
            ]
            try:
                genres = spotify.artist_genres(artist_ids)
            except SpotifyError as e:
                print(f"Genre fetch failed: {e}", file=sys.stderr)
                genres = []
            features = features_client.get(track_id)
        else:
            genres = []
            features = None

        snapshot["genres"] = genres
        snapshot["audio_features"] = features

        if track_id:
            entry = _history_entry(snapshot, genres, features)
            if _should_append(history, entry):
                history.append(entry)

    history = _cap_history(history)
    aggregates = aggregate(history, window=50)

    if dry_run:
        print("--- now-playing ---")
        print(json.dumps(now_playing, indent=2))
        print("--- history length ---", len(history))
        print("--- aggregates ---")
        print(json.dumps(aggregates, indent=2))
        return 0

    _write_json(NOW_PLAYING_PATH, now_playing)
    _write_json(HISTORY_PATH, history)
    _write_json(AGGREGATES_PATH, aggregates)
    features_client.save()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Dry-run against real Spotify (nothing playing case)**

Pause Spotify. Then:

```bash
SPOTIFY_CLIENT_ID='...' SPOTIFY_CLIENT_SECRET='...' SPOTIFY_REFRESH_TOKEN='...' python3 scripts/now_playing.py --dry-run
```

Expected output: a `now-playing` block with `is_playing: false, track: null`, `history length` = 0 (first run), and aggregates showing `state: "calibrating"`. Exit code 0. No files written.

- [ ] **Step 3: Dry-run against real Spotify (something playing)**

Start playing a song on Spotify. Then rerun the same command.

Expected: full track object, at least one genre when the artist has any, features dict (or null), history length 1, aggregates populated with means (with 1 play, means == that track's values). Exit code 0.

- [ ] **Step 4: First real run (writes artifacts)**

While a song is playing:

```bash
SPOTIFY_CLIENT_ID='...' SPOTIFY_CLIENT_SECRET='...' SPOTIFY_REFRESH_TOKEN='...' python3 scripts/now_playing.py
ls -la data/
cat data/aggregates.json
```

Expected: four JSON files in `data/`, `aggregates.json` has the current track's features as the means.

- [ ] **Step 5: Commit**

```bash
git add scripts/now_playing.py data/now-playing.json data/history.json data/aggregates.json data/features-cache.json
git commit -m "Add now-playing orchestrator and initial data artifacts"
```

---

## Task 5: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/now-playing.yml`

**Interfaces:**
- Consumes: repo secrets `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REFRESH_TOKEN`.
- Produces: a cron-driven workflow that runs every 5 minutes on the `now-playing` branch (later: `master`), commits changed data files back to the branch.

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/now-playing.yml
name: now-playing

on:
  schedule:
    - cron: "*/5 * * * *"
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: now-playing
  cancel-in-progress: true

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install requests

      - name: Run pipeline
        env:
          SPOTIFY_CLIENT_ID: ${{ secrets.SPOTIFY_CLIENT_ID }}
          SPOTIFY_CLIENT_SECRET: ${{ secrets.SPOTIFY_CLIENT_SECRET }}
          SPOTIFY_REFRESH_TOKEN: ${{ secrets.SPOTIFY_REFRESH_TOKEN }}
        run: python3 scripts/now_playing.py

      - name: Commit changes
        run: |
          git config user.name "now-playing-bot"
          git config user.email "actions@users.noreply.github.com"
          git add data/
          if git diff --cached --quiet; then
            echo "No changes to commit"
          else
            git commit -m "chore: update now-playing"
            git push
          fi
```

- [ ] **Step 2: Commit and push the branch so the workflow file exists remotely**

```bash
git add .github/workflows/now-playing.yml
git commit -m "Add now-playing GitHub Actions workflow"
git push -u origin now-playing
```

- [ ] **Step 3: Trigger manually via `workflow_dispatch`**

In GitHub UI → Actions → `now-playing` → Run workflow → Branch: `now-playing`. Watch the run.

Expected: green run, and a commit like `chore: update now-playing` appears on the `now-playing` branch. If a track is playing, `data/aggregates.json` has real values; otherwise it stays as-is or the calibrating state.

- [ ] **Step 4: Wait for a scheduled cron run**

Wait ~5 min. Confirm a second run kicks off automatically. Actions may delay it a bit — accept up to ~15 min lag before worrying.

- [ ] **Step 5: Pull the bot's commits into local**

```bash
git pull --ff-only origin now-playing
```

No commit needed here — the bot did it.

---

## Task 6: Front-end (include + styles + JS + music.html wire-in)

**Files:**
- Create: `_includes/now-playing.html`
- Create: `_sass/_now-playing.scss`
- Create: `assets/js/now-playing.js`
- Modify: `_layouts/music.html` — add include above `<div class="music-bands">`.
- Modify: whichever sass file `@import`s partials — add `now-playing`.
- Modify: `_config.yml` — add `_docs` to `exclude`.

- [ ] **Step 1: Confirm the sass entrypoint**

```bash
ls assets/css/
grep -R "@import" assets/css/ _sass/ | head -20
```

Expected: a main SCSS file that `@import`s the partials (`_home`, `_music`, etc.). Note the exact path — we'll add `@import 'now-playing';` next to those imports.

- [ ] **Step 2: Write the include**

```html
{%- comment -%}
Aggregated listening banner: last 50 Spotify plays.
Data comes from data/aggregates.json (written by scripts/now_playing.py).
{%- endcomment -%}
<section class="np" data-np aria-label="Recent listening" hidden>
  <div class="np__eyebrow" data-np-eyebrow>LAST 50 PLAYS</div>
  <div class="np__rule"></div>
  <div class="np__body">
    <div class="np__bars" data-np-bars>
      <!-- filled by JS -->
    </div>
    <div class="np__sweep" data-np-sweep aria-hidden="true"></div>
  </div>
  <div class="np__rule"></div>
  <div class="np__genres" data-np-genres></div>
</section>
```

- [ ] **Step 3: Write the styles**

```scss
// _sass/_now-playing.scss
.np {
  padding: 30px 56px 24px;
  border-bottom: 1px solid var(--fn-rule);
  font-family: var(--fn-sans);
  color: var(--fn-ink);

  &[hidden] { display: none; }
}

.np__eyebrow {
  @extend .fn-eyebrow;
  margin-bottom: 12px;
}

.np__rule {
  border-top: 1px solid var(--fn-rule);
  margin: 8px 0;
}

.np__body {
  position: relative;
}

.np__bars {
  display: grid;
  grid-template-columns: 140px 1fr 48px;
  row-gap: 6px;
  column-gap: 14px;
  align-items: center;
}

.np__bar-label {
  font-family: var(--fn-mono);
  font-size: 10.5px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--fn-ink2);
}

.np__bar-track {
  height: 8px;
  background: var(--fn-panel);
  position: relative;
}

.np__bar-fill {
  height: 100%;
  background: var(--fn-amber);
}

.np__bar-value {
  font-family: var(--fn-mono);
  font-size: 10.5px;
  color: var(--fn-ink);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.np__sweep {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 154px;                         // align to bar column start (label col + gap)
  right: 62px;                         // align to bar column end
  pointer-events: none;

  &::after {
    content: "";
    position: absolute;
    top: 0;
    bottom: 0;
    width: 1px;
    background: var(--fn-ink2);
    opacity: 0.35;
    left: 0;
    animation: np-sweep var(--np-sweep-period, 2s) linear infinite;
  }
}

@keyframes np-sweep {
  0%   { transform: translateX(0); }
  100% { transform: translateX(var(--np-sweep-distance, 100%)); }
}

@media (prefers-reduced-motion: reduce) {
  .np__sweep { display: none; }
}

.np__genres {
  margin-top: 10px;
  font-family: var(--fn-mono);
  font-size: 11px;
  letter-spacing: 0.04em;
  color: var(--fn-ink2);
}

.np--calibrating .np__body,
.np--calibrating .np__rule + .np__rule,
.np--calibrating .np__genres { display: none; }

@media (max-width: 767px) {
  .np { padding: 20px 16px 18px; }
  .np__bars { grid-template-columns: 110px 1fr 42px; }
  .np__sweep { left: 124px; right: 56px; }
}
```

- [ ] **Step 4: Write the JS**

```javascript
// assets/js/now-playing.js
(function () {
  const ROOT_SEL = '[data-np]';
  const POLL_MS = 60_000;
  const FEATURE_KEYS = [
    'energy', 'danceability', 'valence',
    'acousticness', 'instrumentalness', 'speechiness'
  ];
  const FEATURE_LABELS = {
    energy: 'ENERGY',
    danceability: 'DANCEABILITY',
    valence: 'VALENCE',
    acousticness: 'ACOUSTICNESS',
    instrumentalness: 'INSTRUMENTAL',
    speechiness: 'SPEECHINESS',
  };

  let pollTimer = null;

  function fmt(n) {
    return (Math.round(n * 100) / 100).toFixed(2);
  }

  function render(root, data) {
    root.hidden = false;
    const eyebrow = root.querySelector('[data-np-eyebrow]');
    const bars = root.querySelector('[data-np-bars]');
    const genres = root.querySelector('[data-np-genres]');

    if (data && data.state === 'calibrating') {
      root.classList.add('np--calibrating');
      eyebrow.textContent = 'CALIBRATING';
      bars.innerHTML = '';
      genres.textContent = '';
      return;
    }
    root.classList.remove('np--calibrating');

    const artists = data.totals && data.totals.unique_artists;
    const bpm = data.tempo_mean_bpm;
    const plays = data.totals && data.totals.plays;
    eyebrow.textContent =
      `LAST ${plays} PLAYS · ${artists} ARTISTS · AVG ${Math.round(bpm)} BPM`;

    const rows = FEATURE_KEYS.map((key) => {
      const value = data.audio_features_mean[key];
      const pct = Math.max(0, Math.min(1, value)) * 100;
      return `
        <div class="np__bar-label">${FEATURE_LABELS[key]}</div>
        <div class="np__bar-track"><div class="np__bar-fill" style="width:${pct.toFixed(1)}%"></div></div>
        <div class="np__bar-value">${fmt(value)}</div>
      `;
    }).join('');
    bars.innerHTML = rows;

    const g = (data.top_genres || []).map(x => x.name).join(' · ');
    genres.textContent = g;

    // Sweep speed: one full traversal = 1 beat = 60 / BPM seconds.
    if (bpm && Number.isFinite(bpm) && bpm > 0) {
      const period = (60 / bpm).toFixed(3) + 's';
      root.style.setProperty('--np-sweep-period', period);
      root.style.setProperty('--np-sweep-distance', '100%');
    }
  }

  async function fetchOnce(root) {
    try {
      const resp = await fetch(`/data/aggregates.json?t=${Date.now()}`, {
        cache: 'no-store',
      });
      if (!resp.ok) return;
      const data = await resp.json();
      render(root, data);
    } catch (_e) {
      // Silent fail — leave the last rendered state up.
    }
  }

  function startPolling(root) {
    if (pollTimer) return;
    pollTimer = setInterval(() => {
      if (!document.hidden) fetchOnce(root);
    }, POLL_MS);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const root = document.querySelector(ROOT_SEL);
    if (!root) return;
    fetchOnce(root);
    startPolling(root);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stopPolling();
      else { fetchOnce(root); startPolling(root); }
    });
  });
})();
```

- [ ] **Step 5: Wire the include into the layout**

Open `_layouts/music.html`. After the `<header class="music-hero">...</header>` block and before `<div class="music-bands">`, add:

```html
{% include now-playing.html %}
<script src="{{ '/assets/js/now-playing.js' | relative_url }}" defer></script>
```

- [ ] **Step 6: Wire the SCSS partial into the entry file**

In whichever sass file `@import`s the other partials (found in Step 1), add:

```scss
@import 'now-playing';
```

Place it next to `@import 'music';`.

- [ ] **Step 7: Exclude `_docs` from Jekyll builds (belt-and-suspenders)**

Open `_config.yml`. Modify the existing `exclude` block:

```yaml
exclude:
  - _social-card.html
  - _docs
```

- [ ] **Step 8: Test locally**

```bash
bundle exec jekyll serve
```

Open `http://localhost:4000/music/` in a browser.

Expected: the banner renders above the three band cards. Bars display feature means from `data/aggregates.json` (whatever the last cron run wrote, or your local dry-run). The playhead line sweeps left-to-right at the average BPM. Genre chips render below the bars.

Also test the calibrating state: temporarily rename `data/aggregates.json`, hand-write:

```json
{ "state": "calibrating", "generated_at": "2026-07-07T00:00:00Z", "window": {"plays_used": 0, "plays_with_features": 0} }
```

Reload. Expected: `CALIBRATING` label, no bars, no sweep, no genres. Restore the real file after.

Test reduced motion: in Chrome DevTools, Rendering panel, "Emulate CSS media feature prefers-reduced-motion: reduce". The sweep line should disappear; bars stay visible.

- [ ] **Step 9: Commit**

```bash
git add _includes/now-playing.html _sass/_now-playing.scss assets/js/now-playing.js _layouts/music.html assets/css/main.scss _config.yml
git commit -m "Add /music/ Now Playing banner: bars, playhead sweep, top genres"
```

(If the sass entrypoint is a file other than `assets/css/main.scss`, adjust the `git add` accordingly.)

---

## Task 7: README setup section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a "Now playing setup" section**

Append to `README.md`:

````markdown
## Now Playing (aggregated listening banner on /music/)

The `/music/` page shows the average vibe of my last 50 Spotify plays,
updated by a GitHub Actions cron every 5 minutes.

### One-time setup

1. Create a Spotify app at
   [developer.spotify.com](https://developer.spotify.com/dashboard). The
   dashboard requires the app owner to have Spotify Premium. Set the
   redirect URI to `http://127.0.0.1:3000` (no trailing slash), and check
   only the **Web API** box under APIs used.

2. Obtain a refresh token locally:

   ```bash
   SPOTIFY_CLIENT_ID='your-client-id' \
   SPOTIFY_CLIENT_SECRET='your-client-secret' \
   python3 scripts/get_refresh_token.py
   ```

   Approve the browser prompt when it opens. The script prints a refresh
   token between two `====` lines.

3. Add these repo secrets under Settings → Secrets and variables → Actions:

   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`
   - `SPOTIFY_REFRESH_TOKEN`

4. Trigger the workflow once manually via the Actions tab to confirm.
   Subsequent runs happen automatically every 5 minutes.

### Data artifacts

Written to `data/` by the cron. All are safe to commit.

- `now-playing.json` — internal snapshot of the most recent run.
- `history.json` — rolling last 500 plays / 30 days.
- `aggregates.json` — precomputed averages the page reads.
- `features-cache.json` — per-track ReccoBeats cache; keeps runs fast.

### Rotating the client secret

Rotate the Spotify client secret any time you suspect it's leaked
(Settings → View client secret → Rotate) and update the GitHub Actions
secret with the new value. Existing refresh tokens continue to work.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Document Spotify setup for the now-playing banner"
```

---

## Post-plan: merge to master

Only after Tasks 1–7 are complete AND you've watched at least one real cron run produce populated `aggregates.json` AND the branch renders correctly on `bundle exec jekyll serve`.

```bash
git checkout master
git merge --no-ff now-playing
git push origin master
```

The workflow file lives on `master` after merge, and the cron continues from there.

---

## Self-review notes

- **Spec coverage:** every section of `_docs/superpowers/specs/2026-06-28-now-playing-design.md` maps to a task (aggregation → Task 1; Spotify client → Task 2; features + cache → Task 3; orchestrator, dedupe, history cap, artifact writes → Task 4; workflow → Task 5; front-end + placement + reduced-motion → Task 6; README + one-time setup → Task 7). SoundStat fallback is deliberately deferred out of MVP (user decision).
- **Placeholders:** none — every step includes concrete code or exact commands.
- **Type consistency:** `aggregate()` and `SpotifyClient` and `FeaturesClient` signatures are consistent across tasks; the orchestrator (Task 4) imports each with the exact names declared in the earlier tasks.
