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
