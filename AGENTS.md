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

### strategy.py

Only calculate indicators and trading signals.

It must NOT:

- manage cash
- calculate portfolio equity
- simulate fills
- calculate commissions
- access future market data

### execution.py

Responsible for:

- order execution timing
- execution prices
- commissions
- slippage
- execution constraints

### portfolio.py

Responsible for:

- cash
- positions
- market value
- realized/unrealized PnL
- total equity

### backtest.py

Responsible for driving the simulation chronologically.

### metrics.py

Responsible only for calculating performance metrics from completed backtest results.

### validation.py

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

Raw downloaded market data must be stored under:

data/raw/

Once downloaded for an experiment, backtests should read the frozen local dataset instead of downloading it again.

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

- test_strategy.py
- test_execution.py
- test_accounting.py
- test_no_lookahead.py

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

The current phase is only:

SPY
daily bars
20-day / 60-day moving average
long or cash
T close signal
T+1 open execution

Do NOT implement:

- live trading
- broker integration
- leverage
- short selling
- machine learning
- optimization algorithms
- portfolio optimization
- intraday trading

unless explicitly requested.

The purpose of this first strategy is to validate the research infrastructure, not to discover alpha.
