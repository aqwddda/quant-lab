# Quant Lab Development Rules

This repository is a quantitative trading research project.

The current goal is NOT live trading.

The priorities, in order, are:

1. Correctness
2. Reproducibility
3. Auditability
4. Simplicity
5. Performance

Do not optimize strategy returns at the expense of correctness.

## Environment

The project uses Conda.

Environment name:

quant-lab

Python version:

3.11

Do not create another virtual environment unless explicitly requested.

Do not install unnecessary packages.

Before adding a dependency, explain why the standard library or existing dependency is insufficient.

## Architecture

Keep the following responsibilities separate.

### src/strategies/

Only calculate indicators and trading signals.

It must NOT:

- manage cash
- calculate portfolio equity
- simulate fills
- calculate commissions
- access future market data

### src/backtest/execution.py

Responsible for:

- order execution timing
- execution prices
- commissions
- slippage
- execution constraints

### src/backtest/portfolio.py

Responsible for:

- cash
- positions
- market value
- realized/unrealized PnL
- total equity

### src/backtest/engine.py

Responsible for driving the simulation chronologically.

### src/backtest/metrics.py

Responsible only for calculating performance metrics from completed backtest results.

### src/validation.py and src/data/validation.py

Responsible for:

- look-ahead checks
- future mutation tests
- robustness tests
- data validation

Do not merge these responsibilities into one large file.

## Time correctness

Time alignment is critical.

For the current strategy:

T day close data
→ calculate signal
→ signal becomes known after T close
→ execute at T+1 open

Never use T close to both generate the signal and simulate an execution at the same T close.

A trading decision at time T may only depend on information that was available at or before time T.

Forbidden inside strategy logic:

- shift(-1)
- future returns
- future high
- future low
- centered rolling windows
- future timestamps
- incorrectly aligned merges

If such operations are required for evaluation labels, they must be isolated from strategy inputs.

## Data

The data flow is:

Data Provider → Source Snapshot → Normalization → Validation → Frozen Store → Loader → Backtest.

Supplier responses are frozen under data/source/; canonical bars, adjustments and
corporate actions live under data/normalized/; instruments and calendars under
data/reference/; checksummed manifests under data/manifests/.
Current code only supports the formal UTC bar schema and schema_version=3 manifests.
Do not add readers, aliases or special price channels for retired schemas.
Existing frozen files must never be rewritten during source cleanup.

Source Data means the supplier snapshot, not unadjusted historical prices.
Raw Price means historical unadjusted OHLC. Adjustment semantics and units must be
explicit. Yahoo's split-adjusted source OHLC requires an explicit, audited inverse
split normalization before it is called raw.

Providers must never enter Strategy. Backtests and local loaders never access the
internet or download missing files. Downloading is a separate explicit action.
Every frozen version must have provenance, content hashes and a unique dataset ID.
Never silently choose between overlapping dataset versions.

Use Parquet where practical.

Do not silently alter historical data during a backtest.

Validate:

- duplicate timestamps
- sorting
- missing values
- impossible OHLC relationships
- timezone assumptions

## Testing

Use pytest.

Every important accounting operation must have deterministic tests.

At minimum maintain:

- tests/strategies/test_strategy.py
- tests/backtest/test_execution.py
- tests/backtest/test_accounting.py
- tests/backtest/test_no_lookahead.py

Before considering a task complete, run the relevant tests.

Never modify expected test values merely to make a failing implementation pass.

Determine whether the implementation or the expectation is incorrect.

## Future mutation test

Implement a future mutation test.

Procedure:

1. Calculate all signals through date T.
2. Modify all market data after T.
3. Recalculate signals.
4. Signals and indicators through T must remain identical.

If they change, treat this as a critical look-ahead bug.

## Trading costs

Always distinguish:

raw_open

execution_price

trade_value

commission

slippage_cost

Net strategy performance must include transaction costs.

## Outputs

Each completed backtest should output:

reports/trades.csv

reports/equity.csv

reports/metrics.json

reports/equity_curve.png

reports/drawdown.png

The trade log must provide sufficient detail to manually reproduce individual trades.

## Coding style

Prefer simple Python.

Do not introduce unnecessary:

- frameworks
- classes
- factories
- inheritance hierarchies
- abstractions

Use classes only when they materially improve state handling or clarity.

Prefer explicit calculations over hidden framework behavior.

Avoid premature optimization.

Use clear variable names.

Document important assumptions, especially time alignment and execution assumptions.

## Git

Make logically isolated changes.

Before major architectural changes, inspect the existing repository.

Do not overwrite working functionality without understanding it.

Keep generated data, reports, credentials and secrets out of Git.

## Current phase

The source lives directly under src/data/, src/market/, src/chan/,
src/strategies/ and src/backtest/. Imports use src.*.
Do not create another project-name package under src.
src/ itself is the project source root. Each capability has one implementation
and one import path; do not add old-entrypoint wrappers or module aliases.

Data supports current UTC bars, local Forex snapshots, multi-symbol reads,
provider snapshot normalization, immutable manifests and anchored resampling.
Daily supplier session dates may remain auxiliary adjustment/calendar keys;
canonical bars always include UTC timestamp and explicit timeframe semantics.
src.market.Instrument is the only canonical Instrument model. Yahoo/Tushare
normalization constructs it directly after raw supplier metadata is frozen.
Canonical instrument metadata lives in manifest["instruments"] and is validated
with Instrument(**item); do not add a second instrument table or schema.
Supplier name, listing/delisting dates and exchange codes remain source metadata.
Provider Base contains only generic capabilities and the BarProvider protocol.
Yahoo/Tushare remain Equity + D1; date-only request checks belong to
src/data/providers/_daily.py:check_daily_date_request.
LocalBarProvider explicitly imports Equity/Forex/Futures at 1m/5m/15m/30m/1h/4h/1d
using caller-supplied Instrument, timezone and timestamp semantics.
Chan-Core implements inclusion, strict fractals and strokes incrementally;
confirmed structures must never be rewritten. Undefined theory remains documented
as provisional defaults or explicit errors.
The Backtest Engine consumes Strategy/Execution protocols and remains single asset,
long or cash Equity accounting. Risk metrics use daily equity snapshots.
CN backtests are data pipeline smoke tests and must disclose missing A-share
execution rules. Corporate action events are stored but not applied to accounts.
Chan-FX is structure observation only; Forex spread, lot, leverage, margin, swap,
short and final trading rules are not defined. Do not invent them.

Do NOT implement:

- live trading
- broker integration
- leverage
- short selling
- machine learning
- optimization algorithms
- portfolio optimization
- live intraday trading

unless explicitly requested.

The purpose of this first strategy is to validate the research infrastructure, not to discover alpha.
