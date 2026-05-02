"""
kbo_db_crawler.py

목적:
- KBO 공식 사이트 + KBReport 데이터를 크롤링
- DB 적재용 CSV로 저장
- KBO 공식 사이트 데이터를 기본 기준으로 사용
- KBReport는 고급 지표 보완용 CSV로 저장

설치:
pip install requests beautifulsoup4 lxml pandas selenium webdriver-manager

실행:
python kbo_db_crawler.py

출력 폴더:
./output_db_ready/
"""

import csv
import re
import time
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlencode

import pandas as pd
import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, UnexpectedAlertPresentException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# ============================================================
# 공통 설정
# ============================================================

OUTPUT_DIR = Path("output_db_ready")
OUTPUT_DIR.mkdir(exist_ok=True)

START_YEAR = 2021
END_YEAR = 2021

SERIES_REGULAR = "0"

KBO_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.koreabaseball.com/",
}

TEAM_CODES = {
    "LG": "LG",
    "한화": "HH",
    "SSG": "SK",
    "삼성": "SS",
    "NC": "NC",
    "KT": "KT",
    "롯데": "LT",
    "KIA": "HT",
    "두산": "OB",
    "키움": "WO",
}

TEAM_NAME_MAP = {
    "Hero": "키움",
    "키움": "키움",
    "KT": "KT",
    "NC": "NC",
    "삼성": "삼성",
    "두산": "두산",
    "LG": "LG",
    "SSG": "SSG",
    "SK": "SSG",
    "롯데": "롯데",
    "한화": "한화",
    "KIA": "KIA",
}

VALID_TEAM_NAMES = {"LG", "한화", "SSG", "삼성", "NC", "KT", "롯데", "KIA", "두산", "키움"}


# ============================================================
# 공통 정제 함수
# ============================================================

def clean_text(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    if value in {"", "-", "nan", "None"}:
        return None
    return value


def clean_player_name(value):
    value = clean_text(value)
    if value is None:
        return None
    return value.replace("*", "").strip()


def clean_team_name(value):
    value = clean_text(value)
    if value is None:
        return None
    return TEAM_NAME_MAP.get(value, value)


def to_int(value):
    value = clean_text(value)
    if value is None:
        return None
    value = value.replace(",", "")
    try:
        return int(float(value))
    except ValueError:
        return None


def to_float(value):
    value = clean_text(value)
    if value is None:
        return None
    value = value.replace(",", "").replace("%", "")
    try:
        return float(value)
    except ValueError:
        return None


def normalize_percent(value):
    """
    12.3 또는 12.3% 형태를 12.3으로 저장.
    DB에서 비율을 0.123으로 쓸지 12.3으로 쓸지는 백엔드 정책에 맞추면 됨.
    """
    return to_float(value)


def extract_player_id(link: Optional[str]) -> Optional[str]:
    if not link:
        return None
    match = re.search(r"playerId=(\d+)", link)
    return match.group(1) if match else None


def save_csv(rows: List[dict], filename: str, columns: Optional[List[str]] = None):
    path = OUTPUT_DIR / filename

    if not rows:
        print(f"[WARN] 저장할 데이터 없음: {filename}")
        return

    if columns is None:
        columns = list(rows[0].keys())

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"[SAVE] {path} rows={len(rows)}")


# ============================================================
# KBO 공식 사이트 공통 크롤러
# ============================================================

class KBOOfficialCrawler:
    FIELD_NAMES = {
        "season": "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$ddlSeason$ddlSeason",
        "series": "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$ddlSeries$ddlSeries",
        "team": "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$ddlTeam$ddlTeam",
        "position": "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$ddlPos$ddlPos",
        "hf_page": "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$hfPage",
    }

    PAGER_TARGET_PREFIX = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$ucPager$btnNo"

    def get_soup(self, session: requests.Session, url: str) -> BeautifulSoup:
        last_error = None

        for attempt in range(1, 6):
            try:
                resp = session.get(url, headers=KBO_HEADERS, timeout=60)
                resp.raise_for_status()
                resp.encoding = "utf-8"
                return BeautifulSoup(resp.text, "lxml")

            except RequestException as e:
                last_error = e
                print(f"[RETRY] GET 실패 {attempt}/5: {url} / {e}")
                time.sleep(3 * attempt)

        raise last_error

    def extract_form_fields(self, soup: BeautifulSoup) -> dict:
        form = soup.find("form")
        if form is None:
            raise RuntimeError("form 태그를 찾지 못했습니다.")

        data = {}

        for tag in form.find_all("input"):
            name = tag.get("name")
            if not name:
                continue

            input_type = (tag.get("type") or "").lower()
            if input_type in {"checkbox", "radio"}:
                if tag.has_attr("checked"):
                    data[name] = tag.get("value", "on")
            else:
                data[name] = tag.get("value", "")

        for tag in form.find_all("select"):
            name = tag.get("name")
            if not name:
                continue

            selected = tag.find("option", selected=True)
            if selected is not None:
                data[name] = selected.get("value", "")
            else:
                first = tag.find("option")
                data[name] = first.get("value", "") if first else ""

        for tag in form.find_all("textarea"):
            name = tag.get("name")
            if name:
                data[name] = tag.text or ""

        return data

    def extract_updatepanel_html(self, response_text: str) -> str:
        marker = "|updatePanel|"
        idx = response_text.find(marker)
        if idx == -1:
            return response_text

        after = response_text[idx + len(marker):]
        first_sep = after.find("|")
        if first_sep == -1:
            return response_text

        content_start = first_sep + 1
        end_markers = [
            "|0|hiddenField|__EVENTTARGET|",
            "|hiddenField|__EVENTTARGET|",
            "|0|hiddenField|__VIEWSTATE|",
            "|hiddenField|__VIEWSTATE|",
        ]

        end_positions = []
        for end_marker in end_markers:
            pos = after.find(end_marker, content_start)
            if pos != -1:
                end_positions.append(pos)

        if end_positions:
            return after[content_start:min(end_positions)].strip()

        return after[content_start:].strip()

    def response_to_soup(self, response_text: str) -> BeautifulSoup:
        html = self.extract_updatepanel_html(response_text)
        return BeautifulSoup(html, "lxml")

    def postback(
        self,
        session: requests.Session,
        url: str,
        current_soup: BeautifulSoup,
        event_target: str,
        overrides: Optional[dict] = None,
    ) -> BeautifulSoup:
        payload = self.extract_form_fields(current_soup)
        payload["__EVENTTARGET"] = event_target
        payload["__EVENTARGUMENT"] = ""

        if overrides:
            payload.update(overrides)

        last_error = None

        for attempt in range(1, 6):
            try:
                resp = session.post(url, headers=KBO_HEADERS, data=payload, timeout=60)
                resp.raise_for_status()
                resp.encoding = "utf-8"
                return self.response_to_soup(resp.text)

            except RequestException as e:
                last_error = e
                print(f"[RETRY] POST 실패 {attempt}/5: {url} / {e}")
                time.sleep(3 * attempt)

        raise last_error

    def change_select(self, session, url, soup, field_name, value):
        form_data = self.extract_form_fields(soup)
        if field_name not in form_data:
            return soup

        return self.postback(
            session=session,
            url=url,
            current_soup=soup,
            event_target=field_name,
            overrides={field_name: value},
        )

    def apply_filters(
        self,
        session: requests.Session,
        url: str,
        season: str,
        series: str = "0",
        team_code: Optional[str] = None,
        position: Optional[str] = None,
    ) -> BeautifulSoup:
        soup = self.get_soup(session, url)

        soup = self.change_select(session, url, soup, self.FIELD_NAMES["season"], season)
        soup = self.change_select(session, url, soup, self.FIELD_NAMES["series"], series)

        if team_code is not None:
            soup = self.change_select(session, url, soup, self.FIELD_NAMES["team"], team_code)

        if position:
            soup = self.change_select(session, url, soup, self.FIELD_NAMES["position"], position)

        return soup

    def go_to_page(self, session, url, soup, page_no):
        form_data = self.extract_form_fields(soup)
        overrides = {}

        if self.FIELD_NAMES["hf_page"] in form_data:
            overrides[self.FIELD_NAMES["hf_page"]] = str(page_no)

        return self.postback(
            session=session,
            url=url,
            current_soup=soup,
            event_target=f"{self.PAGER_TARGET_PREFIX}{page_no}",
            overrides=overrides,
        )

    def extract_available_page_numbers(self, soup):
        paging = soup.find("div", class_="paging")
        if paging is None:
            return []

        pages = set()
        for a in paging.find_all("a"):
            text = a.get_text(strip=True)
            if text.isdigit():
                pages.add(int(text))
        return sorted(pages)

    def find_table(self, soup, required_keywords: List[str]):
        candidates = []

        for table in soup.find_all("table"):
            text = table.get_text(" ", strip=True)
            if all(keyword in text for keyword in required_keywords):
                candidates.append((len(table.find_all("tr")), table))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def parse_table(self, table, season, team_code=None, record_type=None):
        headers = []
        thead = table.find("thead")
        if thead:
            headers = [th.get_text(" ", strip=True) for th in thead.find_all("th")]
        else:
            headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]

        tbody = table.find("tbody") or table
        rows = []

        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue

            cols = [td.get_text(" ", strip=True) for td in tds]
            row = dict(zip(headers, cols)) if headers and len(headers) == len(cols) else {
                f"col_{i + 1}": value for i, value in enumerate(cols)
            }

            if len(tds) > 1:
                link_tag = tds[1].find("a")
                link = link_tag.get("href") if link_tag and link_tag.get("href") else None
            else:
                link = None

            row["player_link"] = link
            row["player_id"] = extract_player_id(link)
            row["season_year"] = season

            if team_code:
                row["team_code"] = team_code

            if record_type:
                row["record_type"] = record_type

            rows.append(row)

        return rows

    def crawl_kbo_player_table(
        self,
        url: str,
        season: str,
        team_code: str,
        required_keywords: List[str],
        sleep_sec: float = 1.0,
    ):
        session = requests.Session()
        soup = self.apply_filters(session, url, season, SERIES_REGULAR, team_code=team_code)

        table = self.find_table(soup, required_keywords)
        if table is None:
            raise RuntimeError(f"테이블을 찾지 못했습니다: {url}")

        all_rows = []
        seen = set()

        def add_rows(rows):
            for row in rows:
                key = (
                    row.get("season_year"),
                    row.get("player_id"),
                    row.get("선수명"),
                    row.get("팀명"),
                )
                if key not in seen:
                    seen.add(key)
                    all_rows.append(row)

        add_rows(self.parse_table(table, season, team_code=team_code))

        for page_no in self.extract_available_page_numbers(soup):
            if page_no == 1:
                continue

            time.sleep(sleep_sec)
            soup = self.go_to_page(session, url, soup, page_no)
            table = self.find_table(soup, required_keywords)
            if table is None:
                continue
            add_rows(self.parse_table(table, season, team_code=team_code))

        return all_rows

    def crawl_kbo_team_table(
        self,
        url: str,
        season: str,
        record_type: str,
        required_keywords: List[str],
        sleep_sec: float = 1.0,
    ):
        session = requests.Session()
        soup = self.apply_filters(session, url, season, SERIES_REGULAR)

        table = self.find_table(soup, required_keywords)
        if table is None:
            raise RuntimeError(f"테이블을 찾지 못했습니다: {url}")

        all_rows = []
        seen = set()

        def add_rows(rows):
            for row in rows:
                key = (row.get("season_year"), row.get("팀명"), record_type)
                if key not in seen:
                    seen.add(key)
                    all_rows.append(row)

        add_rows(self.parse_table(table, season, record_type=record_type))

        for page_no in self.extract_available_page_numbers(soup):
            if page_no == 1:
                continue

            time.sleep(sleep_sec)
            soup = self.go_to_page(session, url, soup, page_no)
            table = self.find_table(soup, required_keywords)
            if table is None:
                continue
            add_rows(self.parse_table(table, season, record_type=record_type))

        return all_rows


# ============================================================
# KBO 공식 데이터 DB-ready 변환
# ============================================================

def convert_kbo_hitter_row(row):
    return {
        "season_year": to_int(row.get("season_year")),
        "player_id": clean_text(row.get("player_id")),
        "player_name": clean_player_name(row.get("선수명")),
        "team_name": clean_team_name(row.get("팀명")),
        "team_code": clean_text(row.get("team_code")),
        "rank_no": to_int(row.get("순위")),
        "avg": to_float(row.get("AVG")),
        "g": to_int(row.get("G")),
        "pa": to_int(row.get("PA")),
        "ab": to_int(row.get("AB")),
        "r": to_int(row.get("R")),
        "h": to_int(row.get("H")),
        "double_hit": to_int(row.get("2B")),
        "triple_hit": to_int(row.get("3B")),
        "hr": to_int(row.get("HR")),
        "tb": to_int(row.get("TB")),
        "rbi": to_int(row.get("RBI")),
        "sac": to_int(row.get("SAC")),
        "sf": to_int(row.get("SF")),
        "bb": to_int(row.get("BB")),
        "ibb": to_int(row.get("IBB")),
        "hbp": to_int(row.get("HBP")),
        "so": to_int(row.get("SO")),
        "gdp": to_int(row.get("GDP")),
        "slg": to_float(row.get("SLG")),
        "obp": to_float(row.get("OBP")),
        "ops": to_float(row.get("OPS")),
        "mh": to_int(row.get("MH")),
        "risp": to_float(row.get("RISP")),
        "ph_ba": to_float(row.get("PH-BA")),
        "xbh": to_int(row.get("XBH")),
        "go_count": to_int(row.get("GO")),
        "ao_count": to_int(row.get("AO")),
        "go_ao": to_float(row.get("GO/AO")),
        "gw_rbi": to_int(row.get("GW RBI")),
        "bb_k": to_float(row.get("BB/K")),
        "p_pa": to_float(row.get("P/PA")),
        "isop": to_float(row.get("ISOP")),
        "xr": to_float(row.get("XR")),
        "gpa": to_float(row.get("GPA")),
    }


def convert_kbo_pitcher_row(row):
    return {
        "season_year": to_int(row.get("season_year")),
        "player_id": clean_text(row.get("player_id")),
        "player_name": clean_player_name(row.get("선수명")),
        "team_name": clean_team_name(row.get("팀명")),
        "team_code": clean_text(row.get("team_code")),
        "rank_no": to_int(row.get("순위")),
        "era": to_float(row.get("ERA")),
        "g": to_int(row.get("G")),
        "w": to_int(row.get("W")),
        "l": to_int(row.get("L")),
        "sv": to_int(row.get("SV")),
        "hld": to_int(row.get("HLD")),
        "wpct": to_float(row.get("WPCT")),
        "ip": clean_text(row.get("IP")),
        "h": to_int(row.get("H")),
        "hr": to_int(row.get("HR")),
        "bb": to_int(row.get("BB")),
        "hbp": to_int(row.get("HBP")),
        "so": to_int(row.get("SO")),
        "r": to_int(row.get("R")),
        "er": to_int(row.get("ER")),
        "whip": to_float(row.get("WHIP")),
        "cg": to_int(row.get("CG")),
        "sho": to_int(row.get("SHO")),
        "qs": to_int(row.get("QS")),
        "bsv": to_int(row.get("BSV")),
        "tbf": to_int(row.get("TBF")),
        "np": to_int(row.get("NP")),
        "avg": to_float(row.get("AVG")),
        "double_hit": to_int(row.get("2B")),
        "triple_hit": to_int(row.get("3B")),
        "sac": to_int(row.get("SAC")),
        "sf": to_int(row.get("SF")),
        "ibb": to_int(row.get("IBB")),
        "wp": to_int(row.get("WP")),
        "bk": to_int(row.get("BK")),
        "gs": to_int(row.get("GS")),
        "wgs": to_int(row.get("Wgs")),
        "wgr": to_int(row.get("Wgr")),
        "gf": to_int(row.get("GF")),
        "svo": to_int(row.get("SVO")),
        "ts": to_int(row.get("TS")),
        "gdp": to_int(row.get("GDP")),
        "go_count": to_int(row.get("GO")),
        "ao_count": to_int(row.get("AO")),
        "go_ao": to_float(row.get("GO/AO")),
        "babip": to_float(row.get("BABIP")),
        "p_g": to_float(row.get("P/G")),
        "p_ip": to_float(row.get("P/IP")),
        "k9": to_float(row.get("K/9")),
        "bb9": to_float(row.get("BB/9")),
        "k_bb": to_float(row.get("K/BB")),
        "obp": to_float(row.get("OBP")),
        "slg": to_float(row.get("SLG")),
        "ops": to_float(row.get("OPS")),
    }


def convert_kbo_defense_row(row):
    return {
        "season_year": to_int(row.get("season_year")),
        "player_id": clean_text(row.get("player_id")),
        "player_name": clean_player_name(row.get("선수명")),
        "team_name": clean_team_name(row.get("팀명")),
        "team_code": clean_text(row.get("team_code")),
        "rank_no": to_int(row.get("순위")),
        "position": clean_text(row.get("POS")),
        "g": to_int(row.get("G")),
        "gs": to_int(row.get("GS")),
        "ip": clean_text(row.get("IP")),
        "e": to_int(row.get("E")),
        "pko": to_int(row.get("PKO")),
        "po": to_int(row.get("PO")),
        "a": to_int(row.get("A")),
        "dp": to_int(row.get("DP")),
        "fpct": to_float(row.get("FPCT")),
        "pb": to_int(row.get("PB")),
        "sb": to_int(row.get("SB")),
        "cs": to_int(row.get("CS")),
        "cs_rate": normalize_percent(row.get("CS%")),
    }


def convert_kbo_runner_row(row):
    return {
        "season_year": to_int(row.get("season_year")),
        "player_id": clean_text(row.get("player_id")),
        "player_name": clean_player_name(row.get("선수명")),
        "team_name": clean_team_name(row.get("팀명")),
        "team_code": clean_text(row.get("team_code")),
        "rank_no": to_int(row.get("순위")),
        "g": to_int(row.get("G")),
        "sba": to_int(row.get("SBA")),
        "sb": to_int(row.get("SB")),
        "cs": to_int(row.get("CS")),
        "sb_rate": normalize_percent(row.get("SB%")),
        "oob": to_int(row.get("OOB")),
        "pko": to_int(row.get("PKO")),
    }


def convert_kbo_team_row(row):
    # 팀 타자/투수/수비/주루 모두 대응할 수 있도록 넓게 변환
    return {
        "season_year": to_int(row.get("season_year")),
        "team_name": clean_team_name(row.get("팀명")),
        "record_type": clean_text(row.get("record_type")),
        "rank_no": to_int(row.get("순위")),
        "avg": to_float(row.get("AVG")),
        "era": to_float(row.get("ERA")),
        "g": to_int(row.get("G")),
        "pa": to_int(row.get("PA")),
        "ab": to_int(row.get("AB")),
        "r": to_int(row.get("R")),
        "h": to_int(row.get("H")),
        "double_hit": to_int(row.get("2B")),
        "triple_hit": to_int(row.get("3B")),
        "hr": to_int(row.get("HR")),
        "tb": to_int(row.get("TB")),
        "rbi": to_int(row.get("RBI")),
        "sac": to_int(row.get("SAC")),
        "sf": to_int(row.get("SF")),
        "bb": to_int(row.get("BB")),
        "ibb": to_int(row.get("IBB")),
        "hbp": to_int(row.get("HBP")),
        "so": to_int(row.get("SO")),
        "gdp": to_int(row.get("GDP")),
        "slg": to_float(row.get("SLG")),
        "obp": to_float(row.get("OBP")),
        "ops": to_float(row.get("OPS")),
        "mh": to_int(row.get("MH")),
        "risp": to_float(row.get("RISP")),
        "ph_ba": to_float(row.get("PH-BA")),
        "w": to_int(row.get("W")),
        "l": to_int(row.get("L")),
        "sv": to_int(row.get("SV")),
        "hld": to_int(row.get("HLD")),
        "wpct": to_float(row.get("WPCT")),
        "ip": clean_text(row.get("IP")),
        "er": to_int(row.get("ER")),
        "whip": to_float(row.get("WHIP")),
        "cg": to_int(row.get("CG")),
        "sho": to_int(row.get("SHO")),
        "qs": to_int(row.get("QS")),
        "bsv": to_int(row.get("BSV")),
        "tbf": to_int(row.get("TBF")),
        "np": to_int(row.get("NP")),
        "wp": to_int(row.get("WP")),
        "bk": to_int(row.get("BK")),
        "e": to_int(row.get("E")),
        "pko": to_int(row.get("PKO")),
        "po": to_int(row.get("PO")),
        "a": to_int(row.get("A")),
        "dp": to_int(row.get("DP")),
        "fpct": to_float(row.get("FPCT")),
        "pb": to_int(row.get("PB")),
        "sb": to_int(row.get("SB")),
        "cs": to_int(row.get("CS")),
        "cs_rate": normalize_percent(row.get("CS%")),
        "sba": to_int(row.get("SBA")),
        "sb_rate": normalize_percent(row.get("SB%")),
        "oob": to_int(row.get("OOB")),
    }


def convert_team_rank_row(row):
    return {
        "season_year": to_int(row.get("season_year")),
        "team_name": clean_team_name(row.get("팀명")),
        "rank_no": to_int(row.get("순위")),
        "games": to_int(row.get("경기")),
        "wins": to_int(row.get("승")),
        "losses": to_int(row.get("패")),
        "draws": to_int(row.get("무")),
        "win_rate": to_float(row.get("승률")),
        "game_gap": clean_text(row.get("게임차")),
        "last10": clean_text(row.get("최근10경기")),
        "streak": clean_text(row.get("연속")),
        "home": clean_text(row.get("홈")),
        "away": clean_text(row.get("방문")),
        "series": clean_text(row.get("series")),
    }


def merge_by_key(row_groups: List[List[dict]], key_fields: List[str]) -> List[dict]:
    merged = {}

    for rows in row_groups:
        for row in rows:
            key = tuple(row.get(field) for field in key_fields)
            if key not in merged:
                merged[key] = {}
            merged[key].update(row)

    return list(merged.values())


def crawl_team_table_with_fallback(crawler, url, season, record_type, keyword_candidates):
    """KBO 팀 기록 Basic1/Basic2의 컬럼 차이를 고려해 탐색 키워드를 순차 시도한다."""
    last_error = None
    for keywords in keyword_candidates:
        try:
            return crawler.crawl_kbo_team_table(url, season, record_type, keywords)
        except Exception as e:
            last_error = e
            print(f"[WARN] {record_type} keyword retry failed {keywords}: {e}")
    raise RuntimeError(f"{record_type} 테이블을 찾지 못했습니다. 마지막 오류: {last_error}")


# ============================================================
# KBReport 크롤러
# ============================================================

class KBReportCrawler:
    BASE_URL = "http://www.kbreport.sbs"

    def __init__(self):
        self.driver = self._create_driver()

    def _create_driver(self):
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )

        return webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options,
        )

    def close(self):
        if self.driver:
            self.driver.quit()

    def build_url(self, endpoint, params=None, page=None):
        url = self.BASE_URL + endpoint
        if params:
            url = f"{url}?{urlencode(params)}"
        if page is not None and page > 1:
            url = f"{url}#/{page}"
        return url

    def clean_df(self, df):
        df.columns = [str(c).strip() for c in df.columns]
        return df.dropna(how="all").reset_index(drop=True)

    def get_table(self, url, table_index=0, wait_sec=2):
        try:
            self.driver.get(url)
            time.sleep(wait_sec)

            try:
                alert = self.driver.switch_to.alert
                print(f"[KBReport Alert] {alert.text}")
                alert.accept()
                raise ValueError("KBReport alert 발생")
            except NoAlertPresentException:
                pass

            html = self.driver.page_source
            tables = pd.read_html(StringIO(html))
            if not tables:
                raise ValueError(f"No tables found: {url}")
            return self.clean_df(tables[table_index])

        except UnexpectedAlertPresentException:
            try:
                alert = self.driver.switch_to.alert
                print(f"[Unexpected Alert] {alert.text}")
                alert.accept()
            except Exception:
                pass
            raise

    def get_all_pages(self, endpoint, params, key_columns, max_pages=50, rows=100, wait_sec=2):
        all_pages = []
        seen = set()

        params = params.copy()
        params["rows"] = rows

        for page in range(1, max_pages + 1):
            url = self.build_url(endpoint, params=params, page=page)

            try:
                df = self.get_table(url, wait_sec=wait_sec)
            except Exception as e:
                print(f"[KBReport 중단] endpoint={endpoint}, page={page}, error={e}")
                break

            if df.empty:
                break

            new_rows = []
            for _, row in df.iterrows():
                key = tuple(str(row.get(col, "")).strip() for col in key_columns)
                if key not in seen:
                    seen.add(key)
                    new_rows.append(row)

            if not new_rows:
                break

            all_pages.append(pd.DataFrame(new_rows))

        if not all_pages:
            return pd.DataFrame()

        return pd.concat(all_pages, ignore_index=True)

    def get_kbreport_player_hitter(self, year, rows=500):
        common_params = {
            "teamId": "",
            "defense_no": "",
            "year_from": year,
            "year_to": year,
            "gameType": "",
            "split01": "",
            "split02_1": "",
            "split02_2": "",
            "tpa_count": "0",
        }

        main = self.get_all_pages(
            "/leader/main",
            params=common_params,
            key_columns=["선수명", "팀명"],
            max_pages=50,
            rows=rows,
        )

        std = self.get_all_pages(
            "/leader/standard",
            params=common_params,
            key_columns=["선수명", "팀명"],
            max_pages=50,
            rows=rows,
        )

        adv = self.get_all_pages(
            "/leader/advanced",
            params=common_params,
            key_columns=["선수명", "팀명"],
            max_pages=50,
            rows=rows,
        )

        return self.merge_kbreport_tables([main, std, adv], ["선수명", "팀명"], year)

    def get_kbreport_player_pitcher(self, year, rows=500):
        common_params = {
            "teamId": "",
            "pitcher_type": "",
            "year_from": year,
            "year_to": year,
            "gameType": "",
            "split01": "",
            "split02_1": "",
            "split02_2": "",
            "inning_count": "0",
        }

        main = self.get_all_pages(
            "/leader/pitcher/main",
            params=common_params,
            key_columns=["선수명", "팀명"],
            max_pages=50,
            rows=rows,
        )

        std = self.get_all_pages(
            "/leader/pitcher/standard",
            params=common_params,
            key_columns=["선수명", "팀명"],
            max_pages=50,
            rows=rows,
        )

        adv = self.get_all_pages(
            "/leader/pitcher/advanced",
            params=common_params,
            key_columns=["선수명", "팀명"],
            max_pages=50,
            rows=rows,
        )

        return self.merge_kbreport_tables([main, std, adv], ["선수명", "팀명"], year)

    def get_kbreport_team_hitter(self, year, rows=100):
        common_params = {
            "teamId": "",
            "defense_no": "",
            "year_from": year,
            "year_to": year,
            "split01": "",
            "split02_1": "",
            "split02_2": "",
        }

        main = self.get_all_pages("/teams/main", common_params, ["팀명"], max_pages=10, rows=rows)
        std = self.get_all_pages("/teams/standard", common_params, ["팀명"], max_pages=10, rows=rows)
        adv = self.get_all_pages("/teams/advanced", common_params, ["팀명"], max_pages=10, rows=rows)

        return self.merge_kbreport_tables([main, std, adv], ["팀명"], year)

    def get_kbreport_team_pitcher(self, year, rows=100):
        common_params = {
            "teamId": "",
            "pitcher_type": "",
            "year_from": year,
            "year_to": year,
            "split01": "",
            "split02_1": "",
            "split02_2": "",
        }

        main = self.get_all_pages("/teams/pitcher/main", common_params, ["팀명"], max_pages=10, rows=rows)
        std = self.get_all_pages("/teams/pitcher/standard", common_params, ["팀명"], max_pages=10, rows=rows)
        adv = self.get_all_pages("/teams/pitcher/advanced", common_params, ["팀명"], max_pages=10, rows=rows)

        return self.merge_kbreport_tables([main, std, adv], ["팀명"], year)

    def merge_kbreport_tables(self, dfs, key_columns, year):
        merged = {}

        for df in dfs:
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                key = tuple(str(row.get(col, "")).strip() for col in key_columns)
                if key not in merged:
                    merged[key] = {}
                merged[key].update(row.to_dict())

        result = pd.DataFrame(list(merged.values()))
        if not result.empty:
            result["season_year"] = int(year)

            if "선수명" in result.columns:
                result["선수명"] = result["선수명"].apply(clean_player_name)

            if "팀명" in result.columns:
                result["팀명"] = result["팀명"].apply(clean_team_name)

        return result


def pick(row, *names):
    for name in names:
        if name in row and pd.notna(row[name]):
            return row[name]
    return None


def convert_kbreport_hitter_advanced(row):
    return {
        "season_year": to_int(row.get("season_year")),
        "player_name": clean_player_name(row.get("선수명")),
        "team_name": clean_team_name(row.get("팀명")),
        "babip": to_float(pick(row, "BABIP")),
        "bb_rate": normalize_percent(pick(row, "볼넷%", "BB%")),
        "k_rate": normalize_percent(pick(row, "삼진%", "K%")),
        "bb_k": to_float(pick(row, "볼/삼")),
        "iso": to_float(pick(row, "ISO")),
        "ab_per_hr": to_float(pick(row, "타수/홈런")),
        "rc": to_float(pick(row, "RC")),
        "rc27": to_float(pick(row, "RC/27")),
        "wrc": to_float(pick(row, "wRC")),
        "spd": to_float(pick(row, "SPD")),
        "wsb": to_float(pick(row, "wSB")),
        "woba": to_float(pick(row, "wOBA")),
        "wraa": to_float(pick(row, "wRAA")),
        "war": to_float(pick(row, "WAR")),
    }


def convert_kbreport_pitcher_advanced(row):
    return {
        "season_year": to_int(row.get("season_year")),
        "player_name": clean_player_name(row.get("선수명")),
        "team_name": clean_team_name(row.get("팀명")),
        "hr9": to_float(pick(row, "홈런/9")),
        "lob_rate": normalize_percent(pick(row, "LOB%")),
        "fip": to_float(pick(row, "FIP")),
        "kfip": to_float(pick(row, "kFIP")),
        "fip_war": to_float(pick(row, "FIP-WAR")),
        "ra9_war": to_float(pick(row, "RA9-WAR")),
        "k_rate": normalize_percent(pick(row, "삼진%")),
        "bb_rate": normalize_percent(pick(row, "볼넷%")),
        "avg_against": to_float(pick(row, "피안타율")),
        "obp_against": to_float(pick(row, "피출루율")),
        "slg_against": to_float(pick(row, "피장타율")),
        "ops_against": to_float(pick(row, "피OPS")),
    }


def convert_kbreport_team_hitter_advanced(row):
    out = convert_kbreport_hitter_advanced(row)
    out.pop("player_name", None)
    return {
        "season_year": out["season_year"],
        "team_name": out["team_name"],
        "expected_win_rate": to_float(pick(row, "기대승률")),
        "r_per_game": to_float(pick(row, "R/G")),
        **{k: v for k, v in out.items() if k not in {"season_year", "team_name"}},
    }


def convert_kbreport_team_pitcher_advanced(row):
    out = convert_kbreport_pitcher_advanced(row)
    out.pop("player_name", None)
    return {
        "season_year": out["season_year"],
        "team_name": out["team_name"],
        "expected_win_rate": to_float(pick(row, "기대승률")),
        "ra_per_game": to_float(pick(row, "RA/G")),
        **{k: v for k, v in out.items() if k not in {"season_year", "team_name"}},
    }


# ============================================================
# 메인 실행
# ============================================================

def crawl_kbo_official_all():
    crawler = KBOOfficialCrawler()

    URLS = {
        "hitter_basic1": "https://www.koreabaseball.com/Record/Player/HitterBasic/Basic1.aspx",
        "hitter_basic2": "https://www.koreabaseball.com/Record/Player/HitterBasic/Basic2.aspx",
        "hitter_detail1": "https://www.koreabaseball.com/Record/Player/HitterBasic/Detail1.aspx",

        "pitcher_basic1": "https://www.koreabaseball.com/Record/Player/PitcherBasic/Basic1.aspx",
        "pitcher_basic2": "https://www.koreabaseball.com/Record/Player/PitcherBasic/Basic2.aspx",
        "pitcher_detail1": "https://www.koreabaseball.com/Record/Player/PitcherBasic/Detail1.aspx",
        "pitcher_detail2": "https://www.koreabaseball.com/Record/Player/PitcherBasic/Detail2.aspx",

        "defense": "https://www.koreabaseball.com/Record/Player/Defense/Basic.aspx",
        "runner": "https://www.koreabaseball.com/Record/Player/Runner/Basic.aspx",

        "team_hitter_basic1": "https://www.koreabaseball.com/Record/Team/Hitter/Basic1.aspx",
        "team_hitter_basic2": "https://www.koreabaseball.com/Record/Team/Hitter/Basic2.aspx",
        "team_pitcher_basic1": "https://www.koreabaseball.com/Record/Team/Pitcher/Basic1.aspx",
        "team_pitcher_basic2": "https://www.koreabaseball.com/Record/Team/Pitcher/Basic2.aspx",
        "team_defense": "https://www.koreabaseball.com/Record/Team/Defense/Basic.aspx",
        "team_runner": "https://www.koreabaseball.com/Record/Team/Runner/Basic.aspx",
        "team_rank": "https://www.koreabaseball.com/Record/TeamRank/TeamRank.aspx",
    }

    all_hitter = []
    all_pitcher = []
    all_defense = []
    all_runner = []
    all_team_hitter = []
    all_team_pitcher = []
    all_team_defense = []
    all_team_runner = []
    all_team_rank = []

    for year in range(START_YEAR, END_YEAR + 1):
        season = str(year)

        for team_code in TEAM_CODES.values():
            print(f"[KBO] hitter {season} {team_code}")
            hitter_groups = [
                crawler.crawl_kbo_player_table(URLS["hitter_basic1"], season, team_code, ["선수명", "AVG"]),
                crawler.crawl_kbo_player_table(URLS["hitter_basic2"], season, team_code, ["선수명", "OPS"]),
                crawler.crawl_kbo_player_table(URLS["hitter_detail1"], season, team_code, ["선수명", "GPA"]),
            ]
            hitter_rows = merge_by_key(hitter_groups, ["season_year", "player_id", "선수명", "팀명"])
            all_hitter.extend([convert_kbo_hitter_row(r) for r in hitter_rows])

            print(f"[KBO] pitcher {season} {team_code}")
            pitcher_groups = []
            for key in ["pitcher_basic1", "pitcher_basic2", "pitcher_detail1", "pitcher_detail2"]:
                try:
                    pitcher_groups.append(
                        crawler.crawl_kbo_player_table(URLS[key], season, team_code, ["선수명", "ERA"])
                    )
                except Exception as e:
                    print(f"[WARN] pitcher page fail {key}: {e}")

            pitcher_rows = merge_by_key(pitcher_groups, ["season_year", "player_id", "선수명", "팀명"])
            all_pitcher.extend([convert_kbo_pitcher_row(r) for r in pitcher_rows])

            print(f"[KBO] defense {season} {team_code}")
            defense_rows = crawler.crawl_kbo_player_table(URLS["defense"], season, team_code, ["선수명", "POS", "FPCT"])
            all_defense.extend([convert_kbo_defense_row(r) for r in defense_rows])

            print(f"[KBO] runner {season} {team_code}")
            runner_rows = crawler.crawl_kbo_player_table(URLS["runner"], season, team_code, ["선수명", "SB%"])
            all_runner.extend([convert_kbo_runner_row(r) for r in runner_rows])

        print(f"[KBO] team hitter {season}")
        team_hitter_groups = []
        try:
            team_hitter_groups.append(
                crawler.crawl_kbo_team_table(
                    URLS["team_hitter_basic1"], season, "team_hitter", ["팀명", "AVG"]
                )
            )
        except Exception as e:
            print(f"[WARN] team hitter Basic1 fail: {e}")

        try:
            team_hitter_groups.append(
                crawler.crawl_kbo_team_table(
                    URLS["team_hitter_basic2"], season, "team_hitter", ["팀명", "OPS"]
                )
            )
        except Exception as e:
            print(f"[WARN] team hitter Basic2 fail: {e}")

        team_hitter_rows = merge_by_key(team_hitter_groups, ["season_year", "팀명", "record_type"])
        all_team_hitter.extend([convert_kbo_team_row(r) for r in team_hitter_rows])

        print(f"[KBO] team pitcher {season}")
        team_pitcher_groups = []
        try:
            team_pitcher_groups.append(
                crawler.crawl_kbo_team_table(
                    URLS["team_pitcher_basic1"], season, "team_pitcher", ["팀명", "ERA"]
                )
            )
        except Exception as e:
            print(f"[WARN] team pitcher Basic1 fail: {e}")

        try:
            team_pitcher_groups.append(
                crawl_team_table_with_fallback(
                    crawler,
                    URLS["team_pitcher_basic2"],
                    season,
                    "team_pitcher",
                    [
                        ["팀명", "QS"],
                        ["팀명", "TBF"],
                        ["팀명", "CG"],
                        ["팀명", "NP"],
                    ],
                )
            )
        except Exception as e:
            print(f"[WARN] team pitcher Basic2 fail: {e}")

        team_pitcher_rows = merge_by_key(team_pitcher_groups, ["season_year", "팀명", "record_type"])
        all_team_pitcher.extend([convert_kbo_team_row(r) for r in team_pitcher_rows])

        print(f"[KBO] team defense {season}")
        all_team_defense.extend([
            convert_kbo_team_row(r)
            for r in crawler.crawl_kbo_team_table(URLS["team_defense"], season, "team_defense", ["팀명", "FPCT"])
        ])

        print(f"[KBO] team runner {season}")
        all_team_runner.extend([
            convert_kbo_team_row(r)
            for r in crawler.crawl_kbo_team_table(URLS["team_runner"], season, "team_runner", ["팀명", "SB%"])
        ])

        print(f"[KBO] team rank {season}")
        rank_rows = crawler.crawl_kbo_team_table(URLS["team_rank"], season, "team_rank", ["팀명", "승률", "게임차"])
        all_team_rank.extend([convert_team_rank_row(r) for r in rank_rows])

    # 중복 제거
    all_hitter = dedupe(all_hitter, ["season_year", "player_id", "team_name"])
    all_pitcher = dedupe(all_pitcher, ["season_year", "player_id", "team_name"])
    all_defense = dedupe(all_defense, ["season_year", "player_id", "team_name", "position"])
    all_runner = dedupe(all_runner, ["season_year", "player_id", "team_name"])
    all_team_hitter = dedupe(all_team_hitter, ["season_year", "team_name"])
    all_team_pitcher = dedupe(all_team_pitcher, ["season_year", "team_name"])
    all_team_defense = dedupe(all_team_defense, ["season_year", "team_name"])
    all_team_runner = dedupe(all_team_runner, ["season_year", "team_name"])
    all_team_rank = dedupe(all_team_rank, ["season_year", "team_name"])

    save_csv(all_hitter, "player_hitter_stats.csv")
    save_csv(all_pitcher, "player_pitcher_stats.csv")
    save_csv(all_defense, "player_defense_stats.csv")
    save_csv(all_runner, "player_runner_stats.csv")
    save_csv(all_team_hitter, "team_hitter_stats.csv")
    save_csv(all_team_pitcher, "team_pitcher_stats.csv")
    save_csv(all_team_defense, "team_defense_stats.csv")
    save_csv(all_team_runner, "team_runner_stats.csv")
    save_csv(all_team_rank, "team_rank_stats.csv")

    make_master_files(
        all_hitter,
        all_pitcher,
        all_defense,
        all_runner,
        all_team_hitter,
        all_team_pitcher,
        all_team_defense,
        all_team_runner,
        all_team_rank,
    )


def dedupe(rows: List[dict], keys: List[str]) -> List[dict]:
    result = {}
    for row in rows:
        key = tuple(row.get(k) for k in keys)
        result[key] = row
    return list(result.values())


def filter_valid_team_rows(rows: List[dict]) -> List[dict]:
    """KBReport 팀 페이지에 섞일 수 있는 '전체' 또는 리그 평균 행 제거."""
    return [row for row in rows if row.get("team_name") in VALID_TEAM_NAMES]


def make_master_files(*row_groups):
    team_rows = {}
    player_rows = {}
    season_team_rows = {}

    for rows in row_groups:
        for row in rows:
            team_name = row.get("team_name")
            team_code = row.get("team_code")
            season_year = row.get("season_year")
            player_id = row.get("player_id")
            player_name = row.get("player_name")

            if team_name:
                team_rows[team_name] = {
                    "team_name": team_name,
                    "team_code": team_code,
                }

            if player_id:
                player_rows[player_id] = {
                    "player_id": player_id,
                    "player_name": player_name,
                }

            if season_year and player_id and team_name:
                season_team_rows[(season_year, player_id, team_name)] = {
                    "season_year": season_year,
                    "player_id": player_id,
                    "team_name": team_name,
                }

    save_csv(list(team_rows.values()), "teams.csv")
    save_csv(list(player_rows.values()), "players.csv")
    save_csv(list(season_team_rows.values()), "player_season_teams.csv")


def crawl_kbreport_all():
    crawler = KBReportCrawler()

    hitter_adv = []
    pitcher_adv = []
    team_hitter_adv = []
    team_pitcher_adv = []

    try:
        for year in range(START_YEAR, END_YEAR + 1):
            season = str(year)

            print(f"[KBReport] player hitter {season}")
            df = crawler.get_kbreport_player_hitter(season)
            if not df.empty:
                hitter_adv.extend([convert_kbreport_hitter_advanced(row) for _, row in df.iterrows()])

            print(f"[KBReport] player pitcher {season}")
            df = crawler.get_kbreport_player_pitcher(season)
            if not df.empty:
                pitcher_adv.extend([convert_kbreport_pitcher_advanced(row) for _, row in df.iterrows()])

            print(f"[KBReport] team hitter {season}")
            df = crawler.get_kbreport_team_hitter(season)
            if not df.empty:
                team_hitter_adv.extend([convert_kbreport_team_hitter_advanced(row) for _, row in df.iterrows()])

            print(f"[KBReport] team pitcher {season}")
            df = crawler.get_kbreport_team_pitcher(season)
            if not df.empty:
                team_pitcher_adv.extend([convert_kbreport_team_pitcher_advanced(row) for _, row in df.iterrows()])

    finally:
        crawler.close()

    hitter_adv = dedupe(hitter_adv, ["season_year", "player_name", "team_name"])
    pitcher_adv = dedupe(pitcher_adv, ["season_year", "player_name", "team_name"])

    # KBReport 팀 기록에는 '전체' 행이 섞일 수 있으므로 DB 적재 전 제거
    team_hitter_adv = filter_valid_team_rows(team_hitter_adv)
    team_pitcher_adv = filter_valid_team_rows(team_pitcher_adv)

    team_hitter_adv = dedupe(team_hitter_adv, ["season_year", "team_name"])
    team_pitcher_adv = dedupe(team_pitcher_adv, ["season_year", "team_name"])

    save_csv(hitter_adv, "kbreport_player_hitter_advanced.csv")
    save_csv(pitcher_adv, "kbreport_player_pitcher_advanced.csv")
    save_csv(team_hitter_adv, "kbreport_team_hitter_advanced.csv")
    save_csv(team_pitcher_adv, "kbreport_team_pitcher_advanced.csv")


if __name__ == "__main__":
    print("====================================")
    print("KBO 공식 사이트 크롤링 시작")
    print("====================================")
    crawl_kbo_official_all()

    print("====================================")
    print("KBReport 크롤링 시작")
    print("====================================")
    crawl_kbreport_all()

    print("====================================")
    print("전체 완료")
    print(f"출력 폴더: {OUTPUT_DIR.resolve()}")
    print("====================================")
