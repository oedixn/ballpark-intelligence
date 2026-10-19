"""Offline input/architecture ablation. No activation or API changes.

Run from backend: python -m app.ml.ablation --help
"""

import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import numpy as np

from app.ml.benchmark import load_csv_data, collect_test_cases, baseline_predictions
from app.ml.lstm_predictor import (
    HITTER_FEATURES, HITTER_WORKLOAD_FEATURES, HITTER_TARGETS,
    PITCHER_FEATURES, PITCHER_TARGETS, LSTM_ARCHITECTURES,
    _build_model_and_scalers, _prepare_training_data, _calculate_regression_metrics,
)
from app.ml.model_store import save_bundle
from app.ml.train import positive_int


def audit_profiles(path, ids, test_cases):
    """Report coverage without excluding players or adding future missingness."""
    path = Path(path)
    births = {}
    if path.exists():
        with path.open(encoding='utf-8-sig', newline='') as handle:
            for row in csv.DictReader(handle):
                try:
                    birthday = date.fromisoformat(row['birth_date'])
                except (KeyError, ValueError):
                    continue
                pid = row['player_id']
                if pid in births and births[pid] != birthday:
                    raise ValueError(f'생년월일이 충돌하는 선수입니다: {pid}')
                births[pid] = birthday
    return {
        'path': str(path.resolve()),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
        'eligible_players': len(ids), 'eligible_with_birth_date': sum(pid in births for pid in ids),
        'test_players': len(test_cases),
        'test_with_birth_date': sum(pid in births for pid, _ in test_cases),
        'age_used': False,
        'reason': 'Partial current-profile coverage; preserve the original cohort and avoid survival-based selection.',
    }


def variants(model_type):
    feature_sets = [('base', HITTER_FEATURES), ('workload', HITTER_WORKLOAD_FEATURES)]
    if model_type == 'pitcher':
        feature_sets = [('base', PITCHER_FEATURES)]
    return [(name, list(features), architecture)
            for name, features in feature_sets for architecture in LSTM_ARCHITECTURES]


def select_by_validation(results):
    """Never rank configurations by the already-inspected 2025 reference test."""
    return min(results, key=lambda result: result['validation_score'])


def run_type(args, kind, output_dir):
    targets = HITTER_TARGETS if kind == 'hitter' else PITCHER_TARGETS
    base_features = HITTER_FEATURES if kind == 'hitter' else PITCHER_FEATURES
    ids, grouped, names, source = load_csv_data(
        args.csv_dir, kind, args.through_season, include_hitter_games=kind == 'hitter',
    )
    cases = collect_test_cases(ids, grouped.__getitem__, base_features, targets, args.test_season)
    profile_audit = audit_profiles(args.profiles, ids, cases)
    results, reference_labels, reference_case_keys = [], None, None
    for feature_set, features, architecture in variants(kind):
        label = f'{feature_set}__{architecture}'
        print(f'\n=== {kind}: {label} ===', flush=True)
        started = perf_counter()
        model, sx, sy = _build_model_and_scalers(
            ids, grouped.__getitem__, features, targets, lookback=3, architecture=architecture,
            epochs=args.epochs, batch_size=args.batch_size, patience=args.patience, seed=args.seed,
            through_season=args.through_season, validation_season=args.validation_season,
            test_season=args.test_season,
        )
        elapsed = perf_counter() - started
        prepared = _prepare_training_data(
            ids, grouped.__getitem__, features, targets, lookback=3,
            through_season=args.through_season, validation_season=args.validation_season,
            test_season=args.test_season,
        )
        current_cases = collect_test_cases(ids, grouped.__getitem__, features, targets, args.test_season)
        keys = [(pid, int(window[-1]['season_year'])) for pid, window in current_cases]
        labels = [sy.inverse_transform(values) for values in
                  (prepared.y_train, prepared.y_val, prepared.y_test)]
        if reference_labels is None:
            reference_labels, reference_case_keys = labels, keys
        else:
            if keys != reference_case_keys:
                raise ValueError('입력 추가로 테스트 선수가 변경되었습니다. 같은 표본 비교가 필요합니다.')
            for actual, expected in zip(labels, reference_labels):
                np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-12)
        expected = [[window[-1][target] for target in targets] for _, window in current_cases]
        np.testing.assert_allclose(labels[-1], expected, rtol=1e-10, atol=1e-12)
        predictions = sy.inverse_transform(model.predict(prepared.X_test, verbose=0))
        scores = _calculate_regression_metrics(labels[-1], predictions, targets)
        report = dict(model.experiment_report)
        for target in targets:
            np.testing.assert_allclose(scores[target]['mae'], report['evaluation']['metrics'][target]['mae'])
        validation_score = float(min(report['history']['val_rmse']))
        report.update(
            purpose='ablation', feature_set=feature_set, data_source=source,
            profile_audit=profile_audit, training_seconds=elapsed, history_units='scaled',
            selection={'dataset': 'validation', 'metric': 'scaled_rmse', 'value': validation_score},
            test_role='Already-inspected historical reference; not a fresh independent final test.',
        )
        directory = save_bundle(kind, model, sx, sy, report, root=output_dir / 'models', activate=False)
        with (directory / 'test_predictions.csv').open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                'player_id', 'player_name', 'season_year', 'target', 'actual', 'lstm',
            ])
            writer.writeheader()
            for i, (pid, window) in enumerate(current_cases):
                for j, target in enumerate(targets):
                    writer.writerow(dict(
                        player_id=pid, player_name=names.get(pid, ''), season_year=window[-1]['season_year'],
                        target=target, actual=float(labels[-1][i, j]), lstm=float(predictions[i, j]),
                    ))
        results.append(dict(
            label=label, feature_set=feature_set, architecture=architecture, features=features,
            validation_score=validation_score, evaluation=report['evaluation'],
            epochs_run=report['epochs_run'], best_epoch=report['best_epoch'],
            parameter_count=report['parameter_count'], training_seconds=elapsed, artifact_dir=str(directory),
        ))
        # Do not retain all nine TensorFlow models or their training graphs.
        from tensorflow.keras import backend
        backend.clear_session()
    baselines = baseline_predictions(cases, base_features, targets)
    actual = np.array([[window[-1][target] for target in targets] for _, window in cases])
    return dict(
        model_type=kind, data_source=source, profile_audit=profile_audit,
        results=results, selected_by_validation=select_by_validation(results)['label'],
        baselines={name: _calculate_regression_metrics(actual, values, targets)
                   for name, values in baselines.items()},
    )


def write_report(output_dir, results, args):
    summary = dict(
        created_at_utc=datetime.now(timezone.utc).isoformat(), service_activated=False,
        configuration=dict(lookback=3, epochs=args.epochs, patience=args.patience,
                           batch_size=args.batch_size, seed=args.seed,
                           through_season=args.through_season, validation_season=args.validation_season,
                           test_season=args.test_season),
        selection_metric='validation scaled RMSE; identical training target scalers within each player type',
        test_role='Previously inspected historical reference, not a new independent test.', results=results,
    )
    (output_dir / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8',
    )
    lines = ['# 출전량 입력·LSTM 단순화 비교', '',
             f'- 최근 3시즌 입력, 최대 {args.epochs} epoch, Early Stopping {args.patience}, seed {args.seed}',
             f'- 학습 정답 < {args.validation_season}, 검증 {args.validation_season}, 참고 테스트 {args.test_season}',
             '- 모든 조합은 동일 선수·학습/검증/테스트 정답으로 비교합니다. 서비스 모델은 변경하지 않습니다.',
             '- workload: 기존 8개 + PA·AB·G + 입력 3시즌 내부 PA·AB·G 변화량 (14개). 첫 입력의 변화량은 0.',
             '- 나이는 프로필 누락으로 인한 선수 표본 변경·생존 편향을 피하기 위해 제외했습니다.',
             '- 설정 선택은 검증 RMSE만 사용합니다. 테스트는 이미 확인한 연도의 참고 결과입니다.', '']
    for group in results:
        kind = group['model_type']
        audit = group['profile_audit']
        lines += [f'## {kind}', '',
                  f"- 검증 기준 선택: **{group['selected_by_validation']}**",
                  f"- 동일 표본: 학습 {group['results'][0]['evaluation']['train_samples']}개 / "
                  f"검증 {group['results'][0]['evaluation']['validation_samples']}개 / "
                  f"테스트 {group['results'][0]['evaluation']['test_samples']}개.",
                  f"- 생년월일 확보: 학습 대상 {audit['eligible_with_birth_date']}/{audit['eligible_players']}명, "
                  f"테스트 {audit['test_with_birth_date']}/{audit['test_players']}명. 나이 사용 안 함.", '',
                  '| 입력 | 구조 | 파라미터 | 종료/최적 epoch | 검증 RMSE(정규화) |',
                  '| --- | --- | ---: | --- | ---: |']
        for result in group['results']:
            lines.append(f"| {result['feature_set']} | {result['architecture']} | {result['parameter_count']} "
                         f"| {result['epochs_run']}/{result['best_epoch']} | {result['validation_score']:.6f} |")
        lines += ['', '| 입력 | 구조 | 지표 | 검증 MAE | 검증 RMSE | 테스트 MAE | 테스트 RMSE |',
                  '| --- | --- | --- | ---: | ---: | ---: | ---: |']
        for result in group['results']:
            for target, scores in result['evaluation']['metrics'].items():
                validation = result['evaluation']['validation_metrics'][target]
                lines.append(f"| {result['feature_set']} | {result['architecture']} | {target} "
                             f"| {validation['mae']:.6f} | {validation['rmse']:.6f} "
                             f"| {scores['mae']:.6f} | {scores['rmse']:.6f} |")
        lines += ['']
    (output_dir / 'summary.md').write_text('\n'.join(lines), encoding='utf-8')


def main(argv=None):
    backend = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description='출전량 입력과 LSTM 2층/단층 비교; 서비스 적용 없음')
    parser.add_argument('--csv-dir', type=Path, default=backend / 'db/csv/2015_2025_KBO')
    parser.add_argument('--profiles', type=Path, default=backend / 'db/output_db_ready/player_profiles.csv')
    parser.add_argument('--output-dir', type=Path, default=backend / 'models/ablations')
    parser.add_argument('--type', choices=('both', 'hitter', 'pitcher'), default='both')
    parser.add_argument('--through-season', type=positive_int, default=2025)
    parser.add_argument('--validation-season', type=positive_int, default=2024)
    parser.add_argument('--test-season', type=positive_int, default=2025)
    parser.add_argument('--epochs', type=positive_int, default=100)
    parser.add_argument('--patience', type=positive_int, default=10)
    parser.add_argument('--batch-size', type=positive_int, default=16)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args(argv)
    if not args.validation_season < args.test_season <= args.through_season:
        parser.error('검증 시즌 < 테스트 시즌 <= 사용할 마지막 시즌이어야 합니다.')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
    output_dir = args.output_dir.resolve() / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    results = []
    for kind in ('hitter', 'pitcher') if args.type == 'both' else (args.type,):
        results.append(run_type(args, kind, output_dir))
        write_report(output_dir, results, args)
    print(f'비교 보고서: {output_dir / "summary.md"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
