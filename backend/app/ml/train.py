"""Offline training/activation: python -m app.ml.train --help."""

import argparse
from datetime import datetime, timezone
import json
import sys

from app.ml.lstm_predictor import train_hitter_model, train_pitcher_model
from app.ml.model_store import activate_bundle, save_bundle


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('양수를 입력하세요.')
    return number


def build_parser():
    parser = argparse.ArgumentParser(description='LSTM 별도 학습·평가·저장 또는 저장된 버전 활성화')
    parser.add_argument('--type', choices=('hitter', 'pitcher', 'both'), default='hitter')
    parser.add_argument('--epochs', type=positive_int, default=100)
    parser.add_argument('--batch-size', type=positive_int, default=16)
    parser.add_argument('--patience', type=positive_int, default=10)
    parser.add_argument('--max-players', type=positive_int, help='빠른 실험용 선수 표본 수')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--through-season', type=positive_int,
                        default=datetime.now(timezone.utc).year - 1,
                        help='사용할 마지막 시즌. 기본값은 전년도(진행 중 시즌 제외).')
    parser.add_argument('--validation-season', type=positive_int)
    parser.add_argument('--test-season', type=positive_int)
    parser.add_argument('--model-dir', help='저장 루트. API의 ML_MODEL_DIR와 같은 경로를 사용하세요.')
    parser.add_argument('--activate', action='store_true', help='저장 후 서비스에서 사용할 모델로 활성화')
    parser.add_argument('--activate-version', help='재학습 없이 기존 버전 활성화 또는 이전 버전으로 복귀')
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.activate_version and args.type == 'both':
        parser.error('--activate-version은 hitter 또는 pitcher 하나를 지정해야 합니다.')
    if (args.validation_season is not None and args.test_season is not None
            and args.validation_season >= args.test_season):
        parser.error('검증 시즌은 테스트 시즌보다 이전이어야 합니다.')
    if args.test_season is not None and args.test_season > args.through_season:
        parser.error('테스트 시즌은 --through-season을 초과할 수 없습니다.')
    if args.activate_version:
        activate_bundle(args.type, args.activate_version, args.model_dir)
        print(f'{args.type} 활성 버전: {args.activate_version}')
        return 0

    for model_type in ('hitter', 'pitcher') if args.type == 'both' else (args.type,):
        train = train_hitter_model if model_type == 'hitter' else train_pitcher_model
        model, sx, sy = train(
            epochs=args.epochs, batch_size=args.batch_size, patience=args.patience,
            max_players=args.max_players, seed=args.seed, through_season=args.through_season,
            validation_season=args.validation_season, test_season=args.test_season,
        )
        if model is None:
            raise RuntimeError('TensorFlow를 불러올 수 없습니다. backend 의존성을 설치하세요.')
        report = dict(model.experiment_report)
        report['history_units'] = 'scaled'
        report['purpose'] = 'experiment' if args.max_players is not None else 'evaluation'
        directory = save_bundle(model_type, model, sx, sy, report,
                                root=args.model_dir, activate=args.activate)
        size = sum(path.stat().st_size for path in directory.iterdir() if path.is_file())
        print(f'저장: {directory} ({size / 1024:.1f} KiB); 서비스 적용: {args.activate}')
        print(json.dumps(report['evaluation'], ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'학습/활성화 실패: {exc}', file=sys.stderr)
        sys.exit(1)
