from __future__ import annotations

import os
import re
import subprocess


def detect_proxy_url() -> str | None:
    for name in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy"):
        value = os.environ.get(name)
        if value:
            return value
    try:
        result = subprocess.run(
            ["scutil", "--proxy"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return parse_scutil_proxy(result.stdout)


def parse_scutil_proxy(output: str) -> str | None:
    values = dict(re.findall(r"^\s*([A-Z]+(?:Enable|Proxy|Port))\s*:\s*(.+?)\s*$", output, re.MULTILINE))
    https_proxy = _proxy_from_values(values, prefix="HTTPS")
    if https_proxy:
        return https_proxy
    return _proxy_from_values(values, prefix="HTTP")


def requests_proxies(proxy_url: str | None) -> dict[str, str] | None:
    if not proxy_url:
        return None
    return {"http": proxy_url, "https": proxy_url}


def _proxy_from_values(values: dict[str, str], prefix: str) -> str | None:
    if values.get(f"{prefix}Enable") != "1":
        return None
    host = values.get(f"{prefix}Proxy")
    port = values.get(f"{prefix}Port")
    if not host or not port:
        return None
    return f"http://{host}:{port}"
