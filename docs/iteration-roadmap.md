# Bitcoin Liquidation Pulse Iteration Roadmap

This roadmap keeps the project focused as a local BTC market intelligence dashboard.

## Version 0.2: Data Confidence

Goal: make every headline number explain where it came from and whether it is fresh.

- Separate CoinMarketCap 24h liquidation totals from locally collected Binance force-order events.
- Keep an experimental combined value, but do not use it as the default headline metric.
- Add source health for CoinMarketCap, Binance, and mempool.space.
- Record lightweight one-minute dashboard snapshots for trend reconstruction.
- Show data freshness and source labels in the dashboard.

## Version 0.3: Alerting

Goal: turn the dashboard from passive monitoring into actionable local alerts.

- Add configurable thresholds for liquidation spikes, long/short skew, fee pressure, and stale sources.
- Add browser notifications and optional sound alerts.
- Add an alert history panel so users can review what triggered recently.
- Keep all alert rules local and API-key free by default.

## Version 0.4: Trend Analytics

Goal: expose meaningful short-horizon market context from the stored snapshots.

- Add 5-minute, 1-hour, 4-hour, and 24-hour change metrics.
- Add liquidation velocity and skew trend indicators.
- Add fee-pressure trend and mempool block backlog trend.
- Add simple anomaly labels for unusually large changes.

## Version 0.5: Runtime Hardening

Goal: make the app more resilient during long local sessions.

- Move blocking external fetches out of the request path.
- Use a threaded or async server model.
- Add graceful collector shutdown.
- Add structured logs for source failures and reconnects.
- Add a health endpoint for local diagnostics.

## Version 0.6: Source Expansion

Goal: improve market coverage without making the default path fragile.

- Add optional additional liquidation sources such as Coinglass or exchange-specific feeds.
- Add config for symbol selection while keeping BTCUSDT as the default.
- Add source-specific attribution and deduplication rules.
- Keep the no-API-key default mode available.
