"""Optional real TensorFlow smoke test: set RUN_LSTM_SMOKE=1 before unittest."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from app.ml import lstm_predictor as predictor
from app.ml import model_store as store


@unittest.skipUnless(os.getenv('RUN_LSTM_SMOKE') == '1', 'Set RUN_LSTM_SMOKE=1 for real TF training')
class TensorFlowSmokeTests(unittest.TestCase):
    def test_single_layer_workload_models_train_save_and_reload(self):
        from tensorflow.keras.layers import LSTM
        from tensorflow.keras.models import load_model

        features = predictor.HITTER_WORKLOAD_FEATURES
        rows = [dict.fromkeys(predictor.HITTER_FEATURES, 0.2+i*0.01) |
                dict(season_year=2015+i, pa=100+i*10, ab=90+i*8, g=30+i)
                for i in range(8)]
        for architecture, units in [('single32', 32), ('single16', 16)]:
            with self.subTest(architecture=architecture):
                model, sx, sy = predictor._build_model_and_scalers(
                    ['p'], lambda _: rows, features, predictor.HITTER_TARGETS,
                    architecture=architecture, epochs=2, patience=10,
                )
                recurrent = [layer for layer in model.layers if isinstance(layer, LSTM)]
                self.assertEqual(len(recurrent), 1)
                self.assertEqual(recurrent[0].units, units)
                self.assertEqual(model.input_shape, (None, 3, 14))
                X = sx.transform(predictor.sequence_input_values(rows[-3:], features)).reshape(1, 3, 14)
                expected = model.predict(X, verbose=0)
                with TemporaryDirectory() as root:
                    directory = store.save_bundle('hitter', model, sx, sy,
                                                 dict(model.experiment_report, purpose='ablation'), root=root)
                    restored = load_model(str(directory / 'model.keras'), compile=False, safe_mode=True)
                    np.testing.assert_allclose(restored.predict(X, verbose=0), expected, atol=1e-7)
                    self.assertIsNone(store.load_active_bundle('hitter', root))

    def test_early_stopping_waits_ten_epochs_and_restores_best_weights(self):
        from tensorflow.keras import Sequential
        from tensorflow.keras.callbacks import EarlyStopping
        from tensorflow.keras.layers import Dense, Input

        model = Sequential([Input(shape=(1,)), Dense(1, use_bias=False)])
        model.stop_training = False
        callback = EarlyStopping(
            monitor='val_rmse', mode='min', min_delta=0.0,
            patience=10, restore_best_weights=True,
        )
        callback.set_model(model)
        callback.on_train_begin()
        # The improvement in epoch 2 resets the counter; equal scores do not.
        for epoch, score in enumerate([1.0, 0.8] + [0.8] * 10):
            model.set_weights([np.array([[float(epoch)]], dtype=np.float32)])
            callback.on_epoch_end(epoch, {'val_rmse': score})
            self.assertEqual(model.stop_training, epoch == 11)
        callback.on_train_end()
        self.assertEqual(callback.stopped_epoch, 11)
        np.testing.assert_array_equal(model.get_weights()[0], [[1.0]])

    def test_hitter_training_save_reload_and_predictions_match(self):
        self._round_trip('hitter', predictor.HITTER_FEATURES, predictor.HITTER_TARGETS,
                         predictor.predict_next_season)

    def test_pitcher_training_save_reload_and_predictions_match(self):
        self._round_trip('pitcher', predictor.PITCHER_FEATURES, predictor.PITCHER_TARGETS,
                         predictor.predict_pitcher_next_season)

    def test_five_season_benchmark_training_and_saved_model_round_trip(self):
        from tensorflow.keras.models import load_model

        features, targets = predictor.HITTER_FEATURES, predictor.HITTER_TARGETS
        rows = [dict.fromkeys(features, 0.2 + i * 0.01) | {'season_year': 2015 + i}
                for i in range(8)]
        model, sx, sy = predictor._build_model_and_scalers(
            ['p'], lambda _: rows, features, targets, lookback=5, epochs=2, patience=10,
        )
        self.assertEqual(tuple(model.input_shape[1:]), (5, len(features)))
        report = dict(model.experiment_report, purpose='benchmark')
        self.assertEqual(report['lookback'], 5)
        self.assertEqual(report['training_config']['lookback'], 5)
        X = sx.transform([[row[f] for f in features] for row in rows[-5:]]).reshape(1, 5, -1)
        expected = model.predict(X, verbose=0)
        with TemporaryDirectory() as root:
            directory = store.save_bundle('hitter', model, sx, sy, report, root=root)
            restored = load_model(str(directory / 'model.keras'), compile=False, safe_mode=True)
            np.testing.assert_allclose(restored.predict(X, verbose=0), expected, atol=1e-7)
            self.assertIsNone(store.load_active_bundle('hitter', root))

    def _round_trip(self, model_type, features, targets, predict):
        datasets = {}
        for player in range(3):
            datasets[str(player)] = [
                {**{name: 0.2 + i * 0.01 + player * 0.001
                    for name in features}, 'season_year': 2015 + i}
                for i in range(8)
            ]
        model, sx, sy = predictor._build_model_and_scalers(
            list(datasets), datasets.__getitem__, features, targets,
            epochs=2, patience=1, batch_size=8,
        )
        evaluation = model.evaluation_report
        self.assertEqual(evaluation['train_last_season'], 2020)
        self.assertEqual(evaluation['validation_season'], 2021)
        self.assertEqual(evaluation['test_season'], 2022)
        self.assertIn('val_mae', model.experiment_report['history'])
        self.assertIn('val_rmse', model.experiment_report['history'])
        self.assertEqual(model.experiment_report['training_config']['early_stopping'], {
            'monitor': 'val_rmse', 'mode': 'min', 'min_delta': 0.0,
            'patience': 1, 'restore_best_weights': True,
        })
        self.assertEqual(model.experiment_report['epochs_run'], 2)
        report = dict(model.experiment_report)
        original = predict(123, model, sx, sy, time_series=datasets['0'])
        with TemporaryDirectory() as root:
            directory = store.save_bundle(model_type, model, sx, sy, report, root=root, activate=True)
            bundle = store.load_active_bundle(model_type, root)
            self.assertIs(bundle, store.load_active_bundle(model_type, root))
            restored = predict(
                123, bundle.model, bundle.scaler_X, bundle.scaler_y, time_series=datasets['0'],
            )
            self.assertEqual(original['predictions'], restored['predictions'])
            self.assertEqual(original['evaluation'], restored['evaluation'])
            json.dumps(restored, allow_nan=False)
            report_on_disk = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
            self.assertEqual(report_on_disk['evaluation']['dataset'], 'test')
            size = sum(path.stat().st_size for path in Path(directory).iterdir())
            print(f'\nActual {model_type} artifact size: {size / 1024:.1f} KiB')
        store._load_bundle.cache_clear()


if __name__ == '__main__':
    unittest.main()
