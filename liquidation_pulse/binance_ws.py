from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any

import aiohttp

from liquidation_pulse.liquidations import LiquidationStore
from liquidation_pulse.proxy import detect_proxy_url

BINANCE_FORCE_ORDER_WS = "wss://fstream.binance.com/ws/btcusdt@forceOrder"


class BinanceForceOrderCollector:
    def __init__(self, store: LiquidationStore, url: str = BINANCE_FORCE_ORDER_WS, proxy_url: str | None = None) -> None:
        self.store = store
        self.url = url
        self.proxy_url = proxy_url if proxy_url is not None else detect_proxy_url()
        self.status: dict[str, Any] = {
            "state": "idle",
            "message": "collector not started",
            "last_event_ms": None,
            "last_error": None,
            "proxy": self.proxy_url,
        }
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, name="binance-force-order", daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.run(self._collect_forever())

    async def _collect_forever(self) -> None:
        while True:
            try:
                self.status.update({"state": "connecting", "message": "connecting to Binance", "last_error": None})
                timeout = aiohttp.ClientTimeout(total=None, connect=12, sock_read=75)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.ws_connect(self.url, heartbeat=30, proxy=self.proxy_url) as websocket:
                        self.status.update({"state": "connected", "message": "listening for BTCUSDT liquidations"})
                        async for message in websocket:
                            if message.type == aiohttp.WSMsgType.TEXT:
                                self._handle_message(message.data)
                            elif message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                                break
            except Exception as exc:  # noqa: BLE001 - collector must not crash the dashboard
                self.status.update(
                    {
                        "state": "reconnecting",
                        "message": "Binance stream unavailable; retrying",
                        "last_error": str(exc),
                    }
                )
                await asyncio.sleep(5)

    def _handle_message(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return
        event = self.store.add_binance_force_order(payload)
        if event:
            self.status.update(
                {
                    "state": "connected",
                    "message": "liquidation stream active",
                    "last_event_ms": int(time.time() * 1000),
                    "last_error": None,
                }
            )
