# Data Confidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make dashboard numbers source-aware and add lightweight source health plus snapshot history.

**Architecture:** Keep the current local HTTP server and static frontend. Add focused Python helpers for liquidation view selection and snapshot history, then expose those fields through `/api/snapshot`.

**Tech Stack:** Python 3.11+, stdlib HTTP server, requests, aiohttp, Chart.js, unittest, ruff.

## Global Constraints

- Keep the app API-key free by default.
- Keep BTCUSDT as the default symbol.
- Do not add a database for this iteration.
- Keep generated runtime data under `data/`, which is ignored by git.
- Preserve current quick-start commands.

---

### Task 1: Liquidation Source Semantics

**Files:**
- Modify: `liquidation_pulse/external_liquidations.py`
- Test: `tests/test_external_liquidations.py`

**Interfaces:**
- Consumes: `LiquidationStore.snapshot()` dictionaries and CoinMarketCap snapshot dictionaries.
- Produces: `build_liquidation_view(live, external, now_ms)` returning source-aware liquidation payloads.

- [x] Write failing tests proving CMC and Binance are not double-counted by default.
- [x] Implement the liquidation view helper.
- [x] Keep an experimental combined value for comparison.
- [x] Run the focused tests.

### Task 2: Source Health

**Files:**
- Modify: `liquidation_pulse/external_liquidations.py`
- Modify: `liquidation_pulse/onchain.py`
- Modify: `liquidation_pulse/server.py`
- Test: `tests/test_external_liquidations.py`
- Test: `tests/test_onchain.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Produces: client `last_error` and `last_errors` fields.
- Produces: API top-level `health` object.

- [x] Write failing tests for client error tracking and server health fields.
- [x] Add error metadata to source clients.
- [x] Add health assembly in `DashboardState`.
- [x] Run focused tests.

### Task 3: Snapshot History

**Files:**
- Create: `liquidation_pulse/history.py`
- Modify: `liquidation_pulse/server.py`
- Test: `tests/test_history.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Produces: `SnapshotHistory.record(payload, now_ms)` and `SnapshotHistory.summary(now_ms)`.

- [x] Write failing tests for one-minute write throttling and recent point summaries.
- [x] Implement JSONL persistence under `data/snapshots.jsonl`.
- [x] Wire history into server snapshots.
- [x] Run focused tests.

### Task 4: Dashboard UI and Docs

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Modify: `README.md`

**Interfaces:**
- Consumes: `liquidations.basis`, `liquidations.live_collected`, `liquidations.external_24h`, `health`, and `history`.

- [x] Add source health labels to the dashboard.
- [x] Show the selected liquidation basis and separate live Binance amount.
- [x] Avoid unsafe HTML insertion for transaction rows.
- [x] Update README validation and feature notes.
- [x] Run full verification.
