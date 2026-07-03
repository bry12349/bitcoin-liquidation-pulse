from __future__ import annotations

from typing import Any

import requests

from liquidation_pulse.proxy import detect_proxy_url, requests_proxies

SATOSHIS_PER_BTC = 100_000_000
MEMPOOL_BASE_URL = "https://mempool.space/api"


def build_onchain_snapshot(
    fees: dict[str, Any],
    recent: list[dict[str, Any]],
    mempool_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    fee_summary = {
        "fastest": int(fees.get("fastestFee") or 0),
        "half_hour": int(fees.get("halfHourFee") or 0),
        "hour": int(fees.get("hourFee") or 0),
        "economy": int(fees.get("economyFee") or 0),
        "minimum": int(fees.get("minimumFee") or 0),
    }

    return {
        "fees": fee_summary,
        "fee_pressure": _fee_pressure(fee_summary["fastest"]),
        "large_transactions": _large_transactions(recent),
        "mempool_blocks": _mempool_blocks(mempool_blocks),
    }


class MempoolClient:
    def __init__(self, base_url: str = MEMPOOL_BASE_URL, timeout: float = 8.0, proxy_url: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.proxy_url = proxy_url if proxy_url is not None else detect_proxy_url()

    def snapshot(self) -> dict[str, Any]:
        fees = self._get_json("/v1/fees/recommended", {})
        recent = self._get_json("/mempool/recent", [])
        blocks = self._get_json("/v1/fees/mempool-blocks", [])
        return build_onchain_snapshot(fees=fees, recent=recent, mempool_blocks=blocks)

    def _get_json(self, path: str, fallback: Any) -> Any:
        try:
            response = requests.get(
                f"{self.base_url}{path}",
                proxies=requests_proxies(self.proxy_url),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return fallback


def _fee_pressure(fastest_fee: int) -> str:
    if fastest_fee >= 50:
        return "hot"
    if fastest_fee >= 10:
        return "elevated"
    return "quiet"


def _large_transactions(recent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    large = []
    for item in recent:
        value_sat = int(item.get("value") or 0)
        if value_sat < 100_000_000:
            continue
        large.append(
            {
                "txid": str(item.get("txid", "")),
                "btc": round(value_sat / SATOSHIS_PER_BTC, 4),
                "fee_sat": int(item.get("fee") or 0),
                "vsize": int(item.get("vsize") or 0),
            }
        )
    return sorted(large, key=lambda tx: tx["btc"], reverse=True)[:8]


def _mempool_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for index, block in enumerate(blocks[:6], start=1):
        fee_range = block.get("feeRange") or []
        normalized.append(
            {
                "index": index,
                "size_mb": round(float(block.get("blockSize") or 0) / 1_000_000, 2),
                "tx_count": int(block.get("nTx") or 0),
                "min_fee": int(min(fee_range)) if fee_range else 0,
                "max_fee": int(max(fee_range)) if fee_range else 0,
            }
        )
    return normalized
