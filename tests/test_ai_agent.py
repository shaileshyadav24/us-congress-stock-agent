"""Tests for the local prompt agent."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_agent import CongressPromptAgent, execute_agent_plan
from congress_stock_tracker import CongressStockTracker


class TestCongressPromptAgent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tracker = CongressStockTracker(db_path=str(Path(self.tmp.name) / "test.db"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.tracker.import_sample_data()
        self.agent = CongressPromptAgent(self.tracker)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_member_trades(self):
        plan = self.agent.plan("show Nancy Pelosi buys in 2024 limit 5")

        self.assertEqual(plan.action, "trades")
        self.assertEqual(plan.args["member"], "Nancy Pelosi")
        self.assertEqual(plan.args["trade_type"], "buy")
        self.assertEqual(plan.args["year"], 2024)
        self.assertEqual(plan.args["limit"], 5)

    def test_plan_stock_search(self):
        plan = self.agent.plan("search NVDA trades")

        self.assertEqual(plan.action, "search")
        self.assertEqual(plan.args["stock"], "NVDA")

    def test_plan_update(self):
        plan = self.agent.plan("fetch latest trades for pelosi pages 2")

        self.assertEqual(plan.action, "update")
        self.assertEqual(plan.args["members"], ["Nancy Pelosi"])
        self.assertEqual(plan.args["pages"], 2)
        self.assertEqual(plan.args["sources"], ["capitolexposed"])

    def test_execute_trades_plan(self):
        plan = self.agent.plan("show Nancy Pelosi buys in 2024")
        kind, result = execute_agent_plan(plan, self.tracker)
        rows, total = result

        self.assertEqual(kind, "trades")
        self.assertGreaterEqual(total, 2)
        self.assertTrue(all(row["member_name"] == "Nancy Pelosi" for row in rows))
        self.assertTrue(all(row["trade_type"] == "buy" for row in rows))


if __name__ == "__main__":
    unittest.main()
