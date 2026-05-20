from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional
import sys, os, psycopg2, psycopg2.extras, re, urllib.request, urllib.parse
import json as json_lib
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game_simulator.simulator_main import (
    BattingRecord, record_to_player_prob,
    MatchSimulator, LineupMonteCarloSimulator, LineupMarkovModel,
)

app = FastAPI(title="BallPark Intelligence API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB_CONFIG = {"host":"localhost","port":5432,"dbname":"ballpark","user":"ballpark","password":"ballpark1234"}
LATEST_SEASON = 2026

def get_conn(): return psycopg2.connect(**DB_CONFIG)

PLAYER_SELECT = """
    SELECT p.player_id, p.player_name, t.team_name, pst.season_year,
        pst.avg, pst.pa, pst.ab, pst.h, pst.double_hit, pst.triple_hit,
        pst.hr, pst.bb, pst.hbp, pst.so, pst.slg, pst.obp, pst.ops,
        pst.isop, pst.rbi,
        ROUND(CAST(pst.bb AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS bb_rate,
        ROUND(CAST(pst.so AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS k_rate,
        ROUND(CAST(pst.slg-pst.avg AS NUMERIC),3) AS iso,
        ROUND(CAST((pst.bb*0.69+pst.hbp*0.72
            +(pst.h-pst.double_hit-pst.triple_hit-pst.hr)*0.87
            +pst.double_hit*1.217+pst.triple_hit*1.529+pst.hr*1.74)
            /NULLIF(pst.pa,0) AS NUMERIC),3) AS woba,
        ROUND(
            CAST(
                ((((pst.bb*0.69+pst.hbp*0.72+(pst.h-pst.double_hit-pst.triple_hit-pst.hr)*0.87
                +pst.double_hit*1.217+pst.triple_hit*1.529+pst.hr*1.74)
                /NULLIF(pst.pa,0)) - 0.273) / 1.157 + 0.123) / 0.123 * 100
            AS NUMERIC), 0
        ) AS wrc_plus,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY pst.season_year ORDER BY
            (pst.bb*0.69+pst.hbp*0.72+(pst.h-pst.double_hit-pst.triple_hit-pst.hr)*0.87
            +pst.double_hit*1.217+pst.triple_hit*1.529+pst.hr*1.74)/NULLIF(pst.pa,0)
        )*100 AS NUMERIC),0) AS woba_percentile,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY pst.season_year ORDER BY pst.ops)*100 AS NUMERIC),0) AS ops_percentile,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY pst.season_year ORDER BY pst.hr)*100 AS NUMERIC),0) AS hr_percentile,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY pst.season_year ORDER BY CAST(pst.bb AS NUMERIC)/NULLIF(pst.pa,0))*100 AS NUMERIC),0) AS bb_percentile,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY pst.season_year ORDER BY CAST(pst.so AS NUMERIC)/NULLIF(pst.pa,0) DESC)*100 AS NUMERIC),0) AS k_percentile,
        NULL::numeric AS babip, NULL::numeric AS spd, NULL::numeric AS war,
        def.position
    FROM players p
    JOIN player_hitter_stats pst ON p.player_id=pst.player_id
    JOIN teams t ON pst.team_id=t.team_id
    LEFT JOIN player_defense_stats def ON p.player_id=def.player_id AND pst.season_year=def.season_year
"""

PITCHER_SELECT = """
    SELECT p.player_id, p.player_name, t.team_name, ps.season_year,
        NULL::numeric AS avg, NULL::integer AS pa, NULL::integer AS ab,
        NULL::integer AS h, NULL::integer AS double_hit, NULL::integer AS triple_hit,
        NULL::integer AS hr, NULL::integer AS bb, NULL::integer AS hbp,
        NULL::integer AS so, NULL::numeric AS slg, NULL::numeric AS obp,
        NULL::numeric AS ops, NULL::numeric AS isop, NULL::integer AS rbi,
        NULL::numeric AS bb_rate, NULL::numeric AS k_rate, NULL::numeric AS iso,
        NULL::numeric AS woba,
        0::numeric AS woba_percentile, 0::numeric AS ops_percentile,
        0::numeric AS hr_percentile, 0::numeric AS bb_percentile, 0::numeric AS k_percentile,
        NULL::numeric AS babip, NULL::numeric AS spd, NULL::numeric AS war,
        '투수' AS position,
        ps.era, ps.w, ps.l, ps.sv, ps.hld, ps.ip,
        ps.so AS pitcher_so, ps.bb AS pitcher_bb, ps.whip, ps.g,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY ps.season_year ORDER BY ps.era DESC)*100 AS NUMERIC),0) AS era_percentile,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY ps.season_year ORDER BY ps.whip DESC)*100 AS NUMERIC),0) AS whip_percentile,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY ps.season_year ORDER BY ps.so)*100 AS NUMERIC),0) AS so_percentile,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY ps.season_year ORDER BY ps.sv)*100 AS NUMERIC),0) AS sv_percentile,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY ps.season_year ORDER BY ps.w)*100 AS NUMERIC),0) AS w_percentile
    FROM players p
    JOIN player_pitcher_stats ps ON p.player_id=ps.player_id
    JOIN teams t ON ps.team_id=t.team_id
"""

class PlayerRecord(BaseModel):
    name: str; ab: int; hits: int; double: int; triple: int
    hr: int; bb: int; hbp: int = 0

class SimulateRequest(BaseModel):
    team_a_name: str; team_a_lineup: List[PlayerRecord]
    team_b_name: str; team_b_lineup: List[PlayerRecord]; innings: int = 9

class MultiSimulateRequest(BaseModel):
    team_a_name: str; team_a_lineup: List[PlayerRecord]
    team_b_name: str; team_b_lineup: List[PlayerRecord]
    n_games: int = 1000; innings: int = 9

class GameRecordCreate(BaseModel):
    team_name: str; opponent_name: str; result: str; my_score: int; opp_score: int

@app.get("/")
def root(): return {"message": "BallPark Intelligence API is running"}

@app.get("/health")
def health(): return {"status": "ok"}

# ── 선수 목록 조회 ────────────────────────────────
@app.get("/api/players")
def get_players(search: Optional[str] = None):
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        hq = PLAYER_SELECT + " WHERE pst.season_year=%s AND pst.pa > 0"
        hp: list = [LATEST_SEASON]
        if search:
            hq += " AND (p.player_name ILIKE %s OR t.team_name ILIKE %s)"
            hp += [f"%{search}%", f"%{search}%"]
        hq += " ORDER BY woba DESC NULLS LAST LIMIT 50"

        pq = """
            SELECT DISTINCT ON (sub.player_id) * FROM (
        """ + PITCHER_SELECT + """
            WHERE ps.season_year=%s
        """
        pp: list = [LATEST_SEASON]
        if search:
            pq += " AND (p.player_name ILIKE %s OR t.team_name ILIKE %s)"
            pp += [f"%{search}%", f"%{search}%"]
        pq += ") sub ORDER BY sub.player_id, sub.era ASC NULLS LAST LIMIT 50"
        cur.execute(hq, hp)
        hitters = cur.fetchall()
        cur.execute(pq, pp)
        pitchers = cur.fetchall()
        cur.close(); conn.close()

        hitter_ids = {r['player_id'] for r in hitters}
        pitchers_filtered = [r for r in pitchers if r['player_id'] not in hitter_ids]
        return {"players": [dict(r) for r in hitters] + pitchers_filtered}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 선수 상세 조회 ────────────────────────────────
@app.get("/api/players/{player_id}")
def get_player(player_id: int, season: Optional[int] = None):
    target_season = season or LATEST_SEASON
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 보유 시즌 목록 조회
        cur.execute("""
            SELECT array_agg(DISTINCT season_year ORDER BY season_year DESC) AS seasons
            FROM (
                SELECT season_year FROM player_hitter_stats WHERE player_id = %s::varchar AND pa > 0
                UNION
                SELECT season_year FROM player_pitcher_stats WHERE player_id = %s::varchar
            ) s
        """, (player_id, player_id))
        seasons_row = cur.fetchone()
        available_seasons = list(seasons_row['seasons'] or [])

        # 타자 조회
        cur.execute(
            "SELECT * FROM (" + PLAYER_SELECT + " WHERE pst.season_year=%s AND pst.pa > 0) sub WHERE sub.player_id=%s::varchar",
            (target_season, player_id)
        )
        row = cur.fetchone()

        if not row:
            cur.execute(
                "SELECT * FROM (" + PITCHER_SELECT + " WHERE ps.season_year=%s) sub WHERE sub.player_id=%s::varchar",
                (target_season, player_id)
            )
            row = cur.fetchone()

        cur.close(); conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="선수를 찾을 수 없습니다.")

        result = dict(row)
        result['available_seasons'] = available_seasons
        result['current_season'] = target_season
        return result

    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# ── 팀 목록 ──────────────────────────────────────
@app.get("/api/teams")
def get_teams():
    try:
        conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM teams ORDER BY team_name")
        rows = cur.fetchall(); cur.close(); conn.close()
        return {"teams": [dict(r) for r in rows]}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# ── 팀별 라인업 ──────────────────────────────────
@app.get("/api/teams/{team_name}/lineup")
def get_team_lineup(team_name: str):
    try:
        conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT p.player_name, pst.ab, pst.h AS hits, pst.double_hit AS double,
                pst.triple_hit AS triple, pst.hr, pst.bb, pst.hbp
            FROM players p
            JOIN player_hitter_stats pst ON p.player_id=pst.player_id
            JOIN teams t ON pst.team_id=t.team_id
            WHERE t.team_name=%s AND pst.season_year=%s AND pst.pa>=50
            ORDER BY pst.pa DESC LIMIT 9
        """, (team_name, LATEST_SEASON))
        rows = cur.fetchall(); cur.close(); conn.close()
        if not rows: raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다.")
        return {"lineup": [dict(r) for r in rows]}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# ── 단일 경기 시뮬레이션 ─────────────────────────
@app.post("/api/simulate/game")
def simulate_game(req: SimulateRequest):
    team_a = [record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_a_lineup]
    team_b = [record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_b_lineup]
    match  = MatchSimulator(team_a_name=req.team_a_name, team_a_lineup=team_a,
                            team_b_name=req.team_b_name, team_b_lineup=team_b)
    game_log = match.simulate_game(innings=12)
    return {"team_a_name": req.team_a_name, "team_b_name": req.team_b_name,
            "game_log": game_log, "is_draw": game_log.final_score[0] == game_log.final_score[1]}

# ── 다중 경기 시뮬레이션 ──────────────────────────
@app.post("/api/simulate/multi")
def simulate_multi(req: MultiSimulateRequest):
    team_a = [record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_a_lineup]
    team_b = [record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_b_lineup]
    mc_a = LineupMonteCarloSimulator(team_a, seed=42)
    mc_b = LineupMonteCarloSimulator(team_b, seed=42)
    ra = mc_a.simulate_many(n_games=req.n_games, innings=req.innings)
    rb = mc_b.simulate_many(n_games=req.n_games, innings=req.innings)
    ma = LineupMarkovModel(team_a, max_runs=25)
    mb = LineupMarkovModel(team_b, max_runs=25)
    da = ma.game_run_distribution(innings=req.innings)
    db = mb.game_run_distribution(innings=req.innings)
    def team_stat(name, mc, markov, dist):
        return {"name": name, "markov_expected": markov.expected_runs(dist),
                "mean_runs": mc["mean_runs"], "variance": mc["variance"],
                "prob_0_runs": mc["prob_0_runs"], "prob_5_or_more": mc["prob_5_or_more_runs"]}
    return {"team_a": team_stat(req.team_a_name, ra, ma, da),
            "team_b": team_stat(req.team_b_name, rb, mb, db), "n_games": req.n_games}

# ── 전적 저장/조회/삭제 ──────────────────────────
@app.post("/api/records")
def save_record(req: GameRecordCreate):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO game_records(team_name,opponent_name,result,my_score,opp_score) VALUES(%s,%s,%s,%s,%s) RETURNING id",
            (req.team_name, req.opponent_name, req.result, req.my_score, req.opp_score))
        rid = cur.fetchone()[0]; conn.commit(); cur.close(); conn.close()
        return {"id": rid, "message": "전적이 저장되었습니다."}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/records")
def get_records(team_name: Optional[str] = None):
    try:
        conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if team_name:
            cur.execute("SELECT * FROM game_records WHERE team_name=%s ORDER BY played_at DESC LIMIT 20", (team_name,))
        else:
            cur.execute("SELECT * FROM game_records ORDER BY played_at DESC LIMIT 20")
        rows = cur.fetchall(); cur.close(); conn.close()
        return {"records": [dict(r) for r in rows]}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/records/{record_id}")
def delete_record(record_id: int):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM game_records WHERE id=%s", (record_id,))
        conn.commit(); cur.close(); conn.close()
        return {"message": "삭제되었습니다."}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# ── 팀 순위 ──────────────────────────────────────
@app.get("/api/stats/team-rank")
def get_team_rank():
    try:
        # KBO 실시간 API 호출
        data = urllib.parse.urlencode({
            "leId": "1", "srId": "0", "seasonId": "2026",
        }).encode()
        req = urllib.request.Request(
            "https://www.koreabaseball.com/ws/Main.asmx/GetTeamRank",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.koreabaseball.com/",
            }
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            raw = json_lib.loads(res.read().decode("utf-8"))

        teams = []
        for row_obj in raw.get("rows", []):
            cells = row_obj.get("row", [])
            if len(cells) < 8: continue

            def cell_text(i):
                text = cells[i].get("Text", "") if i < len(cells) else ""
                return re.sub(r"<[^>]+>", "", text).strip()

            rank      = cell_text(0)
            team_name = cell_text(1)
            games     = cell_text(2)
            wins      = cell_text(3)
            losses    = cell_text(4)
            draws     = cell_text(5)
            win_rate  = cell_text(6)
            game_gap  = cell_text(7)
            last10    = cell_text(8)  if len(cells) > 8  else "-"
            streak    = cell_text(9)  if len(cells) > 9  else "-"

            if not rank or not team_name: continue

            teams.append({
                "rank":      int(rank) if rank.isdigit() else 0,
                "team_name": team_name,
                "games":     int(games)    if games.isdigit()  else 0,
                "wins":      int(wins)     if wins.isdigit()   else 0,
                "losses":    int(losses)   if losses.isdigit() else 0,
                "draws":     int(draws)    if draws.isdigit()  else 0,
                "win_rate":  float(win_rate) if win_rate else 0.0,
                "game_gap":  game_gap,
                "last10":    last10,
                "streak":    streak,
            })

        if teams:
            return {"teams": teams, "source": "realtime"}

        # KBO API 실패 시 DB fallback
        raise Exception("KBO API 응답 없음")

    except Exception:
        # DB에서 가져오기
        try:
            conn = get_conn()
            cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT t.team_name, r.games, r.wins, r.losses, r.draws,
                    r.win_rate, r.last10, r.streak,
                    ROW_NUMBER() OVER(ORDER BY r.win_rate DESC) AS rank
                FROM team_rank_stats r
                JOIN teams t ON r.team_id=t.team_id
                WHERE r.season_year=%s ORDER BY r.win_rate DESC
            """, (LATEST_SEASON,))
            rows = cur.fetchall()
            cur.close(); conn.close()
            return {"teams": [dict(r) for r in rows], "source": "db"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# ── 타자 기록 ────────────────────────────────────
@app.get("/api/stats/hitters")
def get_hitter_stats(sort: Optional[str] = "woba", limit: int = 50):
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 규정타석 동적 계산 (팀 경기수 × 3.1)
        cur.execute("SELECT MAX(games) FROM team_rank_stats WHERE season_year = %s", (LATEST_SEASON,))
        max_games = cur.fetchone()['max'] or 1
        min_pa = int(max_games * 3.1)

        sc = {"woba":"woba","ops":"pst.ops","hr":"pst.hr","avg":"pst.avg","rbi":"pst.rbi"}.get(sort,"woba")
        cur.execute(f"""
            SELECT p.player_id, p.player_name, t.team_name,
                pst.avg, pst.pa, pst.hr, pst.rbi, pst.obp, pst.slg, pst.ops,
                ROUND(CAST(pst.bb AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS bb_rate,
                ROUND(CAST(pst.so AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS k_rate,
                ROUND(CAST((pst.bb*0.69+pst.hbp*0.72+(pst.h-pst.double_hit-pst.triple_hit-pst.hr)*0.87
                    +pst.double_hit*1.217+pst.triple_hit*1.529+pst.hr*1.74)/NULLIF(pst.pa,0) AS NUMERIC),3) AS woba,
                def.position
            FROM players p
            JOIN player_hitter_stats pst ON p.player_id=pst.player_id
            JOIN teams t ON pst.team_id=t.team_id
            LEFT JOIN player_defense_stats def ON p.player_id=def.player_id AND pst.season_year=def.season_year
            WHERE pst.season_year=%s AND pst.pa >= %s
            ORDER BY {sc} DESC NULLS LAST
            LIMIT %s
        """, (LATEST_SEASON, min_pa, limit))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"hitters": [dict(r) for r in rows], "min_pa": min_pa}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 투수 기록 ────────────────────────────────────
@app.get("/api/stats/pitchers")
def get_pitcher_stats(sort: Optional[str] = "era", limit: int = 50):
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 규정이닝 동적 계산 (팀 경기수 × 1.0)
        cur.execute("SELECT MAX(games) FROM team_rank_stats WHERE season_year = %s", (LATEST_SEASON,))
        max_games = cur.fetchone()['max'] or 1
        min_innings = max_games  # 규정이닝 = 팀 경기수

        sc = {"era":"era_num","w":"ps.w","sv":"ps.sv","so":"ps.so","whip":"ps.whip"}.get(sort,"era_num")
        order = "ASC" if sort in ("era","whip") else "DESC"

        cur.execute(f"""
            SELECT p.player_id, p.player_name, t.team_name,
                ps.era, ps.g, ps.w, ps.l, ps.sv, ps.hld,
                ps.ip, ps.so, ps.bb, ps.hr, ps.whip, ps.wpct,
                CAST(SPLIT_PART(ps.ip::text, ' ', 1) AS NUMERIC) +
                CASE WHEN ps.ip::text LIKE '%1/3%' THEN 0.33
                     WHEN ps.ip::text LIKE '%2/3%' THEN 0.67
                     ELSE 0 END AS era_num
            FROM player_pitcher_stats ps
            JOIN players p ON ps.player_id=p.player_id
            JOIN teams t ON ps.team_id=t.team_id
            WHERE ps.season_year=%s
              AND ps.ip IS NOT NULL
              AND (CAST(SPLIT_PART(ps.ip::text, ' ', 1) AS NUMERIC) +
                   CASE WHEN ps.ip::text LIKE '%1/3%' THEN 0.33
                        WHEN ps.ip::text LIKE '%2/3%' THEN 0.67
                        ELSE 0 END) >= %s
            ORDER BY {sc} {order} NULLS LAST
            LIMIT %s
        """, (LATEST_SEASON, min_innings, limit))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"pitchers": [dict(r) for r in rows], "min_innings": min_innings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 타순 최적화 ───────────────────────────────────
@app.post("/api/lineup/optimize")
def optimize_lineup(req: SimulateRequest):
    try:
        lineup = [record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_a_lineup]
        def obp(p): return p.bb+p.single+p.double+p.triple+p.hr
        def ops(p): return obp(p)+p.single+2*p.double+3*p.triple+4*p.hr
        so = sorted(lineup, key=obp, reverse=True)
        ss = sorted(lineup, key=ops, reverse=True)
        sh = sorted(lineup, key=lambda p: p.hr, reverse=True)
        used, result = set(), []
        def pick(c):
            for p in c:
                if p.name not in used: used.add(p.name); result.append(p); return
        pick(so); pick(ss); pick(ss); pick(sh); pick(sh)
        for p in ss:
            if p.name not in used: result.append(p); used.add(p.name)
        return {"optimized_order": [p.name for p in result]}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# ── KBO 경기 일정 ────────────────────────────────
@app.get("/api/schedule")
def get_schedule(month: Optional[str] = None):
    try:
        now = datetime.now()
        target_month = month or f"{now.month:02d}"
        data = urllib.parse.urlencode({
            "leId":"1","srId":"0","srIdList":"0,9","seasonId":"2026",
            "gameWeek":"","teamId":"","stadiumId":"","gameId":"","gameDay":"",
            "gameMonth": target_month,
        }).encode()
        req = urllib.request.Request(
            "https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList", data=data,
            headers={"Content-Type":"application/x-www-form-urlencoded",
                     "User-Agent":"Mozilla/5.0",
                     "Referer":"https://www.koreabaseball.com/Schedule/Schedule.aspx"})
        with urllib.request.urlopen(req, timeout=10) as res:
            raw = json_lib.loads(res.read().decode("utf-8"))

        STADIUMS = ["잠실","문학","사직","수원","고척","대구","광주","창원","대전","포항","울산","인천"]
        games, current_date = [], ""

        for row_obj in raw.get("rows", []):
            cells = row_obj.get("row", [])
            if not cells: continue
            for cell in cells:
                if cell.get("Class") == "day":
                    current_date = re.sub(r"<[^>]+>", "", cell.get("Text","")).strip(); break
            time_text = play_text = stadium_text = status_text = ""
            for cell in cells:
                cls, text = cell.get("Class"), cell.get("Text","")
                if cls == "time": time_text = re.sub(r"<[^>]+>","",text).strip()
                elif cls == "play": play_text = text
                elif cls is None and any(s in text for s in STADIUMS): stadium_text = text
                elif "우천" in text or "취소" in text: status_text = text
            if not play_text or not current_date: continue
            teams   = re.findall(r"<span(?:[^>]*)>([^<]+)</span>", play_text)
            scores  = re.findall(r'<span class="(?:win|lose|same)">([^<]+)</span>', play_text)
            win_cls = re.findall(r'<span class="(win|lose|same)">', play_text)
            if len(teams) < 2: continue
            team_a, team_b = teams[0], teams[-1]
            score_a = scores[0] if len(scores)>=1 else None
            score_b = scores[1] if len(scores)>=2 else None
            result = (f"{team_a} 승" if win_cls[0]=="win" else f"{team_b} 승" if win_cls[0]=="lose" else "무승부") if (win_cls and score_a and score_b) else None
            games.append({"date":current_date,"time":time_text,"team_a":team_a,"team_b":team_b,
                          "score_a":score_a,"score_b":score_b,"result":result,
                          "stadium":stadium_text,"status":status_text or None})
        return {"month": target_month, "games": games}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# ── 선수 이미지 프록시 ────────────────────────────
@app.get("/api/player-image/{player_id}")
def get_player_image(player_id: int):
    try:
        url = f"https://www.koreabaseball.com/file/Image/Player/2026/M/{player_id}.jpg"
        req = urllib.request.Request(url, headers={
            "User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer":"https://www.koreabaseball.com/Player/Search.aspx",
            "Accept":"image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language":"ko-KR,ko;q=0.9"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = res.read()
            if "html" in res.headers.get("Content-Type","").lower():
                raise HTTPException(status_code=404, detail="이미지 없음")
            return Response(content=data, media_type="image/jpeg")
    except HTTPException: raise
    except Exception: raise HTTPException(status_code=404, detail="이미지 없음")

    # ── 선수 연도별 스탯 조회 ─────────────────────────
@app.get("/api/players/{player_id}/seasons")
def get_player_seasons(player_id: int):
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 타자 연도별
        cur.execute("""
            SELECT season_year,
                pst.avg, pst.pa, pst.hr, pst.rbi, pst.obp, pst.slg, pst.ops,
                ROUND(CAST(pst.bb AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS bb_rate,
                ROUND(CAST(pst.so AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS k_rate,
                ROUND(CAST((pst.bb*0.69+pst.hbp*0.72+(pst.h-pst.double_hit-pst.triple_hit-pst.hr)*0.87
                    +pst.double_hit*1.217+pst.triple_hit*1.529+pst.hr*1.74)/NULLIF(pst.pa,0) AS NUMERIC),3) AS woba
            FROM player_hitter_stats pst
            WHERE pst.player_id = %s::varchar AND pst.pa > 0
            ORDER BY season_year
        """, (player_id,))
        hitter_rows = cur.fetchall()

        # 투수 연도별
        cur.execute("""
            SELECT season_year, ps.era, ps.w, ps.l, ps.sv, ps.ip,
                ps.so AS pitcher_so, ps.bb AS pitcher_bb, ps.whip, ps.g
            FROM player_pitcher_stats ps
            WHERE ps.player_id = %s::varchar
            ORDER BY season_year
        """, (player_id,))
        pitcher_rows = cur.fetchall()

        cur.close(); conn.close()

        if hitter_rows:
            return {"type": "hitter", "seasons": [dict(r) for r in hitter_rows]}
        elif pitcher_rows:
            return {"type": "pitcher", "seasons": [dict(r) for r in pitcher_rows]}
        else:
            raise HTTPException(status_code=404, detail="데이터 없음")

    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

    # ── 머니볼 엔진 ───────────────────────────────────
@app.get("/api/players/{player_id}/moneyball")
def get_moneyball(player_id: int):
    try:
        from app.ml.moneyball import get_player_moneyball
        result = get_player_moneyball(player_id)
        if not result:
            raise HTTPException(status_code=404, detail="타자 데이터 없음")
        # Decimal → float 변환
        for k, v in result['features'].items():
            result['features'][k] = float(v) if v is not None else None
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))
    
    # ── 머니볼 리그 전체 분포 ─────────────────────────
@app.get("/api/moneyball/distribution")
def get_moneyball_distribution():
    try:
        from app.ml.moneyball import get_hitter_features, train_kmeans
        all_data = get_hitter_features(LATEST_SEASON)
        if not all_data:
            raise HTTPException(status_code=404, detail="데이터 없음")

        _, _, labels, type_map, _ = train_kmeans(all_data)

        # 유형별 선수 수 집계
        distribution: dict = {}
        for i, label in enumerate(labels):
            type_name = type_map.get(int(label), "기타")
            if type_name not in distribution:
                distribution[type_name] = 0
            distribution[type_name] += 1

        total = len(labels)
        result = [
            {
                "type": k,
                "count": v,
                "pct": round(v / total * 100, 1)
            }
            for k, v in distribution.items()
        ]
        result.sort(key=lambda x: x["count"], reverse=True)
        return {"distribution": result, "total": total}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))