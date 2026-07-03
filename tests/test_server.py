from __future__ import annotations

import unittest
from unittest.mock import patch
from http.server import HTTPServer
from socketserver import BaseRequestHandler

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


if __name__ == "__main__":
    unittest.main()
