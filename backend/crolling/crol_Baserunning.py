import csv
import re
import time

import requests
from bs4 import BeautifulSoup

TARGET_URL = "https://www.koreabaseball.com/Record/Player/Runner/Basic.aspx"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.koreabaseball.com/",
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
    "순위", "선수명", "팀명", "G", "SBA", "SB", "CS", "SB%", "OOB", "PKO",
    "player_link", "player_id", "season_year", "team_code"
]


# ---------------- 공통 함수 ---------------- #

def get_soup(session, url):
    resp = session.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return BeautifulSoup(resp.text, "lxml")


def extract_form_fields(soup):
    form = soup.find("form")
    data = {}

    for tag in form.find_all("input"):
        name = tag.get("name")
        if not name:
            continue
        data[name] = tag.get("value", "")

    for tag in form.find_all("select"):
        name = tag.get("name")
        if not name:
            continue
        selected = tag.find("option", selected=True)
        data[name] = selected.get("value", "") if selected else ""

    return data


def extract_updatepanel_html(text):
    marker = "|updatePanel|"
    idx = text.find(marker)
    if idx == -1:
        return text

    after = text[idx + len(marker):]
    first_sep = after.find("|")
    content = after[first_sep + 1:]

    end_idx = content.find("|0|hiddenField|")
    if end_idx != -1:
        content = content[:end_idx]

    return content.strip()


def response_to_soup(text):
    return BeautifulSoup(extract_updatepanel_html(text), "lxml")


def postback(session, url, soup, event_target, overrides=None):
    payload = extract_form_fields(soup)
    payload["__EVENTTARGET"] = event_target
    payload["__EVENTARGUMENT"] = ""

    if overrides:
        payload.update(overrides)

    resp = session.post(url, headers=HEADERS, data=payload, timeout=20)
    resp.raise_for_status()
    return response_to_soup(resp.text)


def change_select(session, url, soup, field_name, value):
    return postback(session, url, soup, field_name, {field_name: value})


# ---------------- 핵심 로직 ---------------- #

def apply_filters(session, season, series, team):
    soup = get_soup(session, TARGET_URL)

    soup = change_select(session, TARGET_URL, soup, FIELD_NAMES["season"], season)
    soup = change_select(session, TARGET_URL, soup, FIELD_NAMES["series"], series)
    soup = change_select(session, TARGET_URL, soup, FIELD_NAMES["team"], team)

    return soup


def find_table(soup):
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True)
        if "선수명" in text and "SB%" in text:
            return table
    return None


def extract_player_id(link):
    if not link:
        return None
    m = re.search(r"playerId=(\d+)", link)
    return m.group(1) if m else None


def parse_table(table, season, team_code):
    headers = [th.get_text(strip=True) for th in table.find_all("th")]

    rows = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue

        cols = [td.get_text(strip=True) for td in tds]
        row = dict(zip(headers, cols))

        link_tag = tds[1].find("a")
        link = link_tag["href"] if link_tag else None

        row["player_link"] = link
        row["player_id"] = extract_player_id(link)
        row["season_year"] = season
        row["team_code"] = team_code

        rows.append(row)

    return rows


def get_pages(soup):
    pages = set()
    paging = soup.find("div", class_="paging")

    if paging:
        for a in paging.find_all("a"):
            if a.text.isdigit():
                pages.add(int(a.text))

    return sorted(pages)


def go_page(session, soup, page):
    return postback(
        session,
        TARGET_URL,
        soup,
        f"{PAGER_TARGET_PREFIX}{page}",
        {FIELD_NAMES["hf_page"]: str(page)}
    )


def crawl_runner(season, team_code):
    session = requests.Session()

    soup = apply_filters(session, season, "0", team_code)
    table = find_table(soup)

    all_rows = []
    seen = set()

    def add_rows(rows):
        for r in rows:
            key = (r["player_id"], r["선수명"])
            if key not in seen:
                seen.add(key)
                all_rows.append(r)

    add_rows(parse_table(table, season, team_code))

    for page in get_pages(soup):
        if page == 1:
            continue
        time.sleep(0.5)
        soup = go_page(session, soup, page)
        table = find_table(soup)
        add_rows(parse_table(table, season, team_code))

    return all_rows


def save_csv(rows, filename):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FINAL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


# ---------------- 실행 ---------------- #

def main():
    team_code = "LG"
    all_rows = []

    for year in range(2021, 2023):
        season = str(year)
        print("수집:", season)

        rows = crawl_runner(season, team_code)
        all_rows.extend(rows)

    print(f"\n전체 수집 건수: {len(all_rows)}")
    save_csv(all_rows, f"runner_2021_2024_{team_code}.csv")
    print("CSV 저장 완료")

    print("\n=== 앞 5개 ===")
    for row in all_rows[:5]:
        print(row)

    print("\n=== 뒤 5개 ===")
    for row in all_rows[-5:]:
        print(row)


if __name__ == "__main__":
    main()