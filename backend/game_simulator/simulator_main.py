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
"""

from __future__ import annotations
from dataclasses import dataclass
from itertools import permutations
from typing import Dict, List, Tuple
import math
import random

# ── KBO 리그 평균 & 베이지안 스무딩 상수 (2025 시즌 기준) ──────────────
LEAGUE_AVG = {
    "bb":     0.085,
    "single": 0.150,
    "double": 0.040,
    "triple": 0.004,
    "hr":     0.028,
}
SMOOTHING_K = 200

@dataclass(frozen=True)
class PlayerProb: #선수 1명의 확률 정보를 담는 클래스
    name: str
    bb: float
    single: float
    double: float
    triple: float
    hr: float
    out: float | None = None

    def normalized(self) -> "PlayerProb":
        probs = {
            "bb": self.bb,
            "single": self.single,
            "double": self.double,
            "triple": self.triple,
            "hr": self.hr,
        }
        if self.out is None:
            out = 1.0 - sum(probs.values())
        else:
            out = self.out

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
class BattingRecord: #실제 선수 타격 기록을 담는 클래스
    """
    실제 선수 타격 기록을 담는 클래스

    이 기록을 바탕으로
    BB, 1B, 2B, 3B, HR, OUT 확률을 계산한다.
    """

    name: str       # 선수 이름
    ab: int         # 타수
    hits: int       # 안타
    double: int     # 2루타
    triple: int     # 3루타
    hr: int         # 홈런
    bb: int         # 볼넷
    hbp: int = 0    # 사구, 기본값 0


@dataclass
class PlateAppearanceLog: #한 타석에 대한 정보를 저장하는 클래스
    """
    즉, 경기의 가장 작은 단위 로그
    (타자 한 명이 결과를 낼 때마다 1개 생성됨)
    """

    inning: int          # 몇 회인지 (1~9)
    half: str            # "초" 또는 "말" (공격 팀 구분)
    
    batter_order: int    # 타순 (1번~9번)
    batter_name: str     # 타자 이름

    event: str           # 결과 (BB, 1B, 2B, 3B, HR, OUT)
    
    runs_scored: int     # 이 타석에서 발생한 득점 수
    
    outs_after: int      # 이 타석 이후 아웃카운트 (0~3)
    
    bases_after: str     # 이 타석 이후 주자 상태 (예: "1루, 2루")

@dataclass
class HalfInningLog: #반 이닝(1회초, 1회말 등) 전체 결과를 저장하는 클래스
    
    inning: int                      # 몇 회인지
    half: str                        # "초" or "말"
    
    team_name: str                   # 공격 팀 이름
    
    runs: int                        # 해당 이닝에서 득점한 총 점수
    
    plate_appearances: List[PlateAppearanceLog]
    # 이 이닝 동안 발생한 모든 타석 로그

@dataclass
class GameLog: #한 경기 전체 결과를 저장하는 클래스
    
    #모든 이닝 로그를 포함

    team_a: str                    # A팀 이름
    team_b: str                    # B팀 이름

    final_score: Tuple[int, int]   # (A팀 점수, B팀 점수)

    innings: List[HalfInningLog]   # 모든 이닝 로그 (1회초 ~ 9회말)



def record_to_player_prob(record: BattingRecord) -> PlayerProb:
    """
    선수의 실제 타격 기록을 PlayerProb 확률 구조로 변환
    베이지안 스무딩 적용:
      smoothed = (관측값 * PA + 리그평균 * K) / (PA + K)
    PA가 적을수록 리그 평균 쪽으로 당겨짐
    """
    pa = record.ab + record.bb + record.hbp
    if pa <= 0:
        raise ValueError(f"{record.name}: 유효한 타석 수가 없습니다.")

    single = record.hits - record.double - record.triple - record.hr
    if single < 0:
        raise ValueError(f"{record.name}: 안타 세부 기록이 잘못되었습니다.")

    obs_bb     = (record.bb + record.hbp) / pa
    obs_single = single / pa
    obs_double = record.double / pa
    obs_triple = record.triple / pa
    obs_hr     = record.hr / pa

    w = pa / (pa + SMOOTHING_K)

    bb_prob     = w * obs_bb     + (1 - w) * LEAGUE_AVG["bb"]
    single_prob = w * obs_single + (1 - w) * LEAGUE_AVG["single"]
    double_prob = w * obs_double + (1 - w) * LEAGUE_AVG["double"]
    triple_prob = w * obs_triple + (1 - w) * LEAGUE_AVG["triple"]
    hr_prob     = w * obs_hr     + (1 - w) * LEAGUE_AVG["hr"]

    out_prob = 1.0 - (bb_prob + single_prob + double_prob + triple_prob + hr_prob)

    return PlayerProb(
        name=record.name,
        bb=bb_prob,
        single=single_prob,
        double=double_prob,
        triple=triple_prob,
        hr=hr_prob,
        out=out_prob,
    ).normalized()

def apply_event(base_mask: int, outs: int, event: str) -> Tuple[int, int, int]: #한 타석 결과가 상태를 어떻게 바꾸는지 계산
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

def format_bases(base_mask: int) -> str: #상태 출력용 함수
    """
    base_mask를 사람이 읽을 수 있는 문자열로 변환
    비트마스크 구조:
        1루: 1 (001)
        2루: 2 (010)
        3루: 4 (100)
    """
    bases = []

    # 각 비트를 검사해서 주자가 있는지 확인
    if base_mask & 1:
        bases.append("1루")
    if base_mask & 2:
        bases.append("2루")
    if base_mask & 4:
        bases.append("3루")

    # 아무 주자도 없으면 "주자 없음"
    return ", ".join(bases) if bases else "주자 없음"



class LineupMarkovModel: #마르코프 체인 방식으로 기대 득점 계산
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

    def game_run_distribution(self, innings: int = 9) -> List[float]:
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

    def expected_runs_per_game(self, innings: int = 9) -> float:
        dist = self.game_run_distribution(innings=innings)
        return self.expected_runs(dist)

class LineupMonteCarloSimulator: #몬테카를로 방식으로 경기 반복 시뮬레이션
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

    def simulate_game(self, innings: int = 9) -> int:
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

    def simulate_many(self, n_games: int = 10000, innings: int = 9) -> Dict[str, object]:
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

class MatchSimulator:#두 팀의 경기를 시뮬레이션하는 클래스
    """
    기존 Markov 모델의 상태 전이 규칙(apply_event)을 그대로 사용하면서
    실제 경기처럼 타석 단위로 진행되는 로그를 생성
    """

    def __init__(
        self,
        team_a_name: str,
        team_a_lineup: List[PlayerProb],
        team_b_name: str,
        team_b_lineup: List[PlayerProb],
        seed: int | None = None,
    ) -> None:

        # 팀 이름 저장
        self.team_a_name = team_a_name
        self.team_b_name = team_b_name

        # 선수 확률을 정규화해서 저장
        self.team_a_lineup = [p.normalized() for p in team_a_lineup]
        self.team_b_lineup = [p.normalized() for p in team_b_lineup]

        # 랜덤 시드 (재현 가능한 결과를 위해)
        self.rng = random.Random(seed)

    def sample_event(self, player: PlayerProb) -> str: #이벤트 샘플링 함수
        """
        한 타자의 결과를 확률적으로 샘플링

        예:
        BB 0.1, 1B 0.2, OUT 0.7 이면
        누적 확률 기반으로 랜덤 선택
        """

        x = self.rng.random()  # 0~1 사이 랜덤값
        cumulative = 0.0

        # 이벤트를 하나씩 누적하면서 랜덤값과 비교
        for event, p in player.event_probs():
            cumulative += p
            if x <= cumulative:
                return event

        # 안전장치 (이론적으로 거의 안옴)
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
        """
        한 이닝(초 or 말)을 시뮬레이션

        walkoff_target:
        - None이면 일반 이닝
        - 숫자가 들어오면 해당 점수에 도달하는 순간 공격 종료
        - 예: 원정팀이 4점이면 홈팀은 5점 도달 순간 끝내기 승리
        """

        outs = 0
        base_mask = 0
        runs = 0
        batter_idx = start_batter_idx
        is_walkoff = False

        plate_logs: List[PlateAppearanceLog] = []

        while outs < 3:
            player = lineup[batter_idx]

            # 1. 타석 결과 샘플링
            event = self.sample_event(player)

            # 2. 상태 전이
            new_base_mask, new_outs, scored = apply_event(base_mask, outs, event)

            # 3. 득점 누적
            runs += scored

            # 4. 로그 기록
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

            # 5. 상태 업데이트
            base_mask = new_base_mask
            outs = new_outs

            # 6. 다음 타자
            batter_idx = (batter_idx + 1) % 9

            # 7. 끝내기 조건 확인
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

    def simulate_game(self, innings: int = 9) -> GameLog:
        """
        경기 전체 시뮬레이션

        반영 규칙:
        - team_a는 원정팀: 초 공격
        - team_b는 홈팀: 말 공격
        - 9회초 종료 후 홈팀이 앞서면 9회말 생략
        - 9회말 또는 연장 말 공격에서 홈팀이 앞서는 순간 끝내기 종료
        """

        team_a_score = 0
        team_b_score = 0

        team_a_batter_idx = 0
        team_b_batter_idx = 0

        inning_logs: List[HalfInningLog] = []

        inning = 1

        while True:
            # -------- 초 공격: team_a --------
            top_log, team_a_batter_idx, _ = self.simulate_half_inning(
                inning=inning,
                half="초",
                team_name=self.team_a_name,
                lineup=self.team_a_lineup,
                start_batter_idx=team_a_batter_idx,
            )

            team_a_score += top_log.runs
            inning_logs.append(top_log)

            # 정규 이닝 마지막 초 공격 후 홈팀이 이미 이기고 있으면 말 공격 생략
            # 원정팀이 지고 있으면 말 공격 생략
            if inning >= innings and team_b_score >= team_a_score:
                break

            # -------- 말 공격: team_b --------
            # 정규 이닝 마지막 또는 연장에서는 홈팀이 앞서면 즉시 끝내기
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

            # 홈팀 끝내기 승리
            if is_walkoff:
                break

            # 정규 이닝 이후 양 팀 점수가 다르면 경기 종료
            if inning >= innings and team_a_score != team_b_score:
                break

            # 최대 이닝 초과 시 무승부 종료
            if inning >= innings:
                break

            # 다음 이닝 진행
            inning += 1

        return GameLog(
            team_a=self.team_a_name,
            team_b=self.team_b_name,
            final_score=(team_a_score, team_b_score),
            innings=inning_logs,
        )



def print_game_log(game_log: GameLog) -> None:
    """
    경기 로그를 사람이 읽기 쉬운 형태로 출력

    변경 사항:
    - 경기 시작 정보 먼저 출력
    - 이닝별 로그 출력
    - 마지막에 최종 스코어 출력
    """

    team_a_score, team_b_score = game_log.final_score

    print("=" * 70)
    print(f"{game_log.team_a} vs {game_log.team_b}")
    print("=" * 70)

    # 이닝별 출력
    for half_log in game_log.innings:
        print(f"\n[{half_log.inning}회{half_log.half}] {half_log.team_name} 공격")
        print(f"이닝 득점: {half_log.runs}점")

        # 타석별 출력
        for log in half_log.plate_appearances:
            print(
                f"  {log.batter_order}번 {log.batter_name} - {log.event} "
                f"/ 득점 {log.runs_scored} "
                f"/ 아웃 {log.outs_after} "
                f"/ {log.bases_after}"
            )

    # 최종 스코어는 모든 이닝 출력 후 마지막에 표시
    print("\n" + "=" * 70)
    print("[최종 스코어]")
    print(f"{game_log.team_a} {team_a_score} : {team_b_score} {game_log.team_b}")
    print("=" * 70)

def brute_force_optimize(lineup: List[PlayerProb], innings: int = 9) -> Tuple[List[PlayerProb], float]: #9! 모든 타순 평가
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

def print_lineup(lineup: List[PlayerProb]) -> str: #라인업 출력 함수
    return "\n".join(
        f"{idx}. {player.name}"
        for idx, player in enumerate(lineup, start=1)
    )

def ssg_landers_players() -> List[PlayerProb]:
    """
    SSG 랜더스 라인업 데이터

    실제 프로젝트에서는 여기의 수치를
    KBO / STATIZ / CSV / DB에서 가져온 선수별 시즌 기록으로 교체하면 된다.
    """

    records = [
        BattingRecord(
            name="박성한",
            ab=106,
            hits=46,
            double=10,
            triple=1,
            hr=2,
            bb=24,
            hbp=1,
        ),
        BattingRecord(
            name="정준재",
            ab=62,
            hits=18,
            double=1,
            triple=1,
            hr=1,
            bb=8,
            hbp=1,
        ),
        BattingRecord(
            name="최정",
            ab=101,
            hits=27,
            double=7,
            triple=1,
            hr=7,
            bb=19,
            hbp=3,
        ),
        BattingRecord(
            name="에레디아",
            ab=115,
            hits=31,
            double=4,
            triple=0,
            hr=5,
            bb=6,
            hbp=1,
        ),
        BattingRecord(
            name="한유섬",
            ab=64,
            hits=11,
            double=1,
            triple=0,
            hr=0,
            bb=16,
            hbp=2,
        ),
        BattingRecord(
            name="최지훈",
            ab=106,
            hits=22,
            double=5,
            triple=1,
            hr=4,
            bb=8,
            hbp=2,
        ),
        BattingRecord(
            name="오태곤",
            ab=57,
            hits=14,
            double=4,
            triple=0,
            hr=2,
            bb=4,
            hbp=2,
        ),
        BattingRecord(
            name="최준우",  # 표본이 적음 시뮬레이션에 영향갈 수 있음
            ab=8,
            hits=4,
            double=0,
            triple=0,
            hr=0,
            bb=1,
            hbp=0,
        ),
        BattingRecord(
            name="조형우",
            ab=58,
            hits=16,
            double=4,
            triple=0,
            hr=1,
            bb=5,
            hbp=2,
        ),
    ]

    return [record_to_player_prob(record) for record in records]

def lotte_giants_players() -> List[PlayerProb]:
    """
    롯데 자이언츠 라인업 데이터

    실제 프로젝트에서는 여기의 수치를
    KBO / STATIZ / CSV / DB에서 가져온 선수별 시즌 기록으로 교체하면 된다.
    """

    records = [
        BattingRecord(
            name="장두성",
            ab=48,
            hits=16,
            double=1,
            triple=1,
            hr=0,
            bb=1,
            hbp=1,
        ),
        BattingRecord(
            name="윤동희",
            ab=75,
            hits=14,
            double=4,
            triple=0,
            hr=3,
            bb=6,
            hbp=1,
        ),
        BattingRecord(
            name="레이예스",
            ab=113,
            hits=39,
            double=8,
            triple=0,
            hr=5,
            bb=11,
            hbp=2,
        ),
        BattingRecord(
            name="유강남",
            ab=62,
            hits=16,
            double=4,
            triple=0,
            hr=2,
            bb=1,
            hbp=0,
        ),
        BattingRecord(
            name="김민성",
            ab=14,
            hits=1,
            double=0,
            triple=0,
            hr=1,
            bb=3,
            hbp=0,
        ),
        BattingRecord(
            name="박승욱",
            ab=32,
            hits=11,
            double=2,
            triple=0,
            hr=1,
            bb=1,
            hbp=0,
        ),
        BattingRecord(
            name="전민재",
            ab=77,
            hits=18,
            double=3,
            triple=0,
            hr=0,
            bb=7,
            hbp=0,
        ),
        BattingRecord(
            name="손성빈",
            ab=48,
            hits=10,
            double=2,
            triple=0,
            hr=1,
            bb=6,
            hbp=0,
        ),
        BattingRecord(
            name="한태양",
            ab=74,
            hits=18,
            double=3,
            triple=0,
            hr=0,
            bb=7,
            hbp=1,
        ),
    ]

    return [record_to_player_prob(record) for record in records]



def main() -> None:
    team_a = ssg_landers_players()
    team_b = lotte_giants_players()

    print("=" * 70)
    print("팀 A: SSG 랜더스")
    print(print_lineup(team_a))

    print("\n팀 B: 롯데 자이언츠")
    print(print_lineup(team_b))

    print("\n" + "=" * 70)
    print("[SSG Markov Chain 결과]")

    ssg_model = LineupMarkovModel(team_a, max_runs=25)
    ssg_dist = ssg_model.game_run_distribution(innings=9)
    ssg_expected = ssg_model.expected_runs(ssg_dist)

    print(f"SSG 기대 득점: {ssg_expected:.4f}")

    print("\n[롯데 Markov Chain 결과]")

    lotte_model = LineupMarkovModel(team_b, max_runs=25)
    lotte_dist = lotte_model.game_run_distribution(innings=9)
    lotte_expected = lotte_model.expected_runs(lotte_dist)

    print(f"롯데 기대 득점: {lotte_expected:.4f}")

    print("\n" + "=" * 70)
    print("[SSG vs 롯데 경기 로그 시뮬레이션]")

    match = MatchSimulator(
        team_a_name="SSG 랜더스",
        team_a_lineup=team_a,
        team_b_name="롯데 자이언츠",
        team_b_lineup=team_b,
    )

    game_log = match.simulate_game(innings=9)
    print_game_log(game_log)
    
    print("\n" + "=" * 70)
    print("[Monte Carlo 결과 비교]")

    ssg_mc = LineupMonteCarloSimulator(team_a, seed=42)
    ssg_mc_result = ssg_mc.simulate_many(n_games=5000, innings=9)

    lotte_mc = LineupMonteCarloSimulator(team_b, seed=42)
    lotte_mc_result = lotte_mc.simulate_many(n_games=5000, innings=9)

    print("\nSSG 랜더스")
    print(f"평균 득점: {ssg_mc_result['mean_runs']:.4f}")
    print(f"분산: {ssg_mc_result['variance']:.4f}")
    print(f"0점 확률: {ssg_mc_result['prob_0_runs']:.4%}")
    print(f"5점 이상 확률: {ssg_mc_result['prob_5_or_more_runs']:.4%}")

    print("\n롯데 자이언츠")
    print(f"평균 득점: {lotte_mc_result['mean_runs']:.4f}")
    print(f"분산: {lotte_mc_result['variance']:.4f}")
    print(f"0점 확률: {lotte_mc_result['prob_0_runs']:.4%}")
    print(f"5점 이상 확률: {lotte_mc_result['prob_5_or_more_runs']:.4%}")

    print("\n[Markov vs Monte Carlo 평균 득점 비교]")
    print(f"SSG  - Markov 기대 득점: {ssg_expected:.4f} / Monte Carlo 평균 득점: {ssg_mc_result['mean_runs']:.4f}")
    print(f"롯데 - Markov 기대 득점: {lotte_expected:.4f} / Monte Carlo 평균 득점: {lotte_mc_result['mean_runs']:.4f}")


if __name__ == "__main__":
    main()
