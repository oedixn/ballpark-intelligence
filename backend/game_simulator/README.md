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

## 중계·마무리 투수 켜기 / 끄기

기본값은 **끔**입니다. 옵션 없이 실행하거나 `--no-bullpen`을 지정하면 기존처럼
선발로 보정한 확률을 경기 끝까지 사용합니다. 기존 Markov/팀별 Monte Carlo
보고서와 스코어 그래프·표 기능은 유지됩니다.

```powershell
# 중계·마무리 자동 교체 켜기
.\venv\Scripts\python.exe backend/game_simulator/simulator_main.py --bullpen --no-show

# 끄기: 기존 선발 고정 방식
.\venv\Scripts\python.exe backend/game_simulator/simulator_main.py --no-bullpen --no-show

# 교체 기준 직접 지정
.\venv\Scripts\python.exe backend/game_simulator/simulator_main.py --bullpen --bullpen-config backend/game_simulator/bullpen_config.example.json
```

웹 시뮬레이터에서는 경기 시작 전 **중계·마무리 투수 자동 교체** 체크박스로
선택합니다. 단일 경기와 10,000경기 통계에 동일하게 적용됩니다. API 요청의
`bullpen_enabled`도 기본 `false`이며 `true`일 때만 새 경로로 실행합니다.

### 명단과 교체 판단

- 선발은 기존 선택을 사용합니다. 미선택한 웹 요청은 선발 등판 수가 가장 많은
  후보를 선택합니다. 명시적으로 선택한 선수를 찾을 수 없으면 오류를 반환합니다.
- 불펜 후보는 같은 팀·시즌에서 구원 등판(`g-gs`)이 있고, 구원 등판 수가 선발
  등판 수 이상인 투수입니다. 확정 출전 엔트리를 재현하는 명단은 아닙니다.
- 세이브가 있는 후보 중 최다 세이브 투수를 마무리로 추천합니다. 모두 0이면
  별도 마무리를 지정하지 않습니다. 홀드는 후반 중계 선택에 사용합니다.
- 매 타석 전 사용량, 실점, 점수 차, 주자·아웃 상황으로 교체 여부를 판단한 뒤
  다음 투수를 고릅니다. 초반에는 긴 이닝을 맡을 후보, 후반 접전에는 홀드가 많은
  후보, 정규 마지막 이닝 이후 1~3점 리드에는 마무리를 우선합니다.
- 강판 투수는 재등판하지 않으며, 불펜이 소진되면 마지막 투수가 계속 던집니다.
  주자·아웃·타순, 9회말 생략, 끝내기, 연장·무승부 처리는 유지됩니다.

### 사용량 자료와 설정값

CLI는 `backend/data/game_logs/<선택 시즌>.json`이 있으면 등판당 상대 타자 수를
표본 추출해 경기별 사용량 기준으로 씁니다. `--bullpen-history <경로>`로 파일을
직접 지정할 수도 있습니다. 완료되지 않았거나 시즌이 다른 파일은 오류 처리합니다.
자료가 없으면 순수 선발/순수 구원은 `tbf/g`, 선발·구원 병행 선수는 설정값을
사용합니다. 웹의 날짜 미지정 모드는 연간 DB 기록을, 날짜 지정 모드는 **당일을
제외한 이전 경기 기록만** 사용합니다.

경기별 기록에 저장된 최종 상대 타자 수에는 경기 종료로 등판이 끝난 경우도
포함됩니다. 표본 추출은 사용량의 근사이며, 실제 교체 확률을 학습한 결과는 아닙니다.
현재 일자별 기록에는 세이브·홀드가 없어 날짜 지정 모드는 특정 마무리를 자동
확정하지 않고 사용 가능한 구원 후보를 사용합니다.

`bullpen_config.example.json`의 값은 **미학습 기본 운용 규칙**입니다.

| 설정 | 기본값 | 의미 |
|---|---:|---|
| `starter_batters` / `reliever_batters` | 24 / 6 | 보직별 사용량을 구할 수 없을 때의 상대 타자 수 |
| `starter_max_batters` / `reliever_max_batters` | 36 / 15 | 사용량 기준을 정할 때의 상한; 불펜 소진 시 초과 가능 |
| `starter_min_batters` / `reliever_min_batters` | 9 / 3 | 실점·주자 위기 규칙을 적용할 최소 상대 타자 수 |
| `starter_runs` / `reliever_runs` | 4 / 3 | 조기 교체 기준 실점; 주자 위기는 누적 출루 허용도 함께 확인 |
| `crisis_runners` / `close_margin` | 2 / 3 | 2아웃 미만 위기 판단 주자 수 / 접전 점수 차 |
| `relief_prior_batters` | 60 | 구원 투수의 소표본 확률을 리그 평균으로 보정할 가상 타석 수 |

피로·좌우 상대 보정 계수는 검증 자료가 없어 추가하지 않았습니다. 투수 교체
때마다 원본 타자 확률에서 계산하므로 선발 보정이 누적되지 않습니다. 불펜 모드의
Markov/팀별 Monte Carlo 보고서는 **선발 고정 기준**, 맞대결 결과·그래프는
**불펜 교체 포함**으로 구분됩니다.

### 로그와 검증

타석 로그에 투수와 교체 사유를 기록합니다. `GameLog.pitching_changes`에는 교체 전
주자·아웃·점수 차, `pitching_appearances`에는 투수별 상대 타자 수·아웃·사용량
자료 출처가 들어갑니다. `runs_on_mound`는 승계주자의 득점도 포함한 마운드 위
실점으로, 자책점이나 공식 투수 책임 실점이 아닙니다.

반복 결과의 `bullpen.usage`는 팀별 평균 등판 인원·선발 상대 타자 수·선발 이닝을
제공합니다. 이닝 평균은 일반 소수값입니다. 실제 교체 순간의 점수·주자·아웃과
교체하지 않은 타석을 추가 수집해야 상황별 교체 확률을 학습·검증할 수 있습니다.

```powershell
$env:PYTHONPATH = 'backend'
.\venv\Scripts\python.exe -m unittest discover -s backend/tests -p 'test_bullpen*.py' -v
```
