# CRS 1.0 第五阶段：信用证据分类与自动化验收审计

## 结论

信用告警的证据归类缺陷已修复。`CLEAR` 进入 `against`；`YELLOW`、`RED_CANDIDATE`、`SEVERE_WATCH` 进入 `supporting`，并各自使用不夸大确认程度的说明；`INSUFFICIENT_DATA`、缺失和未知状态只进入 `data_limits`。新增状态矩阵及JSON、Markdown、HTML一致性测试。

GitHub Actions配置已做静态验收，工作流明确用 `America/New_York` 日历日期作为 `--as-of`，避免流程将UTC日期误当作交易地区日期。工作流只存在于 `feature/crs-v1.0`；默认分支没有该文件。本阶段未触发远端工作流，因此没有真实运行、实时采集或Artifact证据。不能声称定时任务已正式生效。

未更改七模块、权重、阈值、85%覆盖门槛、60/40混合方法或NQ-Sentinel规则；没有新增风险指标。CRS仍为 `PROVISIONAL_RESEARCH_ONLY`，历史危机回测未完成。

## 信用证据根因与修复

此前 `_evidence()` 把 `INSUFFICIENT_DATA` 加入 `against`，且告警对象缺失时会直接索引并抛 `KeyError`。这会把“不能判断”放进反向证据，或让诊断报告生成失败。

目前按状态显式分流：

| credit_risk状态 | 证据桶 | 报告语义 |
|---|---|---|
| `CLEAR` | `against` | 可用HY/IG与股票输入上的组合告警为清晰。 |
| `YELLOW` | `supporting` | 存在观察级组合信号，尚未达到红色候选状态。 |
| `RED_CANDIDATE` | `supporting` | 风险组合告警为红色候选；不称为已验证危机概率。 |
| `SEVERE_WATCH` | `supporting` | 信用严重观察状态；不称为已验证危机概率。 |
| `INSUFFICIENT_DATA` | `data_limits` | 输入不足，不能判断信用风险升高或稳定。 |
| 告警缺失 | `data_limits` | 状态缺失，不能作信用判断。 |
| `UNKNOWN`或其他未识别状态 | `data_limits` | 状态不可识别，不能作信用判断。 |

## 回归测试

- 状态矩阵覆盖上述7种情形；另覆盖缺少 `credit_risk` 键。
- 断言只有 `CLEAR` 生成信用风险解除的反向证据；不足、缺失、未知绝不进入信用 `against`；YELLOW、RED_CANDIDATE和SEVERE_WATCH均被明确写入支持证据。
- 报告格式测试确认 `supporting`、`against`、`data_limits` 分别完整保留于JSON、Markdown和HTML。HTML当前基于Markdown文本转义生成，测试检查相同状态文本没有丢失或改桶。
- NQ-Sentinel规则/权重文件未被修改；既有权重回归测试纳入完整测试集。

## GitHub Actions 静态验收

| 检查项 | 静态结果 | 证据与限制 |
|---|---|---|
| 手动触发 | 通过 | YAML含 `workflow_dispatch`。 |
| 编译/离线测试早于采集 | 通过 | `Compile and run offline tests` 步骤先于 `Collect data and write daily reports`。 |
| 数据不足与管道失败区分 | 通过 | CLI写出诊断报告后返回0；score可为 `DATA_INSUFFICIENT`。 |
| 真实运行失败返回非零 | 通过 | CLI异常返回1；采集步骤捕获后写Summary并以原退出码失败；Summary生成失败返回1。 |
| Artifact文件边界 | 通过（配置审计） | 上传glob只包括 `reports/crs/*.json`、`*.md`、`*.html`；不包含DuckDB、Parquet、state cache路径或个人持仓文件。没有真实Artifact可供内容检查。 |
| 状态历史恢复 | 通过（配置审计） | `actions/cache@v4` 缓存 `nq_sentinel_pro/data/crs/state.json`，缓存键按分支和run ID隔离，restore prefix按分支回退；CLI使用该路径。实际跨运行恢复尚未演示。 |
| 日期和交易日边界 | 部分完成 | cron为工作日23:30 UTC，位于美国收盘后；工作流改用`TZ=America/New_York date +%F`，使报告as-of按纽约当地日历日取值。尚未接入NYSE交易日历：工作日市场假日仍会启动，报告可能以假日日期标记、而观测日期停留在上一交易日。生产定时启用前仍需决定并验证假日处理策略。 |
| 默认分支定时生效 | 未生效 | 远端检查确认 `main` 上 `.github/workflows/crs-daily.yml` 返回404。GitHub仅在默认分支安排定时工作流；本阶段不合并、不改main。 |

该workflow会启动真实外部数据采集。本阶段没有触发它，因此不产生未授权的实时采集。远端Actions runs查询没有返回运行记录（`total_count=0`）；未取得运行SHA、起止时间、最终状态或Artifact信息。这表示远端CI未验证，不能称为通过或pending。

## 验收状态

| 验收类别 | 状态 |
|---|---|
| 本地编译和离线测试 | 以 `CRS_PHASE5_TEST_LOG.txt` 的本次运行结果为准。 |
| GitHub Actions远端CI | 未验证；没有关联本次提交的run记录。 |
| 实时数据采集 | 未执行；测试使用本地fixtures。 |
| 完整CRS分数发布 | 不由本阶段测试推断；系统仍按覆盖率和关键数据门槛决定。 |
| 正式风险决策/历史预测能力 | 不支持此用途；`PROVISIONAL_RESEARCH_ONLY`，无已完成的2008/2020/2022危机回测。 |

## 修改文件

| 文件 | 原因 |
|---|---|
| `nq_sentinel_pro/sentinel/crs/runner.py` | 把信用状态映射到正确证据桶；对缺失/非字典告警安全降级为数据限制。 |
| `nq_sentinel_pro/tests/test_crs_engine.py` | 增加信用状态矩阵和三种报告输出一致性回归测试。 |
| `.github/workflows/crs-daily.yml` | 使用纽约当地日历日期，而不是UTC日历日期传入日报as-of。 |
| `docs/CRS_PHASE5_AUDIT.md` | 记录根因、修复、工作流静态验收和剩余边界。 |
| `docs/CRS_PHASE5_TEST_LOG.txt` | 保存本阶段编译及完整测试运行日志。 |
