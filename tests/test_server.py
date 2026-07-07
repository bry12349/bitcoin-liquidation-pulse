from __future__ import annotations

import unittest
from unittest.mock import patch
from http.server import HTTPServer
from pathlib import Path
from socketserver import BaseRequestHandler
import tempfile

from liquidation_pulse.server import DashboardHandler, DashboardState, create_server


class ServerFactoryTest(unittest.TestCase):
    def test_create_server_attaches_state_to_handler_class(self) -> None:
        with patch.object(DashboardState, "start", return_value=None):
            server = create_server(port=0)
        try:
            self.assertTrue(hasattr(DashboardHandler, "state"))
            self.assertIsNotNone(DashboardHandler.state)
        finally:
            server.server_close()

    def test_create_server_uses_next_port_when_default_is_busy(self) -> None:
        occupied = HTTPServer(("127.0.0.1", 0), BaseRequestHandler)
        occupied_port = occupied.server_address[1]
        with patch.object(DashboardState, "start", return_value=None):
            server = create_server(port=occupied_port)
        try:
            self.assertNotEqual(server.server_address[1], occupied_port)
        finally:
            server.server_close()
            occupied.server_close()

    def test_snapshot_includes_source_health_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch("liquidation_pulse.server.DATA_DIR", Path(tmp)):
            state = DashboardState()
            state.onchain.snapshot = lambda: {
                "fees": {"fastest": 8},
                "fee_pressure": "quiet",
                "large_transactions": [],
                "mempool_blocks": [],
            }
            state.external_liquidations.btc_24h_snapshot = lambda: {
                "source": "CoinMarketCap 24h liquidation table",
                "updated_at_ms": 1_700_000_000_000,
                "long_usd": 100.0,
                "short_usd": 300.0,
                "total_usd": 400.0,
                "open_interest_usd": 1_000.0,
            }
            state.collector.status = {
                "state": "connected",
                "message": "test",
                "last_event_ms": None,
                "last_error": None,
                "proxy": None,
            }

            payload = state.snapshot(force_onchain=True)

        self.assertIn("health", payload)
        self.assertIn("cmc", payload["health"])
        self.assertEqual(payload["health"]["cmc"]["status"], "ok")
        self.assertIn("history", payload)
        self.assertEqual(payload["history"]["count"], 1)
        self.assertEqual(payload["liquidations"]["basis"], "external_24h")

    def test_mempool_health_does_not_fake_success_time_when_partial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch("liquidation_pulse.server.DATA_DIR", Path(tmp)):
            state = DashboardState()
            state._cached_onchain = {"fees": {"fastest": 0}}
            state._onchain_updated_ms = 1_700_000_000_000
            state.onchain.last_errors = {"/v1/fees/recommended": "timeout"}
            state.onchain.last_success_ms = None

            health = state._mempool_health()

        self.assertEqual(health["status"], "partial")
        self.assertIsNone(health["last_success_ms"])


if __name__ == "__main__":
    unittest.main()
