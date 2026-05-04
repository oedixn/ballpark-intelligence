from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game_simulator.simulator_main import (
    BattingRecord,
    record_to_player_prob,
    MatchSimulator,
    LineupMonteCarloSimulator,
    LineupMarkovModel,
)

app = FastAPI(title="BallPark Intelligence API")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 요청 스키마 ──────────────────────────────────
class PlayerRecord(BaseModel):
    name: str
    ab: int
    hits: int
    double: int
    triple: int
    hr: int
    bb: int
    hbp: int = 0

class SimulateRequest(BaseModel):
    team_a_name: str
    team_a_lineup: List[PlayerRecord]
    team_b_name: str
    team_b_lineup: List[PlayerRecord]
    innings: int = 9

class MultiSimulateRequest(BaseModel):
    team_a_name: str
    team_a_lineup: List[PlayerRecord]
    team_b_name: str
    team_b_lineup: List[PlayerRecord]
    n_games: int = 1000
    innings: int = 9

# ── 헬스체크 ─────────────────────────────────────
@app.get("/")
def root():
    return {"message": "BallPark Intelligence API is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

# ── 단일 경기 시뮬레이션 ─────────────────────────
@app.post("/api/simulate/game")
def simulate_game(req: SimulateRequest):
    team_a = [record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_a_lineup]
    team_b = [record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_b_lineup]

    match = MatchSimulator(
        team_a_name=req.team_a_name,
        team_a_lineup=team_a,
        team_b_name=req.team_b_name,
        team_b_lineup=team_b,
    )

    game_log = match.simulate_game(innings=req.innings)

    return {
        "team_a_name": req.team_a_name,
        "team_b_name": req.team_b_name,
        "game_log": game_log,
    }

# ── 다중 경기 시뮬레이션 (100경기 통계) ──────────
@app.post("/api/simulate/multi")
def simulate_multi(req: MultiSimulateRequest):
    team_a = [record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_a_lineup]
    team_b = [record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_b_lineup]

    mc_a = LineupMonteCarloSimulator(team_a, seed=42)
    mc_b = LineupMonteCarloSimulator(team_b, seed=42)

    result_a = mc_a.simulate_many(n_games=req.n_games, innings=req.innings)
    result_b = mc_b.simulate_many(n_games=req.n_games, innings=req.innings)

    markov_a = LineupMarkovModel(team_a, max_runs=25)
    markov_b = LineupMarkovModel(team_b, max_runs=25)
    dist_a = markov_a.game_run_distribution(innings=req.innings)
    dist_b = markov_b.game_run_distribution(innings=req.innings)

    return {
        "team_a": {
            "name": req.team_a_name,
            "markov_expected": markov_a.expected_runs(dist_a),
            "mean_runs": result_a["mean_runs"],
            "variance": result_a["variance"],
            "prob_0_runs": result_a["prob_0_runs"],
            "prob_5_or_more": result_a["prob_5_or_more_runs"],
        },
        "team_b": {
            "name": req.team_b_name,
            "markov_expected": markov_b.expected_runs(dist_b),
            "mean_runs": result_b["mean_runs"],
            "variance": result_b["variance"],
            "prob_0_runs": result_b["prob_0_runs"],
            "prob_5_or_more": result_b["prob_5_or_more_runs"],
        },
        "n_games": req.n_games,
    }