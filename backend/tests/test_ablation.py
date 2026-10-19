import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from app.ml.ablation import audit_profiles, select_by_validation, variants
from app.ml import lstm_predictor as predictor
from app.ml.season_features import aggregate_hitter_seasons


class AblationTests(unittest.TestCase):
    def test_predefined_grid_changes_only_inputs_and_architecture(self):
        self.assertEqual(len(variants('hitter')), 6)
        self.assertEqual(len(variants('pitcher')), 3)
        self.assertEqual({architecture for _, _, architecture in variants('hitter')},
                         {'stacked64_32', 'single32', 'single16'})
        self.assertEqual(len(predictor.HITTER_WORKLOAD_FEATURES), 14)

    def test_selection_never_uses_test_metrics(self):
        results = [dict(label='better_test', validation_score=0.2, test_mae=0.01),
                   dict(label='better_validation', validation_score=0.1, test_mae=100)]
        self.assertEqual(select_by_validation(results)['label'], 'better_validation')

    def test_workload_changes_use_only_the_three_input_seasons(self):
        rows = [dict(pa=100, ab=90, g=30), dict(pa=300, ab=250, g=60),
                dict(pa=200, ab=170, g=50)]
        features = ['pa', 'ab', 'g', 'pa_change', 'ab_change', 'g_change']
        np.testing.assert_allclose(predictor.sequence_input_values(rows, features), [
            [100, 90, 30, 0, 0, 0], [300, 250, 60, 200, 160, 30],
            [200, 170, 50, -100, -80, -10],
        ])
        self.assertEqual(predictor.input_feature_requirements(features), ['pa', 'ab', 'g'])

    def test_derived_features_do_not_leak_target_or_change_target_scaler(self):
        rows = [dict(season_year=2015+i, pa=100+i*10, ab=90+i*8, g=20+i, y=i)
                for i in range(11)]
        options = dict(through_season=2025, validation_season=2024, test_season=2025)
        base = predictor._prepare_training_data(['p'], lambda _: rows, ['pa', 'ab', 'g'], ['y'], **options)
        derived = predictor._prepare_training_data(
            ['p'], lambda _: rows, ['pa', 'ab', 'g', 'pa_change', 'ab_change', 'g_change'], ['y'], **options,
        )
        self.assertEqual(derived.X_train.shape, (6, 3, 6))
        np.testing.assert_allclose(derived.y_train, base.y_train)
        np.testing.assert_allclose(derived.scaler_y.data_max_, base.scaler_y.data_max_)
        values = derived.scaler_X.inverse_transform(derived.X_test[0])
        np.testing.assert_allclose(values[:, 3:], [[0, 0, 0], [10, 8, 1], [10, 8, 1]])
        altered = [dict(row) for row in rows]
        altered[-1].update(pa=100000, ab=90000, g=999)
        again = predictor._prepare_training_data(
            ['p'], lambda _: altered, ['pa', 'ab', 'g', 'pa_change', 'ab_change', 'g_change'], ['y'], **options,
        )
        np.testing.assert_allclose(again.X_test, derived.X_test)

    def test_games_are_merged_only_when_requested(self):
        row = dict(player_id='p', season_year=2020, pa=100, ab=90, h=30,
                   double_hit=5, triple_hit=1, hr=2, bb=8, hbp=1, so=10, sf=1, g=30)
        self.assertNotIn('g', aggregate_hitter_seasons([row])[0])
        merged = aggregate_hitter_seasons([row, dict(row, g=20)], include_games=True)[0]
        self.assertEqual(merged['g'], 50)
        self.assertEqual(merged['pa'], 200)

    def test_partial_profiles_are_audited_not_used_to_filter_players(self):
        with TemporaryDirectory() as root:
            path = Path(root) / 'profiles.csv'
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=['player_id', 'birth_date'])
                writer.writeheader()
                writer.writerows([dict(player_id='a', birth_date='2000-01-01'),
                                  dict(player_id='b', birth_date='invalid')])
            audit = audit_profiles(path, ['a', 'b'], [('a', []), ('b', [])])
            self.assertEqual(audit['eligible_players'], 2)
            self.assertEqual(audit['eligible_with_birth_date'], 1)
            self.assertEqual(audit['test_players'], 2)
            self.assertFalse(audit['age_used'])

    def test_unknown_architecture_is_rejected(self):
        with self.assertRaises(ValueError):
            predictor._build_model_and_scalers([], lambda _: [], ['x'], ['y'], architecture='unknown')
