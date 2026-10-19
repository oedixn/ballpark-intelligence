"""Versioned local LSTM artifacts. No training takes place in this module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
from importlib.metadata import PackageNotFoundError, version as package_version
import json
import os
from pathlib import Path
import platform
import re
from threading import RLock
from typing import TYPE_CHECKING
from uuid import uuid4

import numpy as np

if TYPE_CHECKING:
    from sklearn.preprocessing import MinMaxScaler

_load_lock = RLock()


@dataclass
class ModelBundle:
    model: object
    scaler_X: MinMaxScaler
    scaler_y: MinMaxScaler
    report: dict
    version: str


def model_root(root=None):
    default = Path(__file__).resolve().parents[2] / 'models' / 'lstm'
    return Path(root or os.getenv('ML_MODEL_DIR') or default).resolve()


def _type_dir(model_type, root=None):
    if model_type not in ('hitter', 'pitcher'):
        raise ValueError('모델 종류는 hitter 또는 pitcher여야 합니다.')
    return model_root(root) / model_type


def _version_dir(model_type, version, root=None):
    if not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,100}', version):
        raise ValueError('유효하지 않은 모델 버전입니다.')
    return _type_dir(model_type, root) / version


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scaler_state(scaler):
    return {
        'feature_range': list(scaler.feature_range), 'clip': scaler.clip,
        'n_features_in': int(scaler.n_features_in_), 'n_samples_seen': int(scaler.n_samples_seen_),
        **{name: getattr(scaler, name).tolist() for name in
           ('min_', 'scale_', 'data_min_', 'data_max_', 'data_range_')},
    }


def _restore_scaler(state, expected_features):
    from sklearn.preprocessing import MinMaxScaler

    if state['n_features_in'] != expected_features:
        raise ValueError('저장된 스케일러와 모델의 지표 수가 일치하지 않습니다.')
    scaler = MinMaxScaler(feature_range=tuple(state['feature_range']), clip=state['clip'])
    scaler.n_features_in_ = int(state['n_features_in'])
    scaler.n_samples_seen_ = int(state['n_samples_seen'])
    for name in ('min_', 'scale_', 'data_min_', 'data_max_', 'data_range_'):
        values = np.asarray(state[name], dtype=float)
        if values.shape != (expected_features,) or not np.isfinite(values).all():
            raise ValueError('저장된 스케일러가 올바르지 않습니다.')
        setattr(scaler, name, values)
    return scaler


def _expected_spec(model_type):
    from app.ml.lstm_predictor import (
        HITTER_FEATURES, HITTER_TARGETS, PITCHER_FEATURES, PITCHER_TARGETS,
    )
    return ((HITTER_FEATURES, HITTER_TARGETS) if model_type == 'hitter'
            else (PITCHER_FEATURES, PITCHER_TARGETS))


def _read_report(model_type, version, root=None):
    from app.ml.season_features import PREPROCESSING_VERSION

    directory = _version_dir(model_type, version, root)
    report = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
    features, targets = _expected_spec(model_type)
    lookback = report.get('lookback')
    supported_lookback = (type(lookback) is int and (
        lookback == 3 or (lookback == 5 and report.get('purpose') == 'benchmark')
    ))
    if report.get('purpose') == 'ablation' and model_type == 'hitter':
        from app.ml.lstm_predictor import HITTER_WORKLOAD_FEATURES
        supported_features = report.get('features') in (features, HITTER_WORKLOAD_FEATURES)
    else:
        supported_features = report.get('features') == features
    if (report.get('schema_version') != 1 or report.get('model_type') != model_type
            or report.get('preprocessing_version') != PREPROCESSING_VERSION
            or report.get('version') != version or not supported_lookback
            or not supported_features or report.get('targets') != targets):
        raise ValueError('저장된 모델의 입력·출력 사양이 현재 코드와 일치하지 않습니다.')
    for filename in ('model.keras', 'scalers.json'):
        if _sha256(directory / filename) != report['checksums'][filename]:
            raise ValueError(f'모델 파일 무결성 검사 실패: {filename}')
    return report


def activate_bundle(model_type, version, root=None):
    """Switch one small pointer only after every artifact is complete."""
    report = _read_report(model_type, version, root)
    if report['lookback'] != 3:
        raise ValueError('5시즌 모델은 비교 실험 전용입니다. 현재 3시즌 서비스 모델로 활성화할 수 없습니다.')
    if report.get('purpose') == 'ablation':
        raise ValueError('입력·구조 비교 실험 모델은 서비스에 자동 적용할 수 없습니다.')
    directory = _type_dir(model_type, root)
    temporary = directory / f'.current-{uuid4().hex}.tmp'
    _write_json(temporary, {'version': version})
    os.replace(temporary, directory / 'current.json')


def save_bundle(model_type, model, scaler_X, scaler_y, report, *, root=None, activate=False):
    """Save a new version; experiments do not replace the active model by default."""
    version = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
    directory = _version_dir(model_type, version, root)
    directory.mkdir(parents=True, exist_ok=False)
    model.save(str(directory / 'model.keras'))
    _write_json(directory / 'scalers.json', {
        'X': _scaler_state(scaler_X), 'y': _scaler_state(scaler_y),
    })
    dependencies = {}
    for name in ('tensorflow', 'keras', 'numpy', 'scikit-learn'):
        try:
            dependencies[name] = package_version(name)
        except PackageNotFoundError:
            dependencies[name] = None
    stored_report = {
        **report, 'schema_version': 1, 'model_type': model_type, 'version': version,
        'saved_at': datetime.now(timezone.utc).isoformat(),
        'python_version': platform.python_version(), 'dependencies': dependencies,
        'checksums': {name: _sha256(directory / name) for name in ('model.keras', 'scalers.json')},
    }
    _write_json(directory / 'report.json', stored_report)
    _read_report(model_type, version, root)
    if activate:
        activate_bundle(model_type, version, root)
    return directory


@lru_cache(maxsize=4)
def _load_bundle(root, model_type, version):
    report = _read_report(model_type, version, root)
    if report.get('purpose') == 'ablation':
        raise ValueError('입력·구조 비교 실험 모델은 서비스용 모델이 아닙니다.')
    directory = _version_dir(model_type, version, root)
    states = json.loads((directory / 'scalers.json').read_text(encoding='utf-8'))
    # Import the TF runtime before sklearn's native libraries; this also avoids
    # eager TensorFlow imports for requests with no active model.
    from tensorflow.keras.models import load_model
    sx = _restore_scaler(states['X'], len(report['features']))
    sy = _restore_scaler(states['y'], len(report['targets']))
    model = load_model(str(directory / 'model.keras'), compile=False, safe_mode=True)
    if (tuple(model.input_shape[1:]) != (3, len(report['features']))
            or model.output_shape[-1] != len(report['targets'])):
        raise ValueError('저장된 모델의 텐서 크기가 일치하지 않습니다.')
    model.evaluation_report = report['evaluation']
    model.artifact_version = version
    return ModelBundle(model, sx, sy, report, version)


def load_active_bundle(model_type, root=None):
    """Reload after activation; repeated requests reuse the same loaded version."""
    directory = _type_dir(model_type, root)
    pointer = directory / 'current.json'
    if not pointer.exists():
        return None
    with _load_lock:
        version = json.loads(pointer.read_text(encoding='utf-8'))['version']
        _version_dir(model_type, version, root)
        return _load_bundle(str(model_root(root)), model_type, version)
