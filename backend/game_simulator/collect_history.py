"""Collect KBO regular-season daily lines; never infer past stats from annual totals.

Annual CSVs provide player IDs ONLY. Team membership is recovered from that day's
official schedule, so later trades/current profiles do not decide historical teams.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import date, datetime, timezone
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from threading import local
import requests

from .historical import DEFAULT_HISTORY_DIR
from .simulator_main import OUTPUT_DB_READY_DIR

BASE = "https://www.koreabaseball.com"
PREFIX = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$"
_sessions = local()


class DailyPage(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.form, self.selected, self.rows = {}, {}, []
        self.select = self.option = self.row = self.cell = None
        self.option_selected = False
        self.in_table = False
        self.feed(text)
        # The site's malformed conditional comment can hide the first hidden
        # input from HTMLParser. Preserve the ASP.NET state exactly as delivered.
        for raw in re.findall(r"<input\b[^>]*>", text, re.I):
            name = re.search(r'\bname="([^"]*)"',raw)
            value = re.search(r'\bvalue="([^"]*)"',raw)
            if name and value:
                self.form[unescape(name[1])] = unescape(value[1])

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and a.get("name"):
            self.form[a["name"]] = a.get("value", "")
        elif tag == "select":
            self.select = a.get("name")
        elif tag == "option" and self.select:
            self.option = a.get("value", "")
            self.option_selected = "selected" in a
            if self.select not in self.form or self.option_selected:
                self.form[self.select] = self.option
            if self.option_selected:
                self.selected[self.select] = self.option
        elif tag == "table":
            self.in_table = True
        elif tag == "tr" and self.in_table:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, text):
        if self.cell is not None:
            self.cell.append(text)

    def handle_endtag(self, tag):
        if tag == "select":
            self.select = None
        elif tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            self.in_table = False


def _integer(text):
    text = text.replace(",", "").strip()
    if not re.fullmatch(r"\d+", text):
        raise ValueError(f"누적 횟수로 해석할 수 없습니다: {text!r}")
    return int(text)


def _outs(text):
    text = text.strip()
    if text == "0":
        return 0
    m = re.fullmatch(r"(?:(\d+)\s+)?([12])/3", text)
    if m:
        return int(m[1] or 0)*3 + int(m[2])
    if re.fullmatch(r"\d+", text):
        return int(text)*3
    raise ValueError(f"이닝 표기를 해석할 수 없습니다: {text!r}")


def parse_daily(text, season, kind, player_id, player_name):
    page = DailyPage(text)
    if page.selected.get(PREFIX+"ddlYear") != str(season) or page.selected.get(PREFIX+"ddlSeries") != "0":
        raise ValueError("공식 페이지가 요청한 시즌/정규시즌 선택을 반영하지 않았습니다.")
    result = []
    counts = defaultdict(int)
    for cells in page.rows:
        if not cells or not re.fullmatch(r"\d{2}\.\d{2}", cells[0]):
            continue
        played = date(season, *map(int, cells[0].split("."))).isoformat()
        counts[played] += 1
        common = {"player_id": str(player_id), "player_name": player_name, "game_date": played,
                  "appearance": counts[played], "opponent": cells[1]}
        if kind == "hitters":
            if len(cells) != 18:
                raise ValueError(f"타자 일자별 표의 열 수가 바뀌었습니다: {len(cells)}")
            keys = {"pa":3, "ab":4, "r":5, "h":6, "double_hit":7, "triple_hit":8,
                    "hr":9, "bb":13, "hbp":14}
            result.append(common | {key:_integer(cells[index]) for key,index in keys.items()})
        else:
            if len(cells) != 15:
                raise ValueError(f"투수 일자별 표의 열 수가 바뀌었습니다: {len(cells)}")
            keys = {"tbf":5, "h":7, "hr":8, "bb":9, "hbp":10, "so":11, "er":13}
            result.append(common | {key:_integer(cells[index]) for key,index in keys.items()}
                          | {"outs":_outs(cells[6]), "gs":int(cells[2] == "선발")})
    return result


def request(url, data=None):
    if not hasattr(_sessions, "session"):
        _sessions.session = requests.Session()
        _sessions.session.headers.update({"User-Agent":"Mozilla/5.0", "Referer":BASE+"/",
                                          "X-Requested-With":"XMLHttpRequest"})
    for attempt in range(3):
        try:
            response = _sessions.session.request("POST" if data is not None else "GET",
                                                  url, data=data, timeout=25)
            response.raise_for_status()
            return response.content.decode("utf-8-sig")
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(attempt+1)


def fetch_daily(season, kind, pid, cache_dir, refresh=False):
    cache = cache_dir / kind / f"{pid}.html"
    if cache.exists() and not refresh:
        return cache.read_text(encoding="utf-8")
    detail = "HitterDetail" if kind == "hitters" else "PitcherDetail"
    url = f"{BASE}/Record/Player/{detail}/Daily.aspx?playerId={pid}"
    page = DailyPage(request(url))
    form = page.form | {PREFIX+"ddlYear":str(season), PREFIX+"ddlSeries":"0",
                        "__EVENTTARGET":PREFIX+"ddlSeries", "__EVENTARGUMENT":""}
    text = request(url, form)
    # Check selection before keeping a response as a reusable cache.
    chosen = DailyPage(text).selected
    if chosen.get(PREFIX+"ddlYear") != str(season) or chosen.get(PREFIX+"ddlSeries") != "0":
        raise ValueError(f"{kind} {pid}: 요청 시즌/정규시즌 조회 실패")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return text


def discover_player_ids(season,kind,cache_dir,refresh=False):
    """An old local CSV may miss players who debuted later in the year."""
    cache=cache_dir/f"{kind}-player-ids.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding='utf-8'))
    if kind=='hitters':
        from crolling import crol_Hitter as crawler
    else:
        from crolling import crol_Pitcher as crawler
    session=requests.Session()
    ids={}
    for team,code in crawler.TEAM_CODES.items():
        rows=crawler.crawl_one_page_group(session,crawler.URLS['basic1'],str(season),code,
                                           series='0',sleep_sec=.05)
        for r in rows:
            if r.get('player_id'):
                ids[r['player_id']]=r['선수명'].strip()
        print(f"공식 선수 목록 {kind} {team}: 누적 {len(ids)}명",flush=True)
    if not ids:
        raise ValueError('공식 시즌 참가 선수 목록이 비어 있습니다.')
    cache.parent.mkdir(parents=True,exist_ok=True)
    cache.write_text(json.dumps(ids,ensure_ascii=False),encoding='utf-8')
    return ids


def reconcile(lines,games):
    """Independently reconcile both sides of all events before publishing data."""
    checks={}
    for key in ('h','hr','bb','hbp'):
        batting=sum(r[key] for r in lines['hitters'])
        pitching=sum(r[key] for r in lines['pitchers'])
        if batting!=pitching:
            raise ValueError(f'선수 기록 누락 또는 불일치: {key} 타자 {batting}, 투수 {pitching}')
        checks[key]=batting
    pa=sum(r['pa'] for r in lines['hitters'])
    tbf=sum(r['tbf'] for r in lines['pitchers'])
    if pa!=tbf:
        raise ValueError(f'타석/상대 타자 수 불일치: {pa}/{tbf}')
    runs=sum(r['r'] for r in lines['hitters'])
    scored=sum(int(g['T_SCORE_CN'])+int(g['B_SCORE_CN']) for g in games)
    if runs!=scored:
        raise ValueError(f'선수 득점/최종 스코어 불일치: {runs}/{scored}')
    if len(games)!=len({g['G_ID'] for g in games}):
        raise ValueError('중복된 공식 경기 ID가 있습니다.')
    return checks|{'pa_tbf':pa,'runs':runs,'games':len(games),'passed':True}


def collect(as_of, csv_dir=OUTPUT_DB_READY_DIR, output_dir=DEFAULT_HISTORY_DIR, refresh=False):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    csv_dir, output_dir = Path(csv_dir), Path(output_dir)
    cache_dir = output_dir / "raw" / str(as_of.year)
    jobs = []
    for kind, filename in (("hitters","player_hitter_stats.csv"), ("pitchers","player_pitcher_stats.csv")):
        with (csv_dir/filename).open(encoding="utf-8-sig", newline="") as handle:
            ids = {r["player_id"]:r["player_name"] for r in csv.DictReader(handle)
                   if r["season_year"] == str(as_of.year)}
        if not ids:
            raise ValueError(f"{as_of.year}년 선수 ID 목록이 없습니다.")
        ids.update(discover_player_ids(as_of.year,kind,cache_dir,refresh))
        jobs.extend((kind,pid,name) for pid,name in sorted(ids.items()))
    lines = {"hitters":[], "pitchers":[]}
    failures = []

    def load(job):
        kind,pid,name = job
        text = fetch_daily(as_of.year, kind, pid, cache_dir, refresh)
        return kind,parse_daily(text, as_of.year, kind, pid, name)

    # Bounded readers; retries/cache make an interrupted collection resumable.
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(load, job):job for job in jobs}
        for i,future in enumerate(as_completed(pending), 1):
            try:
                kind,rows = future.result()
                lines[kind].extend(r for r in rows if r["game_date"] < as_of.isoformat())
            except Exception as exc:
                failures.append({"job":pending[future], "error":str(exc)})
            if i >= 8 and len(failures) == i:
                for queued in pending:
                    queued.cancel()
                break
            if i % 25 == 0 or i == len(jobs):
                print(f"일자별 기록 {i}/{len(jobs)} · 실패 {len(failures)}", flush=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    if failures:
        (output_dir/f"{as_of.year}-collection-errors.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        raise ValueError(f"선수 {len(failures)}건 수집 실패. 완료 데이터는 교체하지 않았습니다.")

    schedules = {}
    dates = sorted({r["game_date"] for rows in lines.values() for r in rows})
    for i,day in enumerate(dates,1):
        cache = cache_dir/"schedule"/f"{day}.json"
        if cache.exists() and not refresh:
            payload = json.loads(cache.read_text(encoding="utf-8"))
        else:
            payload = json.loads(request(BASE+"/ws/Main.asmx/GetKboGameList",
                                         {"leId":"1","srId":"0","date":day.replace("-","")}))
            if str(payload.get("code")) != "100":
                raise ValueError(f"{day}: 공식 경기 목록 조회 실패")
            cache.parent.mkdir(parents=True,exist_ok=True)
            cache.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8")
        games = [g for g in payload["game"] if int(g["SR_ID"]) == 0 and str(g["GAME_STATE_SC"]) == "3"]
        if any(g["G_DT"] != day.replace("-","") for g in games):
            raise ValueError("공식 경기 목록의 날짜가 요청 날짜와 다릅니다.")
        schedules[day] = games
        if i % 30 == 0:
            print(f"소속팀 확인 {i}/{len(dates)}일",flush=True)
    for rows in lines.values():
        for r in rows:
            teams = set()
            for g in schedules[r["game_date"]]:
                if r["opponent"] == g["HOME_NM"]:
                    teams.add(g["AWAY_NM"])
                if r["opponent"] == g["AWAY_NM"]:
                    teams.add(g["HOME_NM"])
            if len(teams) != 1:
                raise ValueError(f"{r['game_date']} {r['player_name']}: 당시 소속팀을 확인할 수 없습니다.")
            r["team_name"] = teams.pop()
    games=[g for day in dates for g in schedules[day]]
    reconciliation=reconcile(lines,games)
    result = {"schema_version":1,"complete":True,"season":as_of.year,
              "coverage_start":f"{as_of.year}-01-01","coverage_before":as_of.isoformat(),
              "source":BASE+"/Record/Player/ (regular-season daily lines and official schedules)",
              "collected_at":datetime.now(timezone.utc).isoformat(),
              "player_ids_requested":len(jobs), **lines,
              "games":games,"reconciliation":reconciliation}
    target = output_dir/f"{as_of.year}.json"
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False),encoding="utf-8")
    temp.replace(target)
    print(f"저장 완료: {target} · 타자 {len(lines['hitters'])} / 투수 {len(lines['pitchers'])}",flush=True)
    return target


def main():
    parser = argparse.ArgumentParser(description="기준일 당일을 제외한 KBO 정규시즌 경기별 기록 수집")
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--csv-dir", type=Path, default=OUTPUT_DB_READY_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_HISTORY_DIR)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    collect(args.as_of,args.csv_dir,args.output_dir,args.refresh)


if __name__ == "__main__":
    main()
