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

WOBA_EXPR = "(pst.bb*0.69+pst.hbp*0.72+(pst.h-pst.double_hit-pst.triple_hit-pst.hr)*0.87+pst.double_hit*1.217+pst.triple_hit*1.529+pst.hr*1.74)/NULLIF(pst.pa,0)"

PLAYER_SELECT = f"""
    SELECT p.player_id, p.player_name, t.team_name, pst.season_year,
        pst.avg, pst.pa, pst.ab, pst.h, pst.double_hit, pst.triple_hit,
        pst.hr, pst.bb, pst.hbp, pst.so, pst.slg, pst.obp, pst.ops, pst.isop, pst.rbi,
        ROUND(CAST(pst.bb AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS bb_rate,
        ROUND(CAST(pst.so AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS k_rate,
        ROUND(CAST(pst.slg-pst.avg AS NUMERIC),3) AS iso,
        ROUND(CAST({WOBA_EXPR} AS NUMERIC),3) AS woba,
        ROUND(CAST(
            ((((pst.bb*0.69+pst.hbp*0.72+(pst.h-pst.double_hit-pst.triple_hit-pst.hr)*0.87
            +pst.double_hit*1.217+pst.triple_hit*1.529+pst.hr*1.74)/NULLIF(pst.pa,0))-0.273)
            /1.157+0.123)/0.123*100
        AS NUMERIC),0) AS wrc_plus,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY pst.season_year ORDER BY {WOBA_EXPR})*100 AS NUMERIC),0) AS woba_percentile,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY pst.season_year ORDER BY pst.ops)*100 AS NUMERIC),0) AS ops_percentile,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY pst.season_year ORDER BY pst.hr)*100 AS NUMERIC),0) AS hr_percentile,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY pst.season_year ORDER BY CAST(pst.bb AS NUMERIC)/NULLIF(pst.pa,0))*100 AS NUMERIC),0) AS bb_percentile,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY pst.season_year ORDER BY CAST(pst.so AS NUMERIC)/NULLIF(pst.pa,0) DESC)*100 AS NUMERIC),0) AS k_percentile,
        NULL::numeric AS babip, NULL::numeric AS spd, NULL::numeric AS war, def.position
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
        NULL::numeric AS woba, NULL::numeric AS wrc_plus,
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
    name:str; ab:int; hits:int; double:int; triple:int; hr:int; bb:int; hbp:int=0

class SimulateRequest(BaseModel):
    team_a_name:str; team_a_lineup:List[PlayerRecord]
    team_b_name:str; team_b_lineup:List[PlayerRecord]; innings:int=9

class MultiSimulateRequest(BaseModel):
    team_a_name:str; team_a_lineup:List[PlayerRecord]
    team_b_name:str; team_b_lineup:List[PlayerRecord]; n_games:int=1000; innings:int=9

class GameRecordCreate(BaseModel):
    team_name:str; opponent_name:str; result:str; my_score:int; opp_score:int

def search_cond(search, alias="p", team_alias="t"):
    if search: return f" AND ({alias}.player_name ILIKE %s OR {team_alias}.team_name ILIKE %s)"
    return ""

@app.get("/")
def root(): return {"message":"BallPark Intelligence API is running"}
@app.get("/health")
def health(): return {"status":"ok"}

# ── 선수 목록 조회 ────────────────────────────────
@app.get("/api/players")
def get_players(search: Optional[str] = None):
    try:
        conn=get_conn(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        like=[f"%{search}%",f"%{search}%"] if search else []

        # 2026 타자
        hq=PLAYER_SELECT+" WHERE pst.season_year=%s AND pst.pa>=5"+search_cond(search)+" ORDER BY woba DESC NULLS LAST LIMIT 50"
        cur.execute(hq,[LATEST_SEASON]+like); hitters=list(cur.fetchall())

        # 검색 시 과거 시즌 타자 fallback
        if search:
            hq2=PLAYER_SELECT+"""WHERE pst.season_year=(SELECT MAX(s.season_year) FROM player_hitter_stats s WHERE s.player_id=p.player_id AND s.pa>=5) AND pst.pa>=5"""+search_cond(search)+" ORDER BY woba DESC NULLS LAST LIMIT 50"
            cur.execute(hq2,like); hitters2=cur.fetchall()
            ids={r['player_id'] for r in hitters}
            hitters+=[r for r in hitters2 if r['player_id'] not in ids]

        # 투수 (최근 시즌, 3경기 이상)
        pq="SELECT DISTINCT ON(sub.player_id) * FROM("+PITCHER_SELECT+"WHERE ps.season_year=(SELECT MAX(ps2.season_year) FROM player_pitcher_stats ps2 WHERE ps2.player_id=p.player_id) AND ps.g>=3"+search_cond(search,"p","t")+") sub ORDER BY sub.player_id, sub.era ASC NULLS LAST LIMIT 50"
        cur.execute(pq,like); pitchers=cur.fetchall()
        cur.close(); conn.close()

        hitter_ids={r['player_id'] for r in hitters}
        return {"players":[dict(r) for r in hitters]+[r for r in pitchers if r['player_id'] not in hitter_ids]}
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

# ── 선수 상세 조회 ────────────────────────────────
@app.get("/api/players/{player_id}")
def get_player(player_id:int, season:Optional[int]=None):
    target=season or LATEST_SEASON
    try:
        conn=get_conn(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""SELECT array_agg(DISTINCT season_year ORDER BY season_year DESC) AS seasons FROM(
            SELECT season_year FROM player_hitter_stats WHERE player_id=%s::varchar AND pa>0
            UNION SELECT season_year FROM player_pitcher_stats WHERE player_id=%s::varchar) s""",(player_id,player_id))
        available_seasons=list((cur.fetchone()['seasons'] or []))

        # 타자 - 요청 시즌
        cur.execute("SELECT * FROM("+PLAYER_SELECT+"WHERE pst.season_year=%s AND pst.pa>0) sub WHERE sub.player_id=%s::varchar",(target,player_id))
        row=cur.fetchone()

        # 타자 - 최근 시즌 fallback(pa >= 5 이상인 경우만)
        if not row:
            cur.execute("SELECT MAX(season_year) FROM player_hitter_stats WHERE player_id=%s::varchar AND pa>=5",(player_id,))
            lh=cur.fetchone(); lh_season=lh['max'] if lh and lh['max'] else None
            if lh_season:
                cur.execute("SELECT * FROM("+PLAYER_SELECT+"WHERE pst.season_year=%s AND pst.pa>=5) sub WHERE sub.player_id=%s::varchar",(lh_season,player_id))
                row=cur.fetchone()

        # 투수 fallback
        if not row:
            cur.execute("SELECT MAX(season_year) FROM player_pitcher_stats WHERE player_id=%s::varchar AND g>=3",(player_id,))
            lp=cur.fetchone(); lp_season=lp['max'] if lp and lp['max'] else target
            cur.execute("SELECT * FROM("+PITCHER_SELECT+"WHERE ps.season_year=%s) sub WHERE sub.player_id=%s::varchar",(lp_season,player_id))
            row=cur.fetchone()

        cur.close(); conn.close()
        if not row: raise HTTPException(status_code=404,detail="선수를 찾을 수 없습니다.")
        result=dict(row); result['available_seasons']=available_seasons; result['current_season']=target
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

# ── 팀 목록 ──────────────────────────────────────
@app.get("/api/teams")
def get_teams():
    try:
        conn=get_conn(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM teams ORDER BY team_name")
        rows=cur.fetchall(); cur.close(); conn.close()
        return {"teams":[dict(r) for r in rows]}
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

# ── 팀별 라인업 ──────────────────────────────────
@app.get("/api/teams/{team_name}/lineup")
def get_team_lineup(team_name:str):
    try:
        conn=get_conn(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT p.player_name,pst.ab,pst.h AS hits,pst.double_hit AS double,
            pst.triple_hit AS triple,pst.hr,pst.bb,pst.hbp
            FROM players p JOIN player_hitter_stats pst ON p.player_id=pst.player_id
            JOIN teams t ON pst.team_id=t.team_id
            WHERE t.team_name=%s AND pst.season_year=%s AND pst.pa>=50
            ORDER BY pst.pa DESC LIMIT 9""",(team_name,LATEST_SEASON))
        rows=cur.fetchall(); cur.close(); conn.close()
        if not rows: raise HTTPException(status_code=404,detail="팀을 찾을 수 없습니다.")
        return {"lineup":[dict(r) for r in rows]}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

# ── 시뮬레이션 ───────────────────────────────────
@app.post("/api/simulate/game")
def simulate_game(req:SimulateRequest):
    ta=[record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_a_lineup]
    tb=[record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_b_lineup]
    g=MatchSimulator(team_a_name=req.team_a_name,team_a_lineup=ta,team_b_name=req.team_b_name,team_b_lineup=tb).simulate_game(innings=12)
    return {"team_a_name":req.team_a_name,"team_b_name":req.team_b_name,"game_log":g,"is_draw":g.final_score[0]==g.final_score[1]}

@app.post("/api/simulate/multi")
def simulate_multi(req:MultiSimulateRequest):
    ta=[record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_a_lineup]
    tb=[record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_b_lineup]
    ra=LineupMonteCarloSimulator(ta,seed=42).simulate_many(n_games=req.n_games,innings=req.innings)
    rb=LineupMonteCarloSimulator(tb,seed=42).simulate_many(n_games=req.n_games,innings=req.innings)
    ma=LineupMarkovModel(ta,max_runs=25); mb=LineupMarkovModel(tb,max_runs=25)
    da=ma.game_run_distribution(innings=req.innings); db=mb.game_run_distribution(innings=req.innings)
    def st(name,mc,m,d): return {"name":name,"markov_expected":m.expected_runs(d),"mean_runs":mc["mean_runs"],"variance":mc["variance"],"prob_0_runs":mc["prob_0_runs"],"prob_5_or_more":mc["prob_5_or_more_runs"]}
    return {"team_a":st(req.team_a_name,ra,ma,da),"team_b":st(req.team_b_name,rb,mb,db),"n_games":req.n_games}

# ── 전적 ─────────────────────────────────────────
@app.post("/api/records")
def save_record(req:GameRecordCreate):
    try:
        conn=get_conn(); cur=conn.cursor()
        cur.execute("INSERT INTO game_records(team_name,opponent_name,result,my_score,opp_score) VALUES(%s,%s,%s,%s,%s) RETURNING id",(req.team_name,req.opponent_name,req.result,req.my_score,req.opp_score))
        rid=cur.fetchone()[0]; conn.commit(); cur.close(); conn.close()
        return {"id":rid,"message":"전적이 저장되었습니다."}
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

@app.get("/api/records")
def get_records(team_name:Optional[str]=None):
    try:
        conn=get_conn(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if team_name: cur.execute("SELECT * FROM game_records WHERE team_name=%s ORDER BY played_at DESC LIMIT 20",(team_name,))
        else: cur.execute("SELECT * FROM game_records ORDER BY played_at DESC LIMIT 20")
        rows=cur.fetchall(); cur.close(); conn.close()
        return {"records":[dict(r) for r in rows]}
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

@app.delete("/api/records/{record_id}")
def delete_record(record_id:int):
    try:
        conn=get_conn(); cur=conn.cursor()
        cur.execute("DELETE FROM game_records WHERE id=%s",(record_id,))
        conn.commit(); cur.close(); conn.close()
        return {"message":"삭제되었습니다."}
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

# ── 팀 순위 ──────────────────────────────────────
@app.get("/api/stats/team-rank")
def get_team_rank():
    try:
        data=urllib.parse.urlencode({"leId":"1","srId":"0","seasonId":"2026"}).encode()
        req=urllib.request.Request("https://www.koreabaseball.com/ws/Main.asmx/GetTeamRank",data=data,
            headers={"Content-Type":"application/x-www-form-urlencoded","User-Agent":"Mozilla/5.0","Referer":"https://www.koreabaseball.com/"})
        with urllib.request.urlopen(req,timeout=10) as res: raw=json_lib.loads(res.read().decode("utf-8"))
        teams=[]
        for ro in raw.get("rows",[]):
            cells=ro.get("row",[])
            if len(cells)<8: continue
            def ct(i): return re.sub(r"<[^>]+>","",cells[i].get("Text","") if i<len(cells) else "").strip()
            rank,tn,g,w,l,d,wr=ct(0),ct(1),ct(2),ct(3),ct(4),ct(5),ct(6)
            if not rank or not tn: continue
            teams.append({"rank":int(rank) if rank.isdigit() else 0,"team_name":tn,
                "games":int(g) if g.isdigit() else 0,"wins":int(w) if w.isdigit() else 0,
                "losses":int(l) if l.isdigit() else 0,"draws":int(d) if d.isdigit() else 0,
                "win_rate":float(wr) if wr else 0.0,"game_gap":ct(7),
                "last10":ct(8) if len(cells)>8 else "-","streak":ct(9) if len(cells)>9 else "-"})
        if teams: return {"teams":teams,"source":"realtime"}
        raise Exception()
    except Exception:
        try:
            conn=get_conn(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""SELECT t.team_name,r.games,r.wins,r.losses,r.draws,r.win_rate,r.last10,r.streak,
                ROW_NUMBER() OVER(ORDER BY r.win_rate DESC) AS rank
                FROM team_rank_stats r JOIN teams t ON r.team_id=t.team_id
                WHERE r.season_year=%s ORDER BY r.win_rate DESC""",(LATEST_SEASON,))
            rows=cur.fetchall(); cur.close(); conn.close()
            return {"teams":[dict(r) for r in rows],"source":"db"}
        except Exception as e: raise HTTPException(status_code=500,detail=str(e))

# ── 타자 기록 ────────────────────────────────────
@app.get("/api/stats/hitters")
def get_hitter_stats(sort:Optional[str]="woba",limit:int=50):
    try:
        conn=get_conn(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sc={"woba":"woba","ops":"pst.ops","hr":"pst.hr","avg":"pst.avg","rbi":"pst.rbi"}.get(sort,"woba")
        cur.execute("SELECT MAX(games) FROM team_rank_stats WHERE season_year=%s",(LATEST_SEASON,))
        min_pa=int((cur.fetchone()['max'] or 1)*3.1)
        cur.execute(f"""SELECT p.player_id,p.player_name,t.team_name,pst.avg,pst.pa,pst.hr,pst.rbi,pst.obp,pst.slg,pst.ops,
            ROUND(CAST(pst.bb AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS bb_rate,
            ROUND(CAST(pst.so AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS k_rate,
            ROUND(CAST({WOBA_EXPR} AS NUMERIC),3) AS woba,
            ROUND(CAST(((({WOBA_EXPR})-0.273)/1.157+0.123)/0.123*100 AS NUMERIC),0) AS wrc_plus,
            def.position
            FROM players p JOIN player_hitter_stats pst ON p.player_id=pst.player_id
            JOIN teams t ON pst.team_id=t.team_id
            LEFT JOIN player_defense_stats def ON p.player_id=def.player_id AND pst.season_year=def.season_year
            WHERE pst.season_year=%s AND pst.pa>=%s ORDER BY {sc} DESC NULLS LAST LIMIT %s""",(LATEST_SEASON,min_pa,limit))
        rows=cur.fetchall(); cur.close(); conn.close()
        return {"hitters":[dict(r) for r in rows],"min_pa":min_pa}
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

# ── 투수 기록 ────────────────────────────────────
@app.get("/api/stats/pitchers")
def get_pitcher_stats(sort:Optional[str]="era",limit:int=50):
    try:
        conn=get_conn(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT MAX(games) FROM team_rank_stats WHERE season_year=%s",(LATEST_SEASON,))
        row=cur.fetchone(); min_g=max(1,int((row['max'] if row and row['max'] else 1)*0.3))
        sc={"era":"ps.era","w":"ps.w","sv":"ps.sv","so":"ps.so","whip":"ps.whip"}.get(sort,"ps.era")
        order="ASC" if sort in ("era","whip") else "DESC"
        cur.execute(f"""SELECT p.player_id,p.player_name,t.team_name,ps.era,ps.g,ps.w,ps.l,ps.sv,ps.hld,ps.ip,ps.so,ps.bb,ps.hr,ps.whip,ps.wpct
            FROM player_pitcher_stats ps JOIN players p ON ps.player_id=p.player_id
            JOIN teams t ON ps.team_id=t.team_id
            WHERE ps.season_year=%s AND ps.ip IS NOT NULL AND ps.g>=%s
            ORDER BY {sc} {order} NULLS LAST LIMIT %s""",(LATEST_SEASON,min_g,limit))
        rows=cur.fetchall(); cur.close(); conn.close()
        return {"pitchers":[dict(r) for r in rows],"min_g":min_g}
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

# ── 타순 최적화 ───────────────────────────────────
@app.post("/api/lineup/optimize")
def optimize_lineup(req:SimulateRequest):
    try:
        lu=[record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_a_lineup]
        def obp(p): return p.bb+p.single+p.double+p.triple+p.hr
        def ops(p): return obp(p)+p.single+2*p.double+3*p.triple+4*p.hr
        so=sorted(lu,key=obp,reverse=True); ss=sorted(lu,key=ops,reverse=True); sh=sorted(lu,key=lambda p:p.hr,reverse=True)
        used,result=set(),[]
        def pick(c):
            for p in c:
                if p.name not in used: used.add(p.name); result.append(p); return
        pick(so); pick(ss); pick(ss); pick(sh); pick(sh)
        for p in ss:
            if p.name not in used: result.append(p); used.add(p.name)
        return {"optimized_order":[p.name for p in result]}
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

# ── KBO 경기 일정 ────────────────────────────────
@app.get("/api/schedule")
def get_schedule(month:Optional[str]=None):
    try:
        now=datetime.now(); tm=month or f"{now.month:02d}"
        data=urllib.parse.urlencode({"leId":"1","srId":"0","srIdList":"0,9","seasonId":"2026","gameWeek":"","teamId":"","stadiumId":"","gameId":"","gameDay":"","gameMonth":tm}).encode()
        req=urllib.request.Request("https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList",data=data,
            headers={"Content-Type":"application/x-www-form-urlencoded","User-Agent":"Mozilla/5.0","Referer":"https://www.koreabaseball.com/Schedule/Schedule.aspx"})
        with urllib.request.urlopen(req,timeout=10) as res: raw=json_lib.loads(res.read().decode("utf-8"))
        ST=["잠실","문학","사직","수원","고척","대구","광주","창원","대전","포항","울산","인천"]
        games,cd=[],""
        for ro in raw.get("rows",[]):
            cells=ro.get("row",[])
            if not cells: continue
            for c in cells:
                if c.get("Class")=="day": cd=re.sub(r"<[^>]+>","",c.get("Text","")).strip(); break
            tt=pt=st=xt=""
            for c in cells:
                cls,txt=c.get("Class"),c.get("Text","")
                if cls=="time": tt=re.sub(r"<[^>]+>","",txt).strip()
                elif cls=="play": pt=txt
                elif cls is None and any(s in txt for s in ST): st=txt
                elif "우천" in txt or "취소" in txt: xt=txt
            if not pt or not cd: continue
            teams=re.findall(r"<span(?:[^>]*)>([^<]+)</span>",pt)
            scores=re.findall(r'<span class="(?:win|lose|same)">([^<]+)</span>',pt)
            wc=re.findall(r'<span class="(win|lose|same)">',pt)
            if len(teams)<2: continue
            sa=scores[0] if len(scores)>=1 else None; sb=scores[1] if len(scores)>=2 else None
            res=(f"{teams[0]} 승" if wc[0]=="win" else f"{teams[-1]} 승" if wc[0]=="lose" else "무승부") if (wc and sa and sb) else None
            games.append({"date":cd,"time":tt,"team_a":teams[0],"team_b":teams[-1],"score_a":sa,"score_b":sb,"result":res,"stadium":st,"status":xt or None})
        return {"month":tm,"games":games}
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

# ── 선수 이미지 프록시 ────────────────────────────
@app.get("/api/player-image/{player_id}")
def get_player_image(player_id:int):
    try:
        req=urllib.request.Request(f"https://www.koreabaseball.com/file/Image/Player/2026/M/{player_id}.jpg",
            headers={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36","Referer":"https://www.koreabaseball.com/Player/Search.aspx","Accept":"image/*,*/*;q=0.8","Accept-Language":"ko-KR,ko;q=0.9"})
        with urllib.request.urlopen(req,timeout=5) as res:
            data=res.read()
            if "html" in res.headers.get("Content-Type","").lower(): raise HTTPException(status_code=404,detail="이미지 없음")
            return Response(content=data,media_type="image/jpeg")
    except HTTPException: raise
    except Exception: raise HTTPException(status_code=404,detail="이미지 없음")

# ── 선수 연도별 스탯 ──────────────────────────────
@app.get("/api/players/{player_id}/seasons")
def get_player_seasons(player_id:int):
    try:
        conn=get_conn(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"""SELECT season_year,pst.avg,pst.pa,pst.hr,pst.rbi,pst.obp,pst.slg,pst.ops,
            ROUND(CAST(pst.bb AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS bb_rate,
            ROUND(CAST(pst.so AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS k_rate,
            ROUND(CAST({WOBA_EXPR} AS NUMERIC),3) AS woba,
            ROUND(CAST((({WOBA_EXPR})-0.273)/1.157+0.123)/0.123*100 AS NUMERIC),0) AS wrc_plus
            FROM player_hitter_stats pst WHERE pst.player_id=%s::varchar AND pst.pa>0 ORDER BY season_year""",(player_id,))
        hr=cur.fetchall()
        cur.execute("""SELECT season_year,ps.era,ps.w,ps.l,ps.sv,ps.ip,ps.so AS pitcher_so,ps.bb AS pitcher_bb,ps.whip,ps.g
            FROM player_pitcher_stats ps WHERE ps.player_id=%s::varchar ORDER BY season_year""",(player_id,))
        pr=cur.fetchall(); cur.close(); conn.close()
        if hr: return {"type":"hitter","seasons":[dict(r) for r in hr]}
        elif pr: return {"type":"pitcher","seasons":[dict(r) for r in pr]}
        else: raise HTTPException(status_code=404,detail="데이터 없음")
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

# ── 머니볼 엔진 ───────────────────────────────────
@app.get("/api/players/{player_id}/moneyball")
def get_moneyball(player_id:int):
    try:
        from app.ml.moneyball import get_player_moneyball
        result=get_player_moneyball(player_id)
        if not result: raise HTTPException(status_code=404,detail="타자 데이터 없음")
        for k,v in result['features'].items(): result['features'][k]=float(v) if v is not None else None
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

# ── 머니볼 분포 ───────────────────────────────────
@app.get("/api/moneyball/distribution")
def get_moneyball_distribution():
    try:
        from app.ml.moneyball import get_hitter_features,train_kmeans
        all_data=get_hitter_features(LATEST_SEASON)
        if not all_data: raise HTTPException(status_code=404,detail="데이터 없음")
        _,_,labels,type_map,_=train_kmeans(all_data)
        dist: dict={}
        for i,label in enumerate(labels):
            tn=type_map.get(int(label),"기타"); dist[tn]=dist.get(tn,0)+1
        total=len(labels)
        result=sorted([{"type":k,"count":v,"pct":round(v/total*100,1)} for k,v in dist.items()],key=lambda x:x["count"],reverse=True)
        return {"distribution":result,"total":total}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500,detail=str(e))

    # ── 유사 선수 추천 ─────────────────────────────────
@app.get("/api/players/{player_id}/similar")
def get_similar(player_id: int):
    try:
        from app.ml.similar_players import get_similar_players, get_similar_pitchers
        # 타자 먼저 시도
        result = get_similar_players(player_id)
        if not result:
            # 투수 시도
            result = get_similar_pitchers(player_id)
        if not result:
            raise HTTPException(status_code=404, detail="데이터 없음")
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))