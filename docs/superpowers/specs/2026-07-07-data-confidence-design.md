# Data Confidence Design

## Context

Bitcoin Liquidation Pulse currently merges the CoinMarketCap 24h liquidation snapshot with locally collected Binance force-order events. This makes the dashboard visually useful, but it can overstate totals because the CoinMarketCap value may already include Binance or similar exchange activity.

The next iteration should make data provenance explicit without changing the project into a larger platform.

## Selected Approach

Use CoinMarketCap as the primary 24h market snapshot when available, keep Binance live collection as a separate local stream, and expose any combined number as experimental metadata only. This preserves the current no-API-key product shape while removing the misleading default merge.

Alternative approaches considered:

- Keep the current merged total and add a warning. This is the least disruptive, but it leaves the main KPI semantically weak.
- Remove CoinMarketCap and rely only on Binance live events. This is clean, but the dashboard loses useful 24h context after startup.
- Add paid or authenticated data vendors now. This may be useful later, but it is premature for the local default path.

## Architecture

The server remains a small local HTTP server. `DashboardState` continues to own source clients, short caches, and snapshot assembly.

The liquidation response gains explicit sections:

- `external_24h`: CoinMarketCap BTC 24h snapshot, when available.
- `live_collected`: locally collected Binance force-order window.
- `combined_experimental`: optional sum for comparison only.
- `basis`: the source used for headline KPIs.

Top-level liquidation KPI fields remain available for frontend compatibility, but they use the selected `basis` rather than blindly adding sources together.

## Source Health

The API should include a top-level `health` object:

- `cmc`: status, last attempt, last success, and last error.
- `mempool`: status, last attempt, last success, and endpoint errors.
- `binance`: collector state, last event, and last error.

The UI should surface these statuses as compact labels so users can see whether data is current, stale, partial, or unavailable.

## Snapshot History

The server should append a compact dashboard snapshot at most once per minute to `data/snapshots.jsonl`. The file is ignored by git. The API should return a small recent history payload for future trend charts.

Each history point stores:

- timestamp
- liquidation basis
- long, short, total, and net USD
- fastest fee
- fee pressure

## Error Handling

External data failures must not crash the dashboard. Failed sources keep the last successful cached values where available and expose source health so the UI can explain stale data.

## Testing

Tests should cover:

- liquidation source selection does not double count CMC and Binance by default
- the experimental combined value remains available
- source clients expose failure details
- snapshot history rate-limits writes and returns recent points
- server snapshots include `health` and `history`
