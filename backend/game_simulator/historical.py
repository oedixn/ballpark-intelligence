"""Point-in-time inputs. Annual totals and client-supplied rates are never used here."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path

from .simulator_main import (
    BattingRecord, LeagueAverageProb, LineupMarkovModel, MatchSimulator,
    PitcherProb, adjust_lineup_by_pitcher, record_to_player_prob,
)
from .bullpen import appearance_workloads, build_pitching_staff

DEFAULT_HISTORY_DIR = Path(__file__).resolve().parents[1] / "data" / "game_logs"


class HistoryUnavailable(ValueError):
    pass


@lru_cache(maxsize=4)
def _read_history(path, modified, size):
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    if data.get("schema_version") != 1 or data.get("complete") is not True:
        raise HistoryUnavailable("수집이 완료된 경기별 기록이 필요합니다.")
    return data, hashlib.sha256(raw).hexdigest()


def _count(row, key):
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"경기별 기록의 {key} 값이 올바르지 않습니다.")
    return value


class HistoricalInputs:
    def __init__(self, as_of: date, history_dir=None):
        if not isinstance(as_of, date):
            raise ValueError("기준일은 YYYY-MM-DD 형식이어야 합니다.")
        self.as_of = as_of
        self.max_innings = 11 if as_of.year >= 2025 else 12
        folder = Path(history_dir or os.getenv("SIMULATOR_HISTORY_DIR", DEFAULT_HISTORY_DIR))
        path = folder / f"{as_of.year}.json"
        try:
            stat = path.stat()
        except FileNotFoundError as exc:
            raise HistoryUnavailable(f"{as_of.year}년 경기별 기록을 먼저 수집해야 합니다.") from exc
        data, fingerprint = _read_history(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
        if data.get("season") != as_of.year:
            raise HistoryUnavailable("기록 파일의 시즌이 기준일과 다릅니다.")
        if date.fromisoformat(data["coverage_start"]) != date(as_of.year, 1, 1):
            raise HistoryUnavailable("해당 시즌 시작부터 수집된 기록이 필요합니다.")
        if as_of > date.fromisoformat(data["coverage_before"]):
            raise HistoryUnavailable(f"수집 범위는 {data['coverage_before']} 당일 이전까지입니다.")

        selected = {}
        for kind in ("hitters", "pitchers"):
            values = []
            seen = set()
            for row in data[kind]:
                played = date.fromisoformat(row["game_date"])
                if played.year != as_of.year:
                    raise ValueError("다른 시즌의 경기별 기록이 섞여 있습니다.")
                if played >= as_of:
                    continue
                identity = (str(row["player_id"]), row["game_date"], row["appearance"])
                if identity in seen:
                    raise ValueError("중복된 경기별 기록이 있습니다.")
                seen.add(identity)
                values.append(row)
            selected[kind] = values
        if not selected["hitters"] or not selected["pitchers"]:
            raise HistoryUnavailable("기준일 이전의 타자·투수 기록이 부족합니다.")

        self.hitters = self._aggregate(selected["hitters"], "hitter")
        self.pitchers = self._aggregate(selected["pitchers"], "pitcher")
        self._pitcher_appearances = selected["pitchers"]
        # Roster membership follows the last observed team BEFORE the cutoff, not
        # the current profile or an end-of-season roster. All earlier team stints count.
        self.metadata = {
            "season": as_of.year, "as_of": as_of.isoformat(),
            "date_rule": "game_date < as_of", "window_start": f"{as_of.year}-01-01",
            "last_game_date": max(r["game_date"] for v in selected.values() for r in v),
            "source": data["source"], "data_sha256": fingerprint,
            "coverage_before": data["coverage_before"], "collected_at": data["collected_at"],
            "hitter_appearances": len(selected["hitters"]),
            "pitcher_appearances": len(selected["pitchers"]),
            "roster_rule": "last observed team before cutoff; not an active-entry list",
            "pitcher_hit_split": "non-HR hits: 80% singles, 20% doubles; triples not separated",
        }

    @staticmethod
    def _aggregate(rows, kind):
        fields = (["ab", "h", "double_hit", "triple_hit", "hr", "bb", "hbp", "pa"]
                  if kind == "hitter" else ["outs", "tbf", "h", "hr", "bb", "hbp", "so", "er", "gs"])
        grouped = {}
        for r in sorted(rows, key=lambda r: (r["game_date"], r["appearance"])):
            pid = str(r["player_id"])
            item = grouped.setdefault(pid, {key: 0 for key in fields} | {"g": 0, "player_id": pid})
            for key in fields:
                item[key] += _count(r, key)
            item.update(name=r["player_name"], player_name=r["player_name"], team_name=r["team_name"])
            item["g"] += 1
        for r in grouped.values():
            if kind == "hitter":
                if r["h"] > r["ab"] or r["double_hit"] + r["triple_hit"] + r["hr"] > r["h"]:
                    raise ValueError("타격 누적 기록이 서로 일치하지 않습니다.")
                r.update(hits=r["h"], double=r["double_hit"], triple=r["triple_hit"], position=None)
            else:
                r["ip"] = r["outs"] / 3
                r["era"] = r["er"] * 27 / r["outs"] if r["outs"] else None
                r["whip"] = (r["h"] + r["bb"]) * 3 / r["outs"] if r["outs"] else None
        return list(grouped.values())

    def team(self, team_name):
        batters = sorted([r for r in self.hitters if r["team_name"] == team_name and r["ab"] > 0],
                         key=lambda r: (-r["pa"], r["player_id"]))
        pitchers = sorted([r for r in self.pitchers if r["team_name"] == team_name
                           and r["gs"] > 0 and r["tbf"] > 0 and r["outs"] > 0],
                          key=lambda r: (-r["gs"], -r["outs"], r["player_id"]))
        if len(batters) < 9:
            raise HistoryUnavailable(f"{team_name}: 기준일 이전 기록이 있는 타자가 9명 미만입니다.")
        return {"lineup": batters[:9], "batters": batters, "pitchers": pitchers,
                "metadata": self.metadata}

    def league_average(self):
        # Include every pitching appearance, including players now on another team.
        totals = {key: sum(r[key] for r in self.pitchers) for key in ("tbf", "h", "hr", "bb", "hbp")}
        return self._pitching_prob(totals)

    @staticmethod
    def _pitching_prob(r):
        tbf = r["tbf"]
        if tbf <= 0:
            raise HistoryUnavailable("기준일 이전 리그 투수 기록이 부족합니다.")
        bb = r["bb"] + r["hbp"]
        non_hr = r["h"] - r["hr"]
        out = tbf - r["h"] - bb
        if non_hr < 0 or out < 0:
            raise ValueError("투수 기록의 타자 수와 허용 결과가 일치하지 않습니다.")
        return LeagueAverageProb(bb/tbf, non_hr*.8/tbf, non_hr*.2/tbf, 0.0, r["hr"]/tbf, out/tbf)

    def lineup(self, team_name, names):
        pool = self.team(team_name)["batters"]
        if len(names) != 9 or len(set(names)) != 9:
            raise ValueError("타순은 서로 다른 타자 9명으로 구성해야 합니다.")
        result, records, selected_ids = [], [], set()
        for name in names:
            # The API prefers a stable player ID; names remain supported for
            # older clients only when they identify exactly one player.
            matches = [r for r in pool if r["player_id"] == str(name)]
            if not matches:
                matches = [r for r in pool if r["name"] == name]
            if len(matches) != 1:
                raise ValueError(f"{team_name} {name}: 기준일 이전 선수 기록을 고유하게 찾을 수 없습니다.")
            r = matches[0]
            if r['player_id'] in selected_ids:
                raise ValueError('같은 선수를 타순에 두 번 선택할 수 없습니다.')
            selected_ids.add(r['player_id'])
            records.append(r)
            result.append(record_to_player_prob(BattingRecord(
                name=r["name"], ab=r["ab"], hits=r["h"], double=r["double_hit"], triple=r["triple_hit"],
                hr=r["hr"], bb=r["bb"], hbp=r["hbp"],
            )))
        return result, records

    def pitcher(self, team_name, player_id=None, name=None):
        if not player_id and not name:
            return None
        pool = self.team(team_name)["pitchers"]
        found = [r for r in pool if (r["player_id"] == str(player_id) if player_id else r["name"] == name)]
        if len(found) != 1:
            raise ValueError(f"{team_name}: 선택한 선발의 기준일 이전 기록이 없습니다.")
        r = found[0]
        return PitcherProb(name=r["name"], team_name=team_name, **asdict(self._pitching_prob(r)),
                           gs=r["gs"], g=r["g"], ip=r["ip"], era=r["era"], tbf=r["tbf"],
                           player_id=r["player_id"])

    def pitching_staff(self, starter):
        candidates = [
            PitcherProb(name=r["name"], team_name=r["team_name"], **asdict(self._pitching_prob(r)),
                        gs=r["gs"], g=r["g"], ip=r["ip"], era=r["era"] or 0,
                        tbf=r["tbf"], player_id=r["player_id"])
            for r in self.pitchers if r["team_name"] == starter.team_name and r["tbf"] > 0
        ]
        return build_pitching_staff(starter, candidates,
                                    appearance_workloads(self._pitcher_appearances, starter.team_name))

    def matchup_inputs(self, team_a, names_a, team_b, names_b, pitcher_a_id=None, pitcher_b_id=None,
                       pitcher_a=None, pitcher_b=None):
        if team_a == team_b:
            raise ValueError("서로 다른 두 팀을 선택하세요.")
        a, ra = self.lineup(team_a, names_a)
        b, rb = self.lineup(team_b, names_b)
        pa = self.pitcher(team_a, pitcher_a_id, pitcher_a)
        pb = self.pitcher(team_b, pitcher_b_id, pitcher_b)
        avg = self.league_average()
        if pb:
            a = adjust_lineup_by_pitcher(a, pb, avg)
        if pa:
            b = adjust_lineup_by_pitcher(b, pa, avg)
        metadata = self.metadata | {
            "team_a_lineup": ra, "team_b_lineup": rb,
            "pitcher_a": asdict(pa) if pa else None, "pitcher_b": asdict(pb) if pb else None,
            "league_average": asdict(avg),
            "lineup_rule": "chosen order; rates recomputed on server from pre-cutoff appearances",
        }
        return a, b, metadata


def historical_match(inputs, team_a, names_a, team_b, names_b, *, seed=42, bullpen_enabled=False,
                     pitcher_a_id=None, pitcher_b_id=None, pitcher_a=None, pitcher_b=None):
    if bullpen_enabled:
        for team, pid, name in ((team_a, pitcher_a_id, pitcher_a), (team_b, pitcher_b_id, pitcher_b)):
            if not pid and not name:
                starters = inputs.team(team)["pitchers"]
                if not starters:
                    raise HistoryUnavailable(f"{team}: 기준일 이전 선발 후보가 없습니다.")
                if team == team_a:
                    pitcher_a_id = starters[0]["player_id"]
                else:
                    pitcher_b_id = starters[0]["player_id"]
    a, b, metadata = inputs.matchup_inputs(team_a, names_a, team_b, names_b,
                                         pitcher_a_id, pitcher_b_id, pitcher_a, pitcher_b)
    options = {}
    if bullpen_enabled:
        pa, pb = PitcherProb(**metadata["pitcher_a"]), PitcherProb(**metadata["pitcher_b"])
        raw_a, _ = inputs.lineup(team_a, names_a)
        raw_b, _ = inputs.lineup(team_b, names_b)
        options = dict(bullpen_enabled=True, team_a_staff=inputs.pitching_staff(pa),
                       team_b_staff=inputs.pitching_staff(pb), league_avg=inputs.league_average())
    match = MatchSimulator(team_a, raw_a if bullpen_enabled else a,
                           team_b, raw_b if bullpen_enabled else b, seed=seed, **options)
    if bullpen_enabled:
        metadata = metadata | {"bullpen": match.bullpen_metadata()}
    return match, a, b, metadata


def simulate_historical(inputs, team_a, names_a, team_b, names_b, *, n_games=10000, seed=42,
                        innings=9, pitcher_a_id=None, pitcher_b_id=None, pitcher_a=None, pitcher_b=None,
                        bullpen_enabled=False):
    if not 1 <= n_games <= 10000 or not 1 <= innings <= inputs.max_innings:
        raise ValueError(f"경기 수는 1~10,000, 정규 이닝은 1~{inputs.max_innings}여야 합니다.")
    match, a, b, metadata = historical_match(
        inputs, team_a, names_a, team_b, names_b, seed=seed, bullpen_enabled=bullpen_enabled,
        pitcher_a_id=pitcher_a_id, pitcher_b_id=pitcher_b_id, pitcher_a=pitcher_a, pitcher_b=pitcher_b,
    )
    result = match.simulate_many(n_games, innings=innings, max_innings=inputs.max_innings)
    for key, name, lineup in (("team_a", team_a, a), ("team_b", team_b, b)):
        model = LineupMarkovModel(lineup)
        stats = result[key]
        stats.update(name=name, markov_expected=model.expected_runs(model.game_run_distribution(innings)),
                     prob_5_or_more=stats["prob_5_or_more_runs"])
    wa, wb, draws = result["team_a"]["wins"], result["team_b"]["wins"], result["draws"]
    result["matchup"] = {"team_a_wins": wa, "team_b_wins": wb, "draws": draws,
                         "team_a_win_probability": wa/n_games, "team_b_win_probability": wb/n_games,
                         "draw_probability": draws/n_games,
                         "team_a_win_rate": wa/(wa+wb) if wa+wb else None,
                         "team_b_win_rate": wb/(wa+wb) if wa+wb else None}
    result["metadata"] = metadata | {"seed": seed, "n_games": n_games, "innings": innings,
                                    "max_innings": inputs.max_innings, "engine": "MatchSimulator"}
    return result
