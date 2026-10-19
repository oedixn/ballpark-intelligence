import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from app.ml.benchmark import baseline_predictions, collect_test_cases, compare_prediction_files, load_csv_data
from app.ml.lstm_predictor import HITTER_FEATURES, HITTER_TARGETS, _weighted_avg_predict


class BenchmarkTests(unittest.TestCase):
    def test_five_season_window_keeps_the_existing_three_season_baseline(self):
        window = [dict.fromkeys(HITTER_FEATURES, value) | {'season_year': 2020 + i}
                  for i, value in enumerate([50.0, 60.0, 0.2, 0.3, 0.4, 999.0])]
        cases = collect_test_cases(['p'], lambda _: window, HITTER_FEATURES, HITTER_TARGETS,
                                   2025, lookback=5)
        self.assertEqual(len(cases[0][1]), 6)
        predictions = baseline_predictions(cases, HITTER_FEATURES, HITTER_TARGETS)
        np.testing.assert_allclose(predictions['weighted_average'], [[0.36] * 3])
        np.testing.assert_allclose(predictions['last_season'], [[0.4] * 3])

    def test_comparison_restricts_both_runs_to_same_players_and_checks_labels(self):
        def write(path, rows):
            with path.open('w', encoding='utf-8-sig', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    'player_id', 'season_year', 'target', 'actual', 'lstm',
                    'last_season', 'weighted_average',
                ])
                writer.writeheader()
                writer.writerows(rows)
        def row(pid, actual, predicted):
            return dict(player_id=pid, season_year=2025, target='avg', actual=actual,
                        lstm=predicted, last_season=0.2, weighted_average=0.3)
        with TemporaryDirectory() as root:
            old_path, new_path = Path(root) / 'old.csv', Path(root) / 'new.csv'
            write(old_path, [row('a', 0.3, 0.2), row('b', 0.9, 0.0)])
            write(new_path, [row('a', 0.3, 0.28)])
            comparison = compare_prediction_files(old_path, new_path, ['avg'])
            self.assertEqual(comparison['common_test_samples'], 1)
            self.assertEqual(comparison['previous_test_samples'], 2)
            self.assertAlmostEqual(comparison['previous_metrics']['avg']['mae'], 0.1)
            self.assertAlmostEqual(comparison['current_metrics']['avg']['mae'], 0.02)
            write(new_path, [row('a', 0.5, 0.28)])
            with self.assertRaises(AssertionError):
                compare_prediction_files(old_path, new_path, ['avg'])
            write(new_path, [row('a', 0.3, 0.28)] * 2)
            with self.assertRaises(ValueError):
                compare_prediction_files(old_path, new_path, ['avg'])

    def test_baselines_use_only_the_three_input_years(self):
        window = [
            dict.fromkeys(HITTER_FEATURES, value) | {'season_year': 2022 + i}
            for i, value in enumerate([0.2, 0.3, 0.4, 999.0])
        ]
        predictions = baseline_predictions([('p', window)], HITTER_FEATURES, HITTER_TARGETS)
        np.testing.assert_allclose(predictions['last_season'], [[0.4] * 3])
        np.testing.assert_allclose(predictions['weighted_average'], [[0.36] * 3])
        expected = _weighted_avg_predict(window[:3], HITTER_FEATURES, HITTER_TARGETS)
        self.assertEqual(predictions['weighted_average'].tolist()[0], list(expected.values()))

    def test_test_cases_have_same_player_order_and_exclude_missing_years(self):
        data = {
            'a': [dict.fromkeys(HITTER_FEATURES, 0.3) | {'season_year': y}
                  for y in (2022, 2023, 2024, 2025)],
            'b': [dict.fromkeys(HITTER_FEATURES, 0.3) | {'season_year': y}
                  for y in (2021, 2023, 2024, 2025)],
        }
        cases = collect_test_cases(['a', 'b'], data.__getitem__, HITTER_FEATURES, HITTER_TARGETS, 2025)
        self.assertEqual([pid for pid, _ in cases], ['a'])
        self.assertEqual(cases[0][1][-1]['season_year'], 2025)

    def test_csv_cohort_does_not_use_records_after_the_cutoff(self):
        rows = []
        for pid, years in [('included', range(2022, 2026)), ('future_only', range(2023, 2027))]:
            for year in years:
                rows.append(dict(player_id=pid, player_name=pid, season_year=year,
                                 pa=110, ab=100, h=30, double_hit=5, triple_hit=1,
                                 hr=2, bb=5, hbp=1, so=20, sf=4))
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'player_hitter_stats.csv'
            with path.open('w', encoding='utf-8-sig', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            ids, grouped, names, source = load_csv_data(directory, 'hitter', 2025)
            self.assertEqual(ids, ['included'])
            self.assertEqual(len(grouped['future_only']), 3)
            self.assertEqual(names['included'], 'included')
            self.assertEqual(source['raw_rows'], 7)
            self.assertEqual(len(source['sha256']), 64)
            json.dumps(source, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
