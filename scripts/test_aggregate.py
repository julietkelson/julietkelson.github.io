import datetime as dt
import unittest

from aggregate import aggregate


def _days_ago(n: int) -> str:
    when = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=n)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


RECENT = _days_ago(1)

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


def entry(track_id, artists, genres, features, when=RECENT):
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
            entry("c", ["C"], [], None),
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
        self.assertEqual(names[0], "folk")
        self.assertEqual(names[1], "indie")
        self.assertLessEqual(len(result["top_genres"]), 5)

    def test_unique_artists_deduped(self):
        history = [
            entry("a", ["A", "B"], ["folk"], FEATURES_A),
            entry("b", ["B", "C"], ["folk"], FEATURES_B),
        ]
        result = aggregate(history)
        self.assertEqual(result["totals"]["unique_artists"], 3)

    def test_days_window_excludes_plays_older_than_cutoff(self):
        history = [
            entry("old", ["A"], ["folk"], FEATURES_A, when=_days_ago(45)),
            entry("recent1", ["B"], ["folk"], FEATURES_B, when=_days_ago(5)),
            entry("recent2", ["C"], ["folk"], FEATURES_A, when=_days_ago(1)),
        ]
        result = aggregate(history, days=30)
        self.assertEqual(result["totals"]["plays"], 2)

    def test_days_zero_includes_all_history(self):
        history = [
            entry("old", ["A"], ["folk"], FEATURES_A, when=_days_ago(400)),
            entry("recent", ["B"], ["folk"], FEATURES_B, when=_days_ago(1)),
        ]
        result = aggregate(history, days=0)
        self.assertEqual(result["totals"]["plays"], 2)

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


if __name__ == "__main__":
    unittest.main()
