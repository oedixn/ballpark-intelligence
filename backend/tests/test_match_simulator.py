import unittest
from collections import Counter
from statistics import mean, pvariance
from unittest.mock import patch

from game_simulator.simulator_main import GameLog, MatchSimulator, PlayerProb


def make_match(seed=42, only_outs=False):
    player = PlayerProb(
        name="타자", bb=0 if only_outs else 0.08,
        single=0 if only_outs else 0.17, double=0 if only_outs else 0.05,
        triple=0, hr=0 if only_outs else 0.03,
    )
    return MatchSimulator("원정", [player] * 9, "홈", [player] * 9, seed=seed)


class MatchDistributionTests(unittest.TestCase):
    def test_aggregates_the_same_games_as_logged_matches(self):
        logged = make_match()
        scores = [logged.simulate_game().final_score for _ in range(200)]
        result = make_match().simulate_many(n_games=len(scores))
        actual = {
            (entry["team_a_score"], entry["team_b_score"]): entry["count"]
            for entry in result["score_distribution"]
        }
        self.assertEqual(actual, Counter(scores))
        self.assertEqual(sum(actual.values()), 200)
        for index, key in enumerate(("team_a", "team_b")):
            stats = result[key]
            values = [score[index] for score in scores]
            self.assertAlmostEqual(stats["mean_runs"], mean(values))
            self.assertAlmostEqual(stats["variance"], pvariance(values))
            self.assertEqual(stats["wins"], sum(s[index] > s[1 - index] for s in scores))
            self.assertEqual(stats["prob_0_runs"], values.count(0) / len(values))
            self.assertEqual(stats["prob_5_or_more_runs"], sum(v >= 5 for v in values) / len(values))
        self.assertEqual(result["draws"], sum(a == b for a, b in scores))
        self.assertEqual(result["team_a"]["wins"] + result["team_b"]["wins"] + result["draws"], 200)

    def test_zero_variance_and_twelve_inning_draw(self):
        match = make_match(only_outs=True)
        game = match.simulate_game()
        self.assertEqual(len(game.innings), 24)
        self.assertEqual(game.final_score, (0, 0))
        result = match.simulate_many(n_games=3)
        self.assertEqual(result["score_distribution"], [{"team_a_score": 0, "team_b_score": 0, "count": 3}])
        self.assertEqual(result["draws"], 3)
        for key in ("team_a", "team_b"):
            self.assertEqual(result[key]["mean_runs"], 0)
            self.assertEqual(result[key]["variance"], 0)
            self.assertEqual(result[key]["prob_0_runs"], 1)

    def test_walkoff_and_skipped_home_half_use_existing_match_rules(self):
        match = make_match()
        # 1회말 홈런으로 끝내기.
        with patch.object(match, "sample_event", side_effect=["OUT"] * 3 + ["HR"]):
            game = match.simulate_game(innings=1)
        self.assertEqual(game.final_score, (0, 1))
        self.assertEqual(len(game.innings[-1].plate_appearances), 1)
        # 1회말에 앞선 홈팀은 정규 마지막인 2회말을 생략.
        with patch.object(match, "sample_event", side_effect=["OUT"] * 3 + ["HR"] + ["OUT"] * 6):
            game = match.simulate_game(innings=2)
        self.assertEqual(game.final_score, (0, 1))
        self.assertEqual([(i.inning, i.half) for i in game.innings], [(1, "초"), (1, "말"), (2, "초")])

    def test_preserves_high_scores_and_orders_by_frequency(self):
        match = make_match()
        scores = [(30, 1), (0, 0), (30, 1), (1, 30)]
        with patch.object(match, "simulate_game", side_effect=[GameLog("원정", "홈", s, []) for s in scores]):
            result = match.simulate_many(n_games=4)
        self.assertEqual(result["score_distribution"][0], {"team_a_score": 30, "team_b_score": 1, "count": 2})
        self.assertEqual(len(result["score_distribution"]), 3)

    def test_rejects_invalid_counts_and_innings(self):
        for kwargs in ({"n_games": 0}, {"n_games": -1}, {"innings": 0}, {"innings": 13}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                make_match().simulate_many(**kwargs)


if __name__ == "__main__":
    unittest.main()
