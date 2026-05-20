"""
kbo_db_crawler.py

목적:
- KBO 공식 사이트 데이터만 크롤링
- DB 적재용 CSV로 저장
- 생성된 CSV를 PostgreSQL DB에 UPSERT
- Selenium/Chrome 없이 requests + BeautifulSoup 방식으로 동작

설치:
pip install requests beautifulsoup4 lxml pandas psycopg2-binary python-dotenv

실행:
python kbo_db_crawler.py

출력 폴더:
./output_db_ready/
"""

import csv
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup


try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    psycopg2 = None
    execute_values = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


# ============================================================
# 공통 설정
# ============================================================

# 크롤러 파일 위치를 기준으로 output 폴더를 생성합니다.
# Docker에서 /app을 기준으로 실행해도 backend/db/output_db_ready에 저장됩니다.
OUTPUT_DIR = Path(__file__).resolve().parent / "output_db_ready"
OUTPUT_DIR.mkdir(exist_ok=True)

START_YEAR = int(os.getenv("START_YEAR", "2026"))
END_YEAR = int(os.getenv("END_YEAR", "2026"))

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

# DB에는 현재 기준의 대표 팀명(canonical team_name)을 저장합니다.
# 과거 팀명/사이트 표기 차이는 이 매핑을 거쳐 같은 team_id로 연결합니다.
# 예: 2020년 SK 기록도 DB에서는 SSG 구단의 team_id로 저장됩니다.
TEAM_NAME_MAP = {
    # 현재 구단명
    "LG": "LG",
    "한화": "한화",
    "SSG": "SSG",
    "삼성": "삼성",
    "NC": "NC",
    "KT": "KT",
    "롯데": "롯데",
    "KIA": "KIA",
    "두산": "두산",
    "키움": "키움",

    # 과거/영문/약칭 표기
    "MBC": "LG",
    "빙그레": "한화",
    "SK": "SSG",
    "해태": "KIA",
    "OB": "두산",
    "Hero": "키움",
    "Heroes": "키움",
    "히어로즈": "키움",
    "서울": "키움",
    "우리": "키움",
    "넥센": "키움",
}


# team_code가 넘어오는 경우에도 대표 팀명으로 바꾸기 위한 보조 매핑입니다.
# KBO 공식 사이트에서 SSG의 team code가 여전히 SK로 쓰일 수 있어 별도 처리합니다.
TEAM_CODE_TO_CANONICAL_NAME = {
    "LG": "LG",
    "HH": "한화",
    "SK": "SSG",
    "SS": "삼성",
    "NC": "NC",
    "KT": "KT",
    "LT": "롯데",
    "HT": "KIA",
    "OB": "두산",
    "WO": "키움",
}


# ============================================================
# DB 동기화 설정
# ============================================================

# .env 예시
# DB_HOST=localhost
# DB_PORT=5432
# DB_NAME=kbo_db
# DB_USER=postgres
# DB_PASSWORD=your_password

DB_ENABLED = True

CSV_TABLE_CONFIG = {
    # FK 대상 테이블을 먼저 적재해야 합니다.
    "teams.csv": {
        "table": "teams",
        "conflict_cols": ["team_name"],
    },
    "players.csv": {
        "table": "players",
        "conflict_cols": ["player_id"],
    },
    "player_season_teams.csv": {
        "table": "player_season_teams",
        "conflict_cols": ["season_year", "player_id", "team_id"],
    },

    # KBO 공식 기록 테이블: DB 스키마는 team_name이 아니라 team_id를 사용합니다.
    "player_hitter_stats.csv": {
        "table": "player_hitter_stats",
        "conflict_cols": ["season_year", "player_id", "team_id"],
    },
    "player_pitcher_stats.csv": {
        "table": "player_pitcher_stats",
        "conflict_cols": ["season_year", "player_id", "team_id"],
    },
    "player_defense_stats.csv": {
        "table": "player_defense_stats",
        "conflict_cols": ["season_year", "player_id", "team_id", "position"],
    },
    "player_runner_stats.csv": {
        "table": "player_runner_stats",
        "conflict_cols": ["season_year", "player_id", "team_id"],
    },
    "team_hitter_stats.csv": {
        "table": "team_hitter_stats",
        "conflict_cols": ["season_year", "team_id"],
    },
    "team_pitcher_stats.csv": {
        "table": "team_pitcher_stats",
        "conflict_cols": ["season_year", "team_id"],
    },
    "team_defense_stats.csv": {
        "table": "team_defense_stats",
        "conflict_cols": ["season_year", "team_id"],
    },
    "team_runner_stats.csv": {
        "table": "team_runner_stats",
        "conflict_cols": ["season_year", "team_id"],
    },
    "team_rank_stats.csv": {
        "table": "team_rank_stats",
        "conflict_cols": ["season_year", "team_id"],
    },
}

# CSV 컬럼명과 DB 스키마 컬럼명이 다른 경우 UPSERT 직전에 변환합니다.
DB_COLUMN_ALIASES = {
    "player_hitter_stats": {
        "go_count": "go",
        "ao_count": "ao",
    },
    "player_pitcher_stats": {
        "go_count": "go",
        "ao_count": "ao",
    },
}


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
    """크롤링된 팀명을 DB 기준 대표 팀명으로 정규화합니다."""
    value = clean_text(value)
    if value is None:
        return None
    return TEAM_NAME_MAP.get(value, value)


def canonical_team_name_from_row(row: dict) -> Optional[str]:
    """
    row에 team_name과 team_code가 모두 있을 때 대표 팀명을 안정적으로 결정합니다.
    team_name이 과거 표기여도 clean_team_name으로 현재 대표 팀명으로 변환하고,
    team_name이 비어 있으면 team_code를 사용합니다.
    """
    team_name = clean_team_name(row.get("team_name"))
    if team_name:
        return team_name

    team_code = clean_text(row.get("team_code"))
    if team_code:
        return TEAM_CODE_TO_CANONICAL_NAME.get(team_code, team_code)

    return None


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
# PostgreSQL UPSERT / 동기화 로그
# ============================================================

def get_db_config() -> dict:
    if load_dotenv is not None:
        load_dotenv()

    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "kbo_db"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "postgres"),
    }


def get_db_connection():
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2가 설치되어 있지 않습니다. "
            "pip install psycopg2-binary python-dotenv 실행 후 다시 시도하세요."
        )
    return psycopg2.connect(**get_db_config())


def q_ident(name: str) -> str:
    """PostgreSQL identifier quote."""
    return '"' + name.replace('"', '""') + '"'


def ensure_sync_logs_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_logs (
                id SERIAL PRIMARY KEY,
                source VARCHAR(100),
                status VARCHAR(20),
                message TEXT,
                row_count INT,
                synced_at TIMESTAMP DEFAULT NOW()
            );
            """
        )
    conn.commit()


def save_sync_log(conn, source: str, status: str, message: str = "", row_count: int = 0):
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sync_logs (source, status, message, row_count)
                VALUES (%s, %s, %s, %s)
                """,
                (source, status, message[:2000], row_count),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[WARN] sync_logs 저장 실패: {e}")


def table_exists(conn, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
            );
            """,
            (table_name,),
        )
        return bool(cur.fetchone()[0])


def get_table_columns(conn, table_name: str) -> List[str]:
    """DB에 실제 존재하는 컬럼만 조회합니다. CSV의 여분 컬럼은 자동 제외합니다."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position;
            """,
            (table_name,),
        )
        return [row[0] for row in cur.fetchall()]


def get_team_id_map(conn) -> Dict[str, int]:
    """teams 테이블의 team_name -> team_id 매핑을 가져옵니다."""
    with conn.cursor() as cur:
        cur.execute("SELECT team_name, team_id FROM teams;")
        return {team_name: team_id for team_name, team_id in cur.fetchall()}


def ensure_unique_index(conn, table_name: str, conflict_cols: List[str]):
    """
    ON CONFLICT를 쓰려면 conflict_cols에 해당하는 UNIQUE 제약/인덱스가 필요합니다.
    현재 스키마에는 대부분 UNIQUE 제약이 이미 있으나, 없을 때를 대비해 생성합니다.
    """
    index_name = f"ux_{table_name}_{'_'.join(conflict_cols)}"
    cols_sql = ", ".join(q_ident(c) for c in conflict_cols)

    with conn.cursor() as cur:
        cur.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {q_ident(index_name)} "
            f"ON {q_ident(table_name)} ({cols_sql});"
        )
    conn.commit()


def read_csv_for_db(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    df = df.where(pd.notna(df), None)
    return df


def normalize_dataframe_for_schema(conn, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """
    크롤러 CSV를 현재 PostgreSQL 스키마에 맞게 변환합니다.
    - team_name -> team_id 변환
    - CSV 컬럼명과 DB 컬럼명이 다른 항목 rename
    - DB에 없는 CSV 보조 컬럼(player_name, team_name, rank_no 등) 제거
    """
    if df.empty:
        return df

    if not table_exists(conn, table_name):
        raise ValueError(f"DB에 테이블이 없습니다: {table_name}")

    df = df.copy()

    # 컬럼명 alias 적용: go_count -> go 등
    aliases = DB_COLUMN_ALIASES.get(table_name, {})
    rename_map = {src: dst for src, dst in aliases.items() if src in df.columns}
    if rename_map:
        df = df.rename(columns=rename_map)

    db_columns = get_table_columns(conn, table_name)

    # id는 SERIAL/자동증가 컬럼이므로 CSV에 있더라도 넣지 않습니다.
    insertable_columns = [c for c in db_columns if c != "id"]

    # DB 스키마는 대부분 team_name 대신 team_id를 사용합니다.
    # 연도별 팀명 변경(SK→SSG, 넥센→키움 등)은 여기서 대표 팀명으로 정규화한 뒤 team_id로 변환합니다.
    if "team_id" in insertable_columns and "team_id" not in df.columns:
        if "team_name" not in df.columns and "team_code" not in df.columns:
            raise ValueError(f"{table_name}: team_id 변환에 필요한 team_name 또는 team_code 컬럼이 없습니다.")

        team_id_map = get_team_id_map(conn)

        if "team_name" in df.columns:
            df["team_name"] = df["team_name"].apply(clean_team_name)
        else:
            df["team_name"] = None

        if "team_code" in df.columns:
            df["team_name"] = df.apply(
                lambda r: r["team_name"] or TEAM_CODE_TO_CANONICAL_NAME.get(clean_text(r.get("team_code")), clean_text(r.get("team_code"))),
                axis=1,
            )

        df["team_id"] = df["team_name"].map(team_id_map)

        missing_teams = sorted({name for name, team_id in zip(df["team_name"], df["team_id"]) if name and pd.isna(team_id)})
        if missing_teams:
            raise ValueError(
                f"{table_name}: teams 테이블에 없는 팀명: {missing_teams}. "
                "TEAM_NAME_MAP 또는 teams.csv 생성 로직을 확인하세요."
            )

    # DB에 존재하는 컬럼만 남깁니다.
    keep_columns = [c for c in insertable_columns if c in df.columns]
    df = df[keep_columns]

    # 빈 문자열/NaN 정리
    df = df.where(pd.notna(df), None)

    return df


def upsert_dataframe(conn, df: pd.DataFrame, table_name: str, conflict_cols: List[str]) -> int:
    if df.empty:
        return 0

    missing_conflict_cols = [c for c in conflict_cols if c not in df.columns]
    if missing_conflict_cols:
        raise ValueError(f"{table_name} conflict 컬럼 누락: {missing_conflict_cols}")

    columns = list(df.columns)
    update_cols = [c for c in columns if c not in conflict_cols]

    insert_cols_sql = ", ".join(q_ident(c) for c in columns)
    conflict_cols_sql = ", ".join(q_ident(c) for c in conflict_cols)

    if update_cols:
        update_sql = ", ".join(
            f"{q_ident(c)} = EXCLUDED.{q_ident(c)}" for c in update_cols
        )
        sql = (
            f"INSERT INTO {q_ident(table_name)} ({insert_cols_sql}) VALUES %s "
            f"ON CONFLICT ({conflict_cols_sql}) DO UPDATE SET {update_sql};"
        )
    else:
        sql = (
            f"INSERT INTO {q_ident(table_name)} ({insert_cols_sql}) VALUES %s "
            f"ON CONFLICT ({conflict_cols_sql}) DO NOTHING;"
        )

    values = [tuple(row) for row in df.itertuples(index=False, name=None)]

    with conn.cursor() as cur:
        execute_values(cur, sql, values, page_size=1000)

    conn.commit()
    return len(values)


def upsert_csv_file(conn, csv_path: Path, config: dict) -> int:
    table_name = config["table"]
    conflict_cols = config["conflict_cols"]

    df = read_csv_for_db(csv_path)
    df = normalize_dataframe_for_schema(conn, df, table_name)
    ensure_unique_index(conn, table_name, conflict_cols)
    row_count = upsert_dataframe(conn, df, table_name, conflict_cols)
    return row_count

def sync_output_csv_to_db():
    if not DB_ENABLED:
        print("[DB] DB 동기화 비활성화됨")
        return

    print("====================================")
    print("DB UPSERT 시작")
    print("====================================")

    conn = get_db_connection()
    try:
        ensure_sync_logs_table(conn)

        for filename, config in CSV_TABLE_CONFIG.items():
            csv_path = OUTPUT_DIR / filename
            source = config["table"]

            if not csv_path.exists():
                msg = f"CSV 파일 없음: {csv_path}"
                print(f"[SKIP] {msg}")
                save_sync_log(conn, source, "SKIP", msg, 0)
                continue

            try:
                row_count = upsert_csv_file(conn, csv_path, config)
                msg = f"{filename} UPSERT 완료"
                print(f"[DB SAVE] {source} rows={row_count}")
                save_sync_log(conn, source, "SUCCESS", msg, row_count)
            except Exception as e:
                conn.rollback()
                msg = f"{filename} UPSERT 실패: {e}"
                print(f"[DB ERROR] {msg}")
                save_sync_log(conn, source, "FAILED", msg, 0)
                # 특정 테이블 실패가 전체 동기화를 멈추지 않도록 계속 진행

    finally:
        conn.close()

    print("====================================")
    print("DB UPSERT 완료")
    print("====================================")

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



def make_master_files(*row_groups):
    team_rows = {}
    player_rows = {}
    season_team_rows = {}

    for rows in row_groups:
        for row in rows:
            team_name = canonical_team_name_from_row(row)
            team_code = clean_text(row.get("team_code"))
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


if __name__ == "__main__":
    print("====================================")
    print(f"KBO 공식 사이트 크롤링 시작: {START_YEAR}~{END_YEAR}")
    print("====================================")
    crawl_kbo_official_all()


    # 크롤링으로 생성된 CSV를 PostgreSQL에 UPSERT합니다.
    # 테이블은 미리 만들어져 있어야 하고, CSV 컬럼명과 DB 컬럼명이 같아야 합니다.
    sync_output_csv_to_db()

    print("====================================")
    print("전체 완료")
    print(f"출력 폴더: {OUTPUT_DIR.resolve()}")
    print("====================================")
