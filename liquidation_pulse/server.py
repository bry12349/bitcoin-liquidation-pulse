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
from liquidation_pulse.external_liquidations import CoinMarketCapLiquidationClient, build_liquidation_view
from liquidation_pulse.history import SnapshotHistory
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
        self.history = SnapshotHistory(DATA_DIR / "snapshots.jsonl")
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
        liquidations = build_liquidation_view(
            self.liquidations.snapshot(now_ms=now_ms),
            self._cached_external_liquidations,
            now_ms=now_ms,
        )
        payload = {
            "generated_at_ms": now_ms,
            "symbol": "BTCUSDT",
            "liquidations": liquidations,
            "onchain": self._cached_onchain,
            "collector": self.collector.status,
            "health": self._source_health(now_ms),
            "sources": {
                "liquidations": "CoinMarketCap 24h liquidation table; Binance USD-M Futures BTCUSDT forceOrder WebSocket tracked separately",
                "onchain": "mempool.space public API",
            },
            "proxy": self.proxy_url,
        }
        self.history.record(payload, now_ms=now_ms)
        payload["history"] = self.history.summary()
        return payload

    def _source_health(self, now_ms: int) -> dict[str, Any]:
        return {
            "cmc": self._cmc_health(now_ms),
            "mempool": self._mempool_health(),
            "binance": self._binance_health(),
        }

    def _cmc_health(self, now_ms: int) -> dict[str, Any]:
        last_success_ms = self.external_liquidations.last_success_ms or self._external_liquidations_updated_ms or None
        last_attempt_ms = self.external_liquidations.last_attempt_ms or self._external_liquidations_updated_ms or None
        last_error = self.external_liquidations.last_error
        if last_success_ms:
            status = "stale" if now_ms - last_success_ms > 5 * 60_000 else "ok"
        elif last_error:
            status = "error"
        else:
            status = "waiting"
        return {
            "status": status,
            "last_attempt_ms": last_attempt_ms,
            "last_success_ms": last_success_ms,
            "last_error": last_error,
        }

    def _mempool_health(self) -> dict[str, Any]:
        errors = dict(self.onchain.last_errors)
        if errors:
            status = "partial" if self._cached_onchain else "error"
            last_success_ms = self.onchain.last_success_ms
        elif self._cached_onchain:
            status = "ok"
            last_success_ms = self.onchain.last_success_ms or self._onchain_updated_ms or None
        else:
            status = "waiting"
            last_success_ms = None
        return {
            "status": status,
            "last_attempt_ms": self.onchain.last_attempt_ms or self._onchain_updated_ms or None,
            "last_success_ms": last_success_ms,
            "last_errors": errors,
        }

    def _binance_health(self) -> dict[str, Any]:
        status = dict(self.collector.status)
        state = str(status.get("state") or "idle")
        if state == "connected":
            health_status = "ok"
        elif state in {"connecting", "idle"}:
            health_status = "waiting"
        else:
            health_status = "error"
        return {
            "status": health_status,
            "state": state,
            "last_event_ms": status.get("last_event_ms"),
            "last_error": status.get("last_error"),
            "message": status.get("message"),
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
