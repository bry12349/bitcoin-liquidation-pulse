from __future__ import annotations

from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
import errno
import json
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlparse

from liquidation_pulse.binance_ws import BinanceForceOrderCollector
from liquidation_pulse.external_liquidations import CoinMarketCapLiquidationClient, merge_liquidation_snapshots
from liquidation_pulse.liquidations import LiquidationStore
from liquidation_pulse.onchain import MempoolClient
from liquidation_pulse.proxy import detect_proxy_url

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = PROJECT_ROOT / "web"
DATA_DIR = PROJECT_ROOT / "data"


class DashboardState:
    def __init__(self) -> None:
        self.proxy_url = detect_proxy_url()
        self.liquidations = LiquidationStore(DATA_DIR / "liquidations.jsonl")
        self.onchain = MempoolClient(proxy_url=self.proxy_url)
        self.external_liquidations = CoinMarketCapLiquidationClient(proxy_url=self.proxy_url)
        self.collector = BinanceForceOrderCollector(self.liquidations, proxy_url=self.proxy_url)
        self._cached_onchain: dict[str, Any] = {}
        self._onchain_updated_ms = 0
        self._cached_external_liquidations: dict[str, Any] | None = None
        self._external_liquidations_updated_ms = 0

    def start(self) -> None:
        self.collector.start()

    def snapshot(self, force_onchain: bool = False) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        if force_onchain or now_ms - self._onchain_updated_ms > 30_000:
            self._cached_onchain = self.onchain.snapshot()
            self._onchain_updated_ms = now_ms
        if force_onchain or now_ms - self._external_liquidations_updated_ms > 60_000:
            external = self.external_liquidations.btc_24h_snapshot()
            if external:
                self._cached_external_liquidations = external
                self._external_liquidations_updated_ms = now_ms
        liquidations = merge_liquidation_snapshots(
            self.liquidations.snapshot(now_ms=now_ms),
            self._cached_external_liquidations,
        )
        return {
            "generated_at_ms": now_ms,
            "symbol": "BTCUSDT",
            "liquidations": liquidations,
            "onchain": self._cached_onchain,
            "collector": self.collector.status,
            "sources": {
                "liquidations": "CoinMarketCap 24h liquidation table + Binance USD-M Futures BTCUSDT forceOrder WebSocket",
                "onchain": "mempool.space public API",
            },
            "proxy": self.proxy_url,
        }


class DashboardHandler(SimpleHTTPRequestHandler):
    state: DashboardState

    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, directory=directory or str(WEB_ROOT), **kwargs)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/snapshot":
            self._write_json(self.state.snapshot())
            return
        if path == "/api/refresh":
            self._write_json(self.state.snapshot(force_onchain=True))
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _write_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(host: str = "127.0.0.1", port: int = 8765) -> HTTPServer:
    state = DashboardState()
    DashboardHandler.state = state
    handler = partial(DashboardHandler, directory=str(WEB_ROOT))
    last_error: OSError | None = None
    for candidate_port in _candidate_ports(port):
        try:
            server = HTTPServer((host, candidate_port), handler)
        except OSError as exc:
            if exc.errno not in {errno.EADDRINUSE, errno.EACCES}:
                raise
            last_error = exc
            continue
        state.start()
        return server
    if last_error:
        raise last_error
    raise OSError("No available port found")


def _candidate_ports(port: int) -> list[int]:
    if port == 0:
        return [0]
    return list(range(port, port + 20))
