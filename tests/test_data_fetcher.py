"""Tests for data_fetcher normalization and parsing."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_fetcher import CongressDataFetcher, PARTY_MAP, TX_TYPE_MAP
from congress_stock_tracker import CongressMember, CongressStockTracker


class TestNormalization(unittest.TestCase):
    def setUp(self):
        self.fetcher = CongressDataFetcher(cache_dir=".cache_test")

    def test_normalize_trade_data(self):
        raw = {
            "member_name": "Nancy Pelosi",
            "member_id": "P000197",
            "symbol": "aapl",
            "company": "Apple Inc.",
            "trade_date": "2024-06-10",
            "trade_type": "purchase",
            "amount_range": "$1,001-$15,000",
            "source": "capitolexposed.com",
            "filing_date": "2024-06-15",
        }
        result = self.fetcher.normalize_trade_data(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["trade_type"], "buy")
        self.assertEqual(result["financial_year"], 2024)

    def test_reject_missing_symbol(self):
        raw = {"member_name": "Test", "symbol": "", "trade_date": "2024-01-01"}
        self.assertIsNone(self.fetcher.normalize_trade_data(raw))

    def test_deduplicate_trades(self):
        trades = [
            {"member_name": "A", "symbol": "MSFT", "trade_date": "2024-01-01", "trade_type": "buy"},
            {"member_name": "A", "symbol": "MSFT", "trade_date": "2024-01-01", "trade_type": "buy"},
            {"member_name": "A", "symbol": "AAPL", "trade_date": "2024-01-01", "trade_type": "buy"},
        ]
        self.assertEqual(len(self.fetcher.deduplicate_trades(trades)), 2)

    def test_format_amount_range(self):
        self.assertIn("15,001", self.fetcher._format_amount_range("15001", "50000"))

    def test_parse_capitolexposed_trade(self):
        item = {
            "ticker": "AMZN",
            "asset_description": "Amazon.com, Inc.",
            "transaction_type": "purchase",
            "transaction_date": "2026-01-16T00:00:00.000Z",
            "disclosure_date": "2026-01-23T00:00:00.000Z",
            "amount_min": "500001",
            "amount_max": "1000000",
            "member_id": "m-P000197",
        }
        parsed = self.fetcher._parse_capitolexposed_trade(item, "Nancy Pelosi")
        self.assertEqual(parsed["symbol"], "AMZN")
        self.assertEqual(parsed["trade_type"], "buy")

    def test_name_to_slug(self):
        self.assertEqual(self.fetcher._name_to_slug("Nancy Pelosi"), "nancy-pelosi")


class TestCapitolExposedMock(unittest.TestCase):
    def setUp(self):
        self.fetcher = CongressDataFetcher(cache_dir=".cache_test")
        self.fetcher.clear_cache()

    @patch.object(CongressDataFetcher, "_http_get_json")
    def test_fetch_capitolexposed_member(self, mock_get):
        mock_get.return_value = {
            "status": "success",
            "data": [
                {
                    "ticker": "NVDA",
                    "asset_description": "NVIDIA Corp",
                    "transaction_type": "sale",
                    "transaction_date": "2025-01-10T00:00:00.000Z",
                    "disclosure_date": "2025-01-15T00:00:00.000Z",
                    "amount_min": "15001",
                    "amount_max": "50000",
                    "member_id": "m-P000197",
                }
            ],
            "meta": {"has_more": False},
        }
        with patch.object(self.fetcher, "resolve_member_slug", return_value="nancy-pelosi"):
            trades = self.fetcher.fetch_capitolexposed_trades("Nancy Pelosi", "P000197", max_pages=1)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["symbol"], "NVDA")
        self.assertEqual(trades[0]["trade_type"], "sell")


class TestMemberRoster(unittest.TestCase):
    def test_roster_record_to_member(self):
        record = {
            "bioguide_id": "P000197",
            "name": "Nancy Pelosi",
            "party": "D",
            "chamber": "house",
            "state": "CA",
        }
        member = CongressDataFetcher.roster_record_to_member(record)
        self.assertIsInstance(member, CongressMember)
        self.assertEqual(member.member_id, "P000197")
        self.assertEqual(member.party, "Democratic")
        self.assertEqual(member.chamber, "House")

    def test_sync_members_from_roster(self):
        db_path = ".cache_test/test_members.db"
        Path(db_path).unlink(missing_ok=True)
        tracker = CongressStockTracker(db_path=db_path)
        fetcher = CongressDataFetcher(cache_dir=".cache_test")

        roster = [
            {
                "bioguide_id": "P000197",
                "name": "Nancy Pelosi",
                "party": "D",
                "chamber": "house",
                "state": "CA",
                "in_office": True,
                "trade_count": 10,
            },
            {
                "bioguide_id": "X000000",
                "name": "No Trades Member",
                "party": "R",
                "chamber": "house",
                "state": "TX",
                "in_office": True,
                "trade_count": 0,
            },
        ]

        with patch.object(fetcher, "fetch_capitolexposed_roster", return_value=roster):
            summary = fetcher.sync_members_from_roster(
                tracker, traders_only=True, in_office_only=True
            )

        self.assertEqual(summary["added"], 1)
        self.assertEqual(tracker.count_members(), 1)
        Path(db_path).unlink(missing_ok=True)

    def test_ensure_member_for_trade(self):
        db_path = ".cache_test/test_ensure.db"
        Path(db_path).unlink(missing_ok=True)
        tracker = CongressStockTracker(db_path=db_path)
        fetcher = CongressDataFetcher(cache_dir=".cache_test")

        roster_record = {
            "bioguide_id": "M001236",
            "name": "Tim Moore",
            "party": "R",
            "chamber": "house",
            "state": "NC",
        }
        with patch.object(
            fetcher, "lookup_roster_record", return_value=roster_record
        ):
            mid = fetcher.ensure_member_for_trade(
                tracker,
                {
                    "member_id": "M001236",
                    "member_name": "Tim Moore",
                    "symbol": "T",
                    "trade_date": "2026-05-18",
                    "trade_type": "buy",
                },
            )
        self.assertEqual(mid, "M001236")
        self.assertEqual(tracker.count_members(), 1)
        Path(db_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
