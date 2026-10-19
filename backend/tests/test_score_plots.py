import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.backend_bases import MouseEvent

from game_simulator.score_plots import ordered_score_counts, plot_match_scores, show_frequency_table
from game_simulator.simulator_main import MatchSimulator, PlayerProb


class ScorePlotTests(unittest.TestCase):
    def test_score_order_excludes_zero_counts_and_preserves_total_then_away_order(self):
        rows = [
            {"team_a_score": 2, "team_b_score": 0, "count": 3},
            {"team_a_score": 0, "team_b_score": 1, "count": 2},
            {"team_a_score": 0, "team_b_score": 0, "count": 0},
            {"team_a_score": 0, "team_b_score": 2, "count": 1},
            {"team_a_score": 1, "team_b_score": 0, "count": 4},
        ]
        self.assertEqual(ordered_score_counts(rows, "score"), [
            (0, 1, 2), (1, 0, 4), (0, 2, 1), (2, 0, 3),
        ])

    def test_frequency_order_preserves_all_observed_counts(self):
        rows = [
            {"team_a_score": 3, "team_b_score": 2, "count": 1},
            {"team_a_score": 1, "team_b_score": 0, "count": 4},
            {"team_a_score": 0, "team_b_score": 0, "count": 2},
        ]
        self.assertEqual(ordered_score_counts(rows, "frequency"), [(1, 0, 4), (0, 0, 2), (3, 2, 1)])

    def test_saves_and_displays_two_separate_figures_in_sequence(self):
        player = PlayerProb("타자", 0, 0, 0, 0, 0)
        result = MatchSimulator("원정", [player] * 9, "홈", [player] * 9, seed=42).simulate_many(50)
        shown = []

        def show(**kwargs):
            self.assertEqual(kwargs, {"block": True})
            self.assertEqual(len(plt.get_fignums()), 1)
            figure = plt.gcf()
            self.assertEqual(len(figure.axes), 1)
            figure.canvas.draw()
            ax = figure.axes[0]
            x, y = ax.transData.transform((0, 0.25))
            event = MouseEvent("motion_notify_event", figure.canvas, x, y)
            figure.canvas.callbacks.process("motion_notify_event", event)
            self.assertTrue(ax.texts[0].get_visible())
            self.assertIn("원정 0 : 0 홈", ax.texts[0].get_text())
            self.assertIn("50회 (100.00%)", ax.texts[0].get_text())
            outside = MouseEvent("motion_notify_event", figure.canvas, 0, 0)
            figure.canvas.callbacks.process("motion_notify_event", outside)
            self.assertFalse(ax.texts[0].get_visible())
            shown.append(figure)

        with tempfile.TemporaryDirectory() as folder, patch.object(plt, "show", side_effect=show):
            paths = plot_match_scores(result, "원정", "홈", folder, show=True)
            self.assertEqual(len(paths), 2)
            self.assertTrue(paths[0].name.endswith("_frequency.png"))
            self.assertTrue(paths[1].name.endswith("_score.png"))
            for path in paths:
                self.assertEqual(Path(path).read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(len(shown), 2)
        self.assertIsNot(shown[0], shown[1])
        self.assertEqual(plt.get_fignums(), [])

    def test_rejects_mismatched_totals_before_creating_files(self):
        with self.assertRaises(ValueError):
            plot_match_scores({"n_games": 10, "score_distribution": []}, "A", "B", show=False)

    def test_both_graphs_exclude_under_fifty_and_keep_fifty(self):
        result = {"n_games": 150, "team_a": {"wins": 101}, "team_b": {"wins": 49}, "draws": 0,
                  "score_distribution": [
                      {"team_a_score": 0, "team_b_score": 1, "count": 49},
                      {"team_a_score": 1, "team_b_score": 0, "count": 50},
                      {"team_a_score": 2, "team_b_score": 0, "count": 51},
                  ]}
        bars = []

        def show(**_kwargs):
            bars.append([bar.get_height() for bar in plt.gcf().axes[0].patches])

        with tempfile.TemporaryDirectory() as folder, patch.object(plt, "show", side_effect=show):
            plot_match_scores(result, "원정", "홈", folder)
        self.assertEqual(bars, [[51, 50], [50, 51]])
        self.assertEqual(sum(row["count"] for row in result["score_distribution"]), 150)

    def test_graphs_handle_no_scores_meeting_threshold(self):
        result = {"n_games": 2, "team_a": {"wins": 0}, "team_b": {"wins": 0}, "draws": 2,
                  "score_distribution": [{"team_a_score": 0, "team_b_score": 0, "count": 2}]}

        def show(**_kwargs):
            ax = plt.gcf().axes[0]
            self.assertEqual(len(ax.patches), 0)
            self.assertIn("50회 이상 발생한 스코어가 없습니다.", [text.get_text() for text in ax.texts])

        with tempfile.TemporaryDirectory() as folder, patch.object(plt, "show", side_effect=show) as display:
            paths = plot_match_scores(result, "원정", "홈", folder)
            self.assertEqual(len(paths), 2)
            self.assertEqual(display.call_count, 2)

    def test_frequency_table_keeps_all_csv_rows_but_saves_only_first_page(self):
        result = {"n_games": 10, "score_distribution": [
            {"team_a_score": 2, "team_b_score": 1, "count": 2},
            {"team_a_score": 0, "team_b_score": 0, "count": 3},
            {"team_a_score": 1, "team_b_score": 0, "count": 5},
        ]}

        def show(**kwargs):
            self.assertEqual(kwargs, {"block": True})
            self.assertEqual(len(plt.get_fignums()), 1)
            fig = plt.gcf()
            self.assertIn("1/2페이지", fig.axes[0].get_title())
            fig.canvas.draw()
            x, y = fig.axes[2].transAxes.transform((0.5, 0.5))
            for event_name in ("button_press_event", "button_release_event"):
                event = MouseEvent(event_name, fig.canvas, x, y, button=1)
                fig.canvas.callbacks.process(event_name, event)
            self.assertIn("2/2페이지", fig.axes[0].get_title())
            self.assertEqual(fig.axes[0].tables[0][1, 1].get_text().get_text(), "2:1")

        with tempfile.TemporaryDirectory() as folder, patch.object(plt, "show", side_effect=show):
            paths = show_frequency_table(result, "원정", "홈", folder, page_size=2)
            self.assertEqual(len(paths), 2)
            self.assertTrue(paths[1].name.endswith("_01.png"))
            self.assertEqual(list(Path(folder).glob("*.png")), [paths[1]])
            with paths[0].open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(rows[1:], [
                ["1", "1", "0", "5", "50.0000"],
                ["2", "0", "0", "3", "30.0000"],
                ["3", "2", "1", "2", "20.0000"],
            ])
            self.assertEqual(sum(int(row[3]) for row in rows[1:]), 10)
            for path in paths[1:]:
                self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(plt.get_fignums(), [])


if __name__ == "__main__":
    unittest.main()
