# 시뮬레이터 자료용 그래프

프론트/API 연결 없이 시뮬레이터 실행 마지막에 실제 맞대결 10,000경기의
최종 스코어를 집계하고 두 그래프를 각각 표시·저장합니다.

프로젝트 루트 `ballpark-intelligence`에서 Windows PowerShell로 실행:

```powershell
.\venv\Scripts\python.exe -m pip install -r backend/game_simulator/requirements-plots.txt
.\venv\Scripts\python.exe backend/game_simulator/simulator_main.py
```

기존처럼 팀과 선발투수를 선택하면 됩니다. 그래프는 한 번에 하나씩 열리고,
첫 창을 닫으면 다음 창이 열립니다. 창 도구 모음에서 확대하거나 다른 이름으로
저장할 수도 있습니다. 막대 위에 마우스를 올리면 정확한 스코어·횟수·비율을 표시합니다.
이 마우스 표시는 실행 중인 그래프 창에서 작동합니다. 저장한 PNG는 정적 이미지입니다.

- `*_frequency.png`: 50회 이상 나온 스코어 중 빈도순 상위 10개만 표시.
- `*_score.png`: `0:0, 0:1, 1:0, 0:2, 1:1, 2:0, …` 순으로 정렬.
  합계 득점이 같으면 원정팀 득점 오름차순입니다. 50회 이상 나온 스코어만
  표시합니다. 정규분포를 가정하거나 보정하지 않습니다.
- `*_frequency_table.csv`: 빈도순 전체 결과 표. 순위, 두 팀 득점, 횟수, 비율을
  포함하며 Excel에서 한글이 보이도록 UTF-8 BOM으로 저장합니다.
- `*_frequency_table_01.png`: 처음 표시되는 표의 첫 페이지(최대 25행)만 이미지로 저장.
  두 번째 페이지부터는 자동 저장하지 않습니다. 표 창에서는 이전/다음 페이지
  버튼으로 전체 결과를 확인할 수 있습니다.

두 그래프의 50회 미만 제외 조건은 표에 적용하지 않습니다. 표는 전체 관측
결과를 유지하며, 승률과 마우스 표시 비율도 전체 시뮬레이션 횟수를 기준으로 계산합니다.

PNG는 기본적으로 이 폴더의 `results/`에 저장됩니다. 파일 이름에 두 팀과
실행 시각이 들어갑니다. 전체 이미지의 축 라벨은 가독성을 위해 간격 표시하며,
창에서 확대하면 해당 구간의 상세 스코어가 표시됩니다.

```powershell
# 창 없이 그래프 PNG, 전체 표 CSV, 첫 페이지 표 PNG 저장
.\venv\Scripts\python.exe backend/game_simulator/simulator_main.py --no-show

# 저장 폴더, 반복 횟수, 재현용 난수 시드 지정
.\venv\Scripts\python.exe backend/game_simulator/simulator_main.py --games 10000 --seed 42 --output-dir .\simulator_figures

# 한 정렬 방식만 표시·저장
.\venv\Scripts\python.exe backend/game_simulator/simulator_main.py --plot-order score
```

`--plot-order`는 그래프 정렬 방식만 선택합니다. 빈도순 표는 항상 생성됩니다.

기존 마르코프/팀별 몬테카를로 보고서는 유지됩니다. 추가된 두 그래프는
같은 라인업과 상대 선발투수 보정을 사용한 **실제 맞대결 반복 결과**입니다.
9회말 생략·끝내기·최대 12회 연장·무승부를 반영하므로, 기존의 팀별 정규
9이닝 공격 통계와는 다를 수 있습니다.
