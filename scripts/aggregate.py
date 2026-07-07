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

    genre_counts: Counter[str] = Counter()
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
