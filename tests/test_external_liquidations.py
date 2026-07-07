from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

from liquidation_pulse.external_liquidations import (
    CoinMarketCapLiquidationClient,
    build_cmc_btc_snapshot,
    build_liquidation_view,
    merge_liquidation_snapshots,
)


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

    def test_liquidation_view_prefers_external_without_double_counting(self) -> None:
        live = {
            "coverage": {"label": "collected 12 min", "minutes": 12},
            "long": {"usd": 100.0, "count": 2},
            "short": {"usd": 50.0, "count": 1},
            "total_usd": 150.0,
            "net_usd": -50.0,
            "net_bias": "longs flushed",
            "hourly": [{"label": "12:00", "long_usd": 100.0, "short_usd": 50.0, "count": 3}],
            "recent": [],
        }
        external = {
            "source": "CoinMarketCap 24h liquidation table",
            "updated_at_ms": 1_700_000_000_000,
            "long_usd": 1_000.0,
            "short_usd": 2_000.0,
            "total_usd": 3_000.0,
            "open_interest_usd": 10_000.0,
        }

        view = build_liquidation_view(live, external, now_ms=1_700_000_060_000)

        self.assertEqual(view["basis"], "external_24h")
        self.assertEqual(view["long"]["usd"], 1_000.0)
        self.assertEqual(view["short"]["usd"], 2_000.0)
        self.assertEqual(view["total_usd"], 3_000.0)
        self.assertEqual(view["live_collected"]["total_usd"], 150.0)
        self.assertEqual(view["combined_experimental"]["total_usd"], 3_150.0)
        self.assertTrue(view["combined_experimental"]["overlap_risk"])

    def test_liquidation_view_falls_back_to_live_when_external_missing(self) -> None:
        live = {
            "coverage": {"label": "collected 12 min", "minutes": 12},
            "long": {"usd": 100.0, "count": 2},
            "short": {"usd": 50.0, "count": 1},
            "total_usd": 150.0,
            "net_usd": -50.0,
            "net_bias": "longs flushed",
            "hourly": [],
            "recent": [],
        }

        view = build_liquidation_view(live, None, now_ms=1_700_000_060_000)

        self.assertEqual(view["basis"], "live_collected")
        self.assertEqual(view["long"]["usd"], 100.0)
        self.assertEqual(view["total_usd"], 150.0)
        self.assertIsNone(view["external_24h"])
        self.assertIsNone(view["combined_experimental"])

    def test_cmc_client_records_request_failures(self) -> None:
        client = CoinMarketCapLiquidationClient(proxy_url=None)

        with patch("liquidation_pulse.external_liquidations.requests.get") as get:
            get.side_effect = requests.RequestException("network down")
            snapshot = client.btc_24h_snapshot()

        self.assertIsNone(snapshot)
        self.assertIn("network down", client.last_error or "")


if __name__ == "__main__":
    unittest.main()
