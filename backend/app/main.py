from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
import sys, os, psycopg2, psycopg2.extras, re, urllib.request, urllib.parse, json as J, math

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game_simulator.simulator_main import (
    BattingRecord, record_to_player_prob,
    MatchSimulator, LineupMonteCarloSimulator, LineupMarkovModel,
)

def clean(v):
    if isinstance(v, Decimal): return None if v.is_nan() else float(v)
    if isinstance(v, float) and math.isnan(v): return None
    return v

def row(r): return {k: clean(v) for k, v in dict(r).items()}
def rows(rs): return [row(r) for r in rs]

class SafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        def default(o):
            if isinstance(o, Decimal): return None if o.is_nan() else float(o)
            if isinstance(o, float) and math.isnan(o): return None
            raise TypeError(f"Not serializable: {type(o)}")
        return J.dumps(content, ensure_ascii=False, default=default).encode("utf-8")

app = FastAPI(title="BallPark Intelligence API", default_response_class=SafeJSONResponse)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB = {"host":"localhost","port":5432,"dbname":"ballpark","user":"ballpark","password":"ballpark1234"}
SEASON = 2026
def conn(): return psycopg2.connect(**DB)
def cur(c): return c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def clean(v):
    if isinstance(v, Decimal): return None if v.is_nan() else float(v)
    if isinstance(v, float) and math.isnan(v): return None
    return v
def row(r): return {k: clean(v) for k, v in dict(r).items()}
def rows(rs): return [row(r) for r in rs]

WOBA = "(pst.bb*0.69+pst.hbp*0.72+(pst.h-pst.double_hit-pst.triple_hit-pst.hr)*0.87+pst.double_hit*1.217+pst.triple_hit*1.529+pst.hr*1.74)/NULLIF(pst.pa,0)"

HITTER_Q = f"""
    SELECT p.player_id, p.player_name, t.team_name, pst.season_year,
        pst.avg, pst.pa, pst.ab, pst.h, pst.double_hit, pst.triple_hit,
        pst.hr, pst.bb, pst.hbp, pst.so, pst.slg, pst.obp, pst.ops, pst.isop, pst.rbi,
        ROUND(CAST(pst.bb AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS bb_rate,
        ROUND(CAST(pst.so AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS k_rate,
        ROUND(CAST(pst.slg-pst.avg AS NUMERIC),3) AS iso,
        ROUND(CAST({WOBA} AS NUMERIC),3) AS woba,
        ROUND(CAST(((({WOBA})-0.273)/1.157+0.123)/0.123*100 AS NUMERIC),0) AS wrc_plus,
        ROUND(CAST(PERCENT_RANK() OVER(PARTITION BY pst.season_year ORDER BY {WOBA})*100 AS NUMERIC),0) AS woba_percentile,
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

PITCHER_Q = """
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
        NULL::numeric AS babip, NULL::numeric AS spd, NULL::numeric AS war, '투수' AS position,
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

def sc(search, a="p", t="t"):
    return f" AND ({a}.player_name ILIKE %s OR {t}.team_name ILIKE %s)" if search else ""

class PlayerRecord(BaseModel):
    name:str; ab:int; hits:int; double:int; triple:int; hr:int; bb:int; hbp:int=0

class SimReq(BaseModel):
    team_a_name:str; team_a_lineup:List[PlayerRecord]
    team_b_name:str; team_b_lineup:List[PlayerRecord]; innings:int=9

class MultiReq(BaseModel):
    team_a_name:str; team_a_lineup:List[PlayerRecord]
    team_b_name:str; team_b_lineup:List[PlayerRecord]; n_games:int=1000; innings:int=9

class RecordCreate(BaseModel):
    team_name:str; opponent_name:str; result:str; my_score:int; opp_score:int

@app.get("/")
def root(): return {"message":"BallPark Intelligence API is running"}
@app.get("/health")
def health(): return {"status":"ok"}

@app.get("/api/players")
def get_players(search: Optional[str]=None):
    try:
        c=conn(); cr=cur(c); like=[f"%{search}%"]*2 if search else []
        cr.execute(HITTER_Q+" WHERE pst.season_year=%s AND pst.pa>=5"+sc(search)+" ORDER BY woba DESC NULLS LAST LIMIT 50",[SEASON]+like)
        hitters=list(cr.fetchall())
        if search:
            cr.execute(HITTER_Q+"WHERE pst.season_year=(SELECT MAX(s.season_year) FROM player_hitter_stats s WHERE s.player_id=p.player_id AND s.pa>=5) AND pst.pa>=5"+sc(search)+" ORDER BY woba DESC NULLS LAST LIMIT 50",like)
            ids={r['player_id'] for r in hitters}
            hitters+=[r for r in cr.fetchall() if r['player_id'] not in ids]
        cr.execute("SELECT DISTINCT ON(sub.player_id) * FROM("+PITCHER_Q+"WHERE ps.season_year=(SELECT MAX(ps2.season_year) FROM player_pitcher_stats ps2 WHERE ps2.player_id=p.player_id) AND ps.g>=3"+sc(search,"p","t")+") sub ORDER BY sub.player_id, sub.era ASC NULLS LAST LIMIT 50",like)
        pitchers=cr.fetchall(); cr.close(); c.close()
        ids={r['player_id'] for r in hitters}
        return {"players":rows(hitters)+[row(r) for r in pitchers if r['player_id'] not in ids]}
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/players/{player_id}")
def get_player(player_id:int, season:Optional[int]=None):
    target=season or SEASON
    try:
        c=conn(); cr=cur(c)
        cr.execute("SELECT array_agg(DISTINCT season_year ORDER BY season_year DESC) AS seasons FROM(SELECT season_year FROM player_hitter_stats WHERE player_id=%s::varchar AND pa>0 UNION SELECT season_year FROM player_pitcher_stats WHERE player_id=%s::varchar) s",(player_id,player_id))
        av=list((cr.fetchone()['seasons'] or []))
        cr.execute("SELECT * FROM("+HITTER_Q+"WHERE pst.season_year=%s AND pst.pa>0) sub WHERE sub.player_id=%s::varchar",(target,player_id))
        r=cr.fetchone()
        if not r:
            cr.execute("SELECT MAX(season_year) FROM player_hitter_stats WHERE player_id=%s::varchar AND pa>=5",(player_id,))
            ls=cr.fetchone(); ls=ls['max'] if ls and ls['max'] else None
            if ls:
                cr.execute("SELECT * FROM("+HITTER_Q+"WHERE pst.season_year=%s AND pst.pa>=5) sub WHERE sub.player_id=%s::varchar",(ls,player_id))
                r=cr.fetchone()
        if not r:
            cr.execute("SELECT MAX(season_year) FROM player_pitcher_stats WHERE player_id=%s::varchar AND g>=3",(player_id,))
            lp=cr.fetchone(); lp=lp['max'] if lp and lp['max'] else target
            cr.execute("SELECT * FROM("+PITCHER_Q+"WHERE ps.season_year=%s) sub WHERE sub.player_id=%s::varchar",(lp,player_id))
            r=cr.fetchone()
        cr.close(); c.close()
        if not r: raise HTTPException(404,"선수를 찾을 수 없습니다.")
        result=row(r); result['available_seasons']=av; result['current_season']=target
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/teams")
def get_teams():
    try:
        c=conn(); cr=cur(c); cr.execute("SELECT * FROM teams ORDER BY team_name")
        r=cr.fetchall(); cr.close(); c.close()
        return {"teams":rows(r)}
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/teams/{team_name}/lineup")
def get_lineup(team_name:str):
    try:
        c=conn(); cr=cur(c)
        cr.execute("SELECT p.player_name,pst.ab,pst.h AS hits,pst.double_hit AS double,pst.triple_hit AS triple,pst.hr,pst.bb,pst.hbp FROM players p JOIN player_hitter_stats pst ON p.player_id=pst.player_id JOIN teams t ON pst.team_id=t.team_id WHERE t.team_name=%s AND pst.season_year=%s AND pst.pa>=50 ORDER BY pst.pa DESC LIMIT 9",(team_name,SEASON))
        r=cr.fetchall(); cr.close(); c.close()
        if not r: raise HTTPException(404,"팀을 찾을 수 없습니다.")
        return {"lineup":rows(r)}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500,str(e))

@app.post("/api/simulate/game")
def simulate_game(req:SimReq):
    ta=[record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_a_lineup]
    tb=[record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_b_lineup]
    g=MatchSimulator(team_a_name=req.team_a_name,team_a_lineup=ta,team_b_name=req.team_b_name,team_b_lineup=tb).simulate_game(innings=req.innings)
    return {"team_a_name":req.team_a_name,"team_b_name":req.team_b_name,"game_log":g,"is_draw":g.final_score[0]==g.final_score[1]}

@app.post("/api/simulate/multi")
def simulate_multi(req:MultiReq):
    ta=[record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_a_lineup]
    tb=[record_to_player_prob(BattingRecord(**p.dict())) for p in req.team_b_lineup]
    ra=LineupMonteCarloSimulator(ta,seed=42).simulate_many(n_games=req.n_games,innings=req.innings)
    rb=LineupMonteCarloSimulator(tb,seed=42).simulate_many(n_games=req.n_games,innings=req.innings)
    ma=LineupMarkovModel(ta,max_runs=25); mb=LineupMarkovModel(tb,max_runs=25)
    da=ma.game_run_distribution(innings=req.innings); db=mb.game_run_distribution(innings=req.innings)
    def st(name,mc,m,d): return {"name":name,"markov_expected":m.expected_runs(d),"mean_runs":mc["mean_runs"],"variance":mc["variance"],"prob_0_runs":mc["prob_0_runs"],"prob_5_or_more":mc["prob_5_or_more_runs"]}
    return {"team_a":st(req.team_a_name,ra,ma,da),"team_b":st(req.team_b_name,rb,mb,db),"n_games":req.n_games}

@app.post("/api/records")
def save_record(req:RecordCreate):
    try:
        c=conn(); cr=c.cursor()
        cr.execute("INSERT INTO game_records(team_name,opponent_name,result,my_score,opp_score) VALUES(%s,%s,%s,%s,%s) RETURNING id",(req.team_name,req.opponent_name,req.result,req.my_score,req.opp_score))
        rid=cr.fetchone()[0]; c.commit(); cr.close(); c.close()
        return {"id":rid,"message":"전적이 저장되었습니다."}
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/records")
def get_records(team_name:Optional[str]=None):
    try:
        c=conn(); cr=cur(c)
        if team_name: cr.execute("SELECT * FROM game_records WHERE team_name=%s ORDER BY played_at DESC LIMIT 20",(team_name,))
        else: cr.execute("SELECT * FROM game_records ORDER BY played_at DESC LIMIT 20")
        r=cr.fetchall(); cr.close(); c.close()
        return {"records":rows(r)}
    except Exception as e: raise HTTPException(500,str(e))

@app.delete("/api/records/{record_id}")
def delete_record(record_id:int):
    try:
        c=conn(); cr=c.cursor()
        cr.execute("DELETE FROM game_records WHERE id=%s",(record_id,))
        c.commit(); cr.close(); c.close()
        return {"message":"삭제되었습니다."}
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/stats/team-rank")
def get_team_rank():
    try:
        data=urllib.parse.urlencode({"leId":"1","srId":"0","seasonId":"2026"}).encode()
        req=urllib.request.Request("https://www.koreabaseball.com/ws/Main.asmx/GetTeamRank",data=data,
            headers={"Content-Type":"application/x-www-form-urlencoded","User-Agent":"Mozilla/5.0","Referer":"https://www.koreabaseball.com/"})
        with urllib.request.urlopen(req,timeout=10) as res: raw=J.loads(res.read().decode("utf-8"))
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
            c=conn(); cr=cur(c)
            cr.execute("SELECT t.team_name,r.games,r.wins,r.losses,r.draws,r.win_rate,r.last10,r.streak,ROW_NUMBER() OVER(ORDER BY r.win_rate DESC) AS rank FROM team_rank_stats r JOIN teams t ON r.team_id=t.team_id WHERE r.season_year=%s ORDER BY r.win_rate DESC",(SEASON,))
            r=cr.fetchall(); cr.close(); c.close()
            return {"teams":rows(r),"source":"db"}
        except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/stats/hitters")
def get_hitters(sort:Optional[str]="woba",limit:int=50):
    try:
        c=conn(); cr=cur(c)
        sc_map={"woba":"woba","ops":"pst.ops","hr":"pst.hr","avg":"pst.avg","rbi":"pst.rbi"}
        s=sc_map.get(sort,"woba")
        cr.execute("SELECT MAX(games) FROM team_rank_stats WHERE season_year=%s",(SEASON,))
        min_pa=int((cr.fetchone()['max'] or 1)*3.1)
        cr.execute(f"""SELECT p.player_id,p.player_name,t.team_name,pst.avg,pst.pa,pst.hr,pst.rbi,pst.obp,pst.slg,pst.ops,
            ROUND(CAST(pst.bb AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS bb_rate,
            ROUND(CAST(pst.so AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS k_rate,
            ROUND(CAST({WOBA} AS NUMERIC),3) AS woba,
            ROUND(CAST((({WOBA})-0.273)/1.157+0.123)/0.123*100 AS NUMERIC),0) AS wrc_plus,
            def.position
            FROM players p JOIN player_hitter_stats pst ON p.player_id=pst.player_id
            JOIN teams t ON pst.team_id=t.team_id
            LEFT JOIN player_defense_stats def ON p.player_id=def.player_id AND pst.season_year=def.season_year
            WHERE pst.season_year=%s AND pst.pa>=%s ORDER BY {s} DESC NULLS LAST LIMIT %s""",(SEASON,min_pa,limit))
        r=cr.fetchall(); cr.close(); c.close()
        return {"hitters":rows(r),"min_pa":min_pa}
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/stats/pitchers")
def get_pitchers(sort:Optional[str]="era",limit:int=50):
    try:
        c=conn(); cr=cur(c)
        cr.execute("SELECT MAX(games) FROM team_rank_stats WHERE season_year=%s",(SEASON,))
        r=cr.fetchone()
        max_games = r['max'] if r and r['max'] else 1
        min_g = max(1, int(max_games * 0.3))
        min_ip = max_games  # 규정이닝 = 팀 경기 수
        sc_map={"era":"ps.era","w":"ps.w","sv":"ps.sv","so":"ps.so","whip":"ps.whip"}
        s=sc_map.get(sort,"ps.era")
        order="ASC" if sort in ("era","whip") else "DESC"
        cr.execute(f"""SELECT p.player_id,p.player_name,t.team_name,ps.era,ps.g,ps.w,ps.l,ps.sv,ps.hld,ps.ip,ps.so,ps.bb,ps.hr,ps.whip,ps.wpct,
    CAST(REGEXP_REPLACE(ps.ip, '[^0-9].*', '') AS NUMERIC) +
    CASE WHEN ps.ip LIKE '%%2/3%%' THEN 0.667
         WHEN ps.ip LIKE '%%1/3%%' THEN 0.333
         ELSE 0 END AS ip_numeric
    FROM player_pitcher_stats ps JOIN players p ON ps.player_id=p.player_id
    JOIN teams t ON ps.team_id=t.team_id
    WHERE ps.season_year=%s AND ps.ip IS NOT NULL
    AND (CAST(REGEXP_REPLACE(ps.ip, '[^0-9].*', '') AS NUMERIC) +
         CASE WHEN ps.ip LIKE '%%2/3%%' THEN 0.667
              WHEN ps.ip LIKE '%%1/3%%' THEN 0.333
              ELSE 0 END) >= %s
    ORDER BY {s} {order} NULLS LAST LIMIT %s""",(SEASON,min_ip,limit))
        r=cr.fetchall(); cr.close(); c.close()
        return {"pitchers":rows(r),"min_g":min_g}
    except Exception as e: raise HTTPException(500,str(e))

@app.post("/api/lineup/optimize")
def optimize_lineup(req:SimReq):
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
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/schedule")
def get_schedule(month:Optional[str]=None):
    try:
        now=datetime.now(); tm=month or f"{now.month:02d}"
        data=urllib.parse.urlencode({"leId":"1","srId":"0","srIdList":"0,9","seasonId":"2026","gameWeek":"","teamId":"","stadiumId":"","gameId":"","gameDay":"","gameMonth":tm}).encode()
        req=urllib.request.Request("https://www.koreabaseball.com/ws/Schedule.asmx/GetScheduleList",data=data,
            headers={"Content-Type":"application/x-www-form-urlencoded","User-Agent":"Mozilla/5.0","Referer":"https://www.koreabaseball.com/Schedule/Schedule.aspx"})
        with urllib.request.urlopen(req,timeout=10) as res: raw=J.loads(res.read().decode("utf-8"))
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
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/player-image/{player_id}")
def get_player_image(player_id:int):
    try:
        req=urllib.request.Request(f"https://www.koreabaseball.com/file/Image/Player/2026/M/{player_id}.jpg",
            headers={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36","Referer":"https://www.koreabaseball.com/Player/Search.aspx","Accept":"image/*,*/*;q=0.8","Accept-Language":"ko-KR,ko;q=0.9"})
        with urllib.request.urlopen(req,timeout=5) as res:
            data=res.read()
            if "html" in res.headers.get("Content-Type","").lower(): raise HTTPException(404,"이미지 없음")
            return Response(content=data,media_type="image/jpeg")
    except HTTPException: raise
    except Exception: raise HTTPException(404,"이미지 없음")

@app.get("/api/players/{player_id}/seasons")
def get_seasons(player_id:int):
    try:
        c=conn(); cr=cur(c)
        cr.execute(f"""SELECT season_year,pst.avg,pst.pa,pst.hr,pst.rbi,pst.obp,pst.slg,pst.ops,
            ROUND(CAST(pst.bb AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS bb_rate,
            ROUND(CAST(pst.so AS NUMERIC)/NULLIF(pst.pa,0)*100,1) AS k_rate,
            ROUND(CAST({WOBA} AS NUMERIC),3) AS woba,
            ROUND(CAST((({WOBA})-0.273)/1.157+0.123)/0.123*100 AS NUMERIC),0) AS wrc_plus
            FROM player_hitter_stats pst WHERE pst.player_id=%s::varchar AND pst.pa>0 ORDER BY season_year""",(player_id,))
        hr=cr.fetchall()
        cr.execute("SELECT season_year,ps.era,ps.w,ps.l,ps.sv,ps.ip,ps.so AS pitcher_so,ps.bb AS pitcher_bb,ps.whip,ps.g FROM player_pitcher_stats ps WHERE ps.player_id=%s::varchar ORDER BY season_year",(player_id,))
        pr=cr.fetchall(); cr.close(); c.close()
        if hr: return {"type":"hitter","seasons":rows(hr)}
        elif pr: return {"type":"pitcher","seasons":rows(pr)}
        else: raise HTTPException(404,"데이터 없음")
    except HTTPException: raise
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/players/{player_id}/moneyball")
def get_moneyball(player_id:int):
    try:
        from app.ml.moneyball import get_player_moneyball
        result=get_player_moneyball(player_id)
        if not result: raise HTTPException(404,"타자 데이터 없음")
        for k,v in result['features'].items(): result['features'][k]=float(v) if v is not None else None
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/moneyball/distribution")
def get_moneyball_dist():
    try:
        from app.ml.moneyball import get_hitter_features,train_kmeans
        all_data=get_hitter_features(SEASON)
        if not all_data: raise HTTPException(404,"데이터 없음")
        _,_,labels,type_map,_=train_kmeans(all_data)
        dist: dict={}
        for i,label in enumerate(labels):
            tn=type_map.get(int(label),"기타"); dist[tn]=dist.get(tn,0)+1
        total=len(labels)
        return {"distribution":sorted([{"type":k,"count":v,"pct":round(v/total*100,1)} for k,v in dist.items()],key=lambda x:x["count"],reverse=True),"total":total}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/api/players/{player_id}/similar")
def get_similar(player_id:int):
    try:
        from app.ml.similar_players import get_similar_players,get_similar_pitchers
        result=get_similar_players(player_id) or get_similar_pitchers(player_id)
        if not result: raise HTTPException(404,"데이터 없음")
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(500,str(e))

_h_model=_h_sx=_h_sy=_p_model=_p_sx=_p_sy=None

@app.get("/api/players/{player_id}/predict")
def get_prediction(player_id:int):
    global _h_model,_h_sx,_h_sy,_p_model,_p_sx,_p_sy
    try:
        from app.ml.lstm_predictor import predict_next_season,predict_pitcher_next_season,train_hitter_model,train_pitcher_model
        result=None
        try:
            if _h_model is None: _h_model,_h_sx,_h_sy=train_hitter_model()
            result=predict_next_season(player_id,_h_model,_h_sx,_h_sy)
        except: pass
        if not result:
            try:
                if _p_model is None: _p_model,_p_sx,_p_sy=train_pitcher_model()
                result=predict_pitcher_next_season(player_id,_p_model,_p_sx,_p_sy)
            except: pass
        if not result: raise HTTPException(404,"예측 데이터 부족")
        return result
    except HTTPException: raise
    except Exception as e: raise HTTPException(500,str(e))