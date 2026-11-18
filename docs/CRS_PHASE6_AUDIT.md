# CRS 1.0 第六阶段审计：流动性证据与NYSE日期

## 结论

修复了流动性告警和报告证据的两项语义缺陷，并以NYSE交易日历确定日报 `as-of` 日期。融资/Repo/保证金状态不再因未提供而被当成正常；同步抛售事件不再出现在反向证据中。测试覆盖日期、时间、假日、提前收市及JSON/Markdown/HTML输出。

本阶段未改变七模块、权重、指标、阈值、60/40方法、覆盖率门槛、NQ-Sentinel规则或状态机确认规则。没有执行实时采集，也没有声称完成历史危机回测。系统仍是 `PROVISIONAL_RESEARCH_ONLY`。

## 问题一：融资数据缺失被误称为流动性CLEAR

此前流动性状态只看三资产同步下跌布尔值；同步下跌为false时，Repo、融资故障和保证金压力数据即使完全未提供也会得到 `CLEAR`。

现在分别检查两个维度：

1. `synchronized_three_asset_down_20d` 是否可用，以及值为true或false。
2. `repo_extreme`、`funding_market_failure`、`margin_stress` 是否有明确布尔状态。

| 同步抛售 | 融资/Repo/保证金事件 | 告警状态 | 语义 |
|---|---|---|---|
| false | 三项均有明确false | `CLEAR` | 只表示当前配置的组合条件均报告正常。 |
| false | 至少一项未知 | `INSUFFICIENT_DATA` | 不把融资状态未知说成正常。 |
| true | 至少一项未知、没有已确认异常 | `CROSS_ASSET_SELL_OFF` + `data_limits` | 抛售已确认，融资侧仍无法判断。 |
| true | 至少一项true | `RED_CANDIDATE` | 同步抛售与融资侧异常同时确认；仍不是危机概率。 |
| false | 至少一项true | `FUNDING_STRESS_ONLY` | 融资侧有压力，但同步抛售组合条件未满足。 |
| 同步状态未知 | 任意 | `INSUFFICIENT_DATA` | 无法判断跨资产组合条件；已确认的融资异常仍会单列支持证据。 |

缺失、非布尔值及未提供的融资事件均记入 `missing_funding_inputs` / `data_limits`。为避免伪造“确认正常”，手动事件的true和false都必须带HTTPS来源、观测日期、发布时间和检索时间；缺失 `value` 不再默认转为false。手工false证据只有通过校验后才可被当作明确正常状态。

## 问题二：同步抛售被重复写成反向证据

- 已确认的三资产同步下跌保留在 `supporting`。
- `CROSS_ASSET_SELL_OFF` 不再写入 `against`。
- Repo/融资/保证金未知时写入 `data_limits`，说明无法把抛售进一步归类为流动性危机。
- 只有同步抛售false且融资三项全部明确false时，流动性告警才允许生成“组合条件均正常”的反向证据。
- JSON、Markdown和HTML从同一报告payload渲染；回归测试断言三类证据桶及repo缺口一致，且反向证据不含跨资产抛售事件。

## NYSE交易日日期

工作流从固定的纽约日历日改为运行 `python -m sentinel.crs.market_calendar`。该函数使用 `exchange_calendars` 的 `XNYS`交易日session和每个session实际收市时间，返回当前时刻前最近已收市session：

- 周末、感恩节、Good Friday等休市日回退到最近一个实际session。
- 交易日收市前手动运行会选前一个session；收市后才选当天。
- UTC已进入次日但纽约仍为前一日时，不会提前推进as-of日期。
- 使用日历给出的session close，因此可正确处理提前收市。
- 如果无法解析session，工作流写入 `PIPELINE_FAILED` 摘要并以非零状态退出。

实现使用 `exchange_calendars` 的 `XNYS` 日历及session API；项目文档列出的 `get_calendar`、`sessions_in_range` 和 `session_close` 支持按交易所session和实际收市时间查询。[上游项目文档](https://github.com/exchange_calendars/exchange_calendars)；本环境核验并安装的发行版本为4.13.3（[PyPI发行信息](https://pypi.org/project/exchange_calendars/4.13.3/)）。

## 测试

新增覆盖：

- 同步无抛售且融资数据缺失不能为 `CLEAR`。
- 同步抛售且融资侧未知不能声称融资异常已经确认。
- 同步抛售和一项已确认融资异常时才进入 `RED_CANDIDATE`。
- 融资压力存在但无同步抛售时进入 `FUNDING_STRESS_ONLY`。
- `CROSS_ASSET_SELL_OFF` 不会成为反向证据；数据缺口可见。
- JSON/Markdown/HTML的支持证据、反向证据、数据限制一致。
- 手动false融资事件缺少归属信息时拒绝；具备时间和来源证据时保留为false。
- XNYS假日、周末、Good Friday、收市前/后、夏令时、UTC/纽约跨日、感恩节后提前收市。

全量本地编译与测试运行日志在 `docs/CRS_PHASE6_TEST_LOG.txt`。远端GitHub Actions未触发；本地测试不代表远端CI或实时数据采集已通过。

## 自动化与风险边界

- 工作流仍只在 `feature/crs-v1.0`，没有合并到 `main`；定时调度未在默认分支生效。
- 工作流日期解析使用日历库，不访问额外行情或私人数据源。
- `FUNDING_STRESS_ONLY` 是告警状态，仅影响报告语义，不增加评分指标或更改七模块评分。
- 本地模拟测试不构成2008、2020、2022历史危机回测或预测有效性证明。

## 修改文件及原因

| 文件 | 修改理由 |
|---|---|
| `nq_sentinel_pro/sentinel/crs/alerts.py` | 区分融资侧明确正常、已确认压力、缺失，以及同步状态；防止缺失落入CLEAR。 |
| `nq_sentinel_pro/sentinel/crs/runner.py` | 将跨资产抛售留在支持证据，并将未知融资项写入数据限制。 |
| `nq_sentinel_pro/sentinel/crs/manual.py` | 要求手动true/false事件都有来源和时间归属；防止缺失值被当false。 |
| `nq_sentinel_pro/sentinel/crs/market_calendar.py` | 计算最近已收市的NYSE交易日，覆盖假日及早收市。 |
| `nq_sentinel_pro/requirements.txt` | 加入交易日历依赖，供本地和GitHub Actions使用。 |
| `.github/workflows/crs-daily.yml` | 通过NYSE session日历确定as-of，并在日期解析失败时返回非零并写Summary。 |
| `nq_sentinel_pro/tests/test_crs_engine.py` | 增加融资状态、证据分桶、报告一致性、手动false来源回归。 |
| `nq_sentinel_pro/tests/test_crs_market_calendar.py` | 新增交易日、假日、时区和提前收市边界测试。 |
| `docs/CRS_PHASE6_AUDIT.md` | 保存本阶段设计边界、发现、实现和剩余限制。 |
| `docs/CRS_PHASE6_TEST_LOG.txt` | 保存指定编译命令和全量测试日志。 |
