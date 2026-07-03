from __future__ import annotations

import unittest

from liquidation_pulse.proxy import parse_scutil_proxy


class ProxyDetectionTest(unittest.TestCase):
    def test_parse_scutil_proxy_prefers_https_proxy(self) -> None:
        output = """
<dictionary> {
  HTTPEnable : 1
  HTTPPort : 7891
  HTTPProxy : 127.0.0.1
  HTTPSEnable : 1
  HTTPSPort : 7890
  HTTPSProxy : 127.0.0.1
  SOCKSEnable : 1
  SOCKSPort : 7892
  SOCKSProxy : 127.0.0.1
}
"""

        self.assertEqual(parse_scutil_proxy(output), "http://127.0.0.1:7890")

    def test_parse_scutil_proxy_falls_back_to_http_proxy(self) -> None:
        output = """
<dictionary> {
  HTTPEnable : 1
  HTTPPort : 7890
  HTTPProxy : 127.0.0.1
  HTTPSEnable : 0
}
"""

        self.assertEqual(parse_scutil_proxy(output), "http://127.0.0.1:7890")

    def test_parse_scutil_proxy_returns_none_when_disabled(self) -> None:
        self.assertIsNone(parse_scutil_proxy("<dictionary> { HTTPEnable : 0 HTTPSEnable : 0 }"))


if __name__ == "__main__":
    unittest.main()
