# 下一阶段重构与 Chan-Core 验收记录

验收日期：2026-10-06。依据 [本轮实施方案](Quant%20Lab%20下一阶段重构与%20Chan-Core%20自研实施方案.md)。

## 交付

已完成方案的八阶段：可安装 package、Market/Data V3、Local Forex、锚定重采样、Chan primitives/Analyzer、Strategy/Execution 接口、Chan 观察接入、文档和检查工具。
没有实现未定义的 Chan 交易规则、完整 Forex/Futures 账户或本轮排除的线段/中枢/背驰/实时交易。

| 阶段 | 已提交内容 |
| --- | --- |
| Phase 1 | `041af68`：quant_lab editable 包与旧入口兼容 |
| Phase 2 | `6238efe`：Market primitives、V3 Schema/Manifest/Store/Loader |
| Phase 3 | `4b70e54`：Local CSV/Parquet source 冻结链路 |
| Phase 4 | `48134e2`：显式锚点、时区与父版本 lineage 重采样 |
| Phase 5 | `59d0921` 包含/分型；`c3c8ea5` 笔/Analyzer/Golden/因果性 |
| Phase 6 | `23ef4cd`：Engine 与策略解耦、Equity models、日快照指标 |
| Phase 7 | `4bd74b0`：Chan-FX observer、配置、CSV/JSON/静态图工具 |
| 补充修正 | `423504f`：V2/V3 qfq 以本次选择结束时点为 anchor |
| 最终审计 | `4857413`：来源请求/时区、因子覆盖、lineage 与完成时钟验证 |
| Phase 8 | README、architecture、chan-core、当前 AGENTS 与本记录 |

## 环境与测试

继续使用 quant-lab / Python 3.11，未创建新环境，未新增运行依赖。使用已有 setuptools 完成 `pip install -e . --no-deps --no-build-isolation`。

```bash
python -m pytest -q
python -m pip check
```

最终全量 **205 passed，0 skipped**；pip check 为 No broken requirements found。
重构前 123 个测试通过，包迁移仍 123，通过 V3 扩展为 146，通过 Chan 核心后 188；保留所有原有数值预期。

覆盖：

- 7 种 Timeframe、UTC/排序/重复/OHLC/可选字段、无真实 volume Forex、tick_volume、open_interest、资产类别/venue/provider_symbol、期货静态元数据与 multi-symbol 读取。
- V2/V3 本地读取兼容、Manifest/身份/SHA/拒绝覆盖、日线来源时区与复权因子；请求结束时点前 qfq anchor。
- Local EURUSD/GBPUSD CSV 与 Parquet、原始字节冻结、bar-end→bar-start、供应商代码映射、原文件删除后读取、脏数据保留 source 但不发布 Manifest、aware 来源与声明时区一致。
- 1m→5m/15m/1h/4h、5m→1h、1h→4h；OHLC 与 optional fields 聚合、时区/anchor、缺失/partial/重复/逆序拒绝、父版本 SHA 与 lineage 元数据。
- 向上/向下与连续包含、原始索引 lineage、严格顶底、等高/等低排除、重叠三 K。
- 成笔距离、端点更极端替换/较弱忽略/相等保留、反向确认、极值 invariant、gap 不加距离。
- 100→1000 根 confirmed 前缀不变、未来变异按 confirmed_at 检查、右侧继续包含后 as-known 分型快照不变、immutable 对象。
- 人工标注 Golden Fixtures；通用自定义 Strategy、下一开盘与末根信号、账户成本、日快照风险、V3 分钟线完整报告 CLI、Chan 无交易观察 CLI。
- AST 检查 Chan 无 DataFrame/SDK/绘图库/数据层依赖，Engine 无 SMA/Chan 专属导入。

## 冻结 SPY 回归

原 V1、两份真实 V2 Yahoo dataset 未重下载或重写。所有 22 个已有 data 文件与验收前 SHA 相同；两份 V2 Manifest 独立 verify 通过。
默认旧 reports 未覆盖；独立回归产物在 `reports/refactor_spy_smoke/`。

| 项目 | 结果 |
| --- | --- |
| SPY 原文件 SHA | `bdd34d3bc950d433a5eeeaa594be558dd1c920dacbd61f8750366d8836bca19f` |
| Rows / Range | 2766 / 2015-01-02..2025-12-31 |
| 策略 fills | 45 |
| 策略总收益 / CAGR | 1.466718879583301 / 0.08558235360852229 |
| Benchmark fills | 1 |
| Benchmark 总收益 / CAGR | 2.9389675730204616 / 0.13278961489741126 |
| 四张内存表 | equity/trades/benchmark_equity/benchmark_trades 逐值 exact 相同 |

四份 CSV 与历史 baseline SHA 完全一致：

| 文件 | SHA-256 |
| --- | --- |
| trades.csv | `1289681caaa855ee053a5e8e5d5b0eec3ce32b8653d949f91cdf6767663b0793` |
| equity.csv | `d13a13076f5f9b92db9b2670e192cccc041c6ff57d0e3f6c08bc113bcb10edcf` |
| benchmark_trades.csv | `fc9e05be8c9deec50498d006a41a41ada94f4653ab1ae597fc0d1a7ad94657cd` |
| benchmark_equity.csv | `67a9a0bc28c036a1a2d9276b8659f173f193b34f98fb3ed8684845bbe698acd3` |

冻结数据不分发到 Git；干净 checkout 缺原 V1 时，必须明确区分 skipped regression 与已完成真实回归。

## Local → Resample → Chan 端到端

本次使用人工 Golden ranges 生成**明确为合成测试输入**的 225 根 1m EURUSD bar，非真实汇率，不用于收益结论。
通过 CLI 完成本地导入、source 冻结、15m 锚定重采样、结构检查图和 Chan-FX observation。

- 原输入：`reports/chan_smoke_input/EURUSD.csv`；配置/Manifest 副本同目录。
- 独立 Store：`reports/chan_smoke_store/`，未进入原 `data/`。
- Source ID：`local_EURUSD_1m_chan_golden_smoke`。
- Derived ID：`local_EURUSD_15m_chan_golden_smoke`；UTC、anchor=00:00。
- 结果：15 raw bars、15 merged bars、4 fractals、3 strokes；前两笔 confirmed，末笔 tentative。
- 输出：`reports/chan_core_smoke/` 包含四 CSV、chan.json、chan.png。
- config/chan_fx.yaml observation 输出：`reports/chan_observer_smoke/chan_local_EURUSD_15m_chan_golden_smoke/`。
- 未生成 FX 订单、账户或绩效报告；不启用 --observe-only 时明确 NotImplemented。

## 包与断点

从 /tmp 工作目录导入 quant_lab、ChanAnalyzer、load_dataset 成功，绝对路径 inspect_chan.py --help 成功，无 sys.path 注入。
已验证 pdb 的 `b src/quant_lab/chan/stroke.py:58` 能设置真实断点；无需 debug 文件或 IDE launch 配置。
`git diff --check` 无空白错误；data/reports/凭据保持 Git 忽略。

## 明示边界

- 这是增量结构基础设施；朋友尚未确认的初始包含、等值、gap/额外价格条件保留为文档化默认或错误。最终交易理论未实现。
- 日线午夜 session 坐标不是实际交易所开盘；分钟线必须带清楚的来源时区和 bar 语义。固定 elapsed 窗口的 DST 边界不推断修复。
- V3 风险/回撤按 UTC 日末已知估值，午夜估值归新日；bar 净值仍完整保存。
- Forex 执行与期货账户未实现；CN 仍缺完整市场执行约束。Corporate action 未应用于账户。
- 本轮不做新联网下载；真实 Yahoo 来源沿用经校验 V2，真实 Tushare API/token 限制沿用此前记录。合成 FX fixture 不冒充供应商实测。
