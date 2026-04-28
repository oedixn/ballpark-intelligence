import time
from io import StringIO
from urllib.parse import urlencode

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


class KBReportCrawler:
    BASE_URL = "http://www.kbreport.sbs"

    ENDPOINTS = {
        "standard": "/leader/standard",
        "advanced": "/leader/advanced",
        "main": "/leader/main"
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
        "롯데": "롯데",
        "한화": "한화",
        "KIA": "KIA"
    }

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
            options=options
        )

    def close(self):
        if self.driver:
            self.driver.quit()

    def clean(self, df):
        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(how="all").reset_index(drop=True)
        return df

    def build_url(self, endpoint, params=None, page=None):
        url = self.BASE_URL + endpoint
        if params:
            url = f"{url}?{urlencode(params)}"

        if page is not None and page > 1:
            url = f"{url}#/{page}"

        return url

    def get_table_from_page(self, url, table_index=0, wait_sec=2):
        self.driver.get(url)
        time.sleep(wait_sec)

        html = self.driver.page_source
        tables = pd.read_html(StringIO(html))

        if not tables:
            raise ValueError(f"No tables found: {url}")

        return self.clean(tables[table_index])

    def get_all_pages_table(self, endpoint, params=None, table_index=0, max_pages=50, wait_sec=2):
        all_pages = []
        seen_keys = set()
        prev_unique_count = 0

        for page in range(1, max_pages + 1):
            url = self.build_url(endpoint, params=params, page=page)

            try:
                df = self.get_table_from_page(url, table_index=table_index, wait_sec=wait_sec)
            except Exception as e:
                print(f"[페이지 {page} 수집 중단] {e}")
                break

            if df.empty:
                print(f"[페이지 {page}] 데이터 없음 -> 종료")
                break

            print(f"[페이지 {page}] 원본 행 수: {len(df)}")

            if "선수명" in df.columns and "팀명" in df.columns:
                page_keys = list(zip(df["선수명"], df["팀명"]))
            else:
                page_keys = [tuple(row.astype(str)) for _, row in df.iterrows()]

            new_rows = []
            new_count = 0

            for idx, key in enumerate(page_keys):
                if key not in seen_keys:
                    seen_keys.add(key)
                    new_rows.append(df.iloc[idx])
                    new_count += 1

            if new_rows:
                page_df = pd.DataFrame(new_rows).reset_index(drop=True)
                all_pages.append(page_df)

            print(f"[페이지 {page}] 새로 추가된 행 수: {new_count}")

            current_unique_count = len(seen_keys)

            if new_count == 0:
                print(f"[페이지 {page}] 더 이상 새로운 데이터 없음 -> 종료")
                break

            if current_unique_count == prev_unique_count:
                print(f"[페이지 {page}] 유니크 개수 변화 없음 -> 종료")
                break

            prev_unique_count = current_unique_count

        if not all_pages:
            raise ValueError("수집된 페이지 데이터가 없습니다.")

        final_df = pd.concat(all_pages, ignore_index=True)
        return final_df

    def get_all_data(self, year="2025", rows=500, max_pages=50):
        common_params = {
            "rows": rows,
            "teamId": "",
            "defense_no": "",
            "year_from": year,
            "year_to": year,
            "gameType": "",
            "split01": "",
            "split02_1": "",
            "split02_2": "",
            "r_tpa_count": "",
            "tpa_count": "0"
        }

        std = self.get_all_pages_table(
            self.ENDPOINTS["standard"],
            params=common_params,
            max_pages=max_pages
        )

        adv = self.get_all_pages_table(
            self.ENDPOINTS["advanced"],
            params=common_params,
            max_pages=max_pages
        )

        main_params = common_params.copy()
        main_params["order"] = "oWAR"
        main_params["orderType"] = "DESC"

        main = self.get_all_pages_table(
            self.ENDPOINTS["main"],
            params=main_params,
            max_pages=max_pages
        )

        std_cols = ["선수명", "팀명", "안타", "2루타", "3루타", "홈런", "볼넷", "HBP"]
        adv_cols = ["선수명", "팀명", "OPS", "ISO", "BABIP", "볼넷%", "삼진%", "SPD"]
        main_cols = ["선수명", "팀명", "WAR"]

        std = std[[c for c in std_cols if c in std.columns]].copy()
        adv = adv[[c for c in adv_cols if c in adv.columns]].copy()
        main = main[[c for c in main_cols if c in main.columns]].copy()

        std["선수명"] = std["선수명"].astype(str).str.replace("*", "", regex=False).str.strip()
        adv["선수명"] = adv["선수명"].astype(str).str.replace("*", "", regex=False).str.strip()
        main["선수명"] = main["선수명"].astype(str).str.replace("*", "", regex=False).str.strip()

        std["팀명"] = std["팀명"].astype(str).str.strip()
        adv["팀명"] = adv["팀명"].astype(str).str.strip()
        main["팀명"] = main["팀명"].astype(str).str.strip()

        std = std.drop_duplicates(subset=["선수명", "팀명"])
        adv = adv.drop_duplicates(subset=["선수명", "팀명"])
        main = main.drop_duplicates(subset=["선수명", "팀명"])

        df = std.merge(adv, on=["선수명", "팀명"], how="left")
        df = df.merge(main, on=["선수명", "팀명"], how="left")

        if "팀명" in df.columns:
            df["팀명"] = df["팀명"].replace(self.TEAM_NAME_MAP)

        numeric_cols = [
            "안타", "2루타", "3루타", "홈런", "볼넷", "HBP",
            "OPS", "ISO", "BABIP", "볼넷%", "삼진%", "SPD", "WAR"
        ]

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df["시즌"] = int(year)

        if "WAR" in df.columns:
            df = df.sort_values(by="WAR", ascending=False, na_position="last").reset_index(drop=True)

        return df


if __name__ == "__main__":
    # =====================================
    # 여기서 연도 범위를 설정하면 됨
    # 예: 2020 ~ 2024
    # =====================================
    START_YEAR = 2024
    END_YEAR = 2024

    ROWS_PER_PAGE = 500
    MAX_PAGES = 30

    crawler = KBReportCrawler()

    try:
        all_data = []

        for year in range(START_YEAR, END_YEAR + 1):
            print("\n" + "=" * 40)
            print(f"{year} 시즌 수집 시작")
            print("=" * 40)

            df = crawler.get_all_data(
                year=str(year),
                rows=ROWS_PER_PAGE,
                max_pages=MAX_PAGES
            )

            print(f"\n[{year} 시즌 데이터 수집 완료]")
            print(f"총 데이터 개수: {len(df)}개")
            print(f"행 개수: {df.shape[0]}, 열 개수: {df.shape[1]}")

            print("\n[데이터 앞 5줄]")
            print(df.head(5))

            print("\n[데이터 뒤 5줄]")
            print(df.tail(5))

            print("\n[컬럼별 결측치 개수]")
            print(df.isna().sum())

            year_file_name = f"kbo_{year}_final.csv"
            df.to_csv(year_file_name, index=False, encoding="utf-8-sig")
            print(f"\n연도별 저장 완료: {year_file_name}")

            all_data.append(df)

        final_df = pd.concat(all_data, ignore_index=True)

        print("\n" + "=" * 50)
        print(f"{START_YEAR} ~ {END_YEAR} 전체 수집 완료")
        print("=" * 50)
        print(f"총 데이터 개수: {len(final_df)}개")
        print(f"행 개수: {final_df.shape[0]}, 열 개수: {final_df.shape[1]}")

        print("\n[전체 데이터 앞 5줄]")
        print(final_df.head(5))

        print("\n[전체 데이터 뒤 5줄]")
        print(final_df.tail(5))

        print("\n[전체 컬럼별 결측치 개수]")
        print(final_df.isna().sum())

        total_file_name = f"kbo_{START_YEAR}_{END_YEAR}_final.csv"
        final_df.to_csv(total_file_name, index=False, encoding="utf-8-sig")
        print(f"\n전체 저장 완료: {total_file_name}")

    finally:
        crawler.close()