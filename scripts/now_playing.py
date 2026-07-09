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

HISTORY_MAX_ENTRIES = 500
HISTORY_MAX_DAYS = 30


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _now_iso() -> str:
    return _now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s: str) -> dt.datetime:
    """Parse ISO timestamps with or without fractional seconds."""
    s = s.replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        s = s.split(".")[0] + "+00:00"
        return dt.datetime.fromisoformat(s)


def _normalize_iso(s: str) -> str:
    return _parse_iso(s).astimezone(dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
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


def _latest_played_ms(history: list[dict[str, Any]]) -> int | None:
    """Return the last logged play's timestamp in Unix ms, or None if empty."""
    if not history:
        return None
    try:
        when = _parse_iso(history[-1]["logged_at"])
    except (KeyError, ValueError):
        return None
    return int(when.timestamp() * 1000)


def _snapshot_from_item(item: dict[str, Any]) -> dict[str, Any]:
    """Shape a recently-played item into a `now-playing.json` snapshot."""
    track = item.get("track") or {}
    artists = [
        {"id": a.get("id"), "name": a.get("name")}
        for a in track.get("artists", [])
    ]
    album = track.get("album") or {}
    images = album.get("images") or []
    widest = max(images, key=lambda im: im.get("width", 0), default=None)
    return {
        "fetched_at": _now_iso(),
        "played_at": item.get("played_at"),
        "track": {
            "id": track.get("id"),
            "name": track.get("name"),
            "artists": artists,
            "album": {
                "name": album.get("name"),
                "release_date": album.get("release_date"),
                "image": widest.get("url") if widest else None,
            },
            "duration_ms": track.get("duration_ms"),
            "explicit": track.get("explicit"),
            "external_urls": track.get("external_urls") or {},
        },
    }


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

    after_ms = _latest_played_ms(history)
    try:
        items = spotify.recently_played(after_ms=after_ms)
    except SpotifyError as e:
        print(f"Spotify error: {e}", file=sys.stderr)
        return 1

    # Spotify returns newest-first; append in chronological order.
    items.reverse()

    known_played_ats = {
        e.get("logged_at") for e in history if e.get("logged_at")
    }
    new_count = 0
    for item in items:
        played_at_raw = item.get("played_at")
        track = item.get("track") or {}
        track_id = track.get("id")
        if not played_at_raw or not track_id:
            continue
        try:
            played_at = _normalize_iso(played_at_raw)
        except ValueError:
            continue
        if played_at in known_played_ats:
            continue

        artist_ids = [
            a["id"] for a in track.get("artists", []) if a.get("id")
        ]
        try:
            genres = spotify.artist_genres(artist_ids)
        except SpotifyError as e:
            print(f"Genre fetch failed for {track_id}: {e}", file=sys.stderr)
            genres = []

        features = features_client.get(track_id)

        history.append({
            "logged_at": played_at,
            "track_id": track_id,
            "name": track.get("name"),
            "artists": [a.get("name") for a in track.get("artists", [])],
            "genres": genres,
            "audio_features": features,
        })
        known_played_ats.add(played_at)
        new_count += 1

    history.sort(key=lambda e: e.get("logged_at", ""))
    history = _cap_history(history)
    aggregates = aggregate(history, window=50)

    if items:
        now_playing = _snapshot_from_item(items[-1])
    elif history:
        last = history[-1]
        now_playing = {
            "fetched_at": _now_iso(),
            "played_at": last.get("logged_at"),
            "track": {
                "id": last.get("track_id"),
                "name": last.get("name"),
                "artists": [{"name": n} for n in last.get("artists", [])],
            },
        }
    else:
        now_playing = {
            "fetched_at": _now_iso(),
            "track": None,
        }

    if dry_run:
        print(f"--- fetched {len(items)} items, appended {new_count} new ---")
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
