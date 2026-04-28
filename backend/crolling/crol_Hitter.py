import csv
import re
import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.koreabaseball.com/",
}

URLS = {
    "basic1": "https://www.koreabaseball.com/Record/Player/HitterBasic/Basic1.aspx",
    "basic2": "https://www.koreabaseball.com/Record/Player/HitterBasic/Basic2.aspx",
    "detail1": "https://www.koreabaseball.com/Record/Player/HitterBasic/Detail1.aspx",
}

FIELD_NAMES = {
    "season": "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$ddlSeason$ddlSeason",
    "series": "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$ddlSeries$ddlSeries",
    "team": "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$ddlTeam$ddlTeam",
    "hf_page": "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$hfPage",
}

PAGER_TARGET_PREFIX = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$ucPager$btnNo"

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

FINAL_COLUMNS = [
    "순위", "선수명", "팀명",
    "AVG", "G", "PA", "AB", "R", "H", "2B", "3B", "HR", "TB", "RBI", "SAC", "SF",
    "BB", "IBB", "HBP", "SO", "GDP", "SLG", "OBP", "OPS", "MH", "RISP", "PH-BA",
    "XBH", "GO", "AO", "GO/AO", "GW RBI", "BB/K", "P/PA", "ISOP", "XR", "GPA",
    "player_link", "player_id", "season_year", "team_code"
]


def get_soup(session: requests.Session, url: str) -> BeautifulSoup:
    resp = session.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return BeautifulSoup(resp.text, "lxml")


def extract_form_fields(soup: BeautifulSoup) -> dict:
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


def extract_updatepanel_html(response_text: str) -> str:
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
        html_fragment = after[content_start:min(end_positions)]
    else:
        html_fragment = after[content_start:]

    return html_fragment.strip()


def response_to_soup(response_text: str) -> BeautifulSoup:
    html = extract_updatepanel_html(response_text)
    return BeautifulSoup(html, "lxml")


def postback(
    session: requests.Session,
    url: str,
    current_soup: BeautifulSoup,
    event_target: str,
    overrides: Optional[dict] = None,
) -> BeautifulSoup:
    payload = extract_form_fields(current_soup)
    payload["__EVENTTARGET"] = event_target
    payload["__EVENTARGUMENT"] = ""

    if overrides:
        payload.update(overrides)

    resp = session.post(url, headers=HEADERS, data=payload, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return response_to_soup(resp.text)


def change_select(session: requests.Session, url: str, soup: BeautifulSoup, field_name: str, value: str) -> BeautifulSoup:
    current_form_data = extract_form_fields(soup)
    if field_name not in current_form_data:
        return soup

    overrides = {field_name: value}
    return postback(
        session=session,
        url=url,
        current_soup=soup,
        event_target=field_name,
        overrides=overrides,
    )


def apply_filters_step_by_step(
    session: requests.Session,
    url: str,
    season: str,
    series: str,
    team: str,
) -> BeautifulSoup:
    soup = get_soup(session, url)
    soup = change_select(session, url, soup, FIELD_NAMES["season"], season)
    soup = change_select(session, url, soup, FIELD_NAMES["series"], series)
    soup = change_select(session, url, soup, FIELD_NAMES["team"], team)
    return soup


def go_to_page(session: requests.Session, url: str, soup: BeautifulSoup, page_no: int) -> BeautifulSoup:
    current_form_data = extract_form_fields(soup)
    overrides = {}

    if FIELD_NAMES["hf_page"] in current_form_data:
        overrides[FIELD_NAMES["hf_page"]] = str(page_no)

    return postback(
        session=session,
        url=url,
        current_soup=soup,
        event_target=f"{PAGER_TARGET_PREFIX}{page_no}",
        overrides=overrides,
    )


def find_target_table(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    candidates = []

    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True)
        if "선수명" in text and "팀명" in text:
            score = 0
            for keyword in ["AVG", "RISP", "XBH", "GPA", "TB", "OPS", "RBI"]:
                if keyword in text:
                    score += 1
            candidates.append((score, len(table.find_all("tr")), table))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]


def extract_player_id(player_link: Optional[str]) -> Optional[str]:
    if not player_link:
        return None
    match = re.search(r"playerId=(\d+)", player_link)
    return match.group(1) if match else None


def parse_table(table: BeautifulSoup, season: str, team_code: str) -> List[dict]:
    headers = []
    thead = table.find("thead")
    if thead:
        headers = [th.get_text(" ", strip=True) for th in thead.find_all("th")]

    rows = []
    tbody = table.find("tbody")
    if tbody is None:
        return rows

    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue

        cols = [td.get_text(" ", strip=True) for td in tds]
        if headers and len(headers) == len(cols):
            row = dict(zip(headers, cols))
        else:
            row = {f"col_{i+1}": v for i, v in enumerate(cols)}

        player_link_tag = tds[1].find("a") if len(tds) > 1 else None
        player_link = player_link_tag["href"] if player_link_tag and player_link_tag.get("href") else None

        row["player_link"] = player_link
        row["player_id"] = extract_player_id(player_link)
        row["season_year"] = season
        row["team_code"] = team_code

        rows.append(row)

    return rows


def extract_available_page_numbers(soup: BeautifulSoup) -> List[int]:
    paging = soup.find("div", class_="paging")
    if paging is None:
        return []

    pages = set()
    for a in paging.find_all("a"):
        text = a.get_text(strip=True)
        if text.isdigit():
            pages.add(int(text))
    return sorted(pages)


def crawl_one_page_group(
    session: requests.Session,
    url: str,
    season: str,
    team_code: str,
    series: str = "0",
    sleep_sec: float = 0.5,
) -> List[dict]:
    soup = apply_filters_step_by_step(
        session=session,
        url=url,
        season=season,
        series=series,
        team=team_code,
    )

    table = find_target_table(soup)
    if table is None:
        raise RuntimeError(f"테이블을 찾지 못했습니다: {url}")

    all_rows = []
    seen = set()

    rows = parse_table(table, season, team_code)
    for row in rows:
        key = (row.get("player_id"), row.get("선수명"), row.get("팀명"))
        if key not in seen:
            seen.add(key)
            all_rows.append(row)

    page_numbers = extract_available_page_numbers(soup)

    for page_no in page_numbers:
        if page_no == 1:
            continue

        time.sleep(sleep_sec)
        next_soup = go_to_page(session, url, soup, page_no)
        table = find_target_table(next_soup)
        if table is None:
            continue

        rows = parse_table(table, season, team_code)
        for row in rows:
            key = (row.get("player_id"), row.get("선수명"), row.get("팀명"))
            if key not in seen:
                seen.add(key)
                all_rows.append(row)

        soup = next_soup

    return all_rows


def merge_player_rows(*row_groups: List[dict]) -> List[dict]:
    merged: Dict[str, dict] = {}

    for rows in row_groups:
        for row in rows:
            player_id = row.get("player_id")
            player_link = row.get("player_link")
            fallback_key = f"{row.get('season_year')}|{row.get('팀명')}|{row.get('선수명')}"

            key = player_id or player_link or fallback_key

            if key not in merged:
                merged[key] = {}

            merged[key].update(row)

    return list(merged.values())


def sort_rows(rows: List[dict]) -> List[dict]:
    def sort_key(row: dict):
        rank = row.get("순위", "999999")
        try:
            rank_num = int(rank)
        except ValueError:
            rank_num = 999999
        return (row.get("팀명", ""), rank_num, row.get("선수명", ""))

    return sorted(rows, key=sort_key)


def filter_team_only(rows: List[dict], team_name: str) -> List[dict]:
    return [row for row in rows if row.get("팀명") == team_name]


def normalize_rows(rows: List[dict]) -> List[dict]:
    normalized = []

    for row in rows:
        out = {}
        for col in FINAL_COLUMNS:
            out[col] = row.get(col, "")
        normalized.append(out)

    return normalized


def save_csv(rows: List[dict], filename: str) -> None:
    if not rows:
        print("저장할 데이터가 없습니다.")
        return

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FINAL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def crawl_hitter_all_columns(
    season: str,
    team_code: str,
    series: str = "0",
    sleep_sec: float = 0.7,
) -> List[dict]:
    session = requests.Session()

    basic1_rows = crawl_one_page_group(
        session=session,
        url=URLS["basic1"],
        season=season,
        team_code=team_code,
        series=series,
        sleep_sec=sleep_sec,
    )

    basic2_rows = crawl_one_page_group(
        session=session,
        url=URLS["basic2"],
        season=season,
        team_code=team_code,
        series=series,
        sleep_sec=sleep_sec,
    )

    detail1_rows = crawl_one_page_group(
        session=session,
        url=URLS["detail1"],
        season=season,
        team_code=team_code,
        series=series,
        sleep_sec=sleep_sec,
    )

    merged = merge_player_rows(basic1_rows, basic2_rows, detail1_rows)

    # 팀 필터가 서버에서 가끔 불안정하게 먹는 경우를 대비한 최종 안전장치
    # team_code -> 실제 팀명 매핑
    team_name_by_code = {v: k for k, v in TEAM_CODES.items()}
    expected_team_name = team_name_by_code.get(team_code, team_code)

    merged = filter_team_only(merged, expected_team_name)
    merged = sort_rows(merged)
    merged = normalize_rows(merged)

    return merged


def main():
    team_code = "LG"
    series = "0"
    all_rows = []

    for year in range(2021, 2026): #시작년도, 끝년도-1
        season = str(year)
        print(f"수집 시작: season={season}, team={team_code}")

        rows = crawl_hitter_all_columns(
            season=season,
            team_code=team_code,
            series=series,
            sleep_sec=0.7,
        )

        print(f"수집 완료: season={season}, rows={len(rows)}")
        all_rows.extend(rows)

    print(f"\n전체 수집 건수: {len(all_rows)}")
    save_csv(all_rows, "hitter_all_columns_2021_2024_LG.csv")
    print("CSV 저장 완료")

    print("\n=== 앞 5개 ===")
    for row in all_rows[:5]:
        print(row)

    print("\n=== 뒤 5개 ===")
    for row in all_rows[-5:]:
        print(row)

if __name__ == "__main__":
    main()