#!/usr/bin/env python3
"""KBO 선수 기본정보 크롤러.

여러 player_*_stats CSV 파일의 player_id를 합치고 중복을 제거한 뒤,
KBO 공식 선수 상세 페이지에서 등번호/생년월일/포지션/투타/신장/체중을
수집해 선수당 한 행으로 저장한다.
"""

from __future__ import annotations

import argparse
import csv
import glob
import html
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


HITTER_URL = (
    "https://www.koreabaseball.com/Record/Player/"
    "HitterDetail/Basic.aspx?playerId={}"
)
PITCHER_URL = (
    "https://www.koreabaseball.com/Record/Player/"
    "PitcherDetail/Basic.aspx?playerId={}"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

OUTPUT_FIELDS = [
    "player_id",
    "player_name",
    "uniform_number",
    "birth_date",
    "position",
    "throws_hand",
    "bats_side",
    "bat_throw",
    "height_cm",
    "weight_kg",
    "source_tables",
    "name_conflict",
    "source_url",
    "crawl_status",
    "error_message",
]

PROFILE_IDS = {
    "player_name": "playerProfile_lblName",
    "uniform_number": "playerProfile_lblBackNo",
    "birthday_raw": "playerProfile_lblBirthday",
    "position_raw": "playerProfile_lblPosition",
    "height_weight_raw": "playerProfile_lblHeightWeight",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "여러 선수 기록 CSV의 player_id를 중복 제거하고 "
            "KBO 선수 프로필을 수집합니다."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help=(
            "입력 CSV 경로. 생략하면 현재 폴더의 "
            "player_*_stats*.csv를 자동 사용합니다."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        default="player_profiles.csv",
        help="결과 CSV 경로 (기본값: player_profiles.csv)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="선수별 요청 간 대기 시간(초, 기본값: 0.8)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP 요청 제한 시간(초, 기본값: 20)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="URL별 최대 요청 횟수(기본값: 3)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="기존 결과에서 success인 선수는 건너뜁니다.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="테스트용 최대 선수 수. 예: --limit 3",
    )
    return parser.parse_args()


def normalize_player_id(value: str | None) -> str:
    value = (value or "").strip()
    if re.fullmatch(r"\d+\.0", value):
        value = value[:-2]
    return value


def source_table_from_filename(path: str) -> str:
    name = Path(path).name.lower()
    for table in ("hitter", "pitcher", "runner", "defense"):
        if f"player_{table}_stats" in name:
            return table
    return Path(path).stem


def choose_name(names: Iterable[str]) -> tuple[str, str]:
    cleaned = [name.strip() for name in names if name and name.strip()]
    if not cleaned:
        return "", ""

    counts = Counter(cleaned)
    selected = counts.most_common(1)[0][0]
    distinct = sorted(counts)
    conflict = " | ".join(distinct) if len(distinct) > 1 else ""
    return selected, conflict


def load_players(paths: list[str]) -> list[dict[str, str]]:
    names_by_id: dict[str, list[str]] = defaultdict(list)
    sources_by_id: dict[str, set[str]] = defaultdict(set)

    for path in paths:
        source = source_table_from_filename(path)
        try:
            handle = open(path, "r", encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise RuntimeError(f"CSV 파일을 열 수 없습니다: {path}: {exc}") from exc

        with handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            if "player_id" not in fieldnames:
                raise RuntimeError(f"player_id 열이 없습니다: {path}")

            for row in reader:
                player_id = normalize_player_id(row.get("player_id"))
                if not player_id:
                    continue
                names_by_id[player_id].append((row.get("player_name") or "").strip())
                sources_by_id[player_id].add(source)

    players = []
    for player_id in sorted(names_by_id, key=lambda value: (len(value), value)):
        player_name, name_conflict = choose_name(names_by_id[player_id])
        players.append(
            {
                "player_id": player_id,
                "csv_player_name": player_name,
                "name_conflict": name_conflict,
                "source_tables": "|".join(sorted(sources_by_id[player_id])),
            }
        )
    return players


def strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def extract_span(page_html: str, id_suffix: str) -> str:
    pattern = re.compile(
        rf'<span[^>]+id=["\'][^"\']*{re.escape(id_suffix)}["\'][^>]*>'
        rf"(.*?)</span>",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(page_html)
    return strip_html(match.group(1)) if match else ""


def parse_birth_date(value: str) -> str:
    match = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", value)
    if not match:
        return ""
    year, month, day = map(int, match.groups())
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_position(value: str) -> tuple[str, str, str, str]:
    match = re.match(
        r"\s*(.*?)\s*\((우투|좌투|우언)\s*(우타|좌타|양타)\)\s*$",
        value,
    )
    if not match:
        return value.strip(), "", "", ""

    position, throw_text, bat_text = match.groups()
    # 우언은 우완 언더핸드/사이드암이므로 투구 손은 R로 저장하고,
    # 화면 표시용 bat_throw에는 원문인 '우언'을 보존합니다.
    throw_code = {"우투": "R", "좌투": "L", "우언": "R"}[throw_text]
    bat_code = {"우타": "R", "좌타": "L", "양타": "S"}[bat_text]
    return position.strip(), throw_code, bat_code, f"{throw_text}{bat_text}"


def parse_height_weight(value: str) -> tuple[str, str]:
    match = re.search(r"(\d+)\s*cm\s*/\s*(\d+)\s*kg", value, re.IGNORECASE)
    return (match.group(1), match.group(2)) if match else ("", "")


def fetch_html(url: str, timeout: float, retries: int) -> str:
    last_error = ""
    for attempt in range(1, retries + 1):
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Referer": "https://www.koreabaseball.com/",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                return raw.decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                time.sleep(attempt * 1.5)
    raise RuntimeError(last_error or "알 수 없는 HTTP 오류")


def preferred_urls(player: dict[str, str]) -> list[str]:
    player_id = player["player_id"]
    sources = set(player["source_tables"].split("|"))
    if sources == {"pitcher"}:
        templates = [PITCHER_URL, HITTER_URL]
    else:
        templates = [HITTER_URL, PITCHER_URL]
    return [template.format(player_id) for template in templates]


def empty_result(player: dict[str, str]) -> dict[str, str]:
    result = {field: "" for field in OUTPUT_FIELDS}
    result.update(
        {
            "player_id": player["player_id"],
            "player_name": player["csv_player_name"],
            "source_tables": player["source_tables"],
            "name_conflict": player["name_conflict"],
        }
    )
    return result


def crawl_player(
    player: dict[str, str], timeout: float, retries: int
) -> dict[str, str]:
    errors = []
    for url in preferred_urls(player):
        try:
            page_html = fetch_html(url, timeout=timeout, retries=retries)
        except RuntimeError as exc:
            errors.append(f"{url}: {exc}")
            continue

        values = {
            key: extract_span(page_html, id_suffix)
            for key, id_suffix in PROFILE_IDS.items()
        }
        if not values["player_name"]:
            errors.append(f"{url}: 선수 기본정보를 찾지 못함")
            continue

        position, throws_hand, bats_side, bat_throw = parse_position(
            values["position_raw"]
        )
        height_cm, weight_kg = parse_height_weight(values["height_weight_raw"])

        result = empty_result(player)
        result.update(
            {
                "player_name": values["player_name"],
                "uniform_number": values["uniform_number"],
                "birth_date": parse_birth_date(values["birthday_raw"]),
                "position": position,
                "throws_hand": throws_hand,
                "bats_side": bats_side,
                "bat_throw": bat_throw,
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "source_url": url,
                "crawl_status": "success",
                "error_message": "",
            }
        )
        return result

    result = empty_result(player)
    result.update(
        {
            "crawl_status": "failed",
            "error_message": " / ".join(errors)[:1000],
        }
    )
    return result


def read_completed(path: str) -> dict[str, dict[str, str]]:
    completed: dict[str, dict[str, str]] = {}
    if not os.path.exists(path):
        return completed
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            player_id = normalize_player_id(row.get("player_id"))
            if player_id and row.get("crawl_status") == "success":
                completed[player_id] = {field: row.get(field, "") for field in OUTPUT_FIELDS}
    return completed


def write_results(path: str, results: list[dict[str, str]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    os.replace(temporary, output)


def resolve_inputs(arguments: list[str]) -> list[str]:
    if arguments:
        paths = arguments
    else:
        paths = sorted(glob.glob("player_*_stats*.csv"))
    paths = [path for path in paths if Path(path).is_file()]
    if not paths:
        raise RuntimeError(
            "입력 CSV가 없습니다. 스크립트와 같은 폴더에 player_*_stats*.csv를 "
            "두거나 실행 명령에 CSV 경로를 지정하세요."
        )
    return paths


def main() -> int:
    args = parse_args()
    try:
        paths = resolve_inputs(args.inputs)
        players = load_players(paths)
    except RuntimeError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1

    if args.limit is not None:
        players = players[: max(args.limit, 0)]

    completed = read_completed(args.output) if args.resume else {}
    results: list[dict[str, str]] = []
    success_count = 0
    failed_count = 0

    print("입력 CSV:")
    for path in paths:
        print(f"  - {path}")
    print(f"중복 제거 후 선수 수: {len(players)}명")
    if completed:
        print(f"이어하기 대상: 기존 성공 {len(completed)}명")

    try:
        for index, player in enumerate(players, start=1):
            player_id = player["player_id"]
            if player_id in completed:
                result = completed[player_id]
                print(
                    f"[{index}/{len(players)}] {player_id} "
                    f"{result.get('player_name', '')}: 건너뜀"
                )
            else:
                print(
                    f"[{index}/{len(players)}] {player_id} "
                    f"{player['csv_player_name']}: 수집 중"
                )
                result = crawl_player(player, args.timeout, max(args.retries, 1))
                if result["crawl_status"] == "success":
                    print(
                        f"  성공: {result['position']} "
                        f"{result['bat_throw']} / {result['height_cm']}cm "
                        f"{result['weight_kg']}kg"
                    )
                else:
                    print(f"  실패: {result['error_message']}")
                if index < len(players):
                    time.sleep(max(args.delay, 0.0))

            results.append(result)
            if result["crawl_status"] == "success":
                success_count += 1
            else:
                failed_count += 1

            # 중간에 종료되어도 현재까지의 결과가 남도록 매 선수마다 저장한다.
            write_results(args.output, results)
    except KeyboardInterrupt:
        print("\n사용자가 중단했습니다. 현재까지의 결과를 저장했습니다.")
        return 130

    print()
    print(f"완료: 성공 {success_count}명, 실패 {failed_count}명")
    print(f"결과 파일: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
