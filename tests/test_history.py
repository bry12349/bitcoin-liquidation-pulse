from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from liquidation_pulse.history import SnapshotHistory


class SnapshotHistoryTest(unittest.TestCase):
    def test_records_at_most_once_per_minute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshots.jsonl"
            history = SnapshotHistory(path)
            payload = {
                "generated_at_ms": 1_700_000_000_000,
                "liquidations": {
                    "basis": "external_24h",
                    "long": {"usd": 100.0},
                    "short": {"usd": 40.0},
                    "total_usd": 140.0,
                    "net_usd": -60.0,
                },
                "onchain": {"fees": {"fastest": 12}, "fee_pressure": "elevated"},
            }

            self.assertTrue(history.record(payload, now_ms=1_700_000_000_000))
            self.assertFalse(history.record(payload, now_ms=1_700_000_030_000))
            self.assertTrue(history.record(payload, now_ms=1_700_000_060_000))

            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["basis"], "external_24h")

    def test_summary_returns_recent_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshots.jsonl"
            history = SnapshotHistory(path, max_points=2)
            for index in range(3):
                history.record(
                    {
                        "generated_at_ms": 1_700_000_000_000 + index * 60_000,
                        "liquidations": {
                            "basis": "live_collected",
                            "long": {"usd": index},
                            "short": {"usd": index + 1},
                            "total_usd": index + 2,
                            "net_usd": 1,
                        },
                        "onchain": {"fees": {"fastest": index + 3}, "fee_pressure": "quiet"},
                    },
                    now_ms=1_700_000_000_000 + index * 60_000,
                )

            summary = history.summary()

            self.assertEqual(summary["count"], 2)
            self.assertEqual(summary["points"][0]["total_usd"], 3.0)
            self.assertEqual(summary["points"][1]["fee_fastest"], 5)
