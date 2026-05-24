"""Tests for clearing trade data before resync."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from congress_stock_tracker import CongressStockTracker


class TestClearTrades(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tracker = CongressStockTracker(db_path=str(Path(self.tmp.name) / "test.db"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.tracker.import_sample_data()

    def tearDown(self):
        self.tmp.cleanup()

    def test_clear_trades_by_member_rebuilds_stats(self):
        deleted = self.tracker.clear_trades(member="Nancy Pelosi")
        rows, total = self.tracker.query_trades(member="Nancy Pelosi")
        stats = self.tracker.get_stats_filtered(year=2024)

        self.assertEqual(deleted, 3)
        self.assertEqual(total, 0)
        self.assertFalse(any(row["member_name"] == "Nancy Pelosi" for row in stats))

    def test_clear_trades_by_stock_rebuilds_stats(self):
        deleted = self.tracker.clear_trades(stock="MSFT")
        rows, total = self.tracker.query_trades(stock="MSFT")
        member_stats = [
            row for row in self.tracker.get_stats_filtered(year=2024)
            if row["member_name"] == "Nancy Pelosi"
        ]

        self.assertEqual(deleted, 2)
        self.assertEqual(total, 0)
        self.assertEqual(member_stats[0]["total_trades"], 1)

    def test_clear_all_trades_removes_all_stats(self):
        deleted = self.tracker.clear_trades(all_trades=True)

        self.assertEqual(deleted, 12)
        self.assertEqual(self.tracker.query_trades()[1], 0)
        self.assertEqual(self.tracker.get_stats_filtered(), [])


if __name__ == "__main__":
    unittest.main()
