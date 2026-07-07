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

    def test_window_truncates_to_most_recent_n(self):
        history = [
            entry(str(i), [f"A{i}"], ["folk"], FEATURES_A) for i in range(60)
        ]
        result = aggregate(history, window=50)
        self.assertEqual(result["totals"]["plays"], 50)


if __name__ == "__main__":
    unittest.main()
