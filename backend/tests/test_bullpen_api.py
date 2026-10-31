from datetime import date
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from app.main import app
from game_simulator.historical import HistoricalInputs, historical_match
from game_simulator.simulator_main import LeagueAverageProb


def request_payload():
    payload = dict(team_a_name="A", team_b_name="B", n_games=20, innings=9, seed=7)
    for side, team in (("a", "A"), ("b", "B")):
        payload[f"team_{side}_lineup"] = [dict(name=f"{team}{i}", ab=30,hits=8,double=2,
                                               triple=0,hr=1,bb=3,hbp=0) for i in range(9)]
    return payload


def annual_pitchers(team):
    return [dict(player_id=team+role,player_name=team+role,team_name=team,
                 g=20,gs=20 if role=="S" else 0,tbf=480 if role=="S" else 100,
                 h=90 if role=="S" else 20,hr=8 if role=="S" else 2,
                 bb=30 if role=="S" else 8,double_hit=10,triple_hit=0,hbp=1,
                 ip="100" if role=="S" else "25",era="3.0",sv=10 if role=="C" else 0,hld=0)
            for role in ("S","R","C")]


def history():
    data = dict(schema_version=1,complete=True,season=2026,coverage_start="2026-01-01",
                coverage_before="2026-10-31",source="test daily lines",collected_at="2026-10-31",
                hitters=[],pitchers=[])
    for team in ("A","B"):
        for day in ("2026-04-01","2026-04-02"):
            for i in range(9):
                data["hitters"].append(dict(player_id=f"{team}{i}",player_name=f"{team}{i}",
                    team_name=team,game_date=day,appearance=1,ab=30,h=8,double_hit=2,
                    triple_hit=0,hr=1,bb=3,hbp=0,pa=33))
            for role in ("S","R"):
                data["pitchers"].append(dict(player_id=team+role,player_name=team+role,
                    team_name=team,game_date=day,appearance=1,tbf=25 if role=="S" else 5,
                    outs=18 if role=="S" else 3,h=3,hr=0,bb=1,hbp=0,so=3,er=1,gs=int(role=="S")))
    return data


class BullpenApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_annual_routes_use_bullpen_and_return_same_usage_format(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [annual_pitchers("A"),annual_pitchers("B")] * 2
        with patch("app.main.get_conn",return_value=MagicMock()), patch("app.main.get_cur",return_value=cursor), \
             patch("app.main._get_league_avg",return_value=LeagueAverageProb(.08,.17,.05,0,.03,.67)), \
             patch("game_simulator.simulator_main.LineupMarkovModel.game_run_distribution",return_value=[1.]):
            payload = request_payload() | {"bullpen_enabled":True}
            game = self.client.post("/api/simulate/game",json=payload)
            self.assertEqual(game.status_code,200,game.text)
            self.assertTrue(game.json()["game_log"]["bullpen_enabled"])
            self.assertTrue(game.json()["game_log"]["pitching_changes"])
            self.assertTrue(all(pa["pitcher_name"] for h in game.json()["game_log"]["innings"] for pa in h["plate_appearances"]))
            multi = self.client.post("/api/simulate/multi",json=payload)
            self.assertEqual(multi.status_code,200,multi.text)
            result = multi.json()
            self.assertTrue(result["bullpen"]["enabled"])
            self.assertGreater(result["bullpen"]["usage"]["A"]["mean_pitchers"],1)
            self.assertEqual(sum(r["count"] for r in result["score_distribution"]),20)

    def test_off_does_not_load_bullpen_and_preserves_legacy_multi_route(self):
        payload = request_payload()
        with patch("app.main.annual_bullpen_match",side_effect=AssertionError("must not read staff")), \
             patch("app.main._get_league_avg",return_value=None), \
             patch("game_simulator.simulator_main.LineupMarkovModel.game_run_distribution",return_value=[1.]):
            omitted = self.client.post("/api/simulate/multi",json=payload)
            off = self.client.post("/api/simulate/multi",json=payload | {"bullpen_enabled":False})
        self.assertEqual(omitted.status_code,200,omitted.text)
        self.assertEqual(omitted.json(),off.json())
        self.assertNotIn("bullpen",off.json())

    def test_historical_bullpen_uses_only_pre_cutoff_roster_rates_and_workloads(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"2026.json"
            data = history()
            path.write_text(json.dumps(data),encoding="utf-8")
            payload = request_payload()
            args = ("A",[p["name"] for p in payload["team_a_lineup"]],
                    "B",[p["name"] for p in payload["team_b_lineup"]])
            baseline = historical_match(HistoricalInputs(date(2026,4,2),folder),*args,bullpen_enabled=True,seed=7)[0]
            for row in data["pitchers"]:
                if row["game_date"] >= "2026-04-02":
                    row.update(tbf=999,h=999,team_name="future team",gs=1)
            path.write_text(json.dumps(data),encoding="utf-8")
            changed = historical_match(HistoricalInputs(date(2026,4,2),folder),*args,bullpen_enabled=True,seed=7)[0]
            self.assertEqual(baseline.team_a_staff,changed.team_a_staff)
            self.assertEqual(baseline.team_b_staff,changed.team_b_staff)
            self.assertEqual(baseline.simulate_many(20),changed.simulate_many(20))
            with patch.dict(os.environ,{"SIMULATOR_HISTORY_DIR":folder}), \
                 patch("app.main.get_conn",side_effect=AssertionError("no annual data")), \
                 patch("game_simulator.simulator_main.LineupMarkovModel.game_run_distribution",return_value=[1.]):
                payload.update(as_of="2026-04-02",bullpen_enabled=True)
                single = self.client.post("/api/simulate/game",json=payload)
                multi = self.client.post("/api/simulate/multi",json=payload)
            self.assertEqual(single.status_code,200,single.text)
            self.assertEqual(multi.status_code,200,multi.text)
            self.assertTrue(multi.json()["metadata"]["bullpen"]["enabled"])
            self.assertEqual(multi.json()["metadata"]["last_game_date"],"2026-04-01")

    def test_unknown_selected_starter_returns_actionable_error(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [annual_pitchers("A"),annual_pitchers("B")]
        with patch("app.main.get_conn",return_value=MagicMock()), patch("app.main.get_cur",return_value=cursor):
            response = self.client.post("/api/simulate/game",json=request_payload() |
                                        {"bullpen_enabled":True,"pitcher_a_id":"missing"})
        self.assertEqual(response.status_code,400,response.text)
        self.assertIn("선발",response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
