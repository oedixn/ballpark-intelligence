from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sys
import os
import psycopg2
import psycopg2.extras

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

# ── DB 연결 ───────────────────────────────────────
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "ballpark",
    "user": "ballpark",
    "password": "ballpark1234",
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

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

# ── 선수 목록 조회 ────────────────────────────────
@app.get("/api/players")
def get_players(search: Optional[str] = None):
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = """
            SELECT
                p.player_id,
                p.player_name,
                t.team_name,
                pst.season_year,
                pst.avg,
                pst.pa,
                pst.ab,
                pst.h,
                pst.double_hit,
                pst.triple_hit,
                pst.hr,
                pst.bb,
                pst.hbp,
                pst.so,
                pst.slg,
                pst.obp,
                pst.ops,
                pst.isop,
                pst.rbi,
                adv.babip,
                adv.bb_rate,
                adv.k_rate,
                adv.iso,
                adv.spd,
                adv.war,
                adv.woba,
                def.position
            FROM players p
            JOIN player_hitter_stats pst ON p.player_id = pst.player_id
            JOIN teams t ON pst.team_id = t.team_id
            LEFT JOIN kbreport_player_hitter_advanced adv
                ON p.player_name = adv.player_name
                AND pst.season_year = adv.season_year
            LEFT JOIN player_defense_stats def
                ON p.player_id = def.player_id
                AND pst.season_year = def.season_year
            WHERE pst.season_year = 2021
        """

        params = []
        if search:
            query += " AND (p.player_name ILIKE %s OR t.team_name ILIKE %s)"
            params = [f"%{search}%", f"%{search}%"]

        query += " ORDER BY adv.war DESC NULLS LAST LIMIT 100"

        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return {"players": [dict(r) for r in rows]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 선수 상세 조회 ────────────────────────────────
@app.get("/api/players/{player_id}")
def get_player(player_id: int):
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT
                p.player_id,
                p.player_name,
                t.team_name,
                pst.season_year,
                pst.avg,
                pst.pa,
                pst.ab,
                pst.h,
                pst.double_hit,
                pst.triple_hit,
                pst.hr,
                pst.bb,
                pst.hbp,
                pst.so,
                pst.slg,
                pst.obp,
                pst.ops,
                pst.isop,
                pst.rbi,
                adv.babip,
                adv.bb_rate,
                adv.k_rate,
                adv.iso,
                adv.spd,
                adv.war,
                adv.woba,
                def.position
            FROM players p
            JOIN player_hitter_stats pst ON p.player_id = pst.player_id
            JOIN teams t ON pst.team_id = t.team_id
            LEFT JOIN kbreport_player_hitter_advanced adv
                ON p.player_name = adv.player_name
                AND pst.season_year = adv.season_year
            LEFT JOIN player_defense_stats def
                ON p.player_id = def.player_id
                AND pst.season_year = def.season_year
            WHERE p.player_id = %s AND pst.season_year = 2021
        """, (player_id,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="선수를 찾을 수 없습니다.")

        return dict(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 팀 목록 조회 ──────────────────────────────────
@app.get("/api/teams")
def get_teams():
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM teams ORDER BY team_name")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {"teams": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

# ── 다중 경기 시뮬레이션 (통계) ──────────────────
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