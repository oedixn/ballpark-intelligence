"""
라인업 최적화용 Markov Chain + Monte Carlo 구현 예시
-----------------------------------------------------
가정:
- 9명 고정 라인업
- 이벤트: BB, 1B, 2B, 3B, HR, OUT
- 단순 주루 규칙 사용
  * 볼넷: 강제 진루만
  * 단타: 1루 주자는 2루, 2/3루 주자는 홈
  * 2루타: 1루 주자는 3루, 2/3루 주자는 홈
  * 3루타: 모든 주자 홈, 타자 3루
  * 홈런: 모두 홈
  * 아웃: 주자 이동 없음
- 마르코프 계산은 "상태 전이 + 득점 분포 DP" 방식으로 구현
- 몬테카를로는 실제 경기 진행을 반복 샘플링하여 득점 분포 계산

실행 예시:
    python lineup_markov_montecarlo.py
    
현재 버전 반영 사항:
- backend/db/output_db_ready CSV 폴더 기반 데이터 로딩
- 타자는 투수 제외, 포지션별 대표 8명 + 지명타자 1명으로 구성
- 뽑힌 9명의 타순은 PA(타석 수) 내림차순으로 정렬
- 팀 선택 후 해당 팀의 선발투수 후보 중 1명 선택
- 상대 선발투수의 피이벤트 성향으로 타자 이벤트 확률 보정
- 실제 경기 로그 시뮬레이션은 최대 12이닝으로 제한
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from pathlib import Path
from typing import Dict, List, Sequence, Tuple
import csv
import math
import random


# -----------------------------------------------------------------------------
# 기본 설정
# -----------------------------------------------------------------------------

REGULATION_INNINGS = 9
MAX_GAME_INNINGS = 12
PITCHER_ADJUSTMENT_WEIGHT = 0.5

FIELDING_POSITIONS = [
    "포수",
    "1루수",
    "2루수",
    "3루수",
    "유격수",
    "좌익수",
    "중견수",
    "우익수",
]
DESIGNATED_HITTER_POSITION = "지명타자"

# 현재 프로젝트 구조 기준:
# BALLPARK-INTELLIGENCE/
# └─ backend/
#    ├─ db/
#    │  └─ output_db_ready/*.csv
#    └─ game_simulator/
#       └─ simulator_main.py
BACKEND_DIR = Path(__file__).resolve().parents[1]
DB_DIR = BACKEND_DIR / "db"
OUTPUT_DB_READY_DIR = DB_DIR / "output_db_ready"

HITTER_STATS_CSV_PATH = OUTPUT_DB_READY_DIR / "player_hitter_stats.csv"
DEFENSE_STATS_CSV_PATH = OUTPUT_DB_READY_DIR / "player_defense_stats.csv"
PITCHER_STATS_CSV_PATH = OUTPUT_DB_READY_DIR / "player_pitcher_stats.csv"
TEAM_PITCHER_STATS_CSV_PATH = OUTPUT_DB_READY_DIR / "team_pitcher_stats.csv"


# -----------------------------------------------------------------------------
# 데이터 구조
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class PlayerProb: #선수 1명의 확률 정보를 담는 클래스

    name: str
    bb: float
    single: float
    double: float
    triple: float
    hr: float
    out: float | None = None
    position: str | None = None

    def normalized(self) -> "PlayerProb":
        probs = {
            "bb": self.bb,
            "single": self.single,
            "double": self.double,
            "triple": self.triple,
            "hr": self.hr,
        }
        out = 1.0 - sum(probs.values()) if self.out is None else self.out

        if out < 0:
            raise ValueError(f"{self.name}: 확률 합이 1을 초과합니다.")

        total = sum(probs.values()) + out
        if total <= 0:
            raise ValueError(f"{self.name}: 유효한 확률이 아닙니다.")

        return PlayerProb(
            name=self.name,
            bb=probs["bb"] / total,
            single=probs["single"] / total,
            double=probs["double"] / total,
            triple=probs["triple"] / total,
            hr=probs["hr"] / total,
            out=out / total,
            position=self.position,
        )

    def event_probs(self) -> List[Tuple[str, float]]:
        p = self.normalized()
        return [
            ("BB", p.bb),
            ("1B", p.single),
            ("2B", p.double),
            ("3B", p.triple),
            ("HR", p.hr),
            ("OUT", p.out if p.out is not None else 0.0),
        ]


@dataclass(frozen=True)
class PitcherProb:
    """투수 1명의 피이벤트 확률."""

    name: str
    team_name: str
    bb: float
    single: float
    double: float
    triple: float
    hr: float
    out: float
    gs: int = 0
    g: int = 0
    ip: float = 0.0
    era: float = 0.0
    tbf: int = 0

    def normalized(self) -> "PitcherProb":
        total = self.bb + self.single + self.double + self.triple + self.hr + self.out
        if total <= 0:
            raise ValueError(f"{self.name}: 유효한 투수 확률이 아닙니다.")
        return PitcherProb(
            name=self.name,
            team_name=self.team_name,
            bb=self.bb / total,
            single=self.single / total,
            double=self.double / total,
            triple=self.triple / total,
            hr=self.hr / total,
            out=self.out / total,
            gs=self.gs,
            g=self.g,
            ip=self.ip,
            era=self.era,
            tbf=self.tbf,
        )


@dataclass(frozen=True)
class LeagueAverageProb:
    """리그 평균 이벤트 확률."""

    bb: float
    single: float
    double: float
    triple: float
    hr: float
    out: float


@dataclass(frozen=True)
class BattingRecord:
    """실제 선수 타격 기록."""

    name: str
    ab: int
    hits: int
    double: int
    triple: int
    hr: int
    bb: int
    hbp: int = 0
    position: str | None = None


@dataclass
class PlateAppearanceLog:
    inning: int
    half: str
    batter_order: int
    batter_name: str
    event: str
    runs_scored: int
    outs_after: int
    bases_after: str


@dataclass
class HalfInningLog:
    inning: int
    half: str
    team_name: str
    runs: int
    plate_appearances: List[PlateAppearanceLog]


@dataclass
class GameLog:
    team_a: str
    team_b: str
    final_score: Tuple[int, int]
    innings: List[HalfInningLog]


# -----------------------------------------------------------------------------
# 공통 변환 함수
# -----------------------------------------------------------------------------

def _read_csv(csv_path: Path) -> List[Dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV 파일을 찾지 못했습니다: {csv_path}\n"
            "예상 구조: BALLPARK-INTELLIGENCE/backend/db/output_db_ready/*.csv"
        )
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _to_int(value: str | None, default: int = 0) -> int:
    if value is None or str(value).strip() == "":
        return default
    return int(float(str(value).strip()))


def _to_float(value: str | None, default: float = 0.0) -> float:
    """일반 숫자와 KBO 이닝 표기('145 2/3')를 모두 float로 변환한다."""

    if value is None:
        return default

    text = str(value).strip()
    if text == "":
        return default

    if " " in text and "/" in text:
        whole, fraction = text.split(" ", 1)
        numerator, denominator = fraction.split("/", 1)
        return float(whole) + float(numerator) / float(denominator)

    if "/" in text:
        numerator, denominator = text.split("/", 1)
        return float(numerator) / float(denominator)

    return float(text)


def _latest_season(rows: Sequence[Dict[str, str]]) -> int:
    seasons = [int(row["season_year"]) for row in rows if row.get("season_year")]
    if not seasons:
        raise ValueError("시즌 정보가 없습니다.")
    return max(seasons)


def available_teams(hitter_stats_csv_path: Path = HITTER_STATS_CSV_PATH) -> List[str]:
    rows = _read_csv(hitter_stats_csv_path)
    return sorted({row["team_name"] for row in rows if row.get("team_name")})


def available_seasons(hitter_stats_csv_path: Path = HITTER_STATS_CSV_PATH) -> List[int]:
    rows = _read_csv(hitter_stats_csv_path)
    return sorted({int(row["season_year"]) for row in rows if row.get("season_year")})


# -----------------------------------------------------------------------------
# 타자 확률 계산
# -----------------------------------------------------------------------------

def record_to_player_prob(record: BattingRecord) -> PlayerProb:
    """
    선수의 실제 타격 기록을 PlayerProb 확률 구조로 변환한다.

    계산 방식:
    - BB 확률 = (볼넷 + 사구) / PA
    - 1B 확률 = 단타 / PA
    - 2B 확률 = 2루타 / PA
    - 3B 확률 = 3루타 / PA
    - HR 확률 = 홈런 / PA
    - OUT 확률 = 나머지

    현재 모델에서는 PA를 단순화해서 AB + BB + HBP로 계산한다.
    """

    pa = record.ab + record.bb + record.hbp
    if pa <= 0:
        raise ValueError(f"{record.name}: 유효한 타석 수가 없습니다.")

    single = record.hits - record.double - record.triple - record.hr
    if single < 0:
        raise ValueError(f"{record.name}: 안타 세부 기록이 잘못되었습니다.")

    bb_prob = (record.bb + record.hbp) / pa
    single_prob = single / pa
    double_prob = record.double / pa
    triple_prob = record.triple / pa
    hr_prob = record.hr / pa
    out_prob = 1.0 - (bb_prob + single_prob + double_prob + triple_prob + hr_prob)

    return PlayerProb(
        name=record.name,
        bb=bb_prob,
        single=single_prob,
        double=double_prob,
        triple=triple_prob,
        hr=hr_prob,
        out=out_prob,
        position=record.position,
    ).normalized()


def _row_key_for_batting(row: Dict[str, str]) -> Tuple[int, int]:
    return (_to_int(row.get("pa")), _to_int(row.get("ab")))


def _row_key_for_defense(row: Dict[str, str], hitter_by_id: Dict[str, Dict[str, str]]) -> Tuple[int, int, float, int, int]:
    hitter_row = hitter_by_id.get(row.get("player_id", ""), {})
    return (
        _to_int(row.get("gs")),
        _to_int(row.get("g")),
        _to_float(row.get("ip")),
        _to_int(hitter_row.get("pa")),
        _to_int(hitter_row.get("ab")),
    )


def _select_position_based_lineup(
    hitter_rows: List[Dict[str, str]],
    defense_rows: List[Dict[str, str]],
    lineup_size: int = 9,
) -> List[Dict[str, str]]:
    """
    수비 포지션 8명 + 지명타자 1명을 고른 뒤,
    최종 타순은 PA 내림차순으로 정렬한다.
    """

    hitter_by_id = {row["player_id"]: row for row in hitter_rows if row.get("player_id")}
    selected: List[Dict[str, str]] = []
    selected_ids: set[str] = set()

    for position in FIELDING_POSITIONS:
        position_candidates = [
            row
            for row in defense_rows
            if row.get("position") == position
            and row.get("player_id") in hitter_by_id
            and row.get("player_id") not in selected_ids
        ]

        if not position_candidates:
            raise ValueError(f"{position} 후보를 찾지 못했습니다.")

        best_defense = max(position_candidates, key=lambda row: _row_key_for_defense(row, hitter_by_id))
        hitter_row = dict(hitter_by_id[best_defense["player_id"]])
        hitter_row["selected_position"] = position
        selected.append(hitter_row)
        selected_ids.add(best_defense["player_id"])

    dh_candidates = [
        row
        for row in hitter_rows
        if row.get("player_id") not in selected_ids
    ]
    if not dh_candidates:
        raise ValueError("지명타자 후보를 찾지 못했습니다.")

    dh_row = dict(max(dh_candidates, key=_row_key_for_batting))
    dh_row["selected_position"] = DESIGNATED_HITTER_POSITION
    selected.append(dh_row)

    if len(selected) != lineup_size:
        raise ValueError(f"라인업은 {lineup_size}명이 필요하지만 {len(selected)}명만 선택되었습니다.")

    # 선수는 포지션별로 뽑되, 실제 타순은 PA가 많은 순서로 둔다.
    selected.sort(key=_row_key_for_batting, reverse=True)
    return selected


def load_team_batting_records(
    team_name: str,
    season_year: int | None = None,
    hitter_stats_csv_path: Path = HITTER_STATS_CSV_PATH,
    defense_stats_csv_path: Path = DEFENSE_STATS_CSV_PATH,
    min_pa: int = 1,
    player_names: Sequence[str] | None = None,
    lineup_size: int = 9,
    use_position_lineup: bool = True,
) -> List[BattingRecord]:
    """
    DB 폴더의 타자 CSV에서 특정 팀의 BattingRecord 목록을 가져온다.

    기본 방식:
    - 포지션별 대표 선수 8명 + 지명타자 1명 선정
    - 최종 타순은 PA 순으로 정렬

    player_names가 주어지면 해당 순서를 그대로 사용한다.
    """

    hitter_rows_all = _read_csv(hitter_stats_csv_path)
    defense_rows_all = _read_csv(defense_stats_csv_path) if use_position_lineup else []

    if season_year is None:
        season_year = _latest_season(hitter_rows_all)

    hitter_rows = [
        row
        for row in hitter_rows_all
        if row.get("team_name") == team_name
        and int(row.get("season_year", 0)) == season_year
        and _to_int(row.get("pa")) >= min_pa
    ]

    if not hitter_rows:
        teams = ", ".join(available_teams(hitter_stats_csv_path))
        seasons = ", ".join(map(str, available_seasons(hitter_stats_csv_path)))
        raise ValueError(
            f"{season_year}시즌 {team_name} 타자 기록을 찾지 못했습니다. "
            f"사용 가능한 시즌: {seasons} / 팀: {teams}"
        )

    if player_names is not None:
        by_name = {row["player_name"]: row for row in hitter_rows}
        missing = [name for name in player_names if name not in by_name]
        if missing:
            raise ValueError(f"{season_year}시즌 {team_name}에서 찾지 못한 선수: {', '.join(missing)}")
        selected = [dict(by_name[name]) for name in player_names]
        for row in selected:
            row["selected_position"] = row.get("selected_position") or "수동선택"
    elif use_position_lineup:
        defense_rows = [
            row
            for row in defense_rows_all
            if row.get("team_name") == team_name
            and int(row.get("season_year", 0)) == season_year
        ]
        selected = _select_position_based_lineup(hitter_rows, defense_rows, lineup_size=lineup_size)
    else:
        selected = sorted(hitter_rows, key=_row_key_for_batting, reverse=True)[:lineup_size]
        for row in selected:
            row["selected_position"] = None

    if len(selected) != lineup_size:
        raise ValueError(f"라인업은 {lineup_size}명이 필요하지만 {len(selected)}명만 선택되었습니다.")

    return [
        BattingRecord(
            name=row["player_name"],
            ab=_to_int(row.get("ab")),
            hits=_to_int(row.get("h")),
            double=_to_int(row.get("double_hit")),
            triple=_to_int(row.get("triple_hit")),
            hr=_to_int(row.get("hr")),
            bb=_to_int(row.get("bb")),
            hbp=_to_int(row.get("hbp")),
            position=row.get("selected_position") or None,
        )
        for row in selected
    ]


def load_team_players_from_db(
    team_name: str,
    season_year: int | None = None,
    hitter_stats_csv_path: Path = HITTER_STATS_CSV_PATH,
    defense_stats_csv_path: Path = DEFENSE_STATS_CSV_PATH,
    min_pa: int = 1,
    player_names: Sequence[str] | None = None,
    use_position_lineup: bool = True,
) -> List[PlayerProb]:
    records = load_team_batting_records(
        team_name=team_name,
        season_year=season_year,
        hitter_stats_csv_path=hitter_stats_csv_path,
        defense_stats_csv_path=defense_stats_csv_path,
        min_pa=min_pa,
        player_names=player_names,
        lineup_size=9,
        use_position_lineup=use_position_lineup,
    )
    return [record_to_player_prob(record) for record in records]


# -----------------------------------------------------------------------------
# 투수 로딩 및 투수 보정
# -----------------------------------------------------------------------------

def _pitcher_row_to_prob(row: Dict[str, str]) -> PitcherProb:
    tbf = _to_int(row.get("tbf"))
    if tbf <= 0:
        raise ValueError(f"{row.get('player_name', '알 수 없음')}: TBF가 0 이하입니다.")

    hits = _to_int(row.get("h"))
    double = _to_int(row.get("double_hit"))
    triple = _to_int(row.get("triple_hit"))
    hr = _to_int(row.get("hr"))
    bb = _to_int(row.get("bb"))
    hbp = _to_int(row.get("hbp"))

    single = max(0, hits - double - triple - hr)
    bb_prob = (bb + hbp) / tbf
    single_prob = single / tbf
    double_prob = double / tbf
    triple_prob = triple / tbf
    hr_prob = hr / tbf
    out_prob = max(0.0, 1.0 - (bb_prob + single_prob + double_prob + triple_prob + hr_prob))

    return PitcherProb(
        name=row["player_name"],
        team_name=row["team_name"],
        bb=bb_prob,
        single=single_prob,
        double=double_prob,
        triple=triple_prob,
        hr=hr_prob,
        out=out_prob,
        gs=_to_int(row.get("gs")),
        g=_to_int(row.get("g")),
        ip=_to_float(row.get("ip")),
        era=_to_float(row.get("era")),
        tbf=tbf,
    ).normalized()


def load_starting_pitcher_candidates(
    team_name: str,
    season_year: int | None = None,
    pitcher_stats_csv_path: Path = PITCHER_STATS_CSV_PATH,
) -> List[PitcherProb]:
    rows = _read_csv(pitcher_stats_csv_path)
    if season_year is None:
        season_year = _latest_season(rows)

    candidates = [
        row
        for row in rows
        if row.get("team_name") == team_name
        and int(row.get("season_year", 0)) == season_year
        and _to_int(row.get("gs")) > 0
        and _to_int(row.get("tbf")) > 0
    ]

    if not candidates:
        raise ValueError(f"{season_year}시즌 {team_name} 선발투수 후보를 찾지 못했습니다.")

    candidates.sort(
        key=lambda row: (_to_int(row.get("gs")), _to_float(row.get("ip")), _to_int(row.get("tbf"))),
        reverse=True,
    )
    return [_pitcher_row_to_prob(row) for row in candidates]


def choose_starting_pitcher(
    team_name: str,
    season_year: int | None = None,
    pitcher_stats_csv_path: Path = PITCHER_STATS_CSV_PATH,
) -> PitcherProb:
    candidates = load_starting_pitcher_candidates(
        team_name=team_name,
        season_year=season_year,
        pitcher_stats_csv_path=pitcher_stats_csv_path,
    )

    print(f"\n[{team_name} 선발투수 선택]")
    print("번호를 입력하세요. 엔터를 누르면 선발 등판 수가 가장 많은 투수를 사용합니다.")

    for idx, pitcher in enumerate(candidates, start=1):
        print(
            f"{idx}. {pitcher.name} / GS {pitcher.gs} / G {pitcher.g} "
            f"/ IP {pitcher.ip:.1f} / ERA {pitcher.era:.2f} / TBF {pitcher.tbf}"
        )

    selected = input("선발투수 번호 [기본값: 1]: ").strip()
    if selected == "":
        return candidates[0]

    try:
        index = int(selected)
    except ValueError as exc:
        raise ValueError("선발투수 번호는 숫자로 입력해야 합니다.") from exc

    if index < 1 or index > len(candidates):
        raise ValueError(f"선발투수 번호는 1~{len(candidates)} 사이여야 합니다.")

    return candidates[index - 1]


def load_league_average_prob_from_db(
    season_year: int | None = None,
    team_pitcher_stats_csv_path: Path = TEAM_PITCHER_STATS_CSV_PATH,
) -> LeagueAverageProb:
    rows = _read_csv(team_pitcher_stats_csv_path)
    if season_year is None:
        season_year = _latest_season(rows)

    season_rows = [row for row in rows if int(row.get("season_year", 0)) == season_year]
    if not season_rows:
        raise ValueError(f"{season_year}시즌 팀 투수 기록을 찾지 못했습니다.")

    tbf = sum(_to_int(row.get("tbf")) for row in season_rows)
    if tbf <= 0:
        raise ValueError("리그 평균 계산에 필요한 TBF가 없습니다.")

    hits = sum(_to_int(row.get("h")) for row in season_rows)
    double = sum(_to_int(row.get("double_hit")) for row in season_rows)
    triple = sum(_to_int(row.get("triple_hit")) for row in season_rows)
    hr = sum(_to_int(row.get("hr")) for row in season_rows)
    bb = sum(_to_int(row.get("bb")) for row in season_rows)
    hbp = sum(_to_int(row.get("hbp")) for row in season_rows)

    single = max(0, hits - double - triple - hr)

    bb_prob = (bb + hbp) / tbf
    single_prob = single / tbf
    double_prob = double / tbf
    triple_prob = triple / tbf
    hr_prob = hr / tbf
    out_prob = max(0.0, 1.0 - (bb_prob + single_prob + double_prob + triple_prob + hr_prob))

    return LeagueAverageProb(
        bb=bb_prob,
        single=single_prob,
        double=double_prob,
        triple=triple_prob,
        hr=hr_prob,
        out=out_prob,
    )


def adjust_player_prob_by_pitcher(
    batter: PlayerProb,
    pitcher: PitcherProb,
    league_avg: LeagueAverageProb,
    pitcher_weight: float = PITCHER_ADJUSTMENT_WEIGHT,
) -> PlayerProb:
    """
    타자 이벤트 확률을 상대 투수의 리그 평균 대비 허용 성향으로 보정한다.

    보정 계수 = 1 + pitcher_weight * (투수 허용률 / 리그 평균 허용률 - 1)
    """

    b = batter.normalized()
    p = pitcher.normalized()

    def ratio(pitcher_value: float, league_value: float) -> float:
        if league_value <= 0:
            return 1.0
        value = 1.0 + pitcher_weight * ((pitcher_value / league_value) - 1.0)
        return max(0.05, value)

    adjusted = PlayerProb(
        name=b.name,
        bb=b.bb * ratio(p.bb, league_avg.bb),
        single=b.single * ratio(p.single, league_avg.single),
        double=b.double * ratio(p.double, league_avg.double),
        triple=b.triple * ratio(p.triple, league_avg.triple),
        hr=b.hr * ratio(p.hr, league_avg.hr),
        out=(b.out or 0.0) * ratio(p.out, league_avg.out),
        position=b.position,
    )
    return adjusted.normalized()


def adjust_lineup_by_pitcher(
    lineup: List[PlayerProb],
    opposing_pitcher: PitcherProb,
    league_avg: LeagueAverageProb,
    pitcher_weight: float = PITCHER_ADJUSTMENT_WEIGHT,
) -> List[PlayerProb]:
    return [
        adjust_player_prob_by_pitcher(
            batter=player,
            pitcher=opposing_pitcher,
            league_avg=league_avg,
            pitcher_weight=pitcher_weight,
        )
        for player in lineup
    ]


# -----------------------------------------------------------------------------
# 경기 상태 전이
# -----------------------------------------------------------------------------

def apply_event(base_mask: int, outs: int, event: str) -> Tuple[int, int, int]:
    if outs >= 3:
        return 0, 3, 0

    on1 = 1 if (base_mask & 1) else 0
    on2 = 1 if (base_mask & 2) else 0
    on3 = 1 if (base_mask & 4) else 0
    runs = 0

    if event == "OUT":
        return base_mask, outs + 1, 0

    if event == "BB":
        if on1 and on2 and on3:
            runs += 1
            new_on3, new_on2, new_on1 = 1, 1, 1
        elif on1 and on2:
            new_on3, new_on2, new_on1 = 1, 1, 1
        elif on1 and on3:
            new_on3, new_on2, new_on1 = 1, 1, 1
        elif on1:
            new_on3, new_on2, new_on1 = on3, 1, 1
        else:
            new_on3, new_on2, new_on1 = on3, on2, 1
        new_mask = (1 if new_on1 else 0) | (2 if new_on2 else 0) | (4 if new_on3 else 0)
        return new_mask, outs, runs

    if event == "1B":
        runs += on3 + on2
        new_on3 = 0
        new_on2 = on1
        new_on1 = 1
        new_mask = (1 if new_on1 else 0) | (2 if new_on2 else 0) | (4 if new_on3 else 0)
        return new_mask, outs, runs

    if event == "2B":
        runs += on3 + on2
        new_on3 = on1
        new_on2 = 1
        new_on1 = 0
        new_mask = (1 if new_on1 else 0) | (2 if new_on2 else 0) | (4 if new_on3 else 0)
        return new_mask, outs, runs

    if event == "3B":
        runs += on1 + on2 + on3
        return 4, outs, runs

    if event == "HR":
        runs += on1 + on2 + on3 + 1
        return 0, outs, runs

    raise ValueError(f"알 수 없는 이벤트: {event}")


def format_bases(base_mask: int) -> str:
    bases = []
    if base_mask & 1:
        bases.append("1루")
    if base_mask & 2:
        bases.append("2루")
    if base_mask & 4:
        bases.append("3루")
    return ", ".join(bases) if bases else "주자 없음"


# -----------------------------------------------------------------------------
# Markov / Monte Carlo / Match Simulator
# -----------------------------------------------------------------------------

class LineupMarkovModel:
    def __init__(self, lineup: List[PlayerProb], max_runs: int = 25) -> None:
        if len(lineup) != 9:
            raise ValueError("라인업은 9명이어야 합니다.")
        self.lineup = [p.normalized() for p in lineup]
        self.max_runs = max_runs

    def inning_run_distribution(
        self,
        start_batter_idx: int = 0,
        stop_threshold: float = 1e-12,
        max_plate_appearances: int = 60,
    ) -> Tuple[List[float], List[float]]:
        states: Dict[Tuple[int, int, int, int], float] = {(0, 0, 0, start_batter_idx): 1.0}
        finished_run_batter: Dict[Tuple[int, int], float] = {}

        for _ in range(max_plate_appearances):
            next_states: Dict[Tuple[int, int, int, int], float] = {}
            live_prob = 0.0

            for (runs, base_mask, outs, batter_idx), prob in states.items():
                if prob < stop_threshold:
                    continue

                player = self.lineup[batter_idx]
                next_batter = (batter_idx + 1) % 9

                for event, p_event in player.event_probs():
                    if p_event <= 0:
                        continue
                    nb, no, scored = apply_event(base_mask, outs, event)
                    nr = min(self.max_runs, runs + scored)
                    new_prob = prob * p_event
                    if no >= 3:
                        finished_run_batter[(nr, next_batter)] = finished_run_batter.get((nr, next_batter), 0.0) + new_prob
                    else:
                        key = (nr, nb, no, next_batter)
                        next_states[key] = next_states.get(key, 0.0) + new_prob
                        live_prob += new_prob

            states = next_states
            if live_prob < stop_threshold:
                break

        run_dist = [0.0 for _ in range(self.max_runs + 1)]
        next_batter_dist = [0.0 for _ in range(9)]

        for (runs, batter_idx), prob in finished_run_batter.items():
            run_dist[runs] += prob
            next_batter_dist[batter_idx] += prob

        total = sum(run_dist)
        if total <= 0:
            raise RuntimeError("이닝 분포 계산 실패")

        run_dist = [x / total for x in run_dist]
        next_batter_dist = [x / total for x in next_batter_dist]
        return run_dist, next_batter_dist

    def game_run_distribution(self, innings: int = REGULATION_INNINGS) -> List[float]:
        overall: Dict[Tuple[int, int], float] = {(0, 0): 1.0}

        for _inning in range(innings):
            next_overall: Dict[Tuple[int, int], float] = {}
            for (total_runs, lead_idx), prob_lead in overall.items():
                inning_run_dist, next_batter_dist = self.inning_run_distribution(start_batter_idx=lead_idx)
                for inning_runs, p_runs in enumerate(inning_run_dist):
                    if p_runs == 0:
                        continue
                    new_total = min(self.max_runs, total_runs + inning_runs)
                    for next_lead, p_lead_next in enumerate(next_batter_dist):
                        if p_lead_next == 0:
                            continue
                        key = (new_total, next_lead)
                        next_overall[key] = next_overall.get(key, 0.0) + prob_lead * p_runs * p_lead_next
            overall = next_overall

        game_dist = [0.0 for _ in range(self.max_runs + 1)]
        for (runs, _lead), prob in overall.items():
            game_dist[runs] += prob

        total = sum(game_dist)
        if total <= 0:
            raise RuntimeError("경기 분포 계산 실패")
        return [x / total for x in game_dist]

    @staticmethod
    def expected_runs(run_distribution: List[float]) -> float:
        return sum(i * p for i, p in enumerate(run_distribution))

    def expected_runs_per_game(self, innings: int = REGULATION_INNINGS) -> float:
        dist = self.game_run_distribution(innings=innings)
        return self.expected_runs(dist)


class LineupMonteCarloSimulator:
    def __init__(self, lineup: List[PlayerProb], seed: int | None = None) -> None:
        if len(lineup) != 9:
            raise ValueError("라인업은 9명이어야 합니다.")
        self.lineup = [p.normalized() for p in lineup]
        self.rng = random.Random(seed)

    def sample_event(self, player: PlayerProb) -> str:
        x = self.rng.random()
        cumulative = 0.0
        for event, p in player.event_probs():
            cumulative += p
            if x <= cumulative:
                return event
        return "OUT"

    def simulate_game(self, innings: int = REGULATION_INNINGS) -> int:
        score = 0
        batter_idx = 0

        for _ in range(innings):
            outs = 0
            base_mask = 0
            while outs < 3:
                player = self.lineup[batter_idx]
                event = self.sample_event(player)
                base_mask, outs, runs = apply_event(base_mask, outs, event)
                score += runs
                batter_idx = (batter_idx + 1) % 9
        return score

    def simulate_many(self, n_games: int = 10000, innings: int = REGULATION_INNINGS) -> Dict[str, object]:
        scores = [self.simulate_game(innings=innings) for _ in range(n_games)]
        mean_score = sum(scores) / len(scores)
        var = sum((x - mean_score) ** 2 for x in scores) / len(scores)
        distribution: Dict[int, int] = {}
        for s in scores:
            distribution[s] = distribution.get(s, 0) + 1

        prob_5_or_more = sum(v for k, v in distribution.items() if k >= 5) / n_games
        prob_0 = distribution.get(0, 0) / n_games

        return {
            "mean_runs": mean_score,
            "variance": var,
            "distribution": dict(sorted(distribution.items())),
            "prob_0_runs": prob_0,
            "prob_5_or_more_runs": prob_5_or_more,
        }


class MatchSimulator:
    """두 팀의 경기를 실제 경기 흐름처럼 타석 단위로 시뮬레이션한다."""

    def __init__(
        self,
        team_a_name: str,
        team_a_lineup: List[PlayerProb],
        team_b_name: str,
        team_b_lineup: List[PlayerProb],
        seed: int | None = None,
    ) -> None:
        self.team_a_name = team_a_name
        self.team_b_name = team_b_name
        self.team_a_lineup = [p.normalized() for p in team_a_lineup]
        self.team_b_lineup = [p.normalized() for p in team_b_lineup]
        self.rng = random.Random(seed)

    def sample_event(self, player: PlayerProb) -> str:
        x = self.rng.random()
        cumulative = 0.0
        for event, p in player.event_probs():
            cumulative += p
            if x <= cumulative:
                return event
        return "OUT"

    def simulate_half_inning(
        self,
        inning: int,
        half: str,
        team_name: str,
        lineup: List[PlayerProb],
        start_batter_idx: int,
        walkoff_target: int | None = None,
    ) -> Tuple[HalfInningLog, int, bool]:
        outs = 0
        base_mask = 0
        runs = 0
        batter_idx = start_batter_idx
        is_walkoff = False
        plate_logs: List[PlateAppearanceLog] = []

        while outs < 3:
            player = lineup[batter_idx]
            event = self.sample_event(player)
            new_base_mask, new_outs, scored = apply_event(base_mask, outs, event)
            runs += scored

            plate_logs.append(
                PlateAppearanceLog(
                    inning=inning,
                    half=half,
                    batter_order=batter_idx + 1,
                    batter_name=player.name,
                    event=event,
                    runs_scored=scored,
                    outs_after=new_outs,
                    bases_after=format_bases(new_base_mask),
                )
            )

            base_mask = new_base_mask
            outs = new_outs
            batter_idx = (batter_idx + 1) % 9

            if walkoff_target is not None and runs >= walkoff_target:
                is_walkoff = True
                break

        half_log = HalfInningLog(
            inning=inning,
            half=half,
            team_name=team_name,
            runs=runs,
            plate_appearances=plate_logs,
        )
        return half_log, batter_idx, is_walkoff

    def simulate_game(
        self,
        innings: int = REGULATION_INNINGS,
        max_innings: int = MAX_GAME_INNINGS,
    ) -> GameLog:
        """
        경기 전체 시뮬레이션.

        - 정규 9이닝 진행
        - 동점이면 연장 진행
        - 홈팀이 말 공격에서 앞서면 끝내기 종료
        - max_innings, 기본 12회 이후에도 동점이면 무승부 종료
        """

        if max_innings < innings:
            raise ValueError("max_innings는 정규 이닝보다 작을 수 없습니다.")

        team_a_score = 0
        team_b_score = 0
        team_a_batter_idx = 0
        team_b_batter_idx = 0
        inning_logs: List[HalfInningLog] = []
        inning = 1

        while inning <= max_innings:
            top_log, team_a_batter_idx, _ = self.simulate_half_inning(
                inning=inning,
                half="초",
                team_name=self.team_a_name,
                lineup=self.team_a_lineup,
                start_batter_idx=team_a_batter_idx,
            )
            team_a_score += top_log.runs
            inning_logs.append(top_log)

            # 정규 이닝 마지막 이후 홈팀이 이미 앞서면 말 공격 생략
            if inning >= innings and team_b_score > team_a_score:
                break

            walkoff_target = None
            if inning >= innings:
                walkoff_target = team_a_score - team_b_score + 1

            bottom_log, team_b_batter_idx, is_walkoff = self.simulate_half_inning(
                inning=inning,
                half="말",
                team_name=self.team_b_name,
                lineup=self.team_b_lineup,
                start_batter_idx=team_b_batter_idx,
                walkoff_target=walkoff_target,
            )
            team_b_score += bottom_log.runs
            inning_logs.append(bottom_log)

            if is_walkoff:
                break

            if inning >= max_innings:
                break

            if inning >= innings and team_a_score != team_b_score:
                break

            inning += 1

        return GameLog(
            team_a=self.team_a_name,
            team_b=self.team_b_name,
            final_score=(team_a_score, team_b_score),
            innings=inning_logs,
        )


# -----------------------------------------------------------------------------
# 출력 및 실행 보조 함수
# -----------------------------------------------------------------------------

def print_game_log(game_log: GameLog) -> None:
    team_a_score, team_b_score = game_log.final_score

    print("=" * 70)
    print(f"{game_log.team_a} vs {game_log.team_b}")
    print("=" * 70)

    for half_log in game_log.innings:
        print(f"\n[{half_log.inning}회{half_log.half}] {half_log.team_name} 공격")
        print(f"이닝 득점: {half_log.runs}점")
        for log in half_log.plate_appearances:
            print(
                f"  {log.batter_order}번 {log.batter_name} - {log.event} "
                f"/ 득점 {log.runs_scored} "
                f"/ 아웃 {log.outs_after} "
                f"/ {log.bases_after}"
            )

    print("\n" + "=" * 70)
    print("[최종 스코어]")
    print(f"{game_log.team_a} {team_a_score} : {team_b_score} {game_log.team_b}")
    if game_log.innings and game_log.innings[-1].inning >= MAX_GAME_INNINGS and team_a_score == team_b_score:
        print(f"{MAX_GAME_INNINGS}회 종료 무승부")
    print("=" * 70)


def brute_force_optimize(lineup: List[PlayerProb], innings: int = REGULATION_INNINGS) -> Tuple[List[PlayerProb], float]:
    best_order: List[PlayerProb] | None = None
    best_score = -math.inf

    for perm in permutations(lineup, 9):
        model = LineupMarkovModel(list(perm))
        exp_runs = model.expected_runs_per_game(innings=innings)
        if exp_runs > best_score:
            best_score = exp_runs
            best_order = list(perm)

    if best_order is None:
        raise RuntimeError("최적화 실패")
    return best_order, best_score


def print_lineup(lineup: List[PlayerProb]) -> str:
    lines = []
    for idx, player in enumerate(lineup, start=1):
        if player.position:
            lines.append(f"{idx}. {player.name} ({player.position})")
        else:
            lines.append(f"{idx}. {player.name}")
    return "\n".join(lines)


def choose_team(label: str, hitter_stats_csv_path: Path = HITTER_STATS_CSV_PATH) -> str:
    teams = available_teams(hitter_stats_csv_path)
    print(f"\n[{label} 선택]")
    print("사용 가능 팀:", ", ".join(teams))
    default = "SSG" if label == "원정팀" else "롯데"
    selected = input(f"{label} 이름을 입력하세요 [기본값: {default}]: ").strip()
    return selected or default


def run_team_report(team_name: str, lineup: List[PlayerProb], innings: int = REGULATION_INNINGS) -> Tuple[List[float], float]:
    print(f"\n[{team_name} Markov Chain 결과]")
    model = LineupMarkovModel(lineup, max_runs=25)
    dist = model.game_run_distribution(innings=innings)
    expected = model.expected_runs(dist)
    print(f"{team_name} 기대 득점: {expected:.4f}")
    return dist, expected


def run_monte_carlo_report(
    team_name: str,
    lineup: List[PlayerProb],
    seed: int = 42,
    innings: int = REGULATION_INNINGS,
) -> Dict[str, object]:
    mc = LineupMonteCarloSimulator(lineup, seed=seed)
    result = mc.simulate_many(n_games=5000, innings=innings)

    print(f"\n{team_name}")
    print(f"평균 득점: {result['mean_runs']:.4f}")
    print(f"분산: {result['variance']:.4f}")
    print(f"0점 확률: {result['prob_0_runs']:.4%}")
    print(f"5점 이상 확률: {result['prob_5_or_more_runs']:.4%}")
    return result


# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("[DB 경로 확인]")
    print(f"타자 기록 CSV: {HITTER_STATS_CSV_PATH}")
    print(f"수비 기록 CSV: {DEFENSE_STATS_CSV_PATH}")
    print(f"투수 기록 CSV: {PITCHER_STATS_CSV_PATH}")
    print(f"팀 투수 기록 CSV: {TEAM_PITCHER_STATS_CSV_PATH}")

    hitter_rows = _read_csv(HITTER_STATS_CSV_PATH)
    season_year = _latest_season(hitter_rows)
    print(f"사용 시즌: {season_year}")

    team_a_name = choose_team("원정팀", hitter_stats_csv_path=HITTER_STATS_CSV_PATH)
    team_b_name = choose_team("홈팀", hitter_stats_csv_path=HITTER_STATS_CSV_PATH)

    team_a_original = load_team_players_from_db(
        team_a_name,
        season_year=season_year,
        hitter_stats_csv_path=HITTER_STATS_CSV_PATH,
        defense_stats_csv_path=DEFENSE_STATS_CSV_PATH,
        use_position_lineup=True,
    )
    team_b_original = load_team_players_from_db(
        team_b_name,
        season_year=season_year,
        hitter_stats_csv_path=HITTER_STATS_CSV_PATH,
        defense_stats_csv_path=DEFENSE_STATS_CSV_PATH,
        use_position_lineup=True,
    )

    print("=" * 70)
    print(f"팀 A: {team_a_name} 원본 라인업")
    print(print_lineup(team_a_original))

    print(f"\n팀 B: {team_b_name} 원본 라인업")
    print(print_lineup(team_b_original))

    team_a_starting_pitcher = choose_starting_pitcher(
        team_a_name,
        season_year=season_year,
        pitcher_stats_csv_path=PITCHER_STATS_CSV_PATH,
    )
    team_b_starting_pitcher = choose_starting_pitcher(
        team_b_name,
        season_year=season_year,
        pitcher_stats_csv_path=PITCHER_STATS_CSV_PATH,
    )

    league_avg = load_league_average_prob_from_db(
        season_year=season_year,
        team_pitcher_stats_csv_path=TEAM_PITCHER_STATS_CSV_PATH,
    )

    team_a = adjust_lineup_by_pitcher(
        lineup=team_a_original,
        opposing_pitcher=team_b_starting_pitcher,
        league_avg=league_avg,
        pitcher_weight=PITCHER_ADJUSTMENT_WEIGHT,
    )
    team_b = adjust_lineup_by_pitcher(
        lineup=team_b_original,
        opposing_pitcher=team_a_starting_pitcher,
        league_avg=league_avg,
        pitcher_weight=PITCHER_ADJUSTMENT_WEIGHT,
    )

    print("\n" + "=" * 70)
    print("[선발투수 반영]")
    print(f"{team_a_name} 선발투수: {team_a_starting_pitcher.name}")
    print(f"{team_b_name} 선발투수: {team_b_starting_pitcher.name}")
    print(f"투수 보정 가중치: {PITCHER_ADJUSTMENT_WEIGHT:.2f}")

    print("\n" + "=" * 70)
    team_a_dist, team_a_expected = run_team_report(team_a_name, team_a, innings=REGULATION_INNINGS)
    team_b_dist, team_b_expected = run_team_report(team_b_name, team_b, innings=REGULATION_INNINGS)

    print("\n" + "=" * 70)
    print(f"[{team_a_name} vs {team_b_name} 경기 로그 시뮬레이션]")
    print(f"정규 이닝: {REGULATION_INNINGS} / 최대 이닝: {MAX_GAME_INNINGS}")

    match = MatchSimulator(
        team_a_name=team_a_name,
        team_a_lineup=team_a,
        team_b_name=team_b_name,
        team_b_lineup=team_b,
    )

    game_log = match.simulate_game(
        innings=REGULATION_INNINGS,
        max_innings=MAX_GAME_INNINGS,
    )
    print_game_log(game_log)

    print("\n" + "=" * 70)
    print("[Monte Carlo 결과 비교]")

    team_a_mc_result = run_monte_carlo_report(team_a_name, team_a, seed=42, innings=REGULATION_INNINGS)
    team_b_mc_result = run_monte_carlo_report(team_b_name, team_b, seed=42, innings=REGULATION_INNINGS)

    print("\n[Markov vs Monte Carlo 평균 득점 비교]")
    print(
        f"{team_a_name} - Markov 기대 득점: {team_a_expected:.4f} "
        f"/ Monte Carlo 평균 득점: {team_a_mc_result['mean_runs']:.4f}"
    )
    print(
        f"{team_b_name} - Markov 기대 득점: {team_b_expected:.4f} "
        f"/ Monte Carlo 평균 득점: {team_b_mc_result['mean_runs']:.4f}"
    )


if __name__ == "__main__":
    main()
