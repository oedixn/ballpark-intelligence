from __future__ import annotations

import numpy as np
import psycopg2.extras
from collections import Counter
from dataclasses import dataclass
import hashlib
import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sklearn.preprocessing import MinMaxScaler

from app.db import get_connection
from app.ml.season_features import (
    PREPROCESSING_VERSION, aggregate_hitter_seasons, aggregate_pitcher_seasons,
    latest_sequence, valid_sequence,
)

logger = logging.getLogger(__name__)
def get_conn(): return get_connection()

HITTER_FEATURES  = ['avg','obp','slg','ops','bb_rate','k_rate','iso','woba']
HITTER_TARGETS   = ['avg','ops','woba']
HITTER_WORKLOAD_FEATURES = HITTER_FEATURES + ['pa', 'ab', 'g', 'pa_change', 'ab_change', 'g_change']
LSTM_ARCHITECTURES = {'stacked64_32': (64, 32), 'single32': (32,), 'single16': (16,)}
PITCHER_FEATURES = ['era','whip','k9','bb9','hr9','ip','ip_per_g','starter_ratio']
PITCHER_TARGETS  = ['era','whip','k9']

def get_hitter_time_series(player_id: int):
    rows = _fetch_player_rows("""
        SELECT player_id, team_id, season_year, pa, ab, h, double_hit, triple_hit,
               hr, bb, hbp, so, sf
        FROM player_hitter_stats
        WHERE player_id=%s::varchar ORDER BY season_year, team_id
    """, player_id)
    return aggregate_hitter_seasons(rows)

def get_pitcher_time_series(player_id: int):
    rows = _fetch_player_rows("""
        SELECT player_id, team_id, season_year, g, gs, ip, h, hr, bb, so, er
        FROM player_pitcher_stats
        WHERE player_id=%s::varchar ORDER BY season_year, team_id
    """, player_id)
    return aggregate_pitcher_seasons(rows)


def _fetch_player_rows(query, player_id):
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(query, (player_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close(); conn.close()

def get_training_player_ids(min_seasons=4, type='hitter', through_season=None):
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    table, workload, minimum = (
        ('player_hitter_stats', 'pa', 100) if type == 'hitter'
        else ('player_pitcher_stats', 'g', 10)
    )
    cutoff = ' WHERE season_year<=%s' if through_season is not None else ''
    params = (through_season, min_seasons) if through_season is not None else (min_seasons,)
    cur.execute(f"""WITH eligible_seasons AS (
            SELECT player_id, season_year FROM {table}{cutoff}
            GROUP BY player_id, season_year HAVING SUM({workload})>={minimum}
        ) SELECT player_id FROM eligible_seasons
        GROUP BY player_id HAVING COUNT(*)>=%s ORDER BY player_id""", params)
    ids = [r['player_id'] for r in cur.fetchall()]
    cur.close(); conn.close()
    return ids

@dataclass
class PreparedTrainingData:
    X_train: np.ndarray
    y_train: np.ndarray
    X_val: np.ndarray
    y_val: np.ndarray
    X_test: np.ndarray
    y_test: np.ndarray
    scaler_X: MinMaxScaler
    scaler_y: MinMaxScaler
    train_last_season: int
    validation_season: int
    test_season: int
    data_fingerprint: str
    skipped_windows: int


def input_feature_requirements(features):
    """Raw fields needed for features computed inside each input window."""
    changes = {'pa_change': 'pa', 'ab_change': 'ab', 'g_change': 'g'}
    return list(dict.fromkeys(changes.get(feature, feature) for feature in features))


def sequence_input_values(rows, features):
    """Changes use only the input window, never its target or a fourth season."""
    changes = {'pa_change': 'pa', 'ab_change': 'ab', 'g_change': 'g'}
    values = []
    for index, row in enumerate(rows):
        current = []
        for feature in features:
            if feature in changes:
                field = changes[feature]
                current.append(float(row[field]) - float(rows[index-1][field]) if index else 0.0)
            else:
                current.append(float(row[feature]))
        values.append(current)
    return values


def _prepare_training_data(player_ids, get_ts_func, features, targets, *,
                           through_season=None, validation_season=None, test_season=None,
                           lookback=3):
    """Split by the year being predicted, never by randomly shuffling windows.

    Training targets precede validation; test is a strictly later, untouched year.
    Only training samples participate in scaler fitting.
    """
    if type(lookback) is not int or lookback not in (3, 5):
        raise ValueError('입력 시즌 수(lookback)는 3 또는 5여야 합니다.')
    from sklearn.preprocessing import MinMaxScaler

    all_X, all_y, target_seasons, sample_players = [], [], [], []
    skipped_windows = 0
    for pid in player_ids:
        data = sorted([
            r for r in get_ts_func(pid)
            if through_season is None or int(r['season_year']) <= through_season
        ], key=lambda r: int(r['season_year']))
        if len(data) < lookback + 1:
            continue
        year_counts = Counter(int(r['season_year']) for r in data)
        for i in range(len(data) - lookback):
            window = data[i:i+lookback+1]
            if not valid_sequence(window, input_feature_requirements(features) + targets,
                                  season_counts=year_counts):
                skipped_windows += 1
                continue
            all_X.append(sequence_input_values(window[:-1], features))
            all_y.append([float(window[-1][t]) for t in targets])
            target_seasons.append(int(window[-1]['season_year']))
            sample_players.append(str(pid))

    if not all_X:
        return None

    X_raw, y_raw = np.array(all_X), np.array(all_y)
    target_seasons = np.array(target_seasons)
    available_seasons = sorted(set(target_seasons.tolist()))
    if len(available_seasons) < 3:
        return None
    test_season = int(test_season if test_season is not None else available_seasons[-1])
    earlier_seasons = [year for year in available_seasons if year < test_season]
    if not earlier_seasons:
        return None
    validation_season = int(validation_season if validation_season is not None else earlier_seasons[-1])
    if validation_season >= test_season:
        raise ValueError('검증 시즌은 테스트 시즌보다 이전이어야 합니다.')
    train_mask = target_seasons < validation_season
    validation_mask = target_seasons == validation_season
    test_mask = target_seasons == test_season
    if not (train_mask.any() and validation_mask.any() and test_mask.any()):
        raise ValueError('학습·검증·테스트 구간 모두에 예측 사례가 필요합니다. 시즌 설정을 확인하세요.')

    scaler_X = MinMaxScaler().fit(X_raw[train_mask].reshape(-1, len(features)))
    scaler_y = MinMaxScaler().fit(y_raw[train_mask])
    X = scaler_X.transform(X_raw.reshape(-1, len(features))).reshape(X_raw.shape)
    y = scaler_y.transform(y_raw)
    selected = train_mask | validation_mask | test_mask
    fingerprint = hashlib.sha256()
    for arr in (X_raw[selected], y_raw[selected], target_seasons[selected]):
        fingerprint.update(arr.tobytes())
    fingerprint.update('\n'.join(np.array(sample_players)[selected]).encode('utf-8'))
    return PreparedTrainingData(
        X[train_mask], y[train_mask], X[validation_mask], y[validation_mask],
        X[test_mask], y[test_mask], scaler_X, scaler_y,
        int(target_seasons[train_mask].max()), validation_season, test_season,
        fingerprint.hexdigest(), skipped_windows,
    )


def _calculate_regression_metrics(y_true, y_pred, targets):
    """Return per-target MAE/RMSE; callers supply values in original units."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if (y_true.ndim != 2 or y_true.shape != y_pred.shape
            or y_true.shape[0] == 0 or y_true.shape[1] != len(targets)):
        raise ValueError("평가 데이터의 크기와 예측 대상이 일치해야 합니다.")
    if not (np.isfinite(y_true).all() and np.isfinite(y_pred).all()):
        raise ValueError("평가 데이터에는 유한한 숫자만 사용할 수 있습니다.")
    errors = y_pred - y_true
    mae = np.mean(np.abs(errors), axis=0)
    rmse = np.sqrt(np.mean(np.square(errors), axis=0))
    return {
        target: {"mae": float(mae[i]), "rmse": float(rmse[i])}
        for i, target in enumerate(targets)
    }


def _evaluate_in_original_units(model, scaler_y, X_val, y_val, targets):
    """Undo target scaling before calculating interpretable validation errors."""
    y_pred = scaler_y.inverse_transform(model.predict(X_val, verbose=0))
    y_true = scaler_y.inverse_transform(y_val)
    return _calculate_regression_metrics(y_true, y_pred, targets)


def _build_model_and_scalers(player_ids, get_ts_func, features, targets, *,
                             epochs=100, batch_size=16, patience=10, seed=42,
                             through_season=None, validation_season=None, test_season=None,
                             lookback=3, architecture='stacked64_32'):
    if architecture not in LSTM_ARCHITECTURES:
        raise ValueError('지원하지 않는 LSTM 구조입니다.')
    try:
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import Input, LSTM, Dense, Dropout
        from tensorflow.keras.callbacks import EarlyStopping
        from tensorflow.keras.metrics import MeanAbsoluteError, RootMeanSquaredError
        from tensorflow.keras.utils import set_random_seed
    except ImportError as exc:
        raise RuntimeError(f'TensorFlow를 불러올 수 없습니다: {exc}') from exc

    prepared = _prepare_training_data(
        player_ids, get_ts_func, features, targets, through_season=through_season,
        validation_season=validation_season, test_season=test_season,
        lookback=lookback,
    )
    if prepared is None:
        raise ValueError('연속 시즌 기록으로 학습·검증·테스트 세 구간을 만들 수 없습니다.')
    X_train, y_train = prepared.X_train, prepared.y_train
    X_val, y_val = prepared.X_val, prepared.y_val
    scaler_X, scaler_y = prepared.scaler_X, prepared.scaler_y
    validation_season = prepared.validation_season
    set_random_seed(seed)
    print(f"학습 데이터: {len(X_train)}개 시퀀스, {len(features)}개 피처; "
          f"검증: {validation_season} 시즌 {len(X_val)}개 시퀀스")

    units = LSTM_ARCHITECTURES[architecture]
    layers = [Input(shape=(lookback, len(features)))]
    for index, size in enumerate(units):
        layers.extend([LSTM(size, return_sequences=index < len(units) - 1), Dropout(0.2)])
    layers.extend([Dense(16, activation='relu'), Dense(len(targets))])
    model = Sequential(layers)
    # Epoch logs are in scaled units. The report below uses original units.
    model.compile(optimizer='adam', loss='mse', metrics=[
        MeanAbsoluteError(name='mae'), RootMeanSquaredError(name='rmse'),
    ])
    early_stopping_config = {
        "monitor": "val_rmse", "mode": "min", "min_delta": 0.0,
        "patience": patience, "restore_best_weights": True,
    }
    # Stop after `patience` consecutive epochs without a lower validation RMSE.
    early_stopping = EarlyStopping(**early_stopping_config, verbose=1)
    history = model.fit(X_train, y_train, epochs=epochs, batch_size=batch_size,
                        validation_data=(X_val, y_val),
                        callbacks=[early_stopping], verbose=1)

    validation_metrics = _evaluate_in_original_units(model, scaler_y, X_val, y_val, targets)
    # Test is evaluated only after training/epoch selection have finished.
    metrics = _evaluate_in_original_units(
        model, scaler_y, prepared.X_test, prepared.y_test, targets,
    )
    model.evaluation_report = {
        "dataset": "test",
        "split_method": "target_season",
        "train_last_season": prepared.train_last_season,
        "validation_season": validation_season,
        "test_season": prepared.test_season,
        "train_samples": len(X_train),
        "validation_samples": len(X_val),
        "test_samples": len(prepared.X_test),
        "units": "original",
        "metrics": metrics,
        "validation_metrics": validation_metrics,
    }
    model.experiment_report = {
        "preprocessing_version": PREPROCESSING_VERSION,
        "features": list(features), "targets": list(targets), "lookback": lookback,
        "architecture": architecture, "parameter_count": int(model.count_params()),
        "evaluation": model.evaluation_report,
        "history": {key: [float(value) for value in values] for key, values in history.history.items()},
        "epochs_run": len(history.history['loss']),
        "best_epoch": int(np.argmin(history.history['val_rmse'])) + 1,
        "stopped_early": early_stopping.stopped_epoch > 0,
        "training_config": {
            "epochs": epochs, "batch_size": batch_size, "patience": patience, "seed": seed,
            "lookback": lookback,
            "architecture": architecture,
            "early_stopping": early_stopping_config,
            "through_season": through_season, "player_count": len(player_ids),
            "player_ids": [str(pid) for pid in player_ids],
        },
        "data_fingerprint": prepared.data_fingerprint,
        "skipped_windows": prepared.skipped_windows,
    }
    for target, scores in metrics.items():
        print(f"독립 테스트 {target}: MAE={scores['mae']:.6f}, RMSE={scores['rmse']:.6f}")

    return model, scaler_X, scaler_y

def _training_ids(model_type, max_players, seed, through_season):
    ids = get_training_player_ids(4, model_type, through_season)
    if max_players is not None:
        if max_players <= 0:
            raise ValueError('max_players는 양수여야 합니다.')
        ids = sorted(random.Random(seed).sample(ids, min(max_players, len(ids))), key=str)
    return ids


def train_hitter_model(*, max_players=None, seed=42, through_season=None, **options):
    print("타자 LSTM 학습 시작...")
    ids = _training_ids('hitter', max_players, seed, through_season)
    return _build_model_and_scalers(ids, get_hitter_time_series, HITTER_FEATURES, HITTER_TARGETS,
                                    seed=seed, through_season=through_season, **options)

def train_pitcher_model(*, max_players=None, seed=42, through_season=None, **options):
    print("투수 LSTM 학습 시작...")
    ids = _training_ids('pitcher', max_players, seed, through_season)
    return _build_model_and_scalers(ids, get_pitcher_time_series, PITCHER_FEATURES, PITCHER_TARGETS,
                                    seed=seed, through_season=through_season, **options)

# 하위 호환
def train_lstm_model():
    return train_hitter_model()

def _weighted_avg_predict(data, features, targets):
    recent = data[-3:] if len(data) >= 3 else data
    w = np.array([0.2,0.3,0.5]) if len(recent)==3 else np.ones(len(recent))/len(recent)
    w = w[-len(recent):] / w[-len(recent):].sum()
    pred = {}
    for t in targets:
        vals = [float(r[t] or 0) for r in recent]
        pred[t] = round(float(np.dot(w, vals)), 3)
    if len(data) >= 2:
        for t in targets:
            trend = float(data[-1][t] or 0) - float(data[-2][t] or 0)
            pred[t] = round(pred[t] + trend * 0.3, 3)
    return pred

def predict_next_season(player_id: int, model=None, scaler_X=None, scaler_y=None, *, time_series=None):
    data = get_hitter_time_series(player_id) if time_series is None else time_series
    recent = latest_sequence(data, HITTER_FEATURES + HITTER_TARGETS)
    if recent is None: return None

    if model is None:
        pred = _weighted_avg_predict(recent, HITTER_FEATURES, HITTER_TARGETS)
        method = "weighted_average"
    else:
        vals = np.array([[float(r[f]) for f in HITTER_FEATURES] for r in recent])
        scaled = scaler_X.transform(vals).reshape(1, 3, len(HITTER_FEATURES))
        pred_scaled = model.predict(scaled, verbose=0)
        pred_vals = scaler_y.inverse_transform(pred_scaled)[0]
        pred = {t: round(float(pred_vals[i]), 3) for i, t in enumerate(HITTER_TARGETS)}
        method = "lstm"

    return {
        "player_id": player_id,
        "current_season": int(recent[-1]['season_year']),
        "next_season":    int(recent[-1]['season_year']) + 1,
        "predictions": pred,
        "confidence": "high" if len(data)>=7 else "medium" if len(data)>=4 else "low",
        "seasons_used": len(data),
        "method": method,
        "evaluation": getattr(model, 'evaluation_report', None),
        "model_version": getattr(model, 'artifact_version', None),
        "type": "hitter",
        "recent_stats": {
            "avg":  float(recent[-1]['avg']),
            "ops":  float(recent[-1]['ops']),
            "woba": float(recent[-1]['woba']),
        }
    }

def predict_pitcher_next_season(player_id: int, model=None, scaler_X=None, scaler_y=None, *, time_series=None):
    data = get_pitcher_time_series(player_id) if time_series is None else time_series
    recent = latest_sequence(data, PITCHER_FEATURES + PITCHER_TARGETS)
    if recent is None: return None

    if model is None:
        pred = _weighted_avg_predict(recent, PITCHER_FEATURES, PITCHER_TARGETS)
        method = "weighted_average"
    else:
        vals = np.array([[float(r[f]) for f in PITCHER_FEATURES] for r in recent])
        scaled = scaler_X.transform(vals).reshape(1, 3, len(PITCHER_FEATURES))
        pred_scaled = model.predict(scaled, verbose=0)
        pred_vals = scaler_y.inverse_transform(pred_scaled)[0]
        pred = {t: round(float(pred_vals[i]), 3) for i, t in enumerate(PITCHER_TARGETS)}
        method = "lstm"

    return {
        "player_id": player_id,
        "current_season": int(recent[-1]['season_year']),
        "next_season":    int(recent[-1]['season_year']) + 1,
        "predictions": pred,
        "confidence": "high" if len(data)>=7 else "medium" if len(data)>=4 else "low",
        "seasons_used": len(data),
        "method": method,
        "evaluation": getattr(model, 'evaluation_report', None),
        "model_version": getattr(model, 'artifact_version', None),
        "type": "pitcher",
        "recent_stats": {
            "era":  float(recent[-1]['era']),
            "whip": float(recent[-1]['whip']),
            "k9":   float(recent[-1]['k9']),
        }
    }


def predict_saved_next_season(player_id: int):
    """Inference only: load the active artifact for the eligible player type."""
    from app.ml.model_store import load_active_bundle

    for model_type, get_ts, predict, features, targets in [
        ('hitter', get_hitter_time_series, predict_next_season, HITTER_FEATURES, HITTER_TARGETS),
        ('pitcher', get_pitcher_time_series, predict_pitcher_next_season, PITCHER_FEATURES, PITCHER_TARGETS),
    ]:
        data = get_ts(player_id)
        if latest_sequence(data, features + targets) is None:
            continue
        status = 'not_trained'
        bundle = None
        try:
            bundle = load_active_bundle(model_type)
            if bundle is not None:
                status = 'ready'
        except (ImportError, OSError, ValueError, KeyError, TypeError):
            logger.exception('%s 모델 로드 실패; 가중평균 예측으로 전환합니다.', model_type)
            status = 'load_failed'
        args = (bundle.model, bundle.scaler_X, bundle.scaler_y) if bundle else ()
        result = predict(player_id, *args, time_series=data)
        result['model_status'] = status
        return result
    return None
