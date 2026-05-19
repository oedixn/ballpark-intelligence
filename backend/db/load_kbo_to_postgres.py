"""
load_kbo_to_postgres.py

KBO / KBReport 크롤링 결과 CSV를 PostgreSQL DB에 자동 적재하는 스크립트입니다.

특징
- teams -> players -> player_season_teams -> 기록 테이블 순서로 적재
- team_name을 자동으로 team_id로 매핑
- 중복 데이터는 ON CONFLICT로 자동 업데이트
- DB 테이블에 실제로 존재하는 컬럼만 INSERT하므로, CSV에 여분 컬럼이 있어도 안전
- 누락된 CSV 파일은 경고만 출력하고 계속 진행

설치
    pip install psycopg2-binary

사용 전 수정할 것
    아래 DB_CONFIG 값을 본인 PostgreSQL 설정에 맞게 바꾸세요.
    CSV_DIR도 CSV 파일이 들어있는 폴더로 맞추세요.

실행
    python load_kbo_to_postgres.py
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import psycopg2
from psycopg2 import sql


# ============================================================
# 1. DB 접속 설정
# ============================================================

DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "localhost"),
    "port":     int(os.environ.get("DB_PORT", 5432)),
    "dbname":   os.environ.get("DB_NAME", "ballpark"),
    "user":     os.environ.get("DB_USER", "ballpark"),
    "password": os.environ.get("DB_PASSWORD", "ballpark1234"),
}

# 크롤링 결과 CSV 폴더
CSV_DIR = Path(__file__).parent / "output_db_ready"

# CSV 파일명이 (1) 붙은 업로드본인 경우에도 자동으로 찾기 위한 후보 목록
CSV_ALIASES = {
    "teams.csv": ["teams.csv", "teams(1).csv"],
    "players.csv": ["players.csv", "players(1).csv"],
    "player_season_teams.csv": ["player_season_teams.csv", "player_season_teams(1).csv"],
    "player_hitter_stats.csv": ["player_hitter_stats.csv", "player_hitter_stats(1).csv"],
    "player_pitcher_stats.csv": ["player_pitcher_stats.csv", "player_pitcher_stats(1).csv"],
    "player_defense_stats.csv": ["player_defense_stats.csv", "player_defense_stats(1).csv"],
    "player_runner_stats.csv": ["player_runner_stats.csv", "player_runner_stats(1).csv"],
    "team_hitter_stats.csv": ["team_hitter_stats.csv", "team_hitter_stats(1).csv"],
    "team_pitcher_stats.csv": ["team_pitcher_stats.csv", "team_pitcher_stats(1).csv"],
    "team_defense_stats.csv": ["team_defense_stats.csv", "team_defense_stats(1).csv"],
    "team_runner_stats.csv": ["team_runner_stats.csv", "team_runner_stats(1).csv"],
    "team_rank_stats.csv": ["team_rank_stats.csv", "team_rank_stats(1).csv"],
    "kbreport_player_hitter_advanced.csv": [
        "kbreport_player_hitter_advanced.csv",
        "kbreport_player_hitter_advanced(1).csv",
    ],
    "kbreport_player_pitcher_advanced.csv": [
        "kbreport_player_pitcher_advanced.csv",
        "kbreport_player_pitcher_advanced(1).csv",
    ],
    "kbreport_team_hitter_advanced.csv": [
        "kbreport_team_hitter_advanced.csv",
        "kbreport_team_hitter_advanced(1).csv",
    ],
    "kbreport_team_pitcher_advanced.csv": [
        "kbreport_team_pitcher_advanced.csv",
        "kbreport_team_pitcher_advanced(1).csv",
    ],
}

TEAM_CODE_BY_NAME = {
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

VALID_TEAM_NAMES = set(TEAM_CODE_BY_NAME.keys())

# 테이블별 중복 기준. 실제 DB의 UNIQUE 제약과 같아야 합니다.
CONFLICT_TARGETS = {
    "teams": ["team_name"],
    "players": ["player_id"],
    "player_season_teams": ["season_year", "player_id", "team_id"],
    "player_hitter_stats": ["season_year", "player_id", "team_id"],
    "player_pitcher_stats": ["season_year", "player_id", "team_id"],
    "player_defense_stats": ["season_year", "player_id", "team_id", "position"],
    "player_runner_stats": ["season_year", "player_id", "team_id"],
    "team_hitter_stats": ["season_year", "team_id"],
    "team_pitcher_stats": ["season_year", "team_id"],
    "team_defense_stats": ["season_year", "team_id"],
    "team_runner_stats": ["season_year", "team_id"],
    "team_rank_stats": ["season_year", "team_id"],
    "kbreport_player_hitter_advanced": ["season_year", "player_name", "team_id"],
    "kbreport_player_pitcher_advanced": ["season_year", "player_name", "team_id"],
    "kbreport_team_hitter_advanced": ["season_year", "team_id"],
    "kbreport_team_pitcher_advanced": ["season_year", "team_id"],
}

# CSV 파일 -> DB 테이블명
LOAD_PLAN = [
    ("teams.csv", "teams"),
    ("players.csv", "players"),
    ("player_season_teams.csv", "player_season_teams"),
    ("player_hitter_stats.csv", "player_hitter_stats"),
    ("player_pitcher_stats.csv", "player_pitcher_stats"),
    ("player_defense_stats.csv", "player_defense_stats"),
    ("player_runner_stats.csv", "player_runner_stats"),
    ("team_hitter_stats.csv", "team_hitter_stats"),
    ("team_pitcher_stats.csv", "team_pitcher_stats"),
    ("team_defense_stats.csv", "team_defense_stats"),
    ("team_runner_stats.csv", "team_runner_stats"),
    ("team_rank_stats.csv", "team_rank_stats"),
    ("kbreport_player_hitter_advanced.csv", "kbreport_player_hitter_advanced"),
    ("kbreport_player_pitcher_advanced.csv", "kbreport_player_pitcher_advanced"),
    ("kbreport_team_hitter_advanced.csv", "kbreport_team_hitter_advanced"),
    ("kbreport_team_pitcher_advanced.csv", "kbreport_team_pitcher_advanced"),
]


# ============================================================
# 2. 유틸 함수
# ============================================================

def find_csv_file(canonical_name: str) -> Optional[Path]:
    """CSV_DIR 안에서 canonical_name 또는 alias 파일을 찾습니다."""
    aliases = CSV_ALIASES.get(canonical_name, [canonical_name])
    for name in aliases:
        path = CSV_DIR / name
        if path.exists():
            return path

    # 현재 스크립트를 /mnt/data 같은 폴더에서 실행할 때를 위한 보조 검색
    for name in aliases:
        path = Path(name)
        if path.exists():
            return path

    return None


def normalize_value(value: object) -> Optional[str]:
    """CSV 빈 값, NaN 문자열, '-' 등을 DB NULL로 변환합니다."""
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None

    lowered = text.lower()
    if lowered in {"nan", "none", "null"}:
        return None

    if text == "-":
        return None

    # 천 단위 콤마 제거. 예: 1,234 -> 1234
    text = text.replace(",", "")

    return text


def read_csv_rows(path: Path) -> List[Dict[str, Optional[str]]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def get_table_columns(cur, table_name: str) -> List[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    return [row[0] for row in cur.fetchall()]


def table_exists(cur, table_name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        )
        """,
        (table_name,),
    )
    return bool(cur.fetchone()[0])


def fetch_team_map(cur) -> Dict[str, int]:
    cur.execute("SELECT team_id, team_name FROM teams")
    return {team_name: team_id for team_id, team_name in cur.fetchall()}


def add_team_id(row: Dict[str, object], team_map: Dict[str, int]) -> Dict[str, object]:
    """team_name이 있으면 team_id로 변환합니다."""
    team_name = row.get("team_name")
    if team_name:
        row["team_id"] = team_map.get(str(team_name).strip())
    return row


def clean_row_for_table(
    row: Dict[str, object],
    table_name: str,
    db_columns: Sequence[str],
    team_map: Dict[str, int],
) -> Optional[Dict[str, object]]:
    """CSV row를 DB 테이블에 넣을 수 있는 형태로 변환합니다."""
    cleaned = {key: normalize_value(value) for key, value in row.items()}

    # 팀 테이블은 team_code가 비어 있으면 기본 매핑으로 채움
    if table_name == "teams":
        team_name = cleaned.get("team_name")
        if not team_name or team_name not in VALID_TEAM_NAMES:
            return None
        if not cleaned.get("team_code"):
            cleaned["team_code"] = TEAM_CODE_BY_NAME.get(team_name)

    # KBReport 팀 데이터에 혹시 '전체'가 남아 있으면 제거
    if cleaned.get("team_name") == "전체":
        return None

    # team_name -> team_id 변환
    if table_name != "teams" and "team_id" in db_columns:
        cleaned = add_team_id(cleaned, team_map)
        if cleaned.get("team_name") and cleaned.get("team_id") is None:
            print(f"[WARN] team_id 매핑 실패: table={table_name}, team_name={cleaned.get('team_name')}")
            return None

    # players 테이블에 player_id 없는 행은 제외
    if table_name == "players" and not cleaned.get("player_id"):
        return None

    # KBO 선수 기록 테이블은 player_id 필수
    if table_name.startswith("player_") and table_name != "player_season_teams":
        if "player_id" in db_columns and not cleaned.get("player_id"):
            return None

    # DB에 실제 존재하는 컬럼만 남김. id는 SERIAL이므로 제외.
    insertable = {
        key: value
        for key, value in cleaned.items()
        if key in db_columns and key != "id"
    }

    # FK 변환으로 만들어진 team_id가 DB 컬럼이면 추가
    if "team_id" in db_columns and cleaned.get("team_id") is not None:
        insertable["team_id"] = cleaned.get("team_id")

    # conflict target에 필요한 컬럼이 없으면 제외
    required = CONFLICT_TARGETS.get(table_name, [])
    missing_required = [col for col in required if insertable.get(col) is None]
    if missing_required:
        print(f"[WARN] 필수 키 누락으로 스킵: table={table_name}, missing={missing_required}, row={cleaned}")
        return None

    return insertable


def upsert_rows(cur, table_name: str, rows: List[Dict[str, object]]) -> int:
    if not rows:
        return 0

    conflict_cols = CONFLICT_TARGETS[table_name]
    inserted_count = 0

    for row in rows:
        columns = list(row.keys())
        values = [row[col] for col in columns]

        update_cols = [col for col in columns if col not in conflict_cols]

        if update_cols:
            set_clause = sql.SQL(", ").join(
                sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col))
                for col in update_cols
            )
            conflict_action = sql.SQL("DO UPDATE SET {}").format(set_clause)
        else:
            conflict_action = sql.SQL("DO NOTHING")

        query = sql.SQL("""
            INSERT INTO {table} ({columns})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_columns}) {conflict_action}
        """).format(
            table=sql.Identifier(table_name),
            columns=sql.SQL(", ").join(sql.Identifier(col) for col in columns),
            placeholders=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            conflict_columns=sql.SQL(", ").join(sql.Identifier(col) for col in conflict_cols),
            conflict_action=conflict_action,
        )

        cur.execute(query, values)
        inserted_count += 1

    return inserted_count


def load_table(conn, canonical_csv: str, table_name: str) -> None:
    path = find_csv_file(canonical_csv)
    if path is None:
        print(f"[SKIP] CSV 파일 없음: {canonical_csv}")
        return

    with conn.cursor() as cur:
        if not table_exists(cur, table_name):
            print(f"[SKIP] DB 테이블 없음: {table_name}")
            return

        db_columns = get_table_columns(cur, table_name)
        team_map = fetch_team_map(cur) if table_name != "teams" else {}

        raw_rows = read_csv_rows(path)
        cleaned_rows = []

        for row in raw_rows:
            cleaned = clean_row_for_table(row, table_name, db_columns, team_map)
            if cleaned:
                cleaned_rows.append(cleaned)

        count = upsert_rows(cur, table_name, cleaned_rows)

    conn.commit()
    print(f"[OK] {path.name} -> {table_name}: {count} rows")


# ============================================================
# 3. 실행
# ============================================================

def main() -> None:
    print("====================================")
    print("KBO CSV -> PostgreSQL 자동 적재 시작")
    print("====================================")
    print(f"CSV_DIR = {CSV_DIR.resolve()}")

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        for csv_name, table_name in LOAD_PLAN:
            load_table(conn, csv_name, table_name)

        print("====================================")
        print("전체 적재 완료")
        print("====================================")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
