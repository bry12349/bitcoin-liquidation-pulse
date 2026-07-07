from __future__ import annotations

import time
from typing import Any

import requests

from liquidation_pulse.proxy import detect_proxy_url, requests_proxies

CMC_BASE_URL = "https://api.coinmarketcap.com"


class CoinMarketCapLiquidationClient:
    def __init__(self, base_url: str = CMC_BASE_URL, timeout: float = 10.0, proxy_url: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.proxy_url = proxy_url if proxy_url is not None else detect_proxy_url()
        self.last_attempt_ms: int | None = None
        self.last_success_ms: int | None = None
        self.last_error: str | None = None

    def btc_24h_snapshot(self) -> dict[str, Any] | None:
        updated_at_ms = int(time.time() * 1000)
        self.last_attempt_ms = updated_at_ms
        try:
            response = requests.get(
                f"{self.base_url}/data-api/v3/liquidations/table",
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://coinmarketcap.com/charts/liquidations/",
                },
                params={
                    "page": 1,
                    "pageSize": 100,
                    "sort": "totalLiquidations1d",
                    "ascendingOrder": "false",
                    "interval": "1d",
                },
                proxies=requests_proxies(self.proxy_url),
                timeout=self.timeout,
            )
            response.raise_for_status()
            snapshot = build_cmc_btc_snapshot(response.json(), updated_at_ms=updated_at_ms)
        except (requests.RequestException, ValueError) as exc:
            self.last_error = str(exc)
            return None
        if not snapshot:
            self.last_error = "BTC liquidation row not found"
            return None
        self.last_success_ms = updated_at_ms
        self.last_error = None
        return snapshot


def build_cmc_btc_snapshot(payload: dict[str, Any], updated_at_ms: int) -> dict[str, Any] | None:
    items = payload.get("data", {}).get("items", [])
    for item in items:
        if item.get("symbol") != "BTC":
            continue
        long_usd = round(float(item.get("longLiquidations") or 0), 2)
        short_usd = round(float(item.get("shortLiquidations") or 0), 2)
        total_usd = round(float(item.get("totalLiquidations") or long_usd + short_usd), 2)
        return {
            "source": "CoinMarketCap 24h liquidation table",
            "updated_at_ms": updated_at_ms,
            "long_usd": long_usd,
            "short_usd": short_usd,
            "total_usd": total_usd,
            "open_interest_usd": round(float(item.get("openInterestUsd") or 0), 2),
        }
    return None


def merge_liquidation_snapshots(live: dict[str, Any], external: dict[str, Any] | None) -> dict[str, Any]:
    if not external:
        return live

    live_long = float(live.get("long", {}).get("usd") or 0)
    live_short = float(live.get("short", {}).get("usd") or 0)
    long_usd = round(float(external["long_usd"]) + live_long, 2)
    short_usd = round(float(external["short_usd"]) + live_short, 2)
    total_usd = round(long_usd + short_usd, 2)

    merged = dict(live)
    merged["coverage"] = {
        "label": "CMC 24h snapshot + Binance live",
        "minutes": live.get("coverage", {}).get("minutes", 0),
    }
    merged["long"] = {**live.get("long", {}), "usd": long_usd}
    merged["short"] = {**live.get("short", {}), "usd": short_usd}
    merged["total_usd"] = total_usd
    merged["net_usd"] = round(short_usd - long_usd, 2)
    merged["net_bias"] = _net_bias(long_usd, short_usd)
    merged["external_24h"] = external

    if live_long == 0 and live_short == 0 and merged.get("hourly"):
        hourly = [dict(bucket) for bucket in merged["hourly"]]
        hourly[-1] = {**hourly[-1], "label": "24h", "long_usd": long_usd, "short_usd": short_usd}
        merged["hourly"] = hourly

    return merged


def build_liquidation_view(live: dict[str, Any], external: dict[str, Any] | None, now_ms: int) -> dict[str, Any]:
    if not external:
        view = dict(live)
        view["basis"] = "live_collected"
        view["basis_label"] = "Binance live collected"
        view["live_collected"] = live
        view["external_24h"] = None
        view["combined_experimental"] = None
        view["source_note"] = "CoinMarketCap 24h snapshot unavailable; headline uses locally collected Binance events."
        return view

    live_long = float(live.get("long", {}).get("usd") or 0)
    live_short = float(live.get("short", {}).get("usd") or 0)
    live_total = float(live.get("total_usd") or 0)
    long_usd = round(float(external["long_usd"]), 2)
    short_usd = round(float(external["short_usd"]), 2)
    total_usd = round(float(external.get("total_usd") or long_usd + short_usd), 2)

    view = dict(live)
    view["basis"] = "external_24h"
    view["basis_label"] = "CoinMarketCap 24h"
    view["window"] = "external_24h_market_snapshot"
    view["coverage"] = {
        "label": "CMC 24h snapshot; Binance live tracked separately",
        "minutes": live.get("coverage", {}).get("minutes", 0),
    }
    view["long"] = {**live.get("long", {}), "usd": long_usd}
    view["short"] = {**live.get("short", {}), "usd": short_usd}
    view["total_usd"] = total_usd
    view["net_usd"] = round(short_usd - long_usd, 2)
    view["net_bias"] = _net_bias(long_usd, short_usd)
    view["external_24h"] = {
        **external,
        "age_ms": max(0, now_ms - int(external.get("updated_at_ms") or now_ms)),
    }
    view["live_collected"] = live
    view["combined_experimental"] = {
        "long_usd": round(long_usd + live_long, 2),
        "short_usd": round(short_usd + live_short, 2),
        "total_usd": round(total_usd + live_total, 2),
        "net_usd": round((short_usd + live_short) - (long_usd + live_long), 2),
        "net_bias": _net_bias(long_usd + live_long, short_usd + live_short),
        "overlap_risk": True,
        "note": "Experimental only; may double count exchange activity already included in the CMC snapshot.",
    }
    view["source_note"] = "Headline uses CMC 24h. Binance live events are shown separately to avoid default double counting."

    if live_total == 0 and view.get("hourly"):
        hourly = [dict(bucket) for bucket in view["hourly"]]
        hourly[-1] = {**hourly[-1], "label": "CMC 24h", "long_usd": long_usd, "short_usd": short_usd}
        view["hourly"] = hourly

    return view


def _net_bias(long_usd: float, short_usd: float) -> str:
    if long_usd == 0 and short_usd == 0:
        return "neutral"
    if short_usd > long_usd * 1.15:
        return "shorts squeezed"
    if long_usd > short_usd * 1.15:
        return "longs flushed"
    return "balanced"
