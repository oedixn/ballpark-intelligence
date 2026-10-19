"""Run from backend: python -m unittest discover -s tests -v.

These checks use synthetic records and do not connect to PostgreSQL or train TF.
"""

import json
import math
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

# Native Windows TF can fail to initialize if sklearn DLLs are loaded first.
# Optional full-suite TF checks initialize that runtime before numeric helpers.
if os.getenv('RUN_LSTM_SMOKE') == '1':
    import tensorflow

import numpy as np
from sklearn.preprocessing import MinMaxScaler

from app.ml import lstm_predictor as predictor


class RegressionMetricsTests(unittest.TestCase):
    def test_mae_and_rmse_are_separate_for_each_target(self):
        actual = [[0.300, 0.800, 0.400], [0.250, 0.700, 0.350]]
        predicted = [[0.280, 0.900, 0.400], [0.290, 0.700, 0.320]]
        scores = predictor._calculate_regression_metrics(
            actual, predicted, predictor.HITTER_TARGETS,
        )
        expected = {
            'avg': (0.030, math.sqrt(0.001)),
            'ops': (0.050, math.sqrt(0.005)),
            'woba': (0.015, math.sqrt(0.00045)),
        }
        for target, (mae, rmse) in expected.items():
            self.assertAlmostEqual(scores[target]['mae'], mae)
            self.assertAlmostEqual(scores[target]['rmse'], rmse)
        json.dumps(scores, allow_nan=False)

    def test_perfect_predictions_have_zero_error(self):
        actual = [[3.5, 1.2, 5.0], [4.0, 1.3, 4.0]]
        scores = predictor._calculate_regression_metrics(
            actual, actual, predictor.PITCHER_TARGETS,
        )
        for target_scores in scores.values():
            self.assertEqual(target_scores, {'mae': 0.0, 'rmse': 0.0})

    def test_evaluation_restores_each_targets_original_scale(self):
        scaler = MinMaxScaler().fit([[0.2, 0.6, 1.0], [0.4, 1.0, 9.0]])
        actual = [[0.25, 0.7, 3.0], [0.3, 0.9, 5.0]]
        predicted = [[0.27, 0.75, 4.0], [0.28, 0.85, 7.0]]
        model = SimpleNamespace(predict=Mock(return_value=scaler.transform(predicted)))
        scores = predictor._evaluate_in_original_units(
            model, scaler, np.zeros((2, 3, 1)), scaler.transform(actual),
            ['avg', 'ops', 'era'],
        )
        self.assertAlmostEqual(scores['avg']['mae'], 0.02)
        self.assertAlmostEqual(scores['ops']['mae'], 0.05)
        self.assertAlmostEqual(scores['era']['mae'], 1.5)
        self.assertAlmostEqual(scores['era']['rmse'], math.sqrt(2.5))

    def test_invalid_evaluation_data_is_rejected(self):
        for actual, predicted in [
            ([], []),
            ([[1, 2]], [[1]]),
            ([[1, float('nan')]], [[1, 2]]),
            ([[1, 2]], [[1, float('inf')]]),
        ]:
            with self.subTest(actual=actual, predicted=predicted):
                with self.assertRaises(ValueError):
                    predictor._calculate_regression_metrics(
                        actual, predicted, ['a', 'b'],
                    )


class TrainingSplitTests(unittest.TestCase):
    def test_five_season_inputs_have_correct_targets_and_training_only_scalers(self):
        data = [{'season_year': year, 'x': year, 'y': year} for year in range(2015, 2027)]
        prepared = predictor._prepare_training_data(
            ['p'], lambda _: data, ['x'], ['y'], lookback=5,
            through_season=2025, validation_season=2024, test_season=2025,
        )
        self.assertEqual(prepared.X_train.shape, (4, 5, 1))
        self.assertEqual(prepared.X_val.shape, (1, 5, 1))
        self.assertEqual(prepared.X_test.shape, (1, 5, 1))
        np.testing.assert_allclose(prepared.scaler_X.data_max_, [2022])
        np.testing.assert_allclose(prepared.scaler_y.data_max_, [2023])
        np.testing.assert_allclose(
            prepared.scaler_X.inverse_transform(prepared.X_test[0]).ravel(), range(2020, 2025),
        )
        np.testing.assert_allclose(prepared.scaler_y.inverse_transform(prepared.y_test), [[2025]])

    def test_unsupported_lookback_is_rejected(self):
        for lookback in (0, 4, '5', True):
            with self.subTest(lookback=lookback), self.assertRaises(ValueError):
                predictor._prepare_training_data([], lambda _: [], ['x'], ['y'], lookback=lookback)

    def test_validation_and_test_years_are_held_out_without_scaler_leakage(self):
        records = [
            {'season_year': 2018 + i, 'x': float(i), 'y': float(10 + i)}
            for i in range(6)
        ]
        # These extremes belong only to held-out inputs/labels.
        records[-3]['x'] = 50.0
        records[-2]['x'] = 100.0
        records[-1]['y'] = 1000.0
        get_ts = Mock(return_value=records)
        prepared = predictor._prepare_training_data(['player'], get_ts, ['x'], ['y'])
        get_ts.assert_called_once_with('player')
        self.assertEqual(prepared.train_last_season, 2021)
        self.assertEqual(prepared.validation_season, 2022)
        self.assertEqual(prepared.test_season, 2023)
        self.assertEqual(prepared.X_train.shape, (1, 3, 1))
        self.assertEqual(prepared.X_val.shape, (1, 3, 1))
        self.assertEqual(prepared.X_test.shape, (1, 3, 1))
        np.testing.assert_allclose(prepared.scaler_X.data_max_, [2.0])
        np.testing.assert_allclose(prepared.scaler_y.data_max_, [13.0])
        np.testing.assert_allclose(prepared.scaler_y.inverse_transform(prepared.y_train), [[13.0]])
        np.testing.assert_allclose(prepared.scaler_y.inverse_transform(prepared.y_test), [[1000.0]])
        self.assertGreater(prepared.X_val[0, -1, 0], 1.0)

    def test_validation_year_is_global_across_players(self):
        def records(first_year):
            return [
                {'season_year': first_year + i, 'x': i, 'y': i + 1}
                for i in range(5)
            ]

        datasets = {'old': records(2017), 'recent': records(2019)}
        prepared = predictor._prepare_training_data(
            datasets.keys(), datasets.__getitem__, ['x'], ['y'],
        )
        self.assertEqual(prepared.train_last_season, 2021)
        self.assertEqual(prepared.validation_season, 2022)
        self.assertEqual(prepared.test_season, 2023)
        self.assertEqual(len(prepared.X_train), 2)
        self.assertEqual(len(prepared.X_val), 1)
        self.assertEqual(len(prepared.X_test), 1)

    def test_explicit_years_and_cutoff_ignore_future_records(self):
        data = [{'season_year': year, 'x': year, 'y': year} for year in range(2015, 2027)]
        prepared = predictor._prepare_training_data(
            ['p'], lambda _: data, ['x'], ['y'], through_season=2025,
            validation_season=2024, test_season=2025,
        )
        self.assertEqual(prepared.train_last_season, 2023)
        self.assertEqual(prepared.validation_season, 2024)
        self.assertEqual(prepared.test_season, 2025)
        altered = [dict(row) for row in data]
        altered[-1]['x'] = -1000000
        again = predictor._prepare_training_data(
            ['p'], lambda _: altered, ['x'], ['y'], through_season=2025,
            validation_season=2024, test_season=2025,
        )
        self.assertEqual(prepared.data_fingerprint, again.data_fingerprint)

    def test_invalid_or_empty_split_is_rejected(self):
        data = [{'season_year': year, 'x': year, 'y': year} for year in range(2015, 2027)]
        for validation, test in [(2025, 2024), (2024, 2024), (2010, 2025), (2024, 2030)]:
            with self.subTest(validation=validation, test=test):
                with self.assertRaises(ValueError):
                    predictor._prepare_training_data(
                        ['p'], lambda _: data, ['x'], ['y'],
                        validation_season=validation, test_season=test,
                    )

    def test_missing_or_duplicate_seasons_are_not_treated_as_consecutive(self):
        missing = [{'season_year': y, 'x': y, 'y': y} for y in [2015, 2017, 2019, 2021, 2023, 2025]]
        self.assertIsNone(predictor._prepare_training_data(['p'], lambda _: missing, ['x'], ['y']))
        duplicate = [{'season_year': y, 'x': y, 'y': y} for y in [2015, 2016, 2017, 2018, 2018, 2019, 2020]]
        self.assertIsNone(predictor._prepare_training_data(['p'], lambda _: duplicate, ['x'], ['y']))

    def test_insufficient_years_do_not_produce_training_set_scores(self):
        records = [
            {'season_year': 2020 + i, 'x': i, 'y': i}
            for i in range(4)
        ]
        for data in [[], records[:3], records]:
            with self.subTest(record_count=len(data)):
                self.assertIsNone(predictor._prepare_training_data(
                    ['player'], lambda _: data, ['x'], ['y'],
                ))


class PredictionEvaluationTests(unittest.TestCase):
    def test_hitter_and_pitcher_predictions_include_model_evaluation(self):
        cases = [
            ('get_hitter_time_series', predictor.predict_next_season,
             predictor.HITTER_FEATURES, predictor.HITTER_TARGETS),
            ('get_pitcher_time_series', predictor.predict_pitcher_next_season,
             predictor.PITCHER_FEATURES, predictor.PITCHER_TARGETS),
        ]
        for getter, predict, features, targets in cases:
            with self.subTest(getter=getter):
                records = [
                    dict.fromkeys(set(features + targets), 0.5)
                    | {'season_year': 2020 + i}
                    for i in range(3)
                ]
                report = {
                    'validation_season': 2022,
                    'units': 'original',
                    'metrics': {t: {'mae': 0.01, 'rmse': 0.02} for t in targets},
                }
                model = SimpleNamespace(
                    predict=Mock(return_value=np.array([[0.2, 0.3, 0.4]])),
                    evaluation_report=report,
                )
                sx = MinMaxScaler().fit(np.array([[0] * len(features), [1] * len(features)]))
                sy = MinMaxScaler().fit([[0, 0, 0], [1, 1, 1]])
                with patch.object(predictor, getter, return_value=records):
                    result = predict(123, model, sx, sy)
                self.assertEqual(result['evaluation'], report)
                self.assertEqual(result['method'], 'lstm')
                self.assertEqual(result['predictions'], dict(zip(targets, [0.2, 0.3, 0.4])))
                json.dumps(result, allow_nan=False)

    def test_weighted_average_does_not_claim_lstm_evaluation(self):
        cases = [
            ('get_hitter_time_series', predictor.predict_next_season, predictor.HITTER_FEATURES),
            ('get_pitcher_time_series', predictor.predict_pitcher_next_season, predictor.PITCHER_FEATURES),
        ]
        for getter, predict, targets in cases:
            with self.subTest(getter=getter):
                records = [
                    dict.fromkeys(targets, 0.5) | {'season_year': 2020 + i}
                    for i in range(3)
                ]
                with patch.object(predictor, getter, return_value=records):
                    result = predict(123)
                self.assertEqual(result['method'], 'weighted_average')
                self.assertIsNone(result['evaluation'])

    def test_latest_history_must_be_consecutive_for_both_prediction_methods(self):
        for predict, features in [
            (predictor.predict_next_season, predictor.HITTER_FEATURES),
            (predictor.predict_pitcher_next_season, predictor.PITCHER_FEATURES),
        ]:
            for years in ([2020, 2022, 2023], [2020, 2021, 2021, 2022]):
                records = [dict.fromkeys(features, 0.5) | {'season_year': y} for y in years]
                for model in (None, SimpleNamespace(predict=Mock())):
                    with self.subTest(predict=predict.__name__, years=years, model=model):
                        self.assertIsNone(predict(123, model=model, time_series=records))
                        if model is not None:
                            model.predict.assert_not_called()

    def test_latest_invalid_season_does_not_fall_back_to_a_stale_window(self):
        records = [
            dict.fromkeys(predictor.HITTER_FEATURES, 0.5) | {'season_year': y}
            for y in range(2020, 2024)
        ]
        records[-1]['avg'] = None
        self.assertIsNone(predictor.predict_next_season(123, time_series=records))

    def test_confidence_rules_are_preserved(self):
        for count, expected in [(3, 'low'), (4, 'medium'), (7, 'high')]:
            records = [
                dict.fromkeys(predictor.HITTER_FEATURES, 0.5) | {'season_year': 2015 + i}
                for i in range(count)
            ]
            result = predictor.predict_next_season(123, time_series=records)
            self.assertEqual(result['confidence'], expected)


if __name__ == '__main__':
    unittest.main()
