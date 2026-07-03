from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import threading
import time
from typing import Any

WINDOW_MS = 24 * 60 * 60 * 1000
HOUR_MS = 60 * 60 * 1000


@dataclass(frozen=True)
class LiquidationEvent:
    timestamp_ms: int
    symbol: str
    side: str
    liquidation_side: str
    price: float
    quantity: float
    usd: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_ms": self.timestamp_ms,
            "symbol": self.symbol,
            "side": self.side,
            "liquidation_side": self.liquidation_side,
            "price": self.price,
            "quantity": self.quantity,
            "usd": self.usd,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LiquidationEvent:
        return cls(
            timestamp_ms=int(data["timestamp_ms"]),
            symbol=str(data["symbol"]),
            side=str(data["side"]),
            liquidation_side=str(data["liquidation_side"]),
            price=float(data["price"]),
            quantity=float(data["quantity"]),
            usd=float(data["usd"]),
        )


class LiquidationStore:
    def __init__(self, persist_path: Path | None = None) -> None:
        self._events: list[LiquidationEvent] = []
        self._lock = threading.RLock()
        self._persist_path = persist_path
        if persist_path:
            persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_persisted_events()

    def add_binance_force_order(self, payload: dict[str, Any]) -> LiquidationEvent | None:
        order = payload.get("o") or {}
        symbol = str(order.get("s", ""))
        if symbol != "BTCUSDT":
            return None

        side = str(order.get("S", "")).upper()
        if side not in {"BUY", "SELL"}:
            return None

        try:
            price = float(order["p"])
            quantity = float(order["q"])
        except (KeyError, TypeError, ValueError):
            return None

        timestamp_ms = int(payload.get("E") or int(time.time() * 1000))
        liquidation_side = "long" if side == "SELL" else "short"
        event = LiquidationEvent(
            timestamp_ms=timestamp_ms,
            symbol=symbol,
            side=side,
            liquidation_side=liquidation_side,
            price=price,
            quantity=quantity,
            usd=round(price * quantity, 2),
        )

        with self._lock:
            self._events.append(event)
            self._prune_locked(timestamp_ms)
            self._append_event(event)
        return event

    def snapshot(self, now_ms: int | None = None) -> dict[str, Any]:
        now_ms = now_ms or int(time.time() * 1000)
        with self._lock:
            self._prune_locked(now_ms)
            events = list(self._events)

        long_events = [event for event in events if event.liquidation_side == "long"]
        short_events = [event for event in events if event.liquidation_side == "short"]
        long_usd = round(sum(event.usd for event in long_events), 2)
        short_usd = round(sum(event.usd for event in short_events), 2)

        return {
            "window": "rolling_24h_from_collected_data",
            "coverage": self._coverage(events, now_ms),
            "long": {"usd": long_usd, "count": len(long_events)},
            "short": {"usd": short_usd, "count": len(short_events)},
            "total_usd": round(long_usd + short_usd, 2),
            "net_usd": round(short_usd - long_usd, 2),
            "net_bias": self._net_bias(long_usd, short_usd),
            "hourly": self._hourly(events, now_ms),
            "recent": [event.to_dict() for event in sorted(events, key=lambda item: item.timestamp_ms)[-12:]],
        }

    def _coverage(self, events: list[LiquidationEvent], now_ms: int) -> dict[str, Any]:
        if not events:
            return {"label": "waiting for Binance liquidation stream", "minutes": 0}
        first_ms = min(event.timestamp_ms for event in events)
        minutes = max(0, round((now_ms - first_ms) / 60_000))
        label = "rolling 24h" if minutes >= 1440 else f"collected {minutes} min"
        return {"label": label, "minutes": minutes}

    def _hourly(self, events: list[LiquidationEvent], now_ms: int) -> list[dict[str, Any]]:
        end_ms = ((now_ms // HOUR_MS) + 1) * HOUR_MS
        start_ms = end_ms - WINDOW_MS
        buckets: list[dict[str, Any]] = []
        for index in range(24):
            bucket_start = start_ms + index * HOUR_MS
            bucket_end = bucket_start + HOUR_MS
            if index == 23 and now_ms == bucket_end:
                bucket_events = [event for event in events if bucket_start <= event.timestamp_ms <= bucket_end]
            else:
                bucket_events = [event for event in events if bucket_start <= event.timestamp_ms < bucket_end]
            buckets.append(
                {
                    "timestamp_ms": bucket_start,
                    "label": time.strftime("%H:%M", time.localtime(bucket_start / 1000)),
                    "long_usd": round(
                        sum(event.usd for event in bucket_events if event.liquidation_side == "long"),
                        2,
                    ),
                    "short_usd": round(
                        sum(event.usd for event in bucket_events if event.liquidation_side == "short"),
                        2,
                    ),
                    "count": len(bucket_events),
                }
            )
        return buckets

    def _prune_locked(self, now_ms: int) -> None:
        cutoff = now_ms - WINDOW_MS
        self._events = [event for event in self._events if event.timestamp_ms >= cutoff]

    def _append_event(self, event: LiquidationEvent) -> None:
        if not self._persist_path:
            return
        with self._persist_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=True) + "\n")

    def _load_persisted_events(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        now_ms = int(time.time() * 1000)
        with self._persist_path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    event = LiquidationEvent.from_dict(json.loads(line))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    continue
                if event.timestamp_ms >= now_ms - WINDOW_MS:
                    self._events.append(event)

    @staticmethod
    def _net_bias(long_usd: float, short_usd: float) -> str:
        if long_usd == 0 and short_usd == 0:
            return "neutral"
        if short_usd > long_usd * 1.15:
            return "shorts squeezed"
        if long_usd > short_usd * 1.15:
            return "longs flushed"
        return "balanced"
