import csv
from dataclasses import asdict, replace
from datetime import date
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from game_simulator.bullpen import (
    BullpenConfig, PitchingPolicy, PitchingSituation, PitchingStaff,
    appearance_workloads, build_pitching_staff,
)
from game_simulator.simulator_main import (
    LeagueAverageProb, MatchSimulator, PitcherProb, PlayerProb,
    adjust_lineup_by_pitcher, load_team_pitching_staff,
)


AVERAGE = LeagueAverageProb(.08, .17, .05, .005, .03, .665)
BATTER = PlayerProb("타자", .08, .17, .05, .005, .03)


def pitcher(name, team, **kwargs):
    return PitcherProb(name, team, **(asdict(AVERAGE) |
                       {"player_id": name, "g": 20, "gs": 0, "tbf": 120} | kwargs))


def staff(team, budget=3):
    starter = pitcher(team + "S", team, gs=20, tbf=480)
    relievers = (pitcher(team + "R1", team, hld=10), pitcher(team + "R2", team))
    workloads = {(starter.player_id, "starter"): (budget,)}
    workloads.update({(p.player_id, "reliever"): (3,) for p in relievers})
    return PitchingStaff(starter, relievers, workloads=workloads)


def match(enabled=True, seed=42):
    return MatchSimulator("A", [BATTER] * 9, "B", [BATTER] * 9, seed=seed,
                          bullpen_enabled=enabled, team_a_staff=staff("A"),
                          team_b_staff=staff("B"), league_avg=AVERAGE)


class BullpenTests(unittest.TestCase):
    def test_off_preserves_seeded_results_and_does_not_build_pitcher_cache(self):
        legacy = MatchSimulator("A", [BATTER] * 9, "B", [BATTER] * 9, seed=42)
        disabled = match(False)
        self.assertEqual(legacy.simulate_many(100), disabled.simulate_many(100))
        self.assertEqual(legacy.simulate_game(), disabled.simulate_game())
        self.assertEqual(disabled._pitcher_lineups, {})
        self.assertNotIn("bullpen", match(False).simulate_many(1))

    def test_logging_does_not_change_random_stream_and_each_game_resets_pitchers(self):
        logged = match()
        games = [logged.simulate_game() for _ in range(20)]
        aggregate = match().simulate_many(20)
        counts = {(r["team_a_score"], r["team_b_score"]): r["count"] for r in aggregate["score_distribution"]}
        expected = {}
        for game in games:
            expected[game.final_score] = expected.get(game.final_score, 0) + 1
            for team in ("A", "B"):
                used = [r for r in game.pitching_appearances if r["team_name"] == team]
                self.assertEqual(used[0]["pitcher_id"], team + "S")
                self.assertEqual(len({r["pitcher_id"] for r in used}), len(used))
        self.assertEqual(counts, expected)
        self.assertEqual(sum(counts.values()), 20)
        self.assertEqual(aggregate, match().simulate_many(20))
        self.assertTrue(aggregate["bullpen"]["enabled"])
        self.assertFalse(aggregate["bullpen"]["calibrated"])
        for team in ("A", "B"):
            total = sum(r["team_name"] == team for g in games for r in g.pitching_appearances)
            self.assertEqual(aggregate["bullpen"]["usage"][team]["mean_pitchers"], total / 20)

    def test_inning_change_preserves_bases_outs_and_batter_order(self):
        game = match()
        pitching = staff("B", budget=1)
        state = game.pitching_policy.start_game(pitching, game.rng)
        changes = []
        with patch.object(game, "sample_event", side_effect=["BB", "OUT", "HR", "OUT", "OUT"]):
            half, next_idx, _ = game.simulate_half_inning(
                1, "초", "A", [BATTER] * 9, 0, pitching_state=state,
                pitching_changes=changes,
            )
        self.assertEqual(half.runs, 2)
        self.assertEqual(next_idx, 5)
        self.assertEqual([p.batter_order for p in half.plate_appearances], [1, 2, 3, 4, 5])
        self.assertEqual(changes[0].outs, 0)
        self.assertIn("1루", changes[0].bases)
        self.assertEqual(half.plate_appearances[1].outs_after, 1)
        self.assertEqual(half.plate_appearances[2].runs_scored, 2)
        self.assertEqual(half.plate_appearances[0].pitcher_name, "BS")
        self.assertNotEqual(half.plate_appearances[1].pitcher_name, "BS")
        self.assertIsNotNone(half.plate_appearances[1].pitching_change_reason)
        self.assertEqual(state.appearances[1].runs_on_mound, 2)

    def test_matchup_cache_uses_original_batter_rates_for_each_pitcher(self):
        bullpen = replace(staff("B"), relievers=(pitcher("BR", "B", hr=.15, out=.545),))
        game = MatchSimulator("A", [BATTER] * 9, "B", [BATTER] * 9, seed=2,
                              bullpen_enabled=True, team_a_staff=staff("A"), team_b_staff=bullpen,
                              league_avg=AVERAGE, bullpen_config=BullpenConfig(relief_prior_batters=0))
        expected = adjust_lineup_by_pitcher([BATTER] * 9, bullpen.relievers[0], AVERAGE)
        self.assertEqual(game._pitcher_lineups["B"]["BR"], expected)
        self.assertEqual(game.team_a_lineup[0], BATTER.normalized())

    def test_tiny_relief_sample_is_shrunk_and_probability_sums_to_one(self):
        wild = pitcher("BR", "B", tbf=1, hr=.9, out=.001)
        game = MatchSimulator("A", [BATTER] * 9, "B", [BATTER] * 9, bullpen_enabled=True,
                              team_a_staff=staff("A"), team_b_staff=PitchingStaff(staff("B").starter, (wild,)),
                              league_avg=AVERAGE)
        adjusted = game._pitcher_lineups["B"]["BR"][0]
        raw = adjust_lineup_by_pitcher([BATTER] * 9, wild, AVERAGE)[0]
        self.assertLess(adjusted.hr, raw.hr)
        self.assertAlmostEqual(sum(p for _, p in adjusted.event_probs()), 1)

    def test_exhausted_bullpen_keeps_last_pitcher_through_extra_innings(self):
        game = match()
        with patch.object(game, "sample_event", return_value="OUT"):
            log = game.simulate_game()
        self.assertEqual(log.final_score, (0, 0))
        self.assertEqual(len(log.innings), 24)
        for team in ("A", "B"):
            used = [r for r in log.pitching_appearances if r["team_name"] == team]
            self.assertEqual(len(used), 3)
            self.assertEqual(sum(r["outs"] for r in used), 36)
        self.assertEqual(len(log.pitching_changes), 4)

    def test_empty_bullpen_and_walkoff_do_not_create_phantom_appearances(self):
        game = MatchSimulator("A", [BATTER] * 9, "B", [BATTER] * 9,
                              bullpen_enabled=True, team_a_staff=PitchingStaff(staff("A").starter),
                              team_b_staff=PitchingStaff(staff("B").starter), league_avg=AVERAGE)
        with patch.object(game, "sample_event", side_effect=["OUT"] * 3 + ["HR"]):
            log = game.simulate_game(innings=1)
        self.assertEqual(log.final_score, (0, 1))
        self.assertFalse(log.pitching_changes)
        self.assertEqual(sum(r["batters_faced"] for r in log.pitching_appearances), 4)
        with patch.object(game, "sample_event", side_effect=["OUT"] * 3 + ["HR"] + ["OUT"] * 6):
            log = game.simulate_game(innings=2)
        self.assertEqual([(h.inning, h.half) for h in log.innings], [(1,"초"),(1,"말"),(2,"초")])
        self.assertEqual(sum(r["batters_faced"] for r in log.pitching_appearances), 10)

    def test_close_lead_selects_closer_but_tie_and_large_deficit_reserve_him(self):
        p = PitchingPolicy()
        s = staff("A")
        s = replace(s, closer_id="AR2")
        for lead, expected in ((1, "AR2"), (3, "AR2"), (0, "AR1"), (-5, "AR1")):
            state = p.start_game(s, random.Random(1))
            state.current.batters_faced = 3
            situation = PitchingSituation(9, 9, 0, 0, lead)
            with self.subTest(lead=lead):
                self.assertEqual(p.select_replacement(state, situation)[0].player_id, expected)
        # A closer warming up is not a reason to replace a brand-new pitcher.
        state = p.start_game(s, random.Random(1))
        self.assertIsNone(p.should_replace(state, PitchingSituation(9, 9, 0, 0, 1)))

    def test_early_hook_and_crisis_are_separate_from_workload_limit(self):
        policy = PitchingPolicy()
        state = policy.start_game(staff("A", budget=30), random.Random(2))
        state.current.batters_faced = 10
        state.current.runs_on_mound = 4
        self.assertIn("조기", policy.should_replace(state, PitchingSituation(3,9,1,0,-4)))
        state.current.runs_on_mound = 0
        state.current.reaches = 4
        self.assertIn("위기", policy.should_replace(state, PitchingSituation(3,9,1,3,1)))
        self.assertIsNone(policy.should_replace(state, PitchingSituation(3,9,2,3,1)))

    def test_staff_inference_includes_swingman_and_does_not_invent_a_closer(self):
        starter = pitcher("S", "A", gs=20)
        swing = pitcher("swing", "A", gs=5)
        another_starter = pitcher("SP", "A", gs=18)
        s = build_pitching_staff(starter, [starter, swing, another_starter])
        self.assertEqual(s.relievers, (swing,))
        self.assertIsNone(s.closer_id)
        s = build_pitching_staff(starter, [swing, pitcher("C", "A", sv=20)])
        self.assertEqual(s.closer_id, "C")

    def test_config_and_duplicate_staff_validation(self):
        for kwargs in ({"starter_batters":0}, {"reliever_batters":True},
                       {"relief_prior_batters":float("nan")}, {"crisis_runners":4}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                BullpenConfig(**kwargs)
        with self.assertRaises(ValueError):
            PitchingStaff(staff("A").starter, (staff("A").starter,))
        with self.assertRaises(ValueError):
            MatchSimulator("A", [BATTER]*9, "B", [BATTER]*9, bullpen_enabled=True)

    def test_csv_loader_keeps_same_season_team_and_uses_daily_role_workloads(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pitchers.csv"
            rows = [dict(season_year=2026, player_id="R", player_name="R", team_name="A", gs=0,g=20,tbf=100,h=20),
                    dict(season_year=2025, player_id="old", player_name="old", team_name="A", gs=0,g=20,tbf=100,h=20),
                    dict(season_year=2026, player_id="other", player_name="other", team_name="B", gs=0,g=20,tbf=100,h=20)]
            with path.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
            history = Path(folder) / "daily.json"
            daily = [dict(player_id="R",team_name="A",gs=0,tbf=7)]
            history.write_text(json.dumps(dict(schema_version=1,complete=True,season=2026,pitchers=daily)), encoding="utf-8")
            s = load_team_pitching_staff(staff("A").starter, 2026, path, history)
            self.assertEqual([p.name for p in s.relievers], ["R"])
            self.assertEqual(s.workloads[("R","reliever")], (7,))
            usage = PitchingPolicy().new_usage(s, s.relievers[0], "reliever", random.Random(1))
            self.assertEqual((usage.budget, usage.workload_source), (7,"daily_appearance_sample"))
            self.assertEqual(appearance_workloads(daily, "B"), {})


if __name__ == "__main__":
    unittest.main()
