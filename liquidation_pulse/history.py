from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import threading
from typing import Any


class SnapshotHistory:
    def __init__(self, path: Path, max_points: int = 240, min_interval_ms: int = 60_000) -> None:
        self.path = path
        self.max_points = max_points
        self.min_interval_ms = min_interval_ms
        self._lock = threading.RLock()
        self._points: deque[dict[str, Any]] = deque(maxlen=max_points)
        self._last_record_ms: int | None = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def record(self, payload: dict[str, Any], now_ms: int) -> bool:
        with self._lock:
            if self._last_record_ms is not None and now_ms - self._last_record_ms < self.min_interval_ms:
                return False
            point = self._point_from_payload(payload, now_ms)
            self._points.append(point)
            self._last_record_ms = now_ms
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(point, ensure_ascii=True) + "\n")
            return True

    def summary(self) -> dict[str, Any]:
        with self._lock:
            points = list(self._points)
        return {
            "count": len(points),
            "points": points,
        }

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    point = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(point, dict):
                    self._points.append(point)
                    self._last_record_ms = int(point.get("timestamp_ms") or 0)

    @staticmethod
    def _point_from_payload(payload: dict[str, Any], now_ms: int) -> dict[str, Any]:
        liquidations = payload.get("liquidations") or {}
        onchain = payload.get("onchain") or {}
        fees = onchain.get("fees") or {}
        long_usd = float((liquidations.get("long") or {}).get("usd") or 0)
        short_usd = float((liquidations.get("short") or {}).get("usd") or 0)
        return {
            "timestamp_ms": int(payload.get("generated_at_ms") or now_ms),
            "basis": str(liquidations.get("basis") or "unknown"),
            "long_usd": round(long_usd, 2),
            "short_usd": round(short_usd, 2),
            "total_usd": round(float(liquidations.get("total_usd") or long_usd + short_usd), 2),
            "net_usd": round(float(liquidations.get("net_usd") or short_usd - long_usd), 2),
            "fee_fastest": int(fees.get("fastest") or 0),
            "fee_pressure": str(onchain.get("fee_pressure") or "quiet"),
        }
