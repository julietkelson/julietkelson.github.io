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
