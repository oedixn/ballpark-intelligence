import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
from sklearn.preprocessing import MinMaxScaler

from app.ml import lstm_predictor as predictor
from app.ml import model_store as store
from app.ml.train import main as train_main


def example_artifacts():
    sx = MinMaxScaler().fit([[0] * 8, [2] * 8])
    sy = MinMaxScaler().fit([[0.2, 0.6, 0.2], [0.4, 1.2, 0.5]])
    report = {
        'preprocessing_version': predictor.PREPROCESSING_VERSION,
        'features': predictor.HITTER_FEATURES, 'targets': predictor.HITTER_TARGETS,
        'lookback': 3, 'evaluation': {'dataset': 'test', 'units': 'original'},
    }
    model = SimpleNamespace(save=lambda path: Path(path).write_bytes(b'test model'))
    return model, sx, sy, report


class ModelStoreTests(unittest.TestCase):
    def test_workload_experiment_is_saved_but_cannot_be_activated(self):
        model, _, sy, report = example_artifacts()
        features = predictor.HITTER_WORKLOAD_FEATURES
        sx = MinMaxScaler().fit([[0] * len(features), [1] * len(features)])
        report.update(features=features, purpose='ablation')
        with TemporaryDirectory() as root:
            directory = store.save_bundle('hitter', model, sx, sy, report, root=root)
            self.assertEqual(store._read_report('hitter', directory.name, root)['features'], features)
            with self.assertRaisesRegex(ValueError, '비교 실험 모델'):
                store.activate_bundle('hitter', directory.name, root)
            self.assertIsNone(store.load_active_bundle('hitter', root))

    def test_five_season_benchmark_can_be_saved_but_not_activated(self):
        model, sx, sy, report = example_artifacts()
        report.update(lookback=5, purpose='benchmark')
        with TemporaryDirectory() as root:
            directory = store.save_bundle('hitter', model, sx, sy, report, root=root)
            self.assertEqual(store._read_report('hitter', directory.name, root)['lookback'], 5)
            with self.assertRaisesRegex(ValueError, '비교 실험 전용'):
                store.activate_bundle('hitter', directory.name, root)
            self.assertFalse((Path(root) / 'hitter' / 'current.json').exists())

    def test_scalers_round_trip_preserves_transform_and_inverse(self):
        scaler = MinMaxScaler(feature_range=(-1, 1)).fit([[1, 20], [5, 100]])
        restored = store._restore_scaler(store._scaler_state(scaler), 2)
        sample = [[2, 40], [10, 200]]
        np.testing.assert_allclose(scaler.transform(sample), restored.transform(sample))
        np.testing.assert_allclose(sample, restored.inverse_transform(restored.transform(sample)))

    def test_saving_an_experiment_does_not_change_the_active_version(self):
        model, sx, sy, report = example_artifacts()
        with TemporaryDirectory() as root:
            self.assertIsNone(store.load_active_bundle('hitter', root))
            first = store.save_bundle('hitter', model, sx, sy, report, root=root, activate=True)
            pointer = Path(root) / 'hitter' / 'current.json'
            second = store.save_bundle('hitter', model, sx, sy, report, root=root)
            self.assertNotEqual(first.name, second.name)
            self.assertEqual(json.loads(pointer.read_text())['version'], first.name)
            self.assertTrue((second / 'report.json').exists())

    def test_incomplete_or_corrupted_version_cannot_replace_active_model(self):
        model, sx, sy, report = example_artifacts()
        with TemporaryDirectory() as root:
            first = store.save_bundle('hitter', model, sx, sy, report, root=root, activate=True)
            pointer = Path(root) / 'hitter' / 'current.json'
            original_pointer = pointer.read_bytes()
            with self.assertRaises(FileNotFoundError):
                store.activate_bundle('hitter', 'missing-version', root)
            second = store.save_bundle('hitter', model, sx, sy, report, root=root)
            (second / 'model.keras').write_bytes(b'corrupted')
            with self.assertRaises(ValueError):
                store.activate_bundle('hitter', second.name, root)
            self.assertEqual(pointer.read_bytes(), original_pointer)
            store.activate_bundle('hitter', first.name, root)

    def test_new_active_pointer_is_observed_without_server_restart(self):
        model, sx, sy, report = example_artifacts()
        with TemporaryDirectory() as root:
            first = store.save_bundle('hitter', model, sx, sy, report, root=root, activate=True)
            second = store.save_bundle('hitter', model, sx, sy, report, root=root)
            with patch.object(store, '_load_bundle', side_effect=lambda r, t, v: v):
                self.assertEqual(store.load_active_bundle('hitter', root), first.name)
                store.activate_bundle('hitter', second.name, root)
                self.assertEqual(store.load_active_bundle('hitter', root), second.name)

    def test_versions_cannot_escape_the_model_directory(self):
        for version in ('../other', '/absolute', '..', 'bad/name', 'bad\\name'):
            with self.subTest(version=version), self.assertRaises(ValueError):
                store._version_dir('hitter', version)

    def test_old_preprocessing_models_are_rejected_even_with_same_features(self):
        model, sx, sy, report = example_artifacts()
        with TemporaryDirectory() as root:
            directory = store.save_bundle('hitter', model, sx, sy, report, root=root)
            path = directory / 'report.json'
            old_report = json.loads(path.read_text(encoding='utf-8'))
            old_report.pop('preprocessing_version')
            path.write_text(json.dumps(old_report), encoding='utf-8')
            with self.assertRaises(ValueError):
                store.activate_bundle('hitter', directory.name, root)

    def test_cli_activation_does_not_train(self):
        with patch('app.ml.train.activate_bundle') as activate, \
                patch('app.ml.train.train_hitter_model') as train:
            self.assertEqual(train_main(['--type', 'hitter', '--activate-version', 'existing']), 0)
        activate.assert_called_once_with('hitter', 'existing', None)
        train.assert_not_called()


class InferenceOnlyTests(unittest.TestCase):
    def test_pitcher_request_loads_only_pitcher_model_and_never_trains(self):
        records = [
            dict.fromkeys(predictor.PITCHER_FEATURES, 1.0) | {'season_year': 2020 + i}
            for i in range(3)
        ]
        sx = MinMaxScaler().fit([[0] * len(predictor.PITCHER_FEATURES), [2] * len(predictor.PITCHER_FEATURES)])
        sy = MinMaxScaler().fit([[0] * 3, [2] * 3])
        model = SimpleNamespace(
            predict=Mock(return_value=np.array([[0.5, 0.5, 0.5]])),
            evaluation_report={'dataset': 'test'}, artifact_version='saved-version',
        )
        bundle = store.ModelBundle(model, sx, sy, {}, 'saved-version')
        with patch.object(predictor, 'get_hitter_time_series', return_value=[]), \
                patch.object(predictor, 'get_pitcher_time_series', return_value=records), \
                patch.object(predictor, 'train_hitter_model') as hitter_train, \
                patch.object(predictor, 'train_pitcher_model') as pitcher_train, \
                patch.object(store, 'load_active_bundle', return_value=bundle) as load:
            result = predictor.predict_saved_next_season(123)
        load.assert_called_once_with('pitcher')
        hitter_train.assert_not_called()
        pitcher_train.assert_not_called()
        self.assertEqual(result['method'], 'lstm')
        self.assertEqual(result['model_version'], 'saved-version')

    def test_no_active_artifact_returns_explicit_fallback_without_training(self):
        records = [
            dict.fromkeys(predictor.HITTER_FEATURES, 0.5) | {'season_year': 2020 + i}
            for i in range(3)
        ]
        with patch.object(predictor, 'get_hitter_time_series', return_value=records), \
                patch.object(store, 'load_active_bundle', return_value=None), \
                patch.object(predictor, 'train_hitter_model') as train:
            result = predictor.predict_saved_next_season(123)
        train.assert_not_called()
        self.assertEqual(result['model_status'], 'not_trained')
        self.assertEqual(result['method'], 'weighted_average')
        self.assertIsNone(result['evaluation'])

    def test_invalid_sequence_does_not_load_or_train_a_model(self):
        records = [
            dict.fromkeys(predictor.HITTER_FEATURES, 0.5) | {'season_year': year}
            for year in (2019, 2022, 2025)
        ]
        with patch.object(predictor, 'get_hitter_time_series', return_value=records), \
                patch.object(predictor, 'get_pitcher_time_series', return_value=[]), \
                patch.object(store, 'load_active_bundle') as load:
            self.assertIsNone(predictor.predict_saved_next_season(123))
        load.assert_not_called()


if __name__ == '__main__':
    unittest.main()
