# Quant Lab：可审计的日线研究基础工程

当前数据层支持 US/CN 多标的数据管理；交易引擎仍是单资产日线 SMA20/SMA60、long/cash、T 收盘信号、T+1 开盘成交。执行和记账不建模完整 A 股规则；A 股回测仅用于数据链路 smoke test。

熟悉 Python 但刚接触量化研究的读者，可阅读 [项目教程](docs/项目教程.md)。该教程讲解 V1 SPY 实验；V2 数据架构以本文和 [实施方案](docs/Quant%20Lab%20Data%20Layer%20V2%20Implementation%20Plan.md) 为准。

## 环境与默认实验

```bash
conda activate quant-lab
python --version  # Python 3.11
python -m pip install -r requirements-lock.txt
python -m pytest -q
python scripts/run_backtest.py
```

使用已有 Conda 环境。`requirements.txt` 是直接依赖范围；lock 文件记录实际安装版本及项目依赖闭包，未加入 notebook 等无关环境包。

默认配置继续使用原来的 `data/raw/spy_daily.parquet` 和 `.metadata.json`，价格口径为 `legacy_provider_adjusted`。文件 SHA-256 必须为 `bdd34d3bc950d433a5eeeaa594be558dd1c920dacbd61f8750366d8836bca19f`；预期 2766 行、45 次策略成交、1 次 benchmark 成交。该冻结文件不分发到 Git，当前重新下载的数据不能代替它复现历史实验。

所有脚本均可从其他工作目录运行，默认配置路径相对项目根目录。下载与回测严格分离。

## Data Architecture

```text
Yahoo / Tushare Provider
  → Immutable Source Snapshot
  → Explicit Normalization
  → Canonical Schema / Validation
  → Frozen Store + Checksummed Manifest
  → Local Loader
  → Strategy / Backtest
```

| 路径 | 职责 |
| --- | --- |
| `src/data/providers/` | 外部供应商通信、Yahoo exchange timezone 转换；可选能力不支持时明确报错 |
| `src/data/normalize.py` | 字段映射、明确单位转换、供应商倒序数据的显式排序 |
| `src/data/adjustment.py` | 从 raw OHLC 和 exact-date factor 构造研究价格，不补缺失因子 |
| `src/data/validation.py` | schema、数据质量、市场 weekday/calendar 检查 |
| `src/data/store.py` | 本地保存、定位、加载、SHA；不联网 |
| `src/data/manifest.py` | provenance、版本、JSON manifest 和自身校验 |
| `src/data/loader.py` | 校验完整冻结数据后筛选日期/标的，返回 long format |
| `src/data_loader.py` | V1 compatibility wrapper，共用新 Loader 的读取实现 |
| `src/strategy.py` | 仅计算历史收盘均线和仓位目标 |
| `src/execution.py` / `src/portfolio.py` | 成交时序/成本与现金/持仓/损益 |
| `src/backtest.py` / `src/metrics.py` | 按日驱动单资产账户与完成后的绩效计算 |
| `src/validation.py` | Future Mutation Test 与策略因果性检查 |

```text
data/source/{provider}/{dataset_id}/
data/normalized/bars/{market}/1d/{symbol}/{dataset_id}/
data/normalized/adjustments/{market}/{symbol}/{dataset_id}/
data/normalized/corporate_actions/{market}/{symbol}/{dataset_id}/
data/reference/instruments/{market}/{symbol}/{dataset_id}/
data/reference/calendars/{market}/{symbol}/{dataset_id}/
data/manifests/{dataset_id}.json
```

版本目录支持重复请求的新快照；相同 dataset ID 拒绝覆盖。不同版本不会自动互相替换。Loader 找到多个匹配版本时必须指定 ID。Manifest 包含请求/实际区间、供应商版本、行数、单位/复权假设、source/normalized 文件 SHA-256；manifest 旁边的 `.json.sha256` 校验 manifest 本身。Manifest 最后发布；normalization 失败的 source 留作审计，没有 manifest 就不能进入研究读取。

Canonical bars 是 `date, symbol, open, high, low, close, volume`，可有 `amount`。`date` 为 `datetime64[ns]`、无时区、午夜的交易所本地 session 标签，**不是 UTC 时间戳**。存储和返回按 `date, symbol` 升序，键唯一；价格必须有限且正，OHLC 关系合法，成交量非负整数。Loader/Validator 不排序修复、不去重、不补值。

## Price Semantics

Source Data 是供应商返回快照，和 Raw Price 是两个概念。

| price_basis | 产生方式 |
| --- | --- |
| `raw` | Tushare `daily` 未复权 OHLC；Yahoo `auto_adjust=False` 的 source OHLC仍有拆股调整，因此用冻结的全部后续拆股记录显式反向还原历史价格坐标 |
| `provider_adjusted` | Yahoo `Adj Close / reconstructed raw Close` 得到 `provider_adjusted_close_ratio`，同时乘到 raw OHLC；保留供应商复权坐标 |
| `qfq` | cumulative factor：`raw × factor / 截至请求结束日的最新 factor`，各 symbol 独立锚定；保留停牌日因子，不使用结束日之后的 factor |
| `hfq` | `raw × cumulative factor`，保留供应商因子绝对尺度，与 Tushare SDK 一致，不按所选起始日重新缩放 |
| `legacy_provider_adjusted` | 直接读取原 V1 `auto_adjust=True` 冻结 OHLC，避免重新生成历史价格或改变实验定义 |

`qfq/hfq` 需要 cumulative factor；Yahoo ratio 与 Tushare factor 不可混用。不支持或缺失的价格口径明确失败。OHLC 复权不改变 `volume/amount`。

Yahoo normalization 会显式反向还原供应商经过拆股缩放的 volume 和 dividend 金额；还原后无法得到整数成交量则报错。Tushare `vol` 从手乘 100 转为股，`amount` 从千元乘 1000 转为 CNY。仅容忍单位转换中的浮点舍入噪声，不接受真实分数股。

这些是下载时点的供应商快照；后来的公司行动、数据修订、qfq 锚点变化都会影响历史研究价格。Future Mutation Test 验证程序对已冻结输入的因果性，不能证明供应商数据或复权历史在原历史时点已经可得。

公式与口径参考：[yfinance auto_adjust 源码](https://github.com/ranaroussi/yfinance/blob/main/yfinance/utils.py)、[Yahoo 拆股价格口径](https://github.com/ranaroussi/yfinance/issues/687)、[Tushare daily 单位](https://tushare.pro/document/2?doc_id=27)、[Tushare pro_bar 复权](https://tushare.pro/document/2?doc_id=109)。实现的 SDK 数值对照使用本项目锁定版本的实际源码。

## Yahoo Example

```bash
python scripts/download_data.py --provider yahoo --market US --symbol SPY --start 2015-01-01 --end 2025-12-31 --frequency 1d
python scripts/download_data.py --provider yahoo --market US --symbol AAPL --start 2015-01-01 --end 2025-12-31 --frequency 1d
```

Yahoo 使用 `auto_adjust=False, repair=False, actions=True`，结束日期包含在请求范围。返回 timestamp 先转 exchange timezone 再移除时区。为反向还原拆股价格另取完整历史动作快照，其中可以有请求结束日之后的动作；这些用于显式 normalization，不交给 strategy。

CLI 输出 dataset ID、请求/实际区间、source/normalized/manifest 路径和 SHA。下载新 SPY 数据不改变默认 V1 实验。

## Tushare Example

```bash
export TUSHARE_TOKEN='your-token'
python scripts/download_data.py --provider tushare --market CN --symbol 000001.SZ --start 2015-01-01 --end 2025-12-31 --frequency 1d
python scripts/download_data.py --provider tushare --market CN --symbol 600519.SH --start 2015-01-01 --end 2025-12-31 --frequency 1d
```

Token 只从环境变量读取，不写 YAML、不使用 `set_token` 保存到本地。`.env.example` 仅给出变量名，程序不自动解析 `.env`。缺 token 明确失败；真实 API 还受账户积分和权限约束。响应触及 6000 行限制时拒绝当作完整数据，需缩短请求区间。

## Dataset Verification / Loader

```bash
python scripts/verify_dataset.py --dataset-id <download-output-id>
python scripts/inspect_data.py --dataset-id <download-output-id> --price-basis raw
python scripts/verify_dataset.py --legacy-path data/raw/spy_daily.parquet
```

两种检查都只读取本地。也可用 `--manifest path/to/manifest.json`；`--root` 与 `--data-config` 支持独立数据存储目录。校验失败时 `verify_dataset.py` 输出 FAIL 并以非零状态退出。

```python
from src.data.loader import load_bars

bars = load_bars(market='US', symbols=['SPY', 'AAPL'],
                 start='2020-01-01', end='2025-12-31', price_basis='raw')
# 返回 date × symbol long format，键唯一、升序。
# 多个版本时可用 dataset_id='...'，或逐标的映射：
# dataset_id={'SPY': 'spy-version-id', 'AAPL': 'aapl-version-id'}
```

`config/data.yaml` 管数据位置、供应商启用状态和日线默认值。`config/strategy.yaml` 设置 `symbol, market, price_basis, fast_window, slow_window`；`config/backtest.yaml` 设置资金、成本、日期、报告和指标口径，不直接指向 Parquet。

新实验可复制 strategy/backtest YAML，设置 AAPL/US 与 `raw` 或 `provider_adjusted`，并给出独立 reports_dir：

```bash
python scripts/run_backtest.py --strategy-config path/to/strategy.yaml --backtest-config path/to/backtest.yaml --dataset-id <id>
```

交易引擎只接收一个 symbol；多标的读取不意味着多资产 Portfolio 已实现。默认资金 100,000、手续费 0.05%、单边滑点 0.02%，无风险年利率 0。

## 账户、时间与输出

T 收盘才知道目标仓位，T+1 开盘执行。60 日预热意味着第 61 个交易日才可能成交；末日的新信号不成交。Benchmark 在预热后首个可执行开盘尝试买入一次。

买入 `execution_price = raw_open × (1 + slippage_rate)`，卖出为减号。`trade_value = quantity × execution_price`，`commission = trade_value × commission_rate`，`slippage_cost` 只作归因，已经进入成交价，不再扣一次现金。`raw_open` 在历史 V1 实验里表示所选复权坐标的滑点前开盘价，不能解释成历史真实美元价格。

按可用现金与含手续费单股成本向下取整买入。成本基础包含买入手续费；已实现损益包含两侧手续费与滑点。不借款、不允许负现金，期末不强制平仓。

每次输出 `trades.csv, equity.csv, metrics.json, equity_curve.png, drawdown.png`，另有 benchmark 独立交易/净值 CSV。audit 记录配置、market/provider/price_basis/dataset_id、manifest、SHA、源码哈希、环境版本及 Future Mutation Test cutoff。标题、标的、均线窗口、货币、session 文案均由实验决定。数据、报告、缓存和凭据不进入 Git。

总收益为期末净值/初始资金−1；CAGR 用日历年；波动率/Sharpe 用配置的 sessions/year。回撤从初始资金高水位计算。成交笔数与已平仓往返次数分开，胜率等仅统计已平仓往返。Sortino 的负超额收益 RMS 以全部日样本作分母；Turnover 为双边成交金额/平均每日净值，不年化。无定义比率输出 JSON null。

## Known Limitations

Yahoo 仍可能有缺漏、错误拆股/分红或历史修订；反向拆股还原依赖供应商动作记录的完整性。US 只有 weekday 最低检查，未独立验证全部节假日或缺失 session。CN 用供应商交易日历检验已有 bars 的合法 open 日期，不把停牌当成数据补齐。

Tushare 的 corporate action event normalization 暂不支持，明确抛 NotImplementedError；Yahoo 保存 dividend/split 事件。账户尚不处理分红现金或拆股持仓变更：复权模式是 synthetic adjusted-price account，raw 模式是无 corporate action accounting 的研究 smoke test。

尚未建模 A 股 T+1、涨跌停、停牌撮合、整手约束和完整税费；CN 报告明确附带此限制。没有多资产组合、实盘、机器学习、参数优化或 Paper Trading。完成 V2 后应先人工 review，再决定下一阶段。
