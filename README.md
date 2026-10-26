# Trading Research and Execution Platform

A modular platform for researching user-defined strategies, testing them against historical and forward data, paper trading, and (only after explicit configuration and risk checks) routing orders through supported brokers.

The initial goal is a reliable research and paper-trading system. Live trading is a separately enabled capability, not an automatic extension of a backtest. This project is not investment advice and does not promise returns.

## Product Scope

- User profiles, watchlists, portfolios, broker connections, and configurable trading charges.
- Market and instrument coverage for Indian equities and exchange-listed derivatives, plus selected gold, BTC, ETH, and other crypto instruments where lawful and supported by a licensed data or execution provider.
- A scanner and strategy engine that produces timestamped entry, exit, sizing, and risk plans with explanations.
- Independent and combined strategy evaluation, historical backtests, out-of-sample/forward tests, and paper trading.
- Order submission, status tracking, fills, positions, and reconciliation through broker adapters.
- A dashboard for user, instruments, data freshness, strategy runs, trades, and performance.

“Entire stock universe” should mean the current supported instruments from a maintained exchange/broker instrument master, not a hard-coded list. Coverage, historical depth, derivatives availability, and data rights vary by provider and must be visible in the UI.

## Recommended Architecture

Start with a **Python modular monolith**. It keeps domain logic testable and deployable as one application while leaving clear boundaries to split out high-volume data ingestion or execution later. Do not start with microservices: they add operational complexity before there is enough traffic to justify it.

```text
Browser UI
		| HTTPS / WebSocket
FastAPI application
		|-- Identity, portfolios, settings
		|-- Instruments and market-data API
		|-- Strategy registry and run coordinator
		|-- Backtest / forward-test / paper-trading engine
		|-- Risk manager and order service
		|-- Broker and data-provider adapters
		|
		+-- PostgreSQL: users, configs, runs, orders, fills, positions
		+-- Redis: cache, short-lived state, job queue (optional initially)
		+-- Object storage: immutable market-data and run artifacts
		+-- Background workers: ingestion, scans, tests, reconciliation
```

### Suggested stack

- **UI:** React + TypeScript (Vite) for a responsive dashboard; use WebSockets or server-sent events for live status updates.
- **API and domain:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic.
- **Research:** pandas/NumPy for initial analysis; use a mature event-driven backtesting library if its fill, corporate-action, and instrument models meet the requirements. Keep the platform's strategy and risk contracts independent of the chosen library.
- **Persistence:** PostgreSQL as the system of record. Store large immutable OHLCV/tick files and test artifacts in object storage. Add a time-series database only after measured query volume requires it.
- **Jobs:** Begin with a database-backed job runner or a Redis-backed queue for long backtests and ingestion. Jobs must be restartable and idempotent.
- **Packaging:** Docker Compose for local development. Pin dependencies and use reproducible lockfiles.

## Core Boundaries

### Market data and instruments

Define provider interfaces for instrument master, historical bars, quotes, and streaming updates. Normalize all provider responses into canonical instruments and timestamped events. Persist source, exchange timezone, event time, receive time, interval, adjustment status, and data-quality flags. Detect gaps, duplicates, stale quotes, and out-of-order events.

Use official exchange or broker instrument files and provider APIs where available. “Open source” client libraries do not make the underlying market data free to use or redistribute. Confirm licensing, rate limits, retention, and commercial-use terms. Free tiers are useful for development, but should not be assumed to provide complete, real-time, exchange-authorized data.

### Strategies and evaluation

Give every strategy a versioned contract with declared instruments/timeframes, parameters, warm-up needs, and deterministic signal generation. A strategy emits proposed intents; it never places orders directly.

Support two modes:

- **Built-in strategies:** reviewed Python modules implementing the stable strategy interface.
- **User strategies:** initially a constrained configuration/DSL or reviewed uploads. Do not execute arbitrary user Python inside the API process. If arbitrary code is added later, run it in a resource-limited, isolated worker with no broker credentials or network access.

For a combined portfolio, define and document capital allocation, signal conflicts, duplicate exposure, and risk aggregation. Run each strategy independently and in the combined portfolio over the same dataset and assumptions; do not combine reported results by simply adding strategy returns.

Backtests should model point-in-time data, corporate actions, survivorship bias, exchange calendars, lot sizes, tick sizes, order types, partial fills, slippage, and rejected orders where applicable. Separate training, validation, and untouched test periods. Record the exact data snapshot, strategy version, parameters, fees, and execution assumptions with every run so results are reproducible.

Forward testing uses only data available at each decision time and must not leak future bars. Paper trading uses the same signal, risk, and order lifecycle as live trading, but a simulated fill adapter. Clearly distinguish simulated fills from broker-confirmed fills.

### Charges and performance

Make charges configurable by market, product, side, and order/fill as applicable. The proposed ₹20 per trade can be a user-editable default, not a universal fee assumption. Support brokerage, exchange/transaction charges, taxes, slippage, and other relevant costs as separately named fields. Show gross and net P&L and retain the exact fee schedule used for each run.

### Risk and execution

Route all proposed intents through one risk manager before they reach an execution adapter. Start with configurable limits for order quantity/value, per-instrument and portfolio exposure, daily loss, open positions, and stale data. Reject by default when account state, market data, or risk checks are unavailable.

The order lifecycle should explicitly represent `proposed`, `approved`, `submitted`, `partially_filled`, `filled`, `cancel_pending`, `cancelled`, `rejected`, and `unknown`. Use idempotency keys, broker order IDs, retry-safe reconciliation, and an audit log. Do not equate a successful HTTP response with a fill.

Live trading safeguards:

- Paper trading is the default; live mode requires an explicit per-account opt-in and a visible environment indicator.
- Require a human confirmation for initial live orders and provide a global kill switch that blocks new orders.
- Keep broker credentials in a secret manager/environment configuration, never in source control, browser storage, logs, or backtest workers.
- Use least-privilege broker permissions, short-lived tokens where supported, and a documented credential rotation process.
- Reconcile orders, fills, cash, and positions against the broker; alert on mismatches and unknown order states.
- Never silently retry an uncertain order submission. Query broker state first to avoid duplicate orders.

Broker integrations must use supported broker APIs and comply with the broker's terms and applicable Indian regulations. Before enabling live automated execution, verify current SEBI/exchange/broker requirements with qualified compliance counsel. The software architecture cannot determine regulatory eligibility.

## UI Areas

- **Overview:** account/equity summary, open positions, data freshness, run health, and prominent paper/live mode.
- **Instruments:** searchable universe, exchange/asset filters, watchlists, contract details, and availability indicators.
- **Strategy Lab:** create/version strategies, configure parameters and fees, launch independent or combined tests, and compare results.
- **Results:** equity curve, drawdown, trades, exposure, benchmark comparison, costs, assumptions, and downloadable run artifacts.
- **Paper Trading:** simulated orders, positions, fills, and event history.
- **Orders:** broker order states, filters, reconciliation status, and cancel controls where supported.
- **Settings:** profile, broker connections, risk limits, fee schedules, and data-provider configuration.

Do not display a single performance number without its period, market, benchmark, costs, and test type. Label delayed, simulated, stale, and live data distinctly.

## Repository Layout

```text
apps/
	api/                  # FastAPI application and domain modules
	web/                  # React dashboard
workers/
	market_data/          # Provider ingestion and normalization
	jobs/                 # Backtests, scans, paper trading, reconciliation
packages/
	strategy_sdk/         # Strategy contracts and built-in strategies
	trading_core/         # Instruments, portfolio, risk, orders, accounting
	providers/            # Data and broker adapter interfaces/implementations
tests/
	unit/
	integration/
	fixtures/
docs/
	architecture.md
	operations.md
	strategies/
```

Keep broker-specific behavior in adapters and keep strategy documentation beside each strategy. Each strategy document should include its hypothesis, instruments/timeframes, parameters, entry/exit rules, sizing, risk assumptions, costs, known failure modes, and reproducible test configuration. Documentation describes behavior; it is not a claim that a strategy is profitable.

## Phased Delivery Plan

Each phase should have a working demo and passing acceptance checks before the next phase starts. Live orders are explicitly out of scope until the live-trading release gate.

1. **Scope and guardrails:** begin with Indian listed cash equities, paper/research only, and one exchange segment (recommended: NSE cash equities). Define supported symbols, session calendar, strategy fields, risk limits, and data-use requirements. Record broker API availability, permissions, pricing, and terms for Kite (Zerodha), Dhan, and Mirae Asset; do not assume their APIs have identical capabilities.
	**Exit:** scope and acceptance criteria are documented; no broker secrets or live-order code are required.
2. **Codespaces foundation:** add a reproducible devcontainer, pinned Python/Node toolchains, local database, mock market data, and GitHub Actions for lint, tests, and builds. Keep the first release small; only add services when a feature needs them.
	**Exit:** a fresh Codespace starts the app and all CI checks pass without paid market data or broker credentials.
3. **Strategy intake utility:** let the user define a strategy's name, cash-equity universe, timeframe, entry/exit notes, trade style, risk, position count, costs, and test dates. Save locally and export a versioned JSON definition. Treat user-entered rule text as documentation until a later phase gives it a typed, testable representation.
	**Exit:** invalid values are rejected, saved definitions reload, and JSON export round-trips; no order or performance claim is generated.
4. **Instrument and market data:** implement a canonical Indian equity instrument master and one licensed historical-data adapter, with deterministic fixtures for development. Add freshness, gap, duplicate, and adjustment checks. Add real-time data only after source rights and reliability are confirmed.
	**Exit:** instrument IDs map consistently; historical data has documented provenance and passes quality checks.
5. **Strategy runtime and backtesting:** define a typed strategy interface, implement one user-approved first strategy, and evaluate it with point-in-time data, corporate actions, slippage, configurable charges, and reproducible assumptions. Use separate in-sample, validation, and untouched out-of-sample periods.
	**Exit:** deterministic tests cover signals and accounting; results include trades, costs, drawdown, exposure, and data/strategy versions.
6. **Multi-strategy and forward evaluation:** run strategies independently and as a portfolio with explicit capital allocation, signal conflict handling, and aggregate risk rules. Add walk-forward/forward tests and comparison reports.
	**Exit:** combined results are produced by shared portfolio accounting, not by adding strategy returns, and future data cannot leak into decisions.
7. **Paper trading:** use the same strategy, risk, and order lifecycle as live mode with a simulated execution adapter. Add streaming/polling, restart recovery, event history, and simulated-vs-live labels.
	**Exit:** repeatable end-to-end paper sessions survive worker restarts and accurately track simulated orders, fills, cash, and positions.
8. **One broker at a time:** compare official APIs for Kite, Dhan, and Mirae, choose one based on documented access, order types, auth, costs, and support. First add read-only account sync; then manually approved orders behind risk checks, idempotency, reconciliation, and a kill switch. Add other brokers only through independent adapters and capability tests.
	**Exit:** broker sandbox/controlled tests and operational review pass; live mode remains disabled by default. Confirm current legal, exchange, and broker requirements before automated live execution.
9. **Expand and operate:** add BSE coverage, broader universe, and additional products only when data, accounting, and risk models support them. Options, crypto, and other asset classes are separate projects/phases, not a checkbox on the equity MVP. Add monitoring, backups, alerts, incident runbooks, and an always-on deployment before any unattended live use.
	**Exit:** each new asset/product has its own acceptance suite and documented operational owner.

Free Codespaces and CI are for development and tests, not reliable real-time execution. Keep live trading disabled in CI and ephemeral preview deployments. A deployment gate should require durable storage, monitoring, recovery procedures, restricted secrets, and an accountable operator.

## Development and CI

Use GitHub Codespaces as the primary editor with a checked-in `.devcontainer` that installs pinned Python and Node versions, project dependencies, and PostgreSQL for local development. Keep secrets out of Codespaces configuration unless they are required for an explicitly chosen sandbox integration; use mock providers for normal development.

GitHub Actions should run on pull requests and pushes:

- Python formatting/linting, type checks, and unit tests.
- Frontend linting, type checking, and tests/build.
- Integration tests against disposable PostgreSQL and deterministic mock data/brokers.
- Dependency and secret scanning.
- Build and publish an immutable container image after checks pass.

Free CI and developer environments are appropriate for tests and demos, not dependable real-time execution. Codespaces are temporary development environments; free hosting may sleep, restart, limit networking, or lack persistent storage. Keep live execution disabled in CI and ephemeral preview deployments. If live trading is eventually approved, deploy the execution worker to an always-on, monitored environment with durable storage, backups, restricted network access, and an operational owner. Treat free tiers as a cost constraint to validate, not a reliability guarantee.

## Current Local Prototype

The current prototype serves the strategy builder and backtest engine from `server.py` and stores OHLCV rows in a local SQLite database at `data/market_data.db`. On first launch, it seeds deterministic `demo-seed` rows for RELIANCE, TCS, and INFY. These are generated test fixtures, not actual historical exchange prices. The database file is local runtime state and is intentionally not committed.

Run it from the repository root with:

```sh
python3 server.py
```

Open `http://localhost:8001/` for the strategy builder. Save a strategy and choose “Run sample backtest” to load database rows via `/api/ohlcv`. The strategy definition remains in browser storage. The backtest is a prototype and must not be used to infer real-world strategy performance.

`market_data_service.py` currently defines placeholders only: no open-source historical provider download or Kite, Dhan, or Mirae realtime integration is implemented. Until those adapters are added and verified, database contents remain seeded demo data; do not describe them as live, broker-sourced, or actual historical prices.

## Decisions Before Data Integration

Confirm NSE-only or NSE+BSE for the first universe, choose a licensed historical-data source, and clarify the intended initial strategy and timeframe. Separately verify current official API availability and terms for Kite, Dhan, and Mirae before selecting the first broker adapter. Keep the first release research/paper-only.