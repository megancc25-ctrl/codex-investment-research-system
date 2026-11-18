# CRS 1.0 第七阶段：证据语义收尾与验证准备

## 结论

本阶段收紧了反向证据的范围：单一风险子条件未发生不再进入整体 `against`，统一归入 `component_evidence`。因此，三资产未同步下跌但融资侧数据缺失时，报告只呈现该组件观察和融资数据限制，不会把未知的Repo/融资/保证金风险解释成整体风险下降。

本地 `compileall` 与完整 **96项** `unittest` 通过。一次隔离的公开源采集运行完成了诊断报告，但只能得到 `PIPELINE_SUCCESS / DATA_INSUFFICIENT`，覆盖率为38.5%，没有完整CRS分数。GitHub远端工作流没有运行记录，也无法在不改默认分支的前提下触发该 workflow_dispatch。2008、2020、2022的真实 point-in-time 回测仍未就绪；没有生成历史CRS分数或回测表现数字。系统继续保持 `PROVISIONAL_RESEARCH_ONLY`。

## 本阶段修改

### 组件观察与整体反向证据分离

- 新增 `component_evidence` 字段，记录具体模块、信用组合告警和单一跨资产条件的已观察结果。
- 同步抛售为 `AVAILABLE + false` 时，将“未确认三资产同步下跌”放入 `component_evidence`，不进入 `against`。
- 低风险模块分数和 `credit_risk=CLEAR` 作为组件观察记录。整体 `against` 仅在流动性同步条件可用为false、且配置的Repo/融资/保证金事件均明确为false（`NORMAL_CONFIRMED`）时生成组合层结论。
- 即使告警对象声称 `CLEAR`，如同步特征缺失、状态不足或与 `CLEAR` 相矛盾，也不生成整体反向证据，并增加数据限制说明。
- JSON原生保留该字段；Markdown/HTML新增“Component observations/组件观察”栏目。其余三个证据栏目仍保持独立。

### 回归验证

新增用例覆盖：

1. 三资产同步下跌为false、融资输入缺失：整体 `against` 为空，组件观察说明未发生同步下跌，`data_limits` 明确列出融资输入缺失。
2. `component_evidence` 在JSON、Markdown、HTML三种报告中保留。
3. 告警为 `CLEAR` 但同步特征缺失或实际为true时，不生成整体反向证据。
4. 现有同步下跌AVAILABLE/MISSING/INSUFFICIENT_DATA矩阵已更新为新的证据语义。

新增测试先在旧实现上失败：前一用例发现“未同步下跌”仍写入 `against`；后一用例发现报告无组件观察栏目。实现后两项专项测试通过。

## 一次本地实时公开数据采集验证

运行时间：2026-11-18 13:02 UTC（报告生成时间）。使用最近已完成的NYSE交易日 `2026-11-17` 作为 `as-of`。数据库和报告写入临时隔离目录，没有读取个人持仓或私人文件。

| 项目 | 实测结果 |
|---|---|
| Pipeline | `PIPELINE_SUCCESS` |
| Score status | `DATA_INSUFFICIENT` |
| Metric coverage | 38.5% |
| CRS score | 无（`null`） |
| Yahoo价格代理 | NDX、SOX、IEF、GLD、DX-Y.NYB均返回AVAILABLE；最新观察日均为2026-11-17 |
| Yahoo发布时间 | `published_at` 未提供；质量为 `UNVERIFIED_VENDOR_PROXY`，不得视为PIT数据 |
| FRED序列 | 19个请求均为MISSING，原因均为 `The read operation timed out` |
| 关键监测缺口 | 市场广度、MOVE、Repo连续数据、CDX IG/HY仍MISSING；DXY、债券总回报、现货黄金仍为代理；房地产仍为US_ONLY；OAS PIT历史仍RESTRICTED_HISTORY |

这一结果证明本次环境中Yahoo代理数据请求可返回、FRED请求超时且系统正确降级为数据不足。它不证明数据供应商长期可用、价格代理准确、实时发布时点可追溯或数据获得授权；FRED超时也只代表本次运行环境/时点的请求失败，不能推断服务持续不可用。未发布完整分数是预期的安全结果。

生成的临时诊断文件：

- `C:/Users/87918/AppData/Local/Temp/crs-phase7-live-validation/reports/CRS_DAILY_2026-11-17.json`
- `C:/Users/87918/AppData/Local/Temp/crs-phase7-live-validation/reports/CRS_DAILY_2026-11-17.md`
- `C:/Users/87918/AppData/Local/Temp/crs-phase7-live-validation/reports/CRS_DAILY_2026-11-17.html`

这些临时报告没有纳入仓库或Artifact。

## 历史回测准备状态

沿用并复核 [CRS_BACKTEST_READINESS.md](CRS_BACKTEST_READINESS.md) 和 [CRS_DATA_COVERAGE_MATRIX.md](CRS_DATA_COVERAGE_MATRIX.md)：

- 2008：现有价格窗口和受限OAS数据无法提供完整覆盖，也无当时发布版本；`NOT_PIT_VERIFIED`，不可作有效CRS回测。
- 2020：供应商回溯价可能覆盖窗口，但没有当时下载快照和发布/修订时点；FRED当前vintage不等于当时可得数据；`NOT_PIT_VERIFIED`。
- 2022：相同的PIT、修订与授权问题未解决；`NOT_PIT_VERIFIED`。

所以没有计算 Recall、Precision、False Positive Rate、Lead Time、状态稳定性或危机识别表现。现阶段编造这些数字或使用当前修订版本冒充PIT数据都会失实。

## 远端试运行限制

当前 `.github/workflows/crs-daily.yml` 只存在于 `feature/crs-v1.0`，该分支未合并至默认分支 `main`。GitHub要求 `workflow_dispatch` 工作流文件存在于默认分支才能接收手动触发事件；本阶段未修改 `main`。GitHub API在本阶段提交后查询该功能分支Actions运行返回0条记录。当前CLI环境也没有GitHub CLI认证。故未取得真实远端运行URL、运行SHA或Artifact，远端CI与云端真实采集仍为未验证。参见[GitHub官方手动运行工作流说明](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)。

## 不变项与当前边界

- 未修改七模块结构、权重、指标、固定阈值、60/40方法、85%覆盖率门槛或NQ-Sentinel规则。
- 未增加风险指标，没有生成交易指令，没有合并PR/分支。
- 未伪造MOVE、CDX、Repo或历史危机数据，没有宣称危机回测完成。
- 本地一次数据采集成功完成管道，但评分数据不足；远端Actions、持续实时可靠性和预测有效性仍未验证。

## 修改文件

| 文件 | 理由 |
|---|---|
| `nq_sentinel_pro/sentinel/crs/runner.py` | 将模块低分、信用清晰和无同步抛售作为组件观察；整体反向证据不再混入子条件未发生。 |
| `nq_sentinel_pro/sentinel/crs/report.py` | 在Markdown/HTML显式展示`component_evidence`，JSON延续完整保存。 |
| `nq_sentinel_pro/tests/test_crs_engine.py` | 增加融资缺失边界及三种报告格式测试，并更新原同步抛售证据矩阵预期。 |
| `docs/CRS_PHASE7_AUDIT.md` | 记录语义修正、单次实际采集结果、数据限制和回测/远端状态。 |
| `docs/CRS_PHASE7_TEST_LOG.txt` | 保存编译、完整离线测试与实际采集摘要。 |
