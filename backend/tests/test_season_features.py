import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from app.ml import lstm_predictor as predictor
from app.ml.season_features import (
    aggregate_hitter_seasons, aggregate_pitcher_seasons, innings_to_outs,
)


def hitter_stints(year=2020):
    return [
        dict(player_id='p', season_year=year, team_id=1, pa=24, ab=20, h=10,
             double_hit=2, triple_hit=0, hr=1, bb=2, hbp=0, so=5, sf=2),
        dict(player_id='p', season_year=year, team_id=2, pa=86, ab=80, h=10,
             double_hit=1, triple_hit=1, hr=2, bb=4, hbp=1, so=20, sf=1),
    ]


class InningsTests(unittest.TestCase):
    def test_fractional_innings_are_aggregated_as_outs(self):
        for value, expected in [('54 2/3', 164), ('54.2', 164), ('54.20', 164),
                                ('1/3', 1), ('2/3', 2), ('0.1', 1), ('2', 6), ('0', 0)]:
            with self.subTest(value=value):
                self.assertEqual(innings_to_outs(value), expected)

    def test_invalid_or_ambiguous_innings_are_rejected(self):
        for value in [None, '', '-', '-1', 'NaN', '1/2', '3/3', '54.3', '54.5']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                innings_to_outs(value)


class SeasonAggregationTests(unittest.TestCase):
    def test_hitter_stints_recompute_rates_from_counts_and_apply_threshold_after_merge(self):
        result = aggregate_hitter_seasons(hitter_stints())
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row['pa'], 110)
        self.assertEqual(row['ab'], 100)
        self.assertAlmostEqual(row['avg'], 0.2)
        self.assertAlmostEqual(row['slg'], 0.34)
        self.assertAlmostEqual(row['obp'], 27 / 110)
        self.assertAlmostEqual(row['ops'], 0.34 + 27 / 110)
        self.assertAlmostEqual(row['iso'], 0.14)
        self.assertAlmostEqual(row['bb_rate'], 6 / 110 * 100)
        self.assertAlmostEqual(row['k_rate'], 25 / 110 * 100)
        self.assertAlmostEqual(row['woba'],
                               (6 * 0.69 + 0.72 + 13 * 0.87 + 3 * 1.217 + 1.529 + 3 * 1.74) / 110)

    def test_pitcher_stints_recompute_per_nine_workload_and_role(self):
        stints = [
            dict(player_id='p', season_year=2020, team_id=1, g=3, gs=3, ip='10 2/3',
                 h=9, hr=1, bb=4, so=12, er=3, era=999, k9=-1),
            dict(player_id='p', season_year=2020, team_id=2, g=4, gs=1, ip='5 1/3',
                 h=5, hr=2, bb=1, so=6, er=2, era=999, k9=-1),
        ]
        rows = aggregate_pitcher_seasons(stints)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['outs'], 48)
        self.assertEqual(row['ip'], 16)
        self.assertEqual(row['g'], 7)
        self.assertAlmostEqual(row['era'], 45 / 16)
        self.assertAlmostEqual(row['whip'], 19 / 16)
        self.assertAlmostEqual(row['k9'], 18 * 9 / 16)
        self.assertAlmostEqual(row['bb9'], 5 * 9 / 16)
        self.assertAlmostEqual(row['hr9'], 3 * 9 / 16)
        self.assertAlmostEqual(row['starter_ratio'], 4 / 7)
        self.assertAlmostEqual(row['ip_per_g'], 16 / 7)

    def test_zero_innings_and_missing_counts_do_not_turn_into_zero_rates(self):
        zero = dict(player_id='p', season_year=2020, g=10, gs=0, ip='0',
                    h=0, hr=0, bb=0, so=0, er=0)
        self.assertEqual(aggregate_pitcher_seasons([zero]), [])
        missing = hitter_stints()
        missing[0]['bb'] = None
        with self.assertLogs('app.ml.season_features', level='WARNING'):
            self.assertEqual(aggregate_hitter_seasons(missing), [])

    def test_players_and_years_are_never_merged_together(self):
        rows = hitter_stints(2020) + hitter_stints(2021)
        other = [dict(row, player_id='other') for row in hitter_stints(2020)]
        result = aggregate_hitter_seasons(rows + other)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(row['pa'] == 110 for row in result))


class SharedPipelineTests(unittest.TestCase):
    def test_training_and_inference_both_use_merged_yearly_features(self):
        raw = [row for year in range(2015, 2021) for row in hitter_stints(year)]
        with patch.object(predictor, '_fetch_player_rows', return_value=raw):
            data = predictor.get_hitter_time_series('p')
            prepared = predictor._prepare_training_data(
                ['p'], predictor.get_hitter_time_series,
                predictor.HITTER_FEATURES, predictor.HITTER_TARGETS,
            )
            model = SimpleNamespace(predict=Mock(return_value=np.zeros((1, 3))))
            result = predictor.predict_next_season('p', model, prepared.scaler_X, prepared.scaler_y)
        self.assertEqual(len(data), 6)
        self.assertEqual(prepared.skipped_windows, 0)
        self.assertEqual(result['seasons_used'], 6)
        expected = prepared.scaler_X.transform(
            [[row[key] for key in predictor.HITTER_FEATURES] for row in data[-3:]],
        ).reshape(1, 3, len(predictor.HITTER_FEATURES))
        np.testing.assert_allclose(model.predict.call_args.args[0], expected)


if __name__ == '__main__':
    unittest.main()
