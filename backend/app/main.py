from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sys
import os
import psycopg2
import psycopg2.extras
import math
from itertools import permutations
import re
import urllib.request
import urllib.parse
import json as json_lib
from datetime import datetime
from fastapi.responses import Response

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game_simulator.simulator_main import (
    BattingRecord,
    record_to_player_prob,
    MatchSimulator,
    LineupMonteCarloSimulator,
    LineupMarkovModel,
)

app = FastAPI(title="BallPark Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "ballpark",
    "user": "ballpark",
    "password": "ballpark1234",
}

LATEST_SEASON = 2026

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

PLAYER_SELECT = """
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
        ROUND(CAST(pst.bb AS NUMERIC) / NULLIF(pst.pa, 0) * 100, 1) AS bb_rate,
        ROUND(CAST(pst.so AS NUMERIC) / NULLIF(pst.pa, 0) * 100, 1) AS k_rate,
        ROUND(CAST(pst.slg - pst.avg AS NUMERIC), 3) AS iso,
        ROUND(
            CAST(
                (pst.bb * 0.69 + pst.hbp * 0.72
                + (pst.h - pst.double_hit - pst.triple_hit - pst.hr) * 0.87
                + pst.double_hit * 1.217 + pst.triple_hit * 1.529 + pst.hr * 1.74)
                / NULLIF(pst.pa, 0)
            AS NUMERIC), 3
        ) AS woba,
        ROUND(CAST(PERCENT_RANK() OVER (
            PARTITION BY pst.season_year
            ORDER BY (
                pst.bb * 0.69 + pst.hbp * 0.72
                + (pst.h - pst.double_hit - pst.triple_hit - pst.hr) * 0.87
                + pst.double_hit * 1.217 + pst.triple_hit * 1.529 + pst.hr * 1.74
            ) / NULLIF(pst.pa, 0)
        ) * 100 AS NUMERIC), 0) AS woba_percentile,
        ROUND(CAST(PERCENT_RANK() OVER (
            PARTITION BY pst.season_year ORDER BY pst.ops
        ) * 100 AS NUMERIC), 0) AS ops_percentile,
        ROUND(CAST(PERCENT_RANK() OVER (
            PARTITION BY pst.season_year ORDER BY pst.hr
        ) * 100 AS NUMERIC), 0) AS hr_percentile,
        ROUND(CAST(PERCENT_RANK() OVER (
            PARTITION BY pst.season_year
            ORDER BY CAST(pst.bb AS NUMERIC) / NULLIF(pst.pa, 0)
        ) * 100 AS NUMERIC), 0) AS bb_percentile,
        ROUND(CAST(PERCENT_RANK() OVER (
            PARTITION BY pst.season_year
            ORDER BY CAST(pst.so AS NUMERIC) / NULLIF(pst.pa, 0) DESC
        ) * 100 AS NUMERIC), 0) AS k_percentile,
        NULL::numeric AS babip,
        NULL::numeric AS spd,
        NULL::numeric AS war,
        def.position
    FROM players p
    JOIN player_hitter_stats pst ON p.player_id = pst.player_id
    JOIN teams t ON pst.team_id = t.team_id
    LEFT JOIN player_defense_stats def
        ON p.player_id = def.player_id
        AND pst.season_year = def.season_year
"""

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

class GameRecordCreate(BaseModel):
    team_name: str
    opponent_name: str
    result: str
    my_score: int
    opp_score: int

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

        query = PLAYER_SELECT + " WHERE pst.season_year = %s"
        params: list = [LATEST_SEASON]

        if search:
            query += " AND (p.player_name ILIKE %s OR t.team_name ILIKE %s)"
            params += [f"%{search}%", f"%{search}%"]

        query += " ORDER BY woba DESC NULLS LAST LIMIT 100"

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

        cur.execute(
            "SELECT * FROM (" + PLAYER_SELECT + " WHERE pst.season_year = %s) sub WHERE sub.player_id = %s::varchar",
            (LATEST_SEASON, player_id)
        )

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

# ── 팀별 라인업 조회 ──────────────────────────────
@app.get("/api/teams/{team_name}/lineup")
def get_team_lineup(team_name: str):
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                p.player_name,
                pst.ab,
                pst.h      AS hits,
                pst.double_hit AS double,
                pst.triple_hit AS triple,
                pst.hr,
                pst.bb,
                pst.hbp
            FROM players p
            JOIN player_hitter_stats pst ON p.player_id = pst.player_id
            JOIN teams t ON pst.team_id = t.team_id
            WHERE t.team_name = %s
              AND pst.season_year = %s
              AND pst.pa >= 50
            ORDER BY pst.pa DESC
            LIMIT 9
        """, (team_name, LATEST_SEASON))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if not rows:
            raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다.")
        return {"lineup": [dict(r) for r in rows]}
    except HTTPException:
        raise
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

    game_log = match.simulate_game(innings=12)
    score_a  = game_log.final_score[0]
    score_b  = game_log.final_score[1]

    return {
        "team_a_name": req.team_a_name,
        "team_b_name": req.team_b_name,
        "game_log":    game_log,
        "is_draw":     score_a == score_b,
    }

# ── 다중 경기 시뮬레이션 ──────────────────────────
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
    dist_a   = markov_a.game_run_distribution(innings=req.innings)
    dist_b   = markov_b.game_run_distribution(innings=req.innings)

    return {
        "team_a": {
            "name":            req.team_a_name,
            "markov_expected": markov_a.expected_runs(dist_a),
            "mean_runs":       result_a["mean_runs"],
            "variance":        result_a["variance"],
            "prob_0_runs":     result_a["prob_0_runs"],
            "prob_5_or_more":  result_a["prob_5_or_more_runs"],
        },
        "team_b": {
            "name":            req.team_b_name,
            "markov_expected": markov_b.expected_runs(dist_b),
            "mean_runs":       result_b["mean_runs"],
            "variance":        result_b["variance"],
            "prob_0_runs":     result_b["prob_0_runs"],
            "prob_5_or_more":  result_b["prob_5_or_more_runs"],
        },
        "n_games": req.n_games,
    }

# ── 전적 저장 ─────────────────────────────────────
@app.post("/api/records")
def save_record(req: GameRecordCreate):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO game_records (team_name, opponent_name, result, my_score, opp_score)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (req.team_name, req.opponent_name, req.result, req.my_score, req.opp_score))
        record_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"id": record_id, "message": "전적이 저장되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 전적 조회 ─────────────────────────────────────
@app.get("/api/records")
def get_records(team_name: Optional[str] = None):
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if team_name:
            cur.execute("""
                SELECT * FROM game_records
                WHERE team_name = %s
                ORDER BY played_at DESC LIMIT 20
            """, (team_name,))
        else:
            cur.execute("SELECT * FROM game_records ORDER BY played_at DESC LIMIT 20")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {"records": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 전적 삭제 ─────────────────────────────────────
@app.delete("/api/records/{record_id}")
def delete_record(record_id: int):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("DELETE FROM game_records WHERE id = %s", (record_id,))
        conn.commit()
        cur.close()
        conn.close()
        return {"message": "삭제되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 팀 순위 조회 ──────────────────────────────────
@app.get("/api/stats/team-rank")
def get_team_rank():
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                t.team_name,
                r.games,
                r.wins,
                r.losses,
                r.draws,
                r.win_rate,
                r.last10,
                r.streak,
                ROW_NUMBER() OVER (ORDER BY r.win_rate DESC) AS rank
            FROM team_rank_stats r
            JOIN teams t ON r.team_id = t.team_id
            WHERE r.season_year = %s
            ORDER BY r.win_rate DESC
        """, (LATEST_SEASON,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {"teams": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 타자 기록 조회 ────────────────────────────────
@app.get("/api/stats/hitters")
def get_hitter_stats(sort: Optional[str] = "woba", limit: int = 50):
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        sort_col = {
            "woba": "woba",
            "ops":  "pst.ops",
            "hr":   "pst.hr",
            "avg":  "pst.avg",
            "rbi":  "pst.rbi",
        }.get(sort, "woba")

        cur.execute(f"""
            SELECT
                p.player_id,
                p.player_name,
                t.team_name,
                pst.avg,
                pst.pa,
                pst.hr,
                pst.rbi,
                pst.obp,
                pst.slg,
                pst.ops,
                ROUND(CAST(pst.bb AS NUMERIC) / NULLIF(pst.pa, 0) * 100, 1) AS bb_rate,
                ROUND(CAST(pst.so AS NUMERIC) / NULLIF(pst.pa, 0) * 100, 1) AS k_rate,
                ROUND(
                    CAST(
                        (pst.bb * 0.69 + pst.hbp * 0.72
                        + (pst.h - pst.double_hit - pst.triple_hit - pst.hr) * 0.87
                        + pst.double_hit * 1.217 + pst.triple_hit * 1.529 + pst.hr * 1.74)
                        / NULLIF(pst.pa, 0)
                    AS NUMERIC), 3
                ) AS woba,
                def.position
            FROM players p
            JOIN player_hitter_stats pst ON p.player_id = pst.player_id
            JOIN teams t ON pst.team_id = t.team_id
            LEFT JOIN player_defense_stats def
                ON p.player_id = def.player_id
                AND pst.season_year = def.season_year
            WHERE pst.season_year = %s
              AND pst.pa >= 50
            ORDER BY {sort_col} DESC NULLS LAST
            LIMIT %s
        """, (LATEST_SEASON, limit))

        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {"hitters": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 타순 최적화 ───────────────────────────────────
@app.post("/api/lineup/optimize")
def optimize_lineup(req: SimulateRequest):
    try:
        lineup = [record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_a_lineup]

        def obp(p):
            return p.bb + p.single + p.double + p.triple + p.hr

        def ops(p):
            return obp(p) + p.single + 2*p.double + 3*p.triple + 4*p.hr

        sorted_by_obp = sorted(lineup, key=obp, reverse=True)
        sorted_by_ops = sorted(lineup, key=ops, reverse=True)
        sorted_by_hr  = sorted(lineup, key=lambda p: p.hr, reverse=True)

        used   = set()
        result = []

        def pick(candidates):
            for p in candidates:
                if p.name not in used:
                    used.add(p.name)
                    result.append(p)
                    return

        pick(sorted_by_obp)
        pick(sorted_by_ops)
        pick(sorted_by_ops)
        pick(sorted_by_hr)
        pick(sorted_by_hr)
        for p in sorted_by_ops:
            if p.name not in used:
                result.append(p)
                used.add(p.name)

        return {"optimized_order": [p.name for p in result]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── KBO 경기 일정 조회 ────────────────────────────
@app.get("/api/schedule")
def get_schedule(month: Optional[str] = None):
    try:
        now = datetime.now()
        target_month = month or f"{now.month:02d}"

        data = urllib.parse.urlencode({
            "leId": "1",
            "srId": "0",
            "srIdList": "0,9",
            "seasonId": "2026",
            "gameWeek": "",
            "teamId": "",
            "stadiumId": "",
            "gameId": "",
            "gameDay": "",
            "gameMonth": target_month,
        }).encode()

        req = urllib.request.Request(
            "https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.koreabaseball.com/Schedule/Schedule.aspx",
            }
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            raw = json_lib.loads(res.read().decode("utf-8"))

        STADIUMS = ["잠실","문학","사직","수원","고척","대구","광주","창원","대전","포항","울산","인천"]
        games = []
        current_date = ""

        for row_obj in raw.get("rows", []):
            cells = row_obj.get("row", [])
            if not cells:
                continue

            for cell in cells:
                if cell.get("Class") == "day":
                    current_date = re.sub(r"<[^>]+>", "", cell.get("Text", "")).strip()
                    break

            time_text    = ""
            play_text    = ""
            stadium_text = ""
            status_text  = ""

            for cell in cells:
                cls  = cell.get("Class")
                text = cell.get("Text", "")
                if cls == "time":
                    time_text = re.sub(r"<[^>]+>", "", text).strip()
                elif cls == "play":
                    play_text = text
                elif cls is None and any(s in text for s in STADIUMS):
                    stadium_text = text
                elif "우천" in text or "취소" in text:
                    status_text = text

            if not play_text or not current_date:
                continue

            teams  = re.findall(r"<span(?:[^>]*)>([^<]+)</span>", play_text)
            scores = re.findall(r'<span class="(?:win|lose|same)">([^<]+)</span>', play_text)
            win_cls = re.findall(r'<span class="(win|lose|same)">', play_text)

            if len(teams) < 2:
                continue

            team_a = teams[0]
            team_b = teams[-1]
            score_a = scores[0] if len(scores) >= 1 else None
            score_b = scores[1] if len(scores) >= 2 else None

            if win_cls and score_a and score_b:
                if win_cls[0] == "win":
                    result = f"{team_a} 승"
                elif win_cls[0] == "lose":
                    result = f"{team_b} 승"
                else:
                    result = "무승부"
            else:
                result = None

            games.append({
                "date":    current_date,
                "time":    time_text,
                "team_a":  team_a,
                "team_b":  team_b,
                "score_a": score_a,
                "score_b": score_b,
                "result":  result,
                "stadium": stadium_text,
                "status":  status_text or None,
            })

        return {"month": target_month, "games": games}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

# ── 선수 이미지 프록시 ─────────────────────────
@app.get("/api/player-image/{player_id}")
def get_player_image(player_id: int):
    try:
        url = f"https://www.koreabaseball.com/file/Image/Player/2026/M/{player_id}.jpg"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.koreabaseball.com/Player/Search.aspx",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=5) as res:
            data = res.read()
            content_type = res.headers.get("Content-Type", "image/jpeg")
            if "html" in content_type.lower():
                raise HTTPException(status_code=404, detail="이미지 없음")
            return Response(content=data, media_type="image/jpeg")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="이미지 없음")