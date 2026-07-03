from __future__ import annotations

import unittest

from liquidation_pulse.external_liquidations import build_cmc_btc_snapshot, merge_liquidation_snapshots


class ExternalLiquidationsTest(unittest.TestCase):
    def test_builds_cmc_btc_snapshot_from_table_response(self) -> None:
        snapshot = build_cmc_btc_snapshot(
            {
                "data": {
                    "items": [
                        {"symbol": "ETH", "longLiquidations": 1, "shortLiquidations": 2},
                        {
                            "symbol": "BTC",
                            "longLiquidations": 40272456.05,
                            "shortLiquidations": 62709238.59,
                            "totalLiquidations": 102981694.64,
                            "openInterestUsd": 78118836477.32,
                        },
                    ]
                }
            },
            updated_at_ms=1_700_000_000_000,
        )

        self.assertEqual(snapshot["long_usd"], 40272456.05)
        self.assertEqual(snapshot["short_usd"], 62709238.59)
        self.assertEqual(snapshot["total_usd"], 102981694.64)
        self.assertEqual(snapshot["source"], "CoinMarketCap 24h liquidation table")

    def test_merge_uses_external_snapshot_when_live_is_empty(self) -> None:
        live = {
            "coverage": {"label": "waiting", "minutes": 0},
            "long": {"usd": 0, "count": 0},
            "short": {"usd": 0, "count": 0},
            "total_usd": 0,
            "net_usd": 0,
            "net_bias": "neutral",
            "hourly": [{"label": "12:00", "long_usd": 0, "short_usd": 0, "count": 0}],
        }
        external = {"long_usd": 10.0, "short_usd": 30.0, "total_usd": 40.0, "updated_at_ms": 1}

        merged = merge_liquidation_snapshots(live, external)

        self.assertEqual(merged["long"]["usd"], 10.0)
        self.assertEqual(merged["short"]["usd"], 30.0)
        self.assertEqual(merged["total_usd"], 40.0)
        self.assertEqual(merged["net_bias"], "shorts squeezed")
        self.assertEqual(merged["hourly"][-1]["label"], "24h")
        self.assertEqual(merged["coverage"]["label"], "CMC 24h snapshot + Binance live")


if __name__ == "__main__":
    unittest.main()
