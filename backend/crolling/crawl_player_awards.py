#!/usr/bin/env python3
"""KBO 공식 수상 현황 크롤러.

수집 페이지
- MVP / 신인상
- 골든글러브
- KBO 수비상
- 올스타전 MVP / 한국시리즈 MVP

기존 players.csv 및 player_season_teams.csv가 있으면 선수 이름뿐 아니라
수상 연도와 당시 구단까지 확인해 player_id를 안전하게 연결한다.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


URLS = {
    "player_prize": "https://www.koreabaseball.com/Player/Awards/PlayerPrize.aspx",
    "golden_glove": "https://www.koreabaseball.com/Player/Awards/GoldenGlove.aspx",
    "defense_prize": "https://www.koreabaseball.com/Player/Awards/DefensePrize.aspx",
    "series_prize": "https://www.koreabaseball.com/Player/Awards/SeriesPrize.aspx",
}

TEAM_ALIASES = {
    "MBC": "LG",
    "빙그레": "한화",
    "SK": "SSG",
    "해태": "KIA",
    "OB": "두산",
    "넥센": "키움",
    "우리": "키움",
    "서울": "키움",
    "히어로즈": "키움",
}

OUTPUT_FIELDS = [
    "season_year",
    "award_type",
    "award_name",
    "player_id",
    "player_name",
    "team_name",
    "normalized_team_name",
    "position",
    "match_status",
    "candidate_ids",
    "source_url",
]


@dataclass
class Award:
    season_year: int
    award_type: str
    award_name: str
    player_name: str
    team_name: str
    position: str
    source_url: str
    player_id: str = ""
    normalized_team_name: str = ""
    match_status: str = "not_attempted"
    candidate_ids: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="KBO 공식 사이트에서 역대 수상 내역을 수집합니다."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        help=(
            "기존 선수 CSV를 찾을 DB 폴더. 예: backend/db. "
            "생략하면 현재 프로젝트에서 자동 탐색합니다."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "결과 CSV 경로. 생략하면 backend/db/output_db_ready/"
            "player_awards.csv 또는 현재 폴더에 저장합니다."
        ),
    )
    parser.add_argument(
        "--minimum-year",
        type=int,
        help="이 연도 이상의 수상 내역만 저장합니다.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="페이지 요청 제한 시간(초, 기본값 30)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="페이지 요청 사이 대기 시간(초, 기본값 0.8)",
    )
    return parser.parse_args()


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_team_name(team_name: str) -> str:
    name = clean_text(team_name)
    return TEAM_ALIASES.get(name, name)


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Referer": "https://www.koreabaseball.com/",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        }
    )
    return session


def fetch_soup(session: requests.Session, url: str, timeout: float) -> BeautifulSoup:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return BeautifulSoup(response.text, "lxml")


def find_awards_table(soup: BeautifulSoup, required_headers: Iterable[str]) -> Tag:
    required = set(required_headers)
    for table in soup.find_all("table"):
        headers = {clean_text(th.get_text(" ", strip=True)) for th in table.find_all("th")}
        if required.issubset(headers):
            return table
    raise RuntimeError(f"수상 표를 찾을 수 없습니다: required_headers={sorted(required)}")


def parse_year(cell: Tag) -> int | None:
    match = re.search(r"\b(19\d{2}|20\d{2})\b", clean_text(cell.get_text(" ", strip=True)))
    return int(match.group(1)) if match else None


def span_values(element: Tag) -> list[str]:
    return [clean_text(span.get_text(" ", strip=True)) for span in element.find_all("span")]


def parse_person_cell(cell: Tag, include_position: bool) -> list[tuple[str, str, str]]:
    """한 셀의 선수들을 (이름, 팀, 포지션) 목록으로 분리합니다."""
    groups = cell.find_all("p", recursive=False)
    sources: list[Tag] = groups if groups else [cell]
    people: list[tuple[str, str, str]] = []

    for source in sources:
        values = span_values(source)
        group_size = 3 if include_position else 2

        # 일부 과거 표는 한 셀에 여러 선수가 직접 span으로 이어질 수 있습니다.
        for index in range(0, len(values), group_size):
            group = values[index : index + group_size]
            if len(group) < group_size:
                continue
            name, team = group[0], group[1]
            position = group[2] if include_position else ""
            if not name or name == "-" or not team or team == "-":
                continue
            people.append((name, team, position))

    return people


def parse_two_prize_table(
    soup: BeautifulSoup,
    url: str,
    first: tuple[str, str],
    second: tuple[str, str],
) -> list[Award]:
    table = find_awards_table(soup, ("연도",))
    awards: list[Award] = []

    for tr in table.select("tbody tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 3:
            continue
        year = parse_year(cells[0])
        if year is None:
            continue

        for cell, (award_type, award_name) in zip(cells[1:3], (first, second)):
            for player_name, team_name, position in parse_person_cell(
                cell, include_position=True
            ):
                awards.append(
                    Award(
                        season_year=year,
                        award_type=award_type,
                        award_name=award_name,
                        player_name=player_name,
                        team_name=team_name,
                        position=position,
                        source_url=url,
                    )
                )
    return awards


def table_position_headers(table: Tag) -> list[str]:
    for tr in table.select("thead tr"):
        headers = [clean_text(th.get_text(" ", strip=True)) for th in tr.find_all("th")]
        if headers and headers[0] == "연도":
            return headers[1:]
    raise RuntimeError("포지션 헤더를 찾을 수 없습니다.")


def parse_position_prize_table(
    soup: BeautifulSoup,
    url: str,
    award_type: str,
    award_name: str,
    required_header: str,
) -> list[Award]:
    table = find_awards_table(soup, ("연도", required_header))
    positions = table_position_headers(table)
    awards: list[Award] = []

    for tr in table.select("tbody tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        year = parse_year(cells[0])
        if year is None:
            continue

        for position, cell in zip(positions, cells[1:]):
            for player_name, team_name, _ in parse_person_cell(
                cell, include_position=False
            ):
                awards.append(
                    Award(
                        season_year=year,
                        award_type=award_type,
                        award_name=award_name,
                        player_name=player_name,
                        team_name=team_name,
                        position=position,
                        source_url=url,
                    )
                )
    return awards


def crawl_awards(timeout: float, delay: float) -> list[Award]:
    awards: list[Award] = []

    with build_session() as session:
        print("[1/4] MVP·신인상 수집 중...")
        soup = fetch_soup(session, URLS["player_prize"], timeout)
        awards.extend(
            parse_two_prize_table(
                soup,
                URLS["player_prize"],
                ("MVP", "KBO MVP"),
                ("ROOKIE", "KBO 신인상"),
            )
        )
        time.sleep(max(delay, 0))

        print("[2/4] 골든글러브 수집 중...")
        soup = fetch_soup(session, URLS["golden_glove"], timeout)
        awards.extend(
            parse_position_prize_table(
                soup,
                URLS["golden_glove"],
                "GOLDEN_GLOVE",
                "KBO 골든글러브",
                "투수",
            )
        )
        time.sleep(max(delay, 0))

        print("[3/4] KBO 수비상 수집 중...")
        soup = fetch_soup(session, URLS["defense_prize"], timeout)
        awards.extend(
            parse_position_prize_table(
                soup,
                URLS["defense_prize"],
                "DEFENSE_PRIZE",
                "KBO 수비상",
                "좌익수",
            )
        )
        time.sleep(max(delay, 0))

        print("[4/4] 올스타전·한국시리즈 MVP 수집 중...")
        soup = fetch_soup(session, URLS["series_prize"], timeout)
        awards.extend(
            parse_two_prize_table(
                soup,
                URLS["series_prize"],
                ("ALL_STAR_MVP", "KBO 올스타전 MVP"),
                ("KOREAN_SERIES_MVP", "KBO 한국시리즈 MVP"),
            )
        )

    # 동일 레코드가 사이트 구조상 반복되어도 한 번만 저장합니다.
    unique: dict[tuple[object, ...], Award] = {}
    for award in awards:
        key = (
            award.season_year,
            award.award_type,
            award.player_name,
            award.team_name,
            award.position,
        )
        unique[key] = award
    return list(unique.values())


def detect_data_root(explicit: Path | None) -> Path | None:
    if explicit:
        return explicit.resolve()

    script = Path(__file__).resolve()
    candidates = [
        Path.cwd() / "backend" / "db",
        script.parent.parent / "db",
        Path.cwd(),
    ]
    for candidate in candidates:
        if candidate.exists() and (
            list(candidate.rglob("players.csv"))
            or list(candidate.rglob("player_profiles.csv"))
        ):
            return candidate.resolve()
    return None


def read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except (OSError, UnicodeError, csv.Error) as exc:
        print(f"[WARN] CSV 읽기 실패: {path}: {exc}")
        return []


def load_player_indexes(
    data_root: Path | None,
) -> tuple[
    dict[str, set[str]],
    dict[tuple[str, int], set[str]],
    dict[str, set[str]],
    dict[str, set[int]],
    list[Path],
]:
    name_to_ids: dict[str, set[str]] = defaultdict(set)
    career_teams: dict[tuple[str, int], set[str]] = defaultdict(set)
    all_career_teams: dict[str, set[str]] = defaultdict(set)
    career_years: dict[str, set[int]] = defaultdict(set)
    used_files: list[Path] = []

    if data_root is None:
        return (
            name_to_ids,
            career_teams,
            all_career_teams,
            career_years,
            used_files,
        )

    player_files = sorted(
        set(data_root.rglob("players.csv"))
        | set(data_root.rglob("player_profiles.csv"))
    )
    # 정규 시즌 소속 데이터와 프로필용으로 만든 클럽 경력 데이터를 모두
    # 사용합니다. 어느 한 파일이 빠져도 동명이인 판별이 가능해집니다.
    season_team_files = sorted(
        set(data_root.rglob("player_season_teams.csv"))
        | set(data_root.rglob("player_club_history.csv"))
    )

    for path in player_files:
        rows = read_csv(path)
        if not rows:
            continue
        used_files.append(path)
        for row in rows:
            player_id = clean_text(row.get("player_id"))
            player_name = clean_text(row.get("player_name"))
            if player_id and player_name:
                name_to_ids[player_name].add(player_id)

    for path in season_team_files:
        rows = read_csv(path)
        if not rows:
            continue
        used_files.append(path)
        for row in rows:
            player_id = clean_text(row.get("player_id"))
            team_name = normalize_team_name(clean_text(row.get("team_name")))
            year_text = clean_text(row.get("season_year"))
            if not player_id or not team_name or not year_text.isdigit():
                continue
            season_year = int(year_text)
            career_teams[(player_id, season_year)].add(team_name)
            all_career_teams[player_id].add(team_name)
            career_years[player_id].add(season_year)

    return (
        name_to_ids,
        career_teams,
        all_career_teams,
        career_years,
        used_files,
    )


def match_player_ids(
    awards: list[Award],
    name_to_ids: dict[str, set[str]],
    career_teams: dict[tuple[str, int], set[str]],
    all_career_teams: dict[str, set[str]],
    career_years: dict[str, set[int]],
) -> None:
    for award in awards:
        award.normalized_team_name = normalize_team_name(award.team_name)
        name_candidates = sorted(name_to_ids.get(award.player_name, set()))
        award.candidate_ids = "|".join(name_candidates)

        if not name_candidates:
            award.match_status = "unmatched_no_player"
            continue

        # 이름으로 찾은 선수가 한 명뿐이면 이적 때문에 KBO 수상 페이지의
        # 현재 구단과 수상 시즌 구단이 달라도 안전하게 연결할 수 있습니다.
        if len(name_candidates) == 1:
            award.player_id = name_candidates[0]
            award.match_status = "matched_unique_name"
            continue

        matched = [
            player_id
            for player_id in name_candidates
            if award.normalized_team_name
            in career_teams.get((player_id, award.season_year), set())
        ]

        if len(matched) == 1:
            award.player_id = matched[0]
            award.match_status = "matched_season_team"
        elif len(matched) > 1:
            award.candidate_ids = "|".join(sorted(matched))
            award.match_status = "ambiguous"
        else:
            # KBO 페이지의 구단이 이적 후 구단으로 표시된 경우를 대비해
            # 같은 시즌에 실제로 활동한 동명이인이 한 명인지 먼저 확인합니다.
            same_season = [
                player_id
                for player_id in name_candidates
                if award.season_year in career_years.get(player_id, set())
            ]
            if len(same_season) == 1:
                award.player_id = same_season[0]
                award.candidate_ids = same_season[0]
                award.match_status = "matched_season"
                continue

            # 수상 페이지에 적힌 구단이 선수의 전체 경력 중 하나라면 이를
            # 보조 조건으로 사용합니다.
            same_career_team = [
                player_id
                for player_id in name_candidates
                if award.normalized_team_name
                in all_career_teams.get(player_id, set())
            ]
            if len(same_career_team) == 1:
                award.player_id = same_career_team[0]
                award.candidate_ids = same_career_team[0]
                award.match_status = "matched_career_team"
                continue

            # 마지막으로 보유 경력의 시작~종료 연도 안에 수상 시즌이 들어가는
            # 후보가 한 명뿐일 때만 연결합니다. 둘 이상이면 잘못 연결하지 않습니다.
            active_candidates = []
            for player_id in name_candidates:
                years = career_years.get(player_id, set())
                if years and min(years) <= award.season_year <= max(years):
                    active_candidates.append(player_id)
            if len(active_candidates) == 1:
                award.player_id = active_candidates[0]
                award.candidate_ids = active_candidates[0]
                award.match_status = "matched_career_span"
                continue

            unresolved = same_season or same_career_team or active_candidates
            if unresolved:
                award.candidate_ids = "|".join(sorted(unresolved))
            award.match_status = "ambiguous"


def write_awards(path: Path, awards: list[Award]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for award in sorted(
            awards,
            key=lambda item: (
                -item.season_year,
                item.award_type,
                item.position,
                item.player_name,
            ),
        ):
            writer.writerow(asdict(award))
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    data_root = detect_data_root(args.data_root)

    try:
        awards = crawl_awards(args.timeout, args.delay)
    except (requests.RequestException, RuntimeError) as exc:
        print(f"[ERROR] 수상 내역 수집 실패: {exc}", file=sys.stderr)
        return 1

    if args.minimum_year is not None:
        awards = [award for award in awards if award.season_year >= args.minimum_year]

    (
        name_to_ids,
        career_teams,
        all_career_teams,
        career_years,
        used_files,
    ) = load_player_indexes(data_root)
    match_player_ids(
        awards,
        name_to_ids,
        career_teams,
        all_career_teams,
        career_years,
    )

    if args.output:
        output = args.output.resolve()
    elif data_root and (data_root / "output_db_ready").exists():
        output = data_root / "output_db_ready" / "player_awards.csv"
    else:
        output = Path.cwd() / "player_awards.csv"

    write_awards(output, awards)

    type_counts = Counter(award.award_type for award in awards)
    status_counts = Counter(award.match_status for award in awards)

    print()
    print(f"총 수상 기록: {len(awards)}건")
    for award_type, count in sorted(type_counts.items()):
        print(f"  {award_type}: {count}건")
    print("player_id 매칭 결과:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}건")
    print(f"참조한 기존 CSV: {len(set(used_files))}개")
    print(f"저장 완료: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
