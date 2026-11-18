# CRS 1.0 第二阶段质量审计报告（第一轮）

- 审计日期：2026-11-18（Asia/Shanghai）
- 审计目标：`megancc25-ctrl/codex-investment-research-system`
- 分支：`feature/crs-v1.0`
- 审计基线：`fe9a5430d1bfd2d3a83de2e9af904bdd928dde04`
- 审计模式：代码与工作流审阅；本轮不修改运行逻辑、不创建 PR、不合并

## 结论

当前 CRS 是以美国市场为核心的跨资产风险研究原型。七模块、分组评分、缺失值不填零、DuckDB/Parquet 存储、三种日报格式及本地持仓覆盖层均有代码实现。代码形态不等于市场数据完整，也不证明预测有效。

第一轮发现三个需要先处理的高优先级问题：

1. GitHub Actions 把 CLI 的退出码 2（报告生成但数据不足）转换为步骤成功，且没有写入 Actions Summary。绿色工作流可能被误读为已发布完整评分。
2. 总覆盖率按模块内“分组是否至少有一个可用指标”计算。市场广度、MOVE、Repo 压力等关键指标缺失时，85%总覆盖仍可能达标；日报没有一个独立的关键指标缺失门。
3. L4 状态只记录等级和候选等级，没有记录信用触发、流动性触发或人工紧急覆盖的原因。历史状态无法仅凭状态机字段追溯触发归因。

本轮没有修改 CRS 运行代码。依照任务约束，待人工确认后再实施 P0/P1/P2/P3 方案。

## P0 — 工作流状态语义

检查了 `.github/workflows/crs-daily.yml`、`sentinel/crs/cli.py` 和报告生成链：

- CLI 在报告评分可用时返回 0；覆盖不足时返回 2；未捕获异常通常由进程返回非零错误码。
- 工作流允许退出码 0、1、2 之外的逻辑并不清晰：脚本在结果大于 2 时失败，而 2 被吞掉并以 0 结束。因此，数据不足的运行会显示成功。
- 工作流没有 `$GITHUB_STEP_SUMMARY` 输出；界面上看不到覆盖率、关键缺失模块、评分是否发布、分数、状态机状态或来源失败原因。
- 上传步骤在监控步骤失败时仍尝试运行（`always()`），这有利于保留已生成的诊断报告，但不能替代明确的运行状态。
- 调度表达式为周一至周五 23:30 UTC。GitHub 只从默认分支执行计划任务；当前分支尚未合并，因此定时任务尚未在默认分支启用。

建议后续把“流程是否完成”和“评分是否可发布”分开记录，并在 Actions Summary 明确列出：
`PIPELINE_SUCCESS`（报告流程完成）、`DATA_INSUFFICIENT`（报告生成但数据闸门未通过）、`SCORE_PUBLISHED`（完整 CRS 评分生成）、`PIPELINE_FAILED`（采集/计算/写报告发生错误）。具体实现时需定义单次运行的主状态与评分状态，避免把“流程成功”和“评分成功”合并成一个绿色结果。

## P1 — 覆盖和来源完整性

`crs_v1.json` 定义 26 个规则指标。引擎按七模块权重加权模块分组覆盖率；每组只要至少一个指标有效就计为已覆盖。模块内组分取该组可用指标的最大风险分，模块分再对可用组取平均。信用与流动性闸门检查的是模块是否有分数，不要求全部组或指定指标齐全。

这意味着 85% 覆盖率并不能证明所有预先声明的关键风险信号都在场。按现有规则分组，广度组缺失最多减少股票模块权重的四分之一（总分覆盖约 3.75 个百分点），MOVE 组缺失约 5 个百分点，Repo 组缺失约 4 个百分点。三项同时缺失而其他组可用时，理论覆盖仍约为 87.25%，超过 85%。当前实现因此可能发布“可计算的研究评分”，但缺少用户点名的重要风险维度。

关键数据逐项审计：

| 指标 | 当前实现/来源 | 当前限制及审计判断 |
|---|---|---|
| 股票市场广度 | 配置有 `breadth_above_200dma`；指标计算明确不伪造广度；没有自动采集接入 | 运行数据应为缺失；没有独立关键缺失门 |
| MOVE | 配置有 `move_level`；FRED 白名单和市场价格适配器均未接入 MOVE | 当前缺失；没有已验证来源或发布时间 |
| Repo 利率与成交量 | 配置有 `repo_rate_percentile`；无 Repo 费率/成交量历史采集 | 仅事件字段可由人工证据提供 `repo_extreme`；不能视为连续历史指标 |
| CDX IG/HY | 无自动 CDX 适配器；人工事件白名单只有 `cdx_hy_widening`（HY 布尔标记） | 无 IG/HY 点位或历史变化序列；不是评分指标数据 |
| DXY | 优先使用 FRED `DTWEXBGS` 广义贸易加权美元；如缺失可使用 Yahoo `DX-Y.NYB` 代理 | 两者均不能标记为 ICE DXY；FRED 分支有显式“不是 DXY”来源标签 |
| 美国国债总回报 | Yahoo `IEF` 价格代理 | IEF 是 ETF 代理，非广义美国国债总回报指数；价格来源未独立核对 |
| 黄金价格 | Yahoo `GLD` 价格代理 | ETF 代理，非现货黄金基准；价格来源未独立核对 |
| 房地产 | FRED Case-Shiller、成屋销售、按揭利率、CPI | 美国口径；月度发布时点/修订 vintage 未纳入 PIT 数据；不代表全球房地产 |
| HY/IG OAS | FRED ICE BofA HY、IG OAS 序列 | 数据被标记为 `LICENSE_RESTRICTED`；采集返回当前 vintage，发布日期为空。FRED 说明自 2026 年 4 月起这些 OAS 序列仅保留三年观察值，并提示受版权及分发限制。见 [HY OAS 系列说明](https://fred.stlouisfed.org/series/BAMLH0A0HYM2) 与 [IG OAS 系列说明](https://fred.stlouisfed.org/series/BAMLC0A0CM)。 |

源元数据目前不统一：FRED 采集结果有 observation date、retrieved_at、quality、license_note、raw hash，但没有 publication timestamp；行情代理诊断有 latest date 和 retrieved_at；派生 feature 通常把 published_at 设为 null，未保留 retrieved_at 或独立 license_status。日报来源状态表也没有为所有可用数据统一输出这些字段。人工证据则要求发布/检索时间和 HTTPS 来源，结构不同于自动数据。

建议下一阶段增加逐项关键数据状态表：每项保留 source、observation_date、published_at、retrieved_at、quality、license_status；当前没有数据时写成 MISSING/INSUFFICIENT_DATA；明确区分“原始指标”和“代理”，日报首页显示关键缺失项。覆盖率闸门应同时检查总覆盖与指定关键指标/分组条件，不能只检查信用、流动性模块是否有任一分数。

## P2 — 评分与状态机

- 权重：七模块合计 100%；配置加载时检查权重总和及 60/40 混合权重。
- 聚合：模块内按组等权平均，每组取指标最大值，能降低同组重复信号堆叠；但“组有一个指标即可覆盖”会让缺失关键指标被聚合状态遮蔽。
- 85% 门槛：引擎把加权覆盖率先四舍五入到一位小数，再与 85 比较。建议门槛使用未舍入值，只对展示值舍入，并新增 84.9%/85.0% 边界测试。
- 60/40 百分位：历史少于 252 个观测时只用阈值分；足够时用 60%阈值分和 40%经验百分位，最长 1260 条。采集的 feature history 在 as-of 日期过滤后构造，当前观测被排除。但引擎接收的 histories 是无日期数字列表，单独调用 `score_snapshot` 时无法自行证明所有历史值早于决策时点；点时保证依赖调用方。
- 状态升级：普通升级需要连续两次候选确认；降级需要五次确认；人工紧急覆盖可直接 L4。
- L4 触发：分数至少 80 且信用/流动性模块任一至少 85 可产生 L4 候选；但状态机记录不含 trigger_reason。应将候选原因写入 `candidate_reasons` 或等价字段，并持久化到状态历史和日报。
- 边界测试：现有测试覆盖缺失值、完整覆盖、低覆盖、状态机和紧急覆盖，但没有明确的 79.9/80、84.9/85、信用/流动性 84.9/85 等边界断言。

## P3 — 回测准备状态

当前仓库没有可审计的历史发布版本数据集或历史 CRS 日分数档案。FRED 适配器请求截至日期内的当前 CSV，未请求或存档逐日实时 vintage；OAS 可见历史又受三年限制。Yahoo 适配器取 10 年当前供应商历史，也没有历史检索时点/修订信息。房地产序列是当前 vintage 的美国月度数据。

`evaluate_crisis_backtest` 要求调用方提供 `pit_verified` 布尔值，但代码没有验证支持该标记的来源清单、vintage 文件或数据哈希。因此，它是一个输入拒绝门，不是 PIT 来源证明机制。任何没有真实历史发布版本、时间戳证据及可审计授权的数据都不能标成 PIT_VERIFIED。当前没有足够证据声明 2008、2020、2022 的 CRS 回测可行或已经完成。

P3 后续交付应先给出历史可用性矩阵：逐源记录可核实的历史起止日期、发布时间证据、修订/vintage 属性、授权限制和 PIT 可用性。当前没有实际拉取与核对数据集，所以矩阵中的精确起止日期应标注“未现场核验”，不能推测补齐。

## 验证记录

- 本轮执行：`python -m compileall -q sentinel tests local_crs_portfolio.py`；`python -m unittest discover -s tests -v`
- 结果：55 项测试通过；离线单元/模拟测试，不覆盖实时数据服务可用性、许可证合规或模型预测能力。
- 审计基线分支当前无已返回的 CI 状态记录；本地测试通过不等同于 GitHub Actions 对该提交的验证。

## 第一轮审计后续建议（待确认）

1. P0：为 CLI/报告增加明确 pipeline 与 score 状态；工作流生成结构化 Actions Summary，并确保 DATA_INSUFFICIENT 不呈现为 SCORE_PUBLISHED。
2. P1：在不接入未授权/未验证供应商前，先落实关键指标状态清单、关键缺失发布门与“代理/原指标”分离。
3. P2：以精确覆盖率比较门槛；记录 L4 触发类型；补齐用户列出的数值边界测试。
4. P3：编制三份数据/回测文档，并将 PIT 标记从任意布尔输入提升为可审计证据引用；先盘点数据可得性，再决定是否有条件做事件回测。
5. 完成上述修改并保存完整测试日志后，再评估是否创建 PR。当前不创建 PR、不合并，也不修改 main。


## 第二阶段实施结果（2026-11-18）

### 已实施

- **P0**：成功写出诊断报告时 CLI 返回 0；运行异常返回 1；数据不足通过 `score_status=DATA_INSUFFICIENT` 表示，满足全部发布门时为 `SCORE_PUBLISHED`。报告标记 `pipeline_status=PIPELINE_SUCCESS`。GitHub Actions Summary 展示覆盖率、关键缺失模块/指标、评分是否发布、分数、状态、L4原因及缺失/代理来源。CLI、测试/安装或摘要流程失败时在 Summary 显示 `PIPELINE_FAILED`。
- **P1**：新增关键指标发布门：股票广度、MOVE、Repo 百分位、HY OAS、IG OAS 缺一不可；覆盖率门槛比较未舍入值。来源/派生指标保留来源、观察/发布/检索时间、质量和许可状态；MISSING、PROXY_ONLY、US_ONLY 和历史受限来源单独列出。完整矩阵见 `CRS_DATA_COVERAGE_MATRIX.md`。
- **P2**：状态历史保存 L4 候选原因（信用模块、流动性模块、人工紧急覆盖）。新增 79.9/80、84.9/85、关键指标缺失及 as-of 前历史序列测试。百分位输入在特征构建阶段按 as-of 过滤，并排除当前观测。
- **P3**：回测输入必须包含决策时点、来源、观察/发布/检索时间、vintage ID、SHA-256与授权状态；裸 `pit_verified=true` 会被拒绝。可用性和危机窗口判定见 `CRS_BACKTEST_READINESS.md`。该检查验证证据结构与时间顺序，不证明调用方声明的哈希/授权真实有效。

### 文件修改及原因

| 文件 | 修改原因 |
|---|---|
| `.github/workflows/crs-daily.yml` | 让数据不足与流程故障在 Actions Summary 中可见，修正绿色成功的歧义 |
| `nq_sentinel_pro/sentinel/crs/actions_summary.py` | 新增运行摘要渲染器，显示分数门状态、缺失指标和来源失败 |
| `cli.py`、`runner.py`、`report.py` | 明确流程/评分两种状态；错误返回失败；把缺失项和来源血缘写入报告 |
| `collector.py`、`fred.py`、`metrics.py`、`manual.py`、`storage.py` | 补齐运行级来源、观察/发布/检索时间、质量和许可状态；登记未接入/代理指标 |
| `config.py`、`crs_v1.json`、`engine.py` | 将关键指标列为完整评分必需输入；不再使用显示舍入值判定85%门槛 |
| `backtest.py` | 拒绝无来源时间、vintage、哈希或授权状态的历史样本 |
| `tests/test_crs_engine.py` | 增加状态、覆盖率、关键缺失、来源元数据、PIT拒绝与CLI状态测试 |
| `docs/CRS_DATA_COVERAGE_MATRIX.md` | 逐项记录来源、范围证据、发布时间、修订和许可限制 |
| `docs/CRS_BACKTEST_READINESS.md` | 记录2008/2020/2022的PIT准备度，明确不伪造历史结果 |
| `docs/CRS_PHASE2_TEST_LOG.txt` | 保存本次编译与离线测试完整运行记录 |
| `nq_sentinel_pro/CRS_README.md` | 更新CLI退出码、运行状态和新评分发布门说明 |

### 验证与剩余边界

- `python -m compileall -q sentinel tests local_crs_portfolio.py`：通过。
- `python -m unittest discover -s tests -v`：65 项通过（见完整日志文件）。
- 未完成实时来源稳定性验证；无实际广度、MOVE、Repo连续序列或CDX适配器，因此默认数据链可能输出 `DATA_INSUFFICIENT`，这是关键输入门的预期结果。
- 未完成2008/2020/2022点时回测、授权独立核验或样本外验证。没有修改 NQ-Sentinel 原有权重/评分，没有上传个人持仓，没有创建 PR，也没有合并。
