"""Walk through the actual regular-season schedule, hiding each game's date and later stats."""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import csv
from dataclasses import asdict
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from .collect_history import BASE, request
from .historical import DEFAULT_HISTORY_DIR, HistoricalInputs
from .simulator_main import (
    BattingRecord, MatchSimulator, OUTPUT_DB_READY_DIR, PitcherProb, PlayerProb,
    adjust_lineup_by_pitcher, record_to_player_prob,
)


def _table_rows(value):
    data = json.loads(value) if isinstance(value,str) else value
    return [[cell["Text"] for cell in row["row"]] for row in data["rows"]]


def parse_starting_lineups(box):
    if str(box.get("code")) != "100" or len(box.get("arrHitter",[])) != 2:
        raise ValueError("공식 선발 타순을 확인할 수 없습니다.")
    lineups = []
    for side in box["arrHitter"]:
        starters = {}
        for cells in _table_rows(side["table1"]):
            if len(cells) != 3 or not re.fullmatch(r"[1-9]",cells[0]):
                raise ValueError("공식 선발 타순 표의 형식이 바뀌었습니다.")
            # Substitutes repeat the order; the first row is the announced starter.
            starters.setdefault(int(cells[0]),cells[2].strip())
        if set(starters) != set(range(1,10)) or len(set(starters.values())) != 9:
            raise ValueError("고유한 선발 타자 9명을 확인할 수 없습니다.")
        lineups.append([starters[i] for i in range(1,10)])
    return lineups


def prepare_fixtures(history, history_dir=DEFAULT_HISTORY_DIR):
    cache_dir = Path(history_dir)/"raw"/str(history["season"])/"lineups"
    identities=defaultdict(list)
    for r in history['hitters']:
        identities[(r['game_date'],r['team_name'],r['player_name'],r['opponent'])].append(r)
    def load(game):
        gid = game["G_ID"]
        path = cache_dir/f"{gid}.json"
        if path.exists():
            box = json.loads(path.read_text(encoding="utf-8"))
        else:
            box = json.loads(request(BASE+"/ws/Schedule.asmx/GetBoxScoreScroll",
                             {"leId":"1","srId":"0","seasonId":str(history["season"]),"gameId":gid}))
        a,b = parse_starting_lineups(box)
        if not path.exists():
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(box,ensure_ascii=False),encoding="utf-8")
        ids=[]
        day=date(int(game['G_DT'][:4]),int(game['G_DT'][4:6]),int(game['G_DT'][6:8])).isoformat()
        for index,(team,opponent) in enumerate(((game['AWAY_NM'],game['HOME_NM']),(game['HOME_NM'],game['AWAY_NM']))):
            names=_table_rows(box['arrHitter'][index]['table1'])
            totals=_table_rows(box['arrHitter'][index]['table3'])
            side_ids=[];seen=set()
            for cells,stats in zip(names,totals,strict=True):
                order=int(cells[0])
                if order in seen:continue
                seen.add(order)
                candidates=identities[(day,team,cells[2].strip(),opponent)]
                if len({r['player_id'] for r in candidates})>1:
                    # The box score omits IDs. Recover the identity of the already
                    # announced starter by matching its daily line; these target
                    # counts are NOT passed to the forecasting input builder.
                    candidates=[r for r in candidates if r['ab']==int(stats[0]) and r['h']==int(stats[1])]
                distinct={r['player_id'] for r in candidates}
                if len(distinct)>1:
                    raise ValueError(f"선발 타자 ID가 모호합니다: {game['G_ID']} {cells[2]}")
                side_ids.append(next(iter(distinct),None))
            ids.append(side_ids)
        return game | {"lineup_a":a,"lineup_b":b,"lineup_ids_a":ids[0],"lineup_ids_b":ids[1]}
    fixtures = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(load,g):g for g in history["games"]}
        for i,future in enumerate(as_completed(futures),1):
            fixtures.append(future.result())
            if i%50 == 0:
                print(f"실제 선발 타순 {i}/{len(futures)}경기",flush=True)
    return sorted(fixtures,key=lambda g:(g["G_DT"],g["G_ID"]))


def read_prior(season,csv_dir=OUTPUT_DB_READY_DIR):
    """Only the previous year's counts are allowed. No target-year annual fields."""
    prior = {}
    hashes = {}
    for kind,filename in (("hitters","player_hitter_stats.csv"),("pitchers","player_pitcher_stats.csv")):
        path = Path(csv_dir)/filename
        hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        fields = (["ab","h","double_hit","triple_hit","hr","bb","hbp"] if kind=="hitters"
                  else ["tbf","h","hr","bb","hbp"])
        grouped = {}
        with path.open(encoding="utf-8-sig",newline="") as handle:
            for row in csv.DictReader(handle):
                if row["season_year"] != str(season-1):
                    continue
                pid = row["player_id"]
                entry = grouped.setdefault(pid,dict.fromkeys(fields,0)|{"player_id":pid,"name":row["player_name"],"teams":[]})
                if row["team_name"] not in entry["teams"]:
                    entry["teams"].append(row["team_name"])
                for key in fields:
                    text = row.get(key,"").strip()
                    if not re.fullmatch(r"\d+",text):
                        raise ValueError(f"이전 시즌 기록 누락: {pid} {key}")
                    entry[key] += int(text)
        if not grouped:
            raise ValueError(f"개막 초반을 보완할 {season-1}년 기록이 없습니다.")
        prior[kind] = {pid:r for pid,r in grouped.items()
                       if (r["ab"]+r["bb"]+r["hbp"] if kind=="hitters" else r["tbf"])>0}
    return prior,hashes


def _batting_prob(r):
    return record_to_player_prob(BattingRecord(name=r["name"],ab=r["ab"],hits=r["h"],
        double=r["double_hit"],triple=r["triple_hit"],hr=r["hr"],bb=r["bb"],hbp=r["hbp"]))


class SeasonInputs:
    def __init__(self,history,prior,prior_strength=30):
        if history.get("complete") is not True:
            raise ValueError("수집이 완료된 경기별 기록이 필요합니다.")
        self.history,self.prior,self.prior_strength = history,prior,prior_strength
        self._snapshots = {}
        totals_h = defaultdict(int)
        totals_p = defaultdict(int)
        for r in prior["hitters"].values():
            for key in ("ab","h","double_hit","triple_hit","hr","bb","hbp"):
                totals_h[key] += r[key]
        for r in prior["pitchers"].values():
            for key in ("tbf","h","hr","bb","hbp"):
                totals_p[key] += r[key]
        self.prior_h = _batting_prob(dict(totals_h)|{"name":"이전 시즌 리그 평균"})
        self.prior_p = HistoricalInputs._pitching_prob(totals_p)

    def snapshot(self,day):
        if day in self._snapshots:
            return self._snapshots[day]
        cutoff = date.fromisoformat(day)
        if cutoff.year != self.history["season"] or day > self.history["coverage_before"]:
            raise ValueError("경기 날짜가 수집된 시즌/범위를 벗어납니다.")
        selected = {kind:[r for r in self.history[kind] if r["game_date"] < day] for kind in ("hitters","pitchers")}
        current = {kind:{r["player_id"]:r for r in HistoricalInputs._aggregate(selected[kind],kind[:-1])}
                   for kind in selected}
        latest = max((r["game_date"] for rows in selected.values() for r in rows),default=None)
        self._snapshots[day] = current,latest
        return current,latest

    def _blend(self,name,current,prior,current_n):
        strength = self.prior_strength
        fields = ("bb","single","double","triple","hr","out")
        probs = {k:(getattr(current,k)*current_n+getattr(prior,k)*strength)/(current_n+strength) for k in fields}
        return PlayerProb(name=name,**probs).normalized()

    def fixture(self,g):
        day = date(int(g["G_DT"][:4]),int(g["G_DT"][4:6]),int(g["G_DT"][6:8])).isoformat()
        current,latest = self.snapshot(day)
        audits = []
        def hitters(team,names,announced_ids):
            result = []
            for name,announced_id in zip(names,announced_ids,strict=True):
                candidates = {pid for source in (current["hitters"],self.prior["hitters"])
                              for pid,r in source.items() if r["name"] == name}
                # Resolve the identity on the announced lineup. No event/count
                # fields from the target date are read for probability estimates.
                if announced_id:
                    candidates={announced_id}
                if len(candidates)>1:
                    in_team = {pid for pid in candidates if current["hitters"].get(pid,{}).get("team_name")==team}
                    if len(in_team)==1:
                        candidates=in_team
                    else:
                        previous_team={pid for pid in candidates if team in self.prior['hitters'].get(pid,{}).get('teams',[])}
                        if len(previous_team)==1:
                            candidates=previous_team
                # No future season averages are consulted for a rookie/new arrival.
                if len(candidates)>1:
                    raise ValueError(f"동명이인 선발 타자 ID 확인 필요: {team} {name}")
                pid = next(iter(candidates),None)
                now = current["hitters"].get(pid)
                previous = self.prior["hitters"].get(pid)
                prior_prob = _batting_prob(previous) if previous and previous["ab"] else self.prior_h
                n = now["ab"]+now["bb"]+now["hbp"] if now else 0
                now_prob = _batting_prob(now) if n else prior_prob
                result.append(self._blend(name,now_prob,prior_prob,n))
                audits.append({"team":team,"player":name,"player_id":pid,"current_opportunities":n,
                               "prior_source":"previous_player" if previous else "previous_league"})
            return result
        a = hitters(g["AWAY_NM"],g["lineup_a"],g.get("lineup_ids_a",[None]*9))
        b = hitters(g["HOME_NM"],g["lineup_b"],g.get("lineup_ids_b",[None]*9))

        totals = {key:sum(r[key] for r in current["pitchers"].values()) for key in ("tbf","h","hr","bb","hbp")}
        now_avg = HistoricalInputs._pitching_prob(totals) if totals["tbf"] else self.prior_p
        league = asdict(self._blend("리그 평균",now_avg,self.prior_p,totals["tbf"]))
        league.pop("name");league.pop("position")
        from .simulator_main import LeagueAverageProb
        league = LeagueAverageProb(**league)
        def pitcher(pid,name,team):
            pid = str(pid)
            now = current["pitchers"].get(pid)
            previous = self.prior["pitchers"].get(pid)
            prior_prob = HistoricalInputs._pitching_prob(previous) if previous and previous["tbf"] else self.prior_p
            n = now["tbf"] if now else 0
            now_prob = HistoricalInputs._pitching_prob(now) if n else prior_prob
            blended = asdict(self._blend(name.strip(),now_prob,prior_prob,n))
            blended.pop("position")
            audits.append({"team":team,"player":name.strip(),"player_id":pid,"current_opportunities":n,
                           "prior_source":"previous_player" if previous else "previous_league","role":"pitcher"})
            return PitcherProb(team_name=team,**blended)
        pa = pitcher(g["T_PIT_P_ID"],g["T_PIT_P_NM"],g["AWAY_NM"])
        pb = pitcher(g["B_PIT_P_ID"],g["B_PIT_P_NM"],g["HOME_NM"])
        a = adjust_lineup_by_pitcher(a,pb,league)
        b = adjust_lineup_by_pitcher(b,pa,league)
        return a,b,{"as_of":day,"last_current_season_game":latest,"date_rule":"game_date < as_of",
                    "prior_season":self.history["season"]-1,"prior_strength":self.prior_strength,
                    "lineup_assumption":"actual announced starters known before first pitch; substitutes ignored",
                    "players":audits,"pitcher_a":asdict(pa),"pitcher_b":asdict(pb),"league":asdict(league),
                    "lineup_a_probabilities":[asdict(p) for p in a],"lineup_b_probabilities":[asdict(p) for p in b]}


class _FixedLineupMatch(MatchSimulator):
    """Reuse fixed event probabilities without changing draws or transition rules."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._probabilities={id(p):p.event_probs() for p in self.team_a_lineup+self.team_b_lineup}

    def sample_event(self,player):
        x=self.rng.random();cumulative=0.0
        for event,probability in self._probabilities[id(player)]:
            cumulative+=probability
            if x<=cumulative:
                return event
        return 'OUT'


def _simulate_job(job):
    game,a,b,audit,n,seed = job
    max_innings=11 if int(game['G_DT'][:4])>=2025 else 12
    result = _FixedLineupMatch(game["AWAY_NM"],a,game["HOME_NM"],b,seed=seed).simulate_many(n,max_innings=max_innings)
    wa,wb = result["team_a"]["wins"],result["team_b"]["wins"]
    return {"game_id":game["G_ID"],"date":audit["as_of"],"away":game["AWAY_NM"],"home":game["HOME_NM"],
            "actual_away_runs":int(game["T_SCORE_CN"]),"actual_home_runs":int(game["B_SCORE_CN"]),
            "away_win_probability":wa/n,"home_win_probability":wb/n,"draw_probability":result["draws"]/n,
            "away_winrate_decided":wa/(wa+wb) if wa+wb else None,
            "away_mean_runs":result["team_a"]["mean_runs"],"home_mean_runs":result["team_b"]["mean_runs"],
            "n_simulations":n,"seed":seed,"max_innings":max_innings,"inputs":audit,"score_distribution":result["score_distribution"]}


def summarize(results):
    teams = {}
    def team(name):
        return teams.setdefault(name,{"team":name,"games":0,"actual_w":0,"actual_l":0,"actual_d":0,
                                      "expected_w":0.,"expected_l":0.,"expected_d":0.,"actual_runs":0,"expected_runs":0.})
    decided = []
    for r in results:
        a,b=r["actual_away_runs"],r["actual_home_runs"]
        if a!=b:
            decided.append(((a>b)==(r["away_winrate_decided"]>.5),
                            (r["away_winrate_decided"]-int(a>b))**2))
        for side,other in (("away","home"),("home","away")):
            t=team(r[side]);score=r[f"actual_{side}_runs"];opponent=r[f"actual_{other}_runs"]
            t["games"]+=1;t["actual_w"]+=int(score>opponent);t["actual_l"]+=int(score<opponent);t["actual_d"]+=int(score==opponent)
            t["expected_w"]+=r[f"{side}_win_probability"];t["expected_l"]+=r[f"{other}_win_probability"];t["expected_d"]+=r["draw_probability"]
            t["actual_runs"]+=score;t["expected_runs"]+=r[f"{side}_mean_runs"]
    rows=sorted(teams.values(),key=lambda t:t['actual_w']/(t['actual_w']+t['actual_l']),reverse=True)
    for t in rows:
        t["win_error"]=t["expected_w"]-t["actual_w"]
    return {"teams":rows,"actual_games":len(results),"decided_games":len(decided),
            "game_accuracy":sum(x[0] for x in decided)/len(decided),
            "brier_decided":sum(x[1] for x in decided)/len(decided),
            "season_wins_mae":sum(abs(t["win_error"]) for t in rows)/len(rows),
            "actual_mean_runs":sum(t["actual_runs"] for t in rows)/(len(results)*2),
            "expected_mean_runs":sum(t["expected_runs"] for t in rows)/(len(results)*2)}


def run(season,n_games,workers,output_dir,history_dir=DEFAULT_HISTORY_DIR,csv_dir=OUTPUT_DB_READY_DIR,seed=42):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    raw=(Path(history_dir)/f"{season}.json").read_bytes();history=json.loads(raw)
    if history.get('reconciliation',{}).get('passed') is not True:
        raise ValueError('타자·투수 기록과 실제 스코어 합계를 대조한 데이터가 필요합니다. 다시 수집하세요.')
    fixtures=prepare_fixtures(history,history_dir)
    counts=defaultdict(int)
    for g in fixtures:
        counts[g["AWAY_NM"]]+=1;counts[g["HOME_NM"]]+=1
    if len(fixtures)!=720 or len(counts)!=10 or any(n!=144 for n in counts.values()):
        raise ValueError(f"144경기 전체 일정이 아닙니다: {len(fixtures)}경기, 팀별 {dict(counts)}")
    prior,hashes=read_prior(season,csv_dir)
    inputs=SeasonInputs(history,prior)
    jobs=[]
    for g in fixtures:
        a,b,audit=inputs.fixture(g)
        gid_seed=(seed+int(hashlib.sha256(g['G_ID'].encode()).hexdigest()[:8],16))%(2**32)
        jobs.append((g,a,b,audit,n_games,gid_seed))
    config={"season":season,"n_games_per_fixture":n_games,"seed":seed,"workers":workers,
            "history_sha256":hashlib.sha256(raw).hexdigest(),"prior_csv_hashes":hashes,
            "prior_season":season-1,"prior_strength":30,"engine":"MatchSimulator (cached fixed-lineup events)",
            "max_innings":11 if season>=2025 else 12,"bullpen_enabled":False,
            "rules_source":"https://www.koreabaseball.com/MediaNews/Notice/View.aspx?bdSe=11416",
            "date_rule":"same-day games excluded, including earlier doubleheader game",
            "created_at":datetime.now(timezone.utc).isoformat()}
    (output_dir/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    results=[]
    # Append complete per-game results so a long execution remains inspectable.
    with (output_dir/'games.jsonl').open('w',encoding='utf-8') as stream:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i,result in enumerate(pool.map(_simulate_job,jobs,chunksize=1),1):
                results.append(result);stream.write(json.dumps(result,ensure_ascii=False)+'\n');stream.flush()
                if i%20==0:print(f"전체 시즌 시뮬레이션 {i}/720경기",flush=True)
    summary=summarize(results)
    (output_dir/'summary.json').write_text(json.dumps(config|summary,ensure_ascii=False,indent=2),encoding='utf-8')
    text=f"# {season}년 144경기 전체 일정 과거 시점 검증\n\n"
    text+=f"실제 {len(results)}경기, 경기마다 {n_games:,}회 반복. 모든 팀 144경기.\n\n"
    text+=f"정규 9이닝, 최대 {config['max_innings']}회. 2025년부터 적용된 정규시즌 11회 한도를 사용합니다.\n\n"
    text+=f"- 개별 경기 승리 팀 적중률: {summary['game_accuracy']:.2%} (실제 무승부 제외)\n"
    text+=f"- 시즌 승수 평균 절대 오차: {summary['season_wins_mae']:.2f}승\n"
    text+=f"- 평균 득점: 실제 {summary['actual_mean_runs']:.3f} / 모형 {summary['expected_mean_runs']:.3f}\n\n"
    text+="| 팀 | 경기 | 실제 승 | 예상 승 | 차이 |\n|---|---:|---:|---:|---:|\n"
    for t in summary['teams']:text+=f"| {t['team']} | {t['games']} | {t['actual_w']} | {t['expected_w']:.2f} | {t['win_error']:+.2f} |\n"
    text+="\n매 경기 날짜 이전의 당해 시즌 기록만 집계합니다. 개막 초반과 신인 표본은 이전 시즌 선수 또는 리그 평균을 30타석/타자 상당의 사전 표본으로 보완합니다. 경기별 실제 선발 타순과 선발투수가 경기 전에 알려져 있었다는 조건입니다. 경기 후 교체 선수의 성적과 상대 경기 결과는 입력하지 않습니다. 투수 보정은 기존 모형의 가중치 0.5를 사용하며 불펜 교체는 없습니다. 같은 날짜의 더블헤더 1차전도 2차전 입력에서 제외합니다.\n"
    text+="\n2025년 CSV에서는 2025년 행만 사용합니다. 2026년 시즌 전체 합계는 예측 입력에 사용하지 않습니다. 원본 파일 지문, 경기별 기준일·선수별 사용 표본·확률·시드·스코어 분포는 config.json과 games.jsonl에 저장합니다.\n"
    (output_dir/'report.md').write_text(text,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return summary


def main():
    parser=argparse.ArgumentParser(description="실제 720경기를 경기일 이전 기록으로 각각 검증")
    parser.add_argument('--season',type=int,required=True)
    parser.add_argument('--games',type=int,default=10000)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--history-dir',type=Path,default=DEFAULT_HISTORY_DIR)
    parser.add_argument('--csv-dir',type=Path,default=OUTPUT_DB_READY_DIR)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.games<=10000 or not 1<=args.workers<=8:
        parser.error('반복 횟수는 1~10000, 작업 수는 1~8입니다.')
    run(args.season,args.games,args.workers,args.output_dir,args.history_dir,args.csv_dir,args.seed)


if __name__=='__main__':main()
