from __future__ import annotations

import unittest

from liquidation_pulse.onchain import build_onchain_snapshot


class OnchainSnapshotTest(unittest.TestCase):
    def test_builds_fee_pressure_and_large_transactions(self) -> None:
        snapshot = build_onchain_snapshot(
            fees={"fastestFee": 18, "halfHourFee": 12, "hourFee": 8, "economyFee": 3, "minimumFee": 1},
            recent=[
                {"txid": "small", "value": 100_000, "fee": 200, "vsize": 100},
                {"txid": "large", "value": 250_000_000, "fee": 5_000, "vsize": 200},
            ],
            mempool_blocks=[
                {"blockSize": 1_500_000, "nTx": 3200, "feeRange": [2, 5, 9]},
                {"blockSize": 900_000, "nTx": 1400, "feeRange": [1, 2, 3]},
            ],
        )

        self.assertEqual(snapshot["fees"]["fastest"], 18)
        self.assertEqual(snapshot["fee_pressure"], "elevated")
        self.assertEqual(snapshot["large_transactions"][0]["txid"], "large")
        self.assertEqual(snapshot["large_transactions"][0]["btc"], 2.5)
        self.assertEqual(snapshot["mempool_blocks"][0]["tx_count"], 3200)

    def test_handles_missing_network_data(self) -> None:
        snapshot = build_onchain_snapshot(fees={}, recent=[], mempool_blocks=[])

        self.assertEqual(snapshot["fees"]["fastest"], 0)
        self.assertEqual(snapshot["fee_pressure"], "quiet")
        self.assertEqual(snapshot["large_transactions"], [])
        self.assertEqual(snapshot["mempool_blocks"], [])


if __name__ == "__main__":
    unittest.main()
