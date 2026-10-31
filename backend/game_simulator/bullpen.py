"""Optional pitching changes. Default thresholds are explicit, untrained rules.

Daily pitching lines can supply workload samples, but cannot train decisions
conditional on score/outs/runners. No fatigue or platoon coefficients are invented.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import TYPE_CHECKING, Mapping, Sequence

if TYPE_CHECKING:
    from .simulator_main import PitcherProb


def pitcher_key(pitcher: PitcherProb) -> str:
    return pitcher.player_id or pitcher.name


@dataclass(frozen=True)
class BullpenConfig:
    starter_batters: int = 24
    reliever_batters: int = 6
    starter_max_batters: int = 36
    reliever_max_batters: int = 15
    starter_min_batters: int = 9
    starter_runs: int = 4
    reliever_min_batters: int = 3
    reliever_runs: int = 3
    crisis_runners: int = 2
    close_margin: int = 3
    relief_prior_batters: float = 60.0

    def __post_init__(self):
        for name, value in vars(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"불펜 설정 {name}은 유한한 숫자여야 합니다.")
            if name == "relief_prior_batters":
                if value < 0:
                    raise ValueError("불펜 확률 보정 표본 수는 0 이상이어야 합니다.")
            elif not isinstance(value, int) or value < 1:
                raise ValueError(f"불펜 설정 {name}은 양의 정수여야 합니다.")
        if self.crisis_runners > 3:
            raise ValueError("위기 주자 수는 1~3이어야 합니다.")
        if self.starter_batters > self.starter_max_batters or self.reliever_batters > self.reliever_max_batters:
            raise ValueError("기본 상대 타자 수가 최대값보다 클 수 없습니다.")


@dataclass(frozen=True)
class PitchingStaff:
    starter: PitcherProb
    relievers: tuple[PitcherProb, ...] = ()
    closer_id: str | None = None
    # (player ID, starter/reliever) -> observed batters faced per appearance.
    workloads: Mapping[tuple[str, str], tuple[int, ...]] = field(default_factory=dict)

    def __post_init__(self):
        pitchers = (self.starter, *self.relievers)
        keys = [pitcher_key(p) for p in pitchers]
        if len(keys) != len(set(keys)):
            raise ValueError("선발과 불펜 명단에 같은 투수를 중복 등록할 수 없습니다.")
        if any(p.team_name != self.starter.team_name for p in pitchers):
            raise ValueError("투수 명단은 같은 팀으로 구성해야 합니다.")
        if self.closer_id is not None and self.closer_id not in keys[1:]:
            raise ValueError("마무리는 불펜 명단에 있어야 합니다.")


def build_pitching_staff(starter, candidates, workloads=None, closer_id=None):
    """Infer candidates from majority relief usage; save leaders are suggestions."""
    relievers = tuple(sorted(
        (p for p in candidates if pitcher_key(p) != pitcher_key(starter)
         and p.tbf > 0 and p.g - p.gs > 0 and p.g - p.gs >= p.gs),
        key=lambda p: (-(p.g - p.gs), -p.hld, -p.tbf, pitcher_key(p)),
    ))
    if closer_id is None:
        saved = [p for p in relievers if p.sv > 0]
        if saved:
            closer_id = pitcher_key(max(saved, key=lambda p: (p.sv, p.g - p.gs, p.tbf)))
    return PitchingStaff(starter, relievers, closer_id, workloads or {})


def appearance_workloads(rows: Sequence[dict], team_name: str):
    """The caller must restrict dates before supplying historical rows."""
    samples = {}
    for row in rows:
        if row["team_name"] != team_name:
            continue
        tbf = row.get("tbf")
        if isinstance(tbf, bool) or not isinstance(tbf, int) or tbf < 0:
            raise ValueError("경기별 상대 타자 수는 0 이상의 정수여야 합니다.")
        # Zero-batter appearances cannot provide a usable workload budget.
        if tbf:
            role = "starter" if row["gs"] else "reliever"
            samples.setdefault((str(row["player_id"]), role), []).append(tbf)
    return {key: tuple(values) for key, values in samples.items()}


@dataclass
class PitcherUsage:
    pitcher: PitcherProb
    role: str
    budget: int
    workload_source: str
    batters_faced: int = 0
    outs: int = 0
    runs_on_mound: int = 0  # Includes inherited runners; NOT earned runs.
    reaches: int = 0


@dataclass
class PitchingState:
    staff: PitchingStaff
    appearances: list[PitcherUsage]

    @property
    def current(self):
        return self.appearances[-1]

    def available(self):
        used = {pitcher_key(u.pitcher) for u in self.appearances}
        return [p for p in self.staff.relievers if pitcher_key(p) not in used]


@dataclass(frozen=True)
class PitchingSituation:
    inning: int
    regulation_innings: int
    outs: int
    bases: int
    lead: int  # Defensive team's score minus offensive team's CURRENT score.
    is_inning_start: bool = False


class PitchingPolicy:
    """Workload + situation baseline; decisions and next-pitcher choice are separate."""
    def __init__(self, config=None):
        self.config = config or BullpenConfig()

    def _mean_budget(self, pitcher, role):
        c = self.config
        fallback = c.starter_batters if role == "starter" else c.reliever_batters
        cap = c.starter_max_batters if role == "starter" else c.reliever_max_batters
        # TBF/G is role-specific only for pure starters or pure relievers.
        pure = (pitcher.gs == pitcher.g) if role == "starter" else (pitcher.gs == 0)
        if pure and pitcher.g > 0 and pitcher.tbf > 0:
            return min(cap, max(1, math.ceil(pitcher.tbf / pitcher.g))), "season_role_mean"
        return fallback, "configured_fallback"

    def new_usage(self, staff, pitcher, role, rng):
        samples = staff.workloads.get((pitcher_key(pitcher), "starter" if role == "starter" else "reliever"), ())
        if samples:
            cap = self.config.starter_max_batters if role == "starter" else self.config.reliever_max_batters
            budget, source = min(cap, max(1, rng.choice(samples))), "daily_appearance_sample"
        else:
            budget, source = self._mean_budget(pitcher, "starter" if role == "starter" else "reliever")
        return PitcherUsage(pitcher, role, budget, source)

    def start_game(self, staff, rng):
        return PitchingState(staff, [self.new_usage(staff, staff.starter, "starter", rng)])

    def should_replace(self, state, situation):
        u, c = state.current, self.config
        if not state.available() or u.batters_faced == 0:
            return None
        if u.batters_faced >= u.budget:
            return "상대 타자 수 기준 도달"
        minimum = c.starter_min_batters if u.role == "starter" else c.reliever_min_batters
        runs_limit = c.starter_runs if u.role == "starter" else c.reliever_runs
        if u.batters_faced >= minimum:
            if u.runs_on_mound >= runs_limit:
                return "실점 누적에 따른 조기 교체"
            if (situation.bases.bit_count() >= c.crisis_runners and situation.outs < 2
                    and abs(situation.lead) <= c.close_margin and u.reaches >= runs_limit):
                return "접전 주자 위기"
        closer_available = any(pitcher_key(p) == state.staff.closer_id for p in state.available())
        if (situation.is_inning_start and situation.inning >= situation.regulation_innings and situation.outs == 0
                and situation.bases == 0 and 1 <= situation.lead <= c.close_margin
                and closer_available):
            return "후반 리드 상황 마무리 투입"
        return None

    def select_replacement(self, state, situation):
        available = state.available()
        if not available:
            return None
        closer = next((p for p in available if pitcher_key(p) == state.staff.closer_id), None)
        if closer and situation.inning >= situation.regulation_innings and 1 <= situation.lead <= self.config.close_margin:
            return closer, "closer"
        pool = [p for p in available if p is not closer] or available
        if situation.inning < situation.regulation_innings - 2 or abs(situation.lead) > self.config.close_margin:
            # Long relief / lower priority situations: reserve high-hold pitchers.
            pitcher = max(pool, key=lambda p: (self._mean_budget(p, "reliever")[0], -p.hld, p.tbf))
        else:
            pitcher = max(pool, key=lambda p: (p.hld, p.g - p.gs, p.tbf))
        return pitcher, "closer" if pitcher is closer else "reliever"

    def replace(self, state, replacement, rng):
        pitcher, role = replacement
        state.appearances.append(self.new_usage(state.staff, pitcher, role, rng))
