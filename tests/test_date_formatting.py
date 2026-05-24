"""Tests for user-facing date formatting."""

import csv
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from congress_stock_tracker import (
    CongressStockTracker,
    format_display_date,
    parse_user_date,
)


class TestDateFormatting(unittest.TestCase):
    def test_format_display_date(self):
        self.assertEqual(format_display_date("2024-03-05"), "5 March 2024")
        self.assertEqual(format_display_date("2024-12-31"), "31 December 2024")

    def test_parse_user_date(self):
        self.assertEqual(parse_user_date("5 March 2024"), "2024-03-05")
        self.assertEqual(parse_user_date("5, March, 2024"), "2024-03-05")
        self.assertEqual(parse_user_date("31 Dec 2024"), "2024-12-31")
        self.assertEqual(parse_user_date("2024-12-31"), "2024-12-31")

    def test_exports_use_display_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            tracker = CongressStockTracker(db_path=str(db_path))
            with contextlib.redirect_stdout(io.StringIO()):
                tracker.import_sample_data()

            csv_base = Path(tmp) / "trades"
            with contextlib.redirect_stdout(io.StringIO()):
                tracker.export_data(filename=str(csv_base), fmt="csv", member="Nancy Pelosi")
            with open(f"{csv_base}.csv", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertIn("20 September 2024", {row["trade_date"] for row in rows})

            json_base = Path(tmp) / "trades"
            with contextlib.redirect_stdout(io.StringIO()):
                tracker.export_data(filename=str(json_base), fmt="json", member="Nancy Pelosi")
            with open(f"{json_base}.json", encoding="utf-8") as f:
                payload = json.load(f)
            self.assertIn("20 September 2024", {row["trade_date"] for row in payload})


if __name__ == "__main__":
    unittest.main()
