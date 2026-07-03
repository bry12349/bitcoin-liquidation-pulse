from __future__ import annotations

import unittest

from liquidation_pulse.liquidations import LiquidationStore


class LiquidationStoreTest(unittest.TestCase):
    def test_classifies_binance_sell_as_long_liquidation(self) -> None:
        store = LiquidationStore()

        event = store.add_binance_force_order(
            {
                "E": 1_700_000_000_000,
                "o": {
                    "s": "BTCUSDT",
                    "S": "SELL",
                    "p": "65000",
                    "q": "0.25",
                },
            }
        )

        self.assertIsNotNone(event)
        snapshot = store.snapshot(now_ms=1_700_000_000_000)
        self.assertEqual(snapshot["long"]["count"], 1)
        self.assertEqual(snapshot["short"]["count"], 0)
        self.assertEqual(snapshot["long"]["usd"], 16250.0)

    def test_classifies_binance_buy_as_short_liquidation(self) -> None:
        store = LiquidationStore()

        store.add_binance_force_order(
            {
                "E": 1_700_000_000_000,
                "o": {
                    "s": "BTCUSDT",
                    "S": "BUY",
                    "p": "64000",
                    "q": "0.5",
                },
            }
        )

        snapshot = store.snapshot(now_ms=1_700_000_000_000)
        self.assertEqual(snapshot["short"]["count"], 1)
        self.assertEqual(snapshot["short"]["usd"], 32000.0)
        self.assertEqual(snapshot["net_bias"], "shorts squeezed")

    def test_prunes_events_outside_rolling_24h_window(self) -> None:
        store = LiquidationStore()
        now_ms = 1_700_086_400_000

        store.add_binance_force_order(
            {"E": now_ms - 86_400_001, "o": {"s": "BTCUSDT", "S": "SELL", "p": "60000", "q": "1"}}
        )
        store.add_binance_force_order(
            {"E": now_ms - 60_000, "o": {"s": "BTCUSDT", "S": "SELL", "p": "61000", "q": "1"}}
        )

        snapshot = store.snapshot(now_ms=now_ms)
        self.assertEqual(snapshot["long"]["count"], 1)
        self.assertEqual(snapshot["long"]["usd"], 61000.0)

    def test_builds_hourly_bins(self) -> None:
        store = LiquidationStore()
        base_ms = 1_700_000_000_000

        store.add_binance_force_order(
            {"E": base_ms, "o": {"s": "BTCUSDT", "S": "SELL", "p": "50000", "q": "0.1"}}
        )
        store.add_binance_force_order(
            {"E": base_ms + 3_600_000, "o": {"s": "BTCUSDT", "S": "BUY", "p": "50000", "q": "0.2"}}
        )

        snapshot = store.snapshot(now_ms=base_ms + 3_600_000)
        non_empty = [bucket for bucket in snapshot["hourly"] if bucket["long_usd"] or bucket["short_usd"]]
        self.assertEqual(len(non_empty), 2)
        self.assertEqual(non_empty[0]["long_usd"], 5000.0)
        self.assertEqual(non_empty[1]["short_usd"], 10000.0)


if __name__ == "__main__":
    unittest.main()
