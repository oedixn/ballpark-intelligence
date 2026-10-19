"""Reproducible CSV benchmark; never activates a service model.

Run from backend: python -m app.ml.benchmark --help
"""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import numpy as np

from app.ml.lstm_predictor import (
    HITTER_FEATURES, HITTER_TARGETS, PITCHER_FEATURES, PITCHER_TARGETS,
    _build_model_and_scalers, _calculate_regression_metrics, _prepare_training_data,
    _weighted_avg_predict,
    input_feature_requirements,
)
from app.ml.model_store import save_bundle
from app.ml.season_features import aggregate_hitter_seasons, aggregate_pitcher_seasons, valid_sequence
from app.ml.train import positive_int


def load_csv_data(csv_dir, model_type, through_season, lookback=3, *, include_hitter_games=False):
    path = Path(csv_dir) / f'player_{model_type}_stats.csv'
    with path.open(encoding='utf-8-sig', newline='') as handle:
        raw = [row for row in csv.DictReader(handle) if int(row['season_year']) <= through_season]
    aggregate = aggregate_hitter_seasons if model_type == 'hitter' else aggregate_pitcher_seasons
    workload, minimum = ('pa', 100) if model_type == 'hitter' else ('g', 10)
    grouped = defaultdict(list)
    aggregated = (aggregate(raw, include_games=True)
                  if model_type == 'hitter' and include_hitter_games else aggregate(raw))
    for row in aggregated:
        grouped[str(row['player_id'])].append(row)
    ids = sorted(pid for pid, rows in grouped.items()
                 if sum(row[workload] >= minimum for row in rows) >= 4)
    names = {str(row['player_id']): row.get('player_name', '') for row in raw}
    source = {
        'type': 'repository_csv', 'path': str(path.resolve()),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'raw_rows': len(raw), 'eligible_players': len(ids),
        'cohort': f'at least 4 seasons with {workload}>={minimum}; consecutive {lookback}-year inputs',
    }
    return ids, grouped, names, source


def collect_test_cases(ids, get_ts, features, targets, test_season, lookback=3):
    cases = []
    for pid in ids:
        data = sorted(get_ts(pid), key=lambda row: int(row['season_year']))
        year_counts = Counter(int(row['season_year']) for row in data)
        for i in range(len(data) - lookback):
            window = data[i:i+lookback+1]
            if (int(window[-1]['season_year']) == test_season
                    and valid_sequence(window, input_feature_requirements(features) + targets,
                                       season_counts=year_counts)):
                cases.append((pid, window))
    return cases


def baseline_predictions(cases, features, targets):
    previous, weighted = [], []
    for _, window in cases:
        previous.append([float(window[-2][target]) for target in targets])
        # Keep the existing three-season API baseline unchanged, even for a
        # five-season LSTM. Never include the target season in its inputs.
        prediction = _weighted_avg_predict(window[-4:-1], features, targets)
        weighted.append([prediction[target] for target in targets])
    return {'last_season': np.asarray(previous), 'weighted_average': np.asarray(weighted)}


def run_benchmark(args, model_type, output_dir):
    features, targets = ((HITTER_FEATURES, HITTER_TARGETS) if model_type == 'hitter'
                         else (PITCHER_FEATURES, PITCHER_TARGETS))
    ids, grouped, names, source = load_csv_data(
        args.csv_dir, model_type, args.through_season, args.lookback,
    )
    started = perf_counter()
    model, sx, sy = _build_model_and_scalers(
        ids, grouped.__getitem__, features, targets, epochs=args.epochs,
        batch_size=args.batch_size, patience=args.patience, seed=args.seed,
        through_season=args.through_season, validation_season=args.validation_season,
        test_season=args.test_season,
        lookback=args.lookback,
    )
    training_seconds = perf_counter() - started
    prepared = _prepare_training_data(
        ids, grouped.__getitem__, features, targets, through_season=args.through_season,
        validation_season=args.validation_season, test_season=args.test_season,
        lookback=args.lookback,
    )
    cases = collect_test_cases(
        ids, grouped.__getitem__, features, targets, prepared.test_season, args.lookback,
    )
    actual = sy.inverse_transform(prepared.y_test)
    expected = np.array([[row[target] for target in targets] for _, window in cases for row in window[-1:]])
    np.testing.assert_allclose(actual, expected, rtol=1e-7, atol=1e-9)
    predictions = {'lstm': sy.inverse_transform(model.predict(prepared.X_test, verbose=0)),
                   **baseline_predictions(cases, features, targets)}
    scores = {name: _calculate_regression_metrics(actual, predicted, targets)
              for name, predicted in predictions.items()}
    for target in targets:
        np.testing.assert_allclose(scores['lstm'][target]['mae'], model.evaluation_report['metrics'][target]['mae'])

    report = dict(model.experiment_report)
    report['purpose'] = 'benchmark'
    report['history_units'] = 'scaled'
    report['data_source'] = source
    report['training_seconds'] = training_seconds
    report['epochs_run'] = len(report['history']['loss'])
    report['best_epoch'] = int(np.argmin(report['history']['val_rmse'])) + 1
    evaluation = dict(model.evaluation_report)
    evaluation['baselines'] = {key: value for key, value in scores.items() if key != 'lstm'}
    report['evaluation'] = evaluation
    directory = save_bundle(model_type, model, sx, sy, report, root=output_dir / 'models', activate=False)
    with (directory / 'test_predictions.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            'player_id', 'player_name', 'season_year', 'target', 'actual',
            'lstm', 'last_season', 'weighted_average',
        ])
        writer.writeheader()
        for i, (pid, _) in enumerate(cases):
            for j, target in enumerate(targets):
                writer.writerow({
                    'player_id': pid, 'player_name': names.get(pid, ''),
                    'season_year': prepared.test_season, 'target': target,
                    'actual': actual[i, j],
                    **{key: values[i, j] for key, values in predictions.items()},
                })
    return {
        'model_type': model_type, 'artifact_dir': str(directory), 'data_source': source,
        'lookback': args.lookback,
        'epochs_run': report['epochs_run'], 'best_epoch': report['best_epoch'],
        'training_seconds': training_seconds, 'evaluation': evaluation,
    }


def write_summary(output_dir, results, args):
    summary = {
        'seed': args.seed, 'epochs_limit': args.epochs, 'patience': args.patience,
        'lookback': args.lookback,
        'created_at_utc': datetime.now(timezone.utc).isoformat(), 'service_activated': False,
        'results': results,
    }
    (output_dir / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8',
    )
    lines = ['# LSTM 성적 예측 성능 측정', '',
             f'- 데이터: 저장소 CSV, {args.through_season}년까지',
             f'- 분리: 학습 정답 < {args.validation_season}, 검증 {args.validation_season}, 테스트 {args.test_season}',
             f'- 설정: seed={args.seed}, 최대 {args.epochs} epoch, patience={args.patience}',
             f'- 입력: 최근 연속 {args.lookback}시즌 → 다음 시즌 예측',
             '- 서비스 모델 활성화 없음. 지표는 원래 단위이며 낮을수록 좋습니다.',
             '- 이 테스트는 기록·경력 조건을 만족하는 선수 대상이며 전체 KBO 선수 성능을 뜻하지 않습니다.', '',
             '| 유형 | 지표 | LSTM MAE | LSTM RMSE | 전년도 유지 MAE | 전년도 유지 RMSE | 가중평균 MAE | 가중평균 RMSE |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for result in results:
        evaluation = result['evaluation']
        for target, metric in evaluation['metrics'].items():
            previous = evaluation['baselines']['last_season'][target]
            weighted = evaluation['baselines']['weighted_average'][target]
            lines.append(f"| {result['model_type']} | {target} | {metric['mae']:.6f} | {metric['rmse']:.6f} "
                         f"| {previous['mae']:.6f} | {previous['rmse']:.6f} | {weighted['mae']:.6f} | {weighted['rmse']:.6f} |")
    lines += ['', '## 실행 상세', '']
    for result in results:
        e = result['evaluation']
        lines.append(f"- {result['model_type']}: 학습 {e['train_samples']} / 검증 {e['validation_samples']} / "
                     f"테스트 {e['test_samples']}개. {result['epochs_run']} epoch 실행, 최적 epoch {result['best_epoch']}. "
                     f"학습 시간 {result['training_seconds']:.1f}초. 모델·개별 예측: `{result['artifact_dir']}`")
    lines += ['', '가중평균 기준 모델은 현재 API의 0.2/0.3/0.5 가중치와 추세 보정·반올림을 그대로 사용합니다.',
              '한 번의 시간 분리·seed 결과입니다. 이후 구조 선택은 검증 점수로 하고, 이 테스트 점수로 반복 튜닝하지 않습니다.', '']
    (output_dir / 'summary.md').write_text('\n'.join(lines), encoding='utf-8')


def compare_prediction_files(previous_path, current_path, targets):
    """Re-score both runs on identical player/season pairs, not full cohorts."""
    def read_cases(path):
        cases = defaultdict(dict)
        with Path(path).open(encoding='utf-8-sig', newline='') as handle:
            for row in csv.DictReader(handle):
                key = (row['player_id'], int(row['season_year']))
                target = row['target']
                if target in cases[key]:
                    raise ValueError(f'중복 선수·시즌·지표: {key}, {target}')
                cases[key][target] = row
        if any(set(values) != set(targets) for values in cases.values()):
            raise ValueError('비교 파일에 누락되거나 다른 예측 지표가 있습니다.')
        return cases

    previous, current = read_cases(previous_path), read_cases(current_path)
    common = sorted(previous.keys() & current.keys())
    if not common:
        raise ValueError('두 실험에 공통 테스트 선수가 없습니다.')
    def values(cases, field):
        return np.array([[float(cases[key][target][field]) for target in targets]
                         for key in common])
    actual = values(current, 'actual')
    np.testing.assert_allclose(values(previous, 'actual'), actual, rtol=1e-9, atol=1e-12)
    return {
        'previous_test_samples': len(previous), 'current_test_samples': len(current),
        'common_test_samples': len(common),
        'common_players': [{'player_id': pid, 'season_year': year} for pid, year in common],
        'previous_metrics': _calculate_regression_metrics(actual, values(previous, 'lstm'), targets),
        'current_metrics': _calculate_regression_metrics(actual, values(current, 'lstm'), targets),
        'baselines': {
            field: _calculate_regression_metrics(actual, values(current, field), targets)
            for field in ('last_season', 'weighted_average')
        },
    }


def write_lookback_comparison(output_dir, previous_dir):
    previous_dir = Path(previous_dir).resolve()
    previous_summary = json.loads((previous_dir / 'summary.json').read_text(encoding='utf-8'))
    current_summary = json.loads((output_dir / 'summary.json').read_text(encoding='utf-8'))
    for key in ('seed', 'epochs_limit', 'patience'):
        if previous_summary[key] != current_summary[key]:
            raise ValueError(f'비교 실험 설정이 다릅니다: {key}')
    previous_results = {result['model_type']: result for result in previous_summary['results']}
    comparisons = []
    lines = ['# 최근 3시즌 대 5시즌 입력 비교', '',
             '- 두 모델이 모두 예측 가능한 동일 선수·동일 시즌에서 재계산한 원래 단위 오차입니다.',
             '- 학습·검증 표본 수는 입력 길이에 따라 다릅니다. 입력 길이만의 순수한 효과로 단정할 수 없습니다.',
             '- 단일 seed·단일 테스트 연도 결과이며 서비스 모델은 변경하지 않았습니다.', '',
             '| 유형 | 지표 | 3시즌 MAE | 5시즌 MAE | 3시즌 RMSE | 5시즌 RMSE |',
             '| --- | --- | ---: | ---: | ---: | ---: |']
    for current in current_summary['results']:
        previous = previous_results[current['model_type']]
        old_dir, new_dir = Path(previous['artifact_dir']), Path(current['artifact_dir'])
        old_report = json.loads((old_dir / 'report.json').read_text(encoding='utf-8'))
        new_report = json.loads((new_dir / 'report.json').read_text(encoding='utf-8'))
        if old_report['lookback'] != 3 or new_report['lookback'] != 5:
            raise ValueError('--compare-run은 기존 3시즌 실행과 새 5시즌 실행을 비교합니다.')
        if previous['data_source']['sha256'] != current['data_source']['sha256']:
            raise ValueError('두 실험의 원본 데이터 지문이 다릅니다.')
        if old_report['targets'] != new_report['targets'] or old_report['features'] != new_report['features']:
            raise ValueError('두 모델의 입력·출력 지표가 다릅니다.')
        for key in ('train_last_season', 'validation_season', 'test_season'):
            if previous['evaluation'][key] != current['evaluation'][key]:
                raise ValueError(f'비교 실험의 데이터 분리 연도가 다릅니다: {key}')
        comparison = compare_prediction_files(
            old_dir / 'test_predictions.csv', new_dir / 'test_predictions.csv', new_report['targets'],
        )
        comparison.update({
            'model_type': current['model_type'],
            'previous_artifact_dir': str(old_dir), 'current_artifact_dir': str(new_dir),
        })
        comparisons.append(comparison)
        for target in new_report['targets']:
            old = comparison['previous_metrics'][target]
            new = comparison['current_metrics'][target]
            lines.append(f"| {current['model_type']} | {target} | {old['mae']:.6f} | {new['mae']:.6f} "
                         f"| {old['rmse']:.6f} | {new['rmse']:.6f} |")
    lines += ['', '## 공통 테스트 표본', '']
    for comparison in comparisons:
        lines.append(f"- {comparison['model_type']}: {comparison['common_test_samples']}명 "
                     f"(기존 전체 {comparison['previous_test_samples']}명, 새 전체 {comparison['current_test_samples']}명)")
    lines += ['', f'3시즌 실행: `{previous_dir}`', f'5시즌 실행: `{output_dir}`', '']
    (output_dir / 'comparison.json').write_text(json.dumps({
        'previous_run': str(previous_dir), 'current_run': str(output_dir),
        'results': comparisons,
    }, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    (output_dir / 'comparison.md').write_text('\n'.join(lines), encoding='utf-8')


def main(argv=None):
    backend_dir = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description='CSV 기반 LSTM·기준 모델 성능 비교; 서비스 적용 없음')
    parser.add_argument('--csv-dir', type=Path, default=backend_dir / 'db/csv/2015_2025_KBO')
    parser.add_argument('--output-dir', type=Path, default=backend_dir / 'models/benchmarks')
    parser.add_argument('--type', choices=['hitter', 'pitcher', 'both'], default='both')
    parser.add_argument('--through-season', type=positive_int, default=2025)
    parser.add_argument('--validation-season', type=positive_int, default=2024)
    parser.add_argument('--test-season', type=positive_int, default=2025)
    parser.add_argument('--epochs', type=positive_int, default=100)
    parser.add_argument('--batch-size', type=positive_int, default=16)
    parser.add_argument('--patience', type=positive_int, default=10)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--lookback', type=int, choices=(3, 5), default=3,
                        help='입력할 과거 시즌 수. 5시즌은 서비스 적용 없는 비교 실험 전용.')
    parser.add_argument('--compare-run', type=Path,
                        help='동일 선수 비교에 사용할 기존 3시즌 벤치마크 실행 폴더')
    args = parser.parse_args(argv)
    if not args.validation_season < args.test_season <= args.through_season:
        parser.error('검증 시즌 < 테스트 시즌 <= 사용할 마지막 시즌이어야 합니다.')
    if args.compare_run and args.lookback != 5:
        parser.error('--compare-run은 --lookback 5와 함께 사용하세요.')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
    output_dir = args.output_dir.resolve() / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    results = []
    for model_type in ('hitter', 'pitcher') if args.type == 'both' else (args.type,):
        results.append(run_benchmark(args, model_type, output_dir))
        write_summary(output_dir, results, args)
    if args.compare_run:
        write_lookback_comparison(output_dir, args.compare_run)
    print(f'성능 보고서: {output_dir / "summary.md"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
