#!/usr/bin/env python3
"""KBO 공식 사이트의 연도별 정규시즌 팀 순위를 CSV로 저장한다.

기본 실행 범위는 2015~2026년이며, 프로젝트의 DB 적재 폴더인
``backend/db/output_db_ready/team_rank_stats.csv``에 저장한다.

Docker 실행 예시::

    docker compose run --rm backend \
      python crolling/crawl_team_rank_stats.py

출력 경로를 바꾸려면::

    python crolling/crawl_team_rank_stats.py \
      --start-year 2015 --end-year 2026 \
      --output db/output_db_ready/team_rank_stats.csv

주의:
- KBO 페이지는 ASP.NET postback으로 시즌을 변경하므로 Selenium을 사용한다.
- 선택된 시즌과 수집한 시즌이 일치하는지 확인한다.
- 완료된 과거 시즌(기본값: 종료 연도 전)은 팀당 144경기인지 검사한다.
- 서로 다른 시즌의 표가 완전히 같으면 잘못 수집된 것으로 보고 저장하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait


KBO_TEAM_RANK_URL = "https://www.koreabaseball.com/Record/TeamRank/TeamRank.aspx"
DEFAULT_START_YEAR = 2015
DEFAULT_END_YEAR = 2026
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "db"
    / "output_db_ready"
    / "team_rank_stats.csv"
)

SEASON_SELECT = "select[id$='ddlSeason_ddlSeason'], select[name$='$ddlSeason$ddlSeason']"
SERIES_SELECT = "select[id$='ddlSeries_ddlSeries'], select[name$='$ddlSeries$ddlSeries']"
REQUIRED_HEADERS = [
    "순위",
    "팀명",
    "경기",
    "승",
    "패",
    "무",
    "승률",
    "게임차",
    "최근10경기",
    "연속",
    "홈",
    "방문",
]
CSV_COLUMNS = [
    "season_year",
    "team_name",
    "rank_no",
    "games",
    "wins",
    "losses",
    "draws",
    "win_rate",
    "game_gap",
    "last10",
    "streak",
    "home",
    "away",
    "series",
]

# 프로젝트의 teams 테이블은 현재 구단명 10개를 사용한다.
TEAM_NAME_MAP = {
    "SK": "SSG",
    "SK 와이번스": "SSG",
    "넥센": "키움",
    "넥센 히어로즈": "키움",
    "히어로즈": "키움",
    "키움 히어로즈": "키움",
    "KT 위즈": "KT",
    "kt wiz": "KT",
    "KIA 타이거즈": "KIA",
    "두산 베어스": "두산",
    "롯데 자이언츠": "롯데",
    "삼성 라이온즈": "삼성",
    "한화 이글스": "한화",
    "LG 트윈스": "LG",
    "NC 다이노스": "NC",
}


def clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def parse_int(value: str, field: str, year: int, team: str) -> int:
    text = clean_text(value).replace(",", "")
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{year} {team}: {field} 값이 정수가 아닙니다: {value!r}") from exc


def parse_float(value: str, field: str, year: int, team: str) -> float:
    text = clean_text(value).replace(",", "")
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"{year} {team}: {field} 값이 숫자가 아닙니다: {value!r}") from exc


def find_rank_table(soup: BeautifulSoup):
    """필수 헤더가 모두 있는 팀 순위 표를 찾는다."""
    for table in soup.find_all("table"):
        headers = [clean_text(th.get_text(" ", strip=True)) for th in table.find_all("th")]
        if all(header in headers for header in REQUIRED_HEADERS):
            return table
    return None


def parse_rank_table(html: str, year: int, keep_original_team_names: bool = False) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    table = find_rank_table(soup)
    if table is None:
        raise RuntimeError(f"{year}: 팀 순위 표를 찾지 못했습니다.")

    header_cells = table.select("thead th") or table.find_all("th")
    headers = [clean_text(th.get_text(" ", strip=True)) for th in header_cells]
    header_index = {name: headers.index(name) for name in REQUIRED_HEADERS}

    body = table.find("tbody") or table
    result: list[dict] = []
    for tr in body.find_all("tr"):
        cells = [clean_text(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        if not cells or len(cells) <= max(header_index.values()):
            continue

        raw_team_name = cells[header_index["팀명"]]
        team_name = raw_team_name if keep_original_team_names else TEAM_NAME_MAP.get(raw_team_name, raw_team_name)
        games = parse_int(cells[header_index["경기"]], "경기", year, team_name)
        wins = parse_int(cells[header_index["승"]], "승", year, team_name)
        losses = parse_int(cells[header_index["패"]], "패", year, team_name)
        draws = parse_int(cells[header_index["무"]], "무", year, team_name)

        if wins + losses + draws != games:
            raise ValueError(
                f"{year} {team_name}: 경기 수 불일치 "
                f"({wins}승 + {losses}패 + {draws}무 != {games}경기)"
            )

        result.append(
            {
                "season_year": year,
                "team_name": team_name,
                "rank_no": parse_int(cells[header_index["순위"]], "순위", year, team_name),
                "games": games,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": parse_float(cells[header_index["승률"]], "승률", year, team_name),
                "game_gap": cells[header_index["게임차"]],
                "last10": cells[header_index["최근10경기"]],
                "streak": cells[header_index["연속"]],
                "home": cells[header_index["홈"]],
                "away": cells[header_index["방문"]],
                "series": "정규시즌",
            }
        )

    return result


def find_chrome_binary() -> str | None:
    configured = os.getenv("CHROME_BIN")
    if configured and Path(configured).exists():
        return configured
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    return None


def create_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1600,1200")
    options.add_argument("--lang=ko-KR")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    )

    chrome_binary = find_chrome_binary()
    if chrome_binary:
        options.binary_location = chrome_binary

    driver_path = os.getenv("CHROMEDRIVER_PATH") or shutil.which("chromedriver")
    if driver_path:
        return webdriver.Chrome(service=Service(driver_path), options=options)
    return webdriver.Chrome(options=options)


def selected_value(driver: webdriver.Chrome, selector: str) -> str:
    element = driver.find_element(By.CSS_SELECTOR, selector)
    return Select(element).first_selected_option.get_attribute("value") or ""


def current_table_signature(driver: webdriver.Chrome) -> str:
    """현재 순위표의 텍스트를 반환한다. 표가 없으면 빈 문자열이다."""
    table = find_rank_table(BeautifulSoup(driver.page_source, "lxml"))
    return clean_text(table.get_text(" ", strip=True)) if table is not None else ""


def select_value_and_wait(
    driver: webdriver.Chrome,
    selector: str,
    value: str,
    timeout: int,
    wait_for_table_change: bool = False,
) -> None:
    """select 변경 뒤 postback/화면 갱신과 선택값 반영을 기다린다."""
    wait = WebDriverWait(driver, timeout)
    element = wait.until(lambda d: d.find_element(By.CSS_SELECTOR, selector))
    current = Select(element).first_selected_option.get_attribute("value") or ""
    if current == value:
        return

    old_table_signature = current_table_signature(driver) if wait_for_table_change else ""

    try:
        Select(element).select_by_value(value)
    except Exception as exc:
        options = [
            (opt.get_attribute("value"), clean_text(opt.text))
            for opt in Select(element).options
        ]
        raise RuntimeError(f"선택값 {value!r}을 찾을 수 없습니다. 선택지: {options}") from exc

    try:
        wait.until(lambda d: selected_value(d, selector) == value)
    except (StaleElementReferenceException, TimeoutException):
        wait.until(lambda d: selected_value(d, selector) == value)
    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    if wait_for_table_change and old_table_signature:
        try:
            wait.until(
                lambda d: bool(current_table_signature(d))
                and current_table_signature(d) != old_table_signature
            )
        except TimeoutException as exc:
            raise RuntimeError(
                f"선택값을 {value!r}로 바꿨지만 순위표 내용이 변경되지 않았습니다."
            ) from exc


def select_regular_season(driver: webdriver.Chrome, timeout: int) -> None:
    """리그 구분을 정규시즌으로 맞춘다. KBO 현재 페이지의 값은 0이다."""
    try:
        element = WebDriverWait(driver, timeout).until(
            lambda d: d.find_element(By.CSS_SELECTOR, SERIES_SELECT)
        )
    except TimeoutException as exc:
        raise RuntimeError("정규시즌 선택 상자를 찾지 못했습니다.") from exc

    select = Select(element)
    regular = next(
        (
            opt
            for opt in select.options
            if opt.get_attribute("value") == "0" or "정규" in clean_text(opt.text)
        ),
        None,
    )
    if regular is None:
        options = [(opt.get_attribute("value"), clean_text(opt.text)) for opt in select.options]
        raise RuntimeError(f"정규시즌 선택지를 찾지 못했습니다: {options}")

    value = regular.get_attribute("value") or "0"
    select_value_and_wait(driver, SERIES_SELECT, value, timeout)


def validate_season_rows(
    year: int,
    rows: list[dict],
    expected_team_count: int,
    require_144_games: bool,
) -> None:
    if len(rows) != expected_team_count:
        raise ValueError(f"{year}: {expected_team_count}팀이 아니라 {len(rows)}행이 수집됐습니다.")

    team_names = [row["team_name"] for row in rows]
    if len(set(team_names)) != expected_team_count:
        raise ValueError(f"{year}: 팀명이 중복됐습니다: {team_names}")

    if require_144_games:
        incomplete = [(row["team_name"], row["games"]) for row in rows if row["games"] != 144]
        if incomplete:
            raise ValueError(f"{year}: 완료된 시즌인데 144경기가 아닌 팀이 있습니다: {incomplete}")


def fingerprint(rows: Iterable[dict]) -> tuple:
    """season_year를 제외한 표 전체를 비교하기 위한 지문."""
    return tuple(
        tuple(row[column] for column in CSV_COLUMNS if column != "season_year")
        for row in rows
    )


def crawl_seasons(
    start_year: int,
    end_year: int,
    timeout: int = 30,
    expected_team_count: int = 10,
    completed_through: int | None = None,
    keep_original_team_names: bool = False,
    headless: bool = True,
) -> list[dict]:
    if start_year > end_year:
        raise ValueError("시작 연도는 종료 연도보다 클 수 없습니다.")

    driver = create_driver(headless=headless)
    all_rows: list[dict] = []
    seen_fingerprints: dict[tuple, int] = {}

    try:
        driver.set_page_load_timeout(timeout)
        driver.get(KBO_TEAM_RANK_URL)
        WebDriverWait(driver, timeout).until(
            lambda d: d.find_element(By.CSS_SELECTOR, SEASON_SELECT)
        )

        for year in range(start_year, end_year + 1):
            print(f"[수집] {year} 정규시즌")
            select_value_and_wait(
                driver,
                SEASON_SELECT,
                str(year),
                timeout,
                wait_for_table_change=True,
            )
            select_regular_season(driver, timeout)

            # postback 직후 표 렌더링이 끝날 때까지 기다린다.
            WebDriverWait(driver, timeout).until(
                lambda d: find_rank_table(BeautifulSoup(d.page_source, "lxml")) is not None
            )
            time.sleep(0.4)

            actual_year = selected_value(driver, SEASON_SELECT)
            if actual_year != str(year):
                raise RuntimeError(f"{year}: 페이지의 실제 선택 연도가 {actual_year!r}입니다.")

            rows = parse_rank_table(
                driver.page_source,
                year,
                keep_original_team_names=keep_original_team_names,
            )
            validate_season_rows(
                year,
                rows,
                expected_team_count,
                require_144_games=completed_through is not None and year <= completed_through,
            )

            table_fingerprint = fingerprint(rows)
            duplicate_year = seen_fingerprints.get(table_fingerprint)
            if duplicate_year is not None:
                raise RuntimeError(
                    f"{year} 순위표가 {duplicate_year} 순위표와 완전히 같습니다. "
                    "시즌 선택이 적용되지 않았을 가능성이 있어 저장을 중단합니다."
                )
            seen_fingerprints[table_fingerprint] = year

            all_rows.extend(rows)
            print(f"[완료] {year}: {len(rows)}팀")
    finally:
        driver.quit()

    return all_rows


def write_csv_atomic(rows: list[dict], output: Path) -> None:
    """검증이 끝난 전체 결과만 원자적으로 교체한다."""
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{output.stem}.", suffix=".tmp", dir=output.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp_name, output)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="KBO 공식 사이트에서 연도별 정규시즌 팀 순위를 수집합니다."
    )
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--expected-team-count", type=int, default=10)
    parser.add_argument(
        "--completed-through",
        type=int,
        default=2025,
        help="이 연도까지는 팀당 144경기인지 검사합니다. 기본값: 2025",
    )
    parser.add_argument(
        "--keep-original-team-names",
        action="store_true",
        help="SK→SSG, 넥센→키움으로 바꾸지 않고 당시 구단명을 그대로 저장합니다.",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="로컬 디버깅용: headless 모드를 끄고 브라우저를 표시합니다.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        rows = crawl_seasons(
            start_year=args.start_year,
            end_year=args.end_year,
            timeout=args.timeout,
            expected_team_count=args.expected_team_count,
            completed_through=args.completed_through,
            keep_original_team_names=args.keep_original_team_names,
            headless=not args.show_browser,
        )
        expected_rows = (args.end_year - args.start_year + 1) * args.expected_team_count
        if len(rows) != expected_rows:
            raise RuntimeError(f"전체 행 수 불일치: 예상 {expected_rows}, 실제 {len(rows)}")

        write_csv_atomic(rows, args.output)
        print(f"[저장 완료] {args.output.resolve()}")
        print(f"[검증 완료] {args.start_year}~{args.end_year}, 총 {len(rows)}행")
        return 0
    except Exception as exc:
        print(f"[오류] {exc}")
        print("기존 CSV는 변경하지 않았습니다.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
