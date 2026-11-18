# CRS 1.0 第二阶段质量审计与修正记录

## 范围与基线

审计对象为 `feature/crs-v1.0` 上的 CRS 1.0 实现。NQ-Sentinel 原始评分权重、指标与历史记录保持不变；本次不创建真实交易、不修改 `main`、不合并分支。报告中的评分仅为研究指标，不是危机概率或交易建议。

本次修正针对阶段二审计发现的发布状态歧义、关键数据缺失可能被总体覆盖率掩盖、来源元数据不足、L4来源语义不完整和历史回测缺少点时证据等风险。数据源是否配置不等于当日真实采集成功；日报中的实际状态由运行产物给出。

## P0：流程与评分状态

- CLI 将“诊断报告成功写出”视为 `PIPELINE_SUCCESS`，但不将 `DATA_INSUFFICIENT` 显示为完整评分成功；运行异常返回非零并显示 `PIPELINE_FAILED`。
- 报告使用独立 `pipeline_status` 和 `score_status`，其中评分状态为 `SCORE_PUBLISHED` 或 `DATA_INSUFFICIENT`。
- GitHub Actions Summary 展示覆盖率、关键缺失模块/指标、是否发布完整评分、最终分数（如有）、状态机状态，以及各失败/缺失来源和原因。
- Summary 渲染失败也会令 workflow 失败；安装或离线检查阶段失败会写出 `PIPELINE_FAILED` 摘要。

## P1：数据覆盖与来源完整性

- CRS 总覆盖率按配置模块权重对模块内组覆盖率聚合，评分发布使用未四舍五入的覆盖率并要求达到 85%。
- 即便总覆盖率达到 85%，缺少 credit/liquidity 关键模块或关键指标（广度、MOVE、Repo百分位、HY/IG OAS）仍阻止发布。
- 对未接入的 MOVE、广度、Repo连续序列和CDX，保持 `MISSING`；DXY、IEF、GLD等只能按明确代理标注，不冒充原指标。
- 采集状态和特征保留来源、观察日期、发布时间、检索时间、质量及许可字段；未知发布时间保持空值。受限 OAS 原值在公共日报中脱敏。
- 数据源范围、授权和实测覆盖日期逐项见 [CRS_DATA_COVERAGE_MATRIX.md](CRS_DATA_COVERAGE_MATRIX.md)。

## P2：评分、点时与状态机

- 模块权重总和及模块内组聚合通过配置和测试核查；NQ-Sentinel权重回归测试确保原值未变。
- 历史百分位仅接收决策日前传入的历史；评分函数不主动读取当前/未来观测作为历史。采集层历史查询截止到 `asof`，去重并截断至窗口。
- 回测输入要求带决策时点、观察/发布时间/检索时间、vintage/source ID、SHA-256及授权状态，并校验时间顺序；这些结构检查不等于真实性证明。
- L0-L4保持升级两次确认、降级五次确认；人工市场功能失效为紧急覆盖。修正 L4 的常规评分触发条件不再错误依赖紧急覆盖标志，并记录 `CREDIT_MODULE_SCORE` / `LIQUIDITY_MODULE_SCORE` 原因码；人工覆盖记录独立原因码。
- 自动化测试覆盖 79.9/80 分、84.9/85 分模块门槛、84.9%/85%覆盖率、关键数据门槛、点时排除以及状态迁移。

## P3：回测准备

未伪造 2008、2020 或 2022 年历史数据，也没有计算危机命中率、提前量或误报率。现阶段相关源缺少可验证的历史发布版本、修订快照或授权证据，不能标为 `PIT_VERIFIED`。逐源矩阵及阻断项见 [CRS_BACKTEST_READINESS.md](CRS_BACKTEST_READINESS.md)。

## 验证与限制

执行命令：`python -m compileall -q sentinel tests local_crs_portfolio.py` 和 `python -m unittest discover -s tests -v`。完整标准输出、测试数和退出码记录在 [CRS_PHASE2_TEST_LOG.txt](CRS_PHASE2_TEST_LOG.txt)。该日志为本地离线测试，不代表 GitHub Actions 已运行，也不代表实时数据源已端到端验证。具体当日实时覆盖应以实际报告为准；没有原始真实观测时评分保持不足数据。

## 修改清单与理由

| 文件 | 修改理由 |
|---|---|
| `.github/workflows/crs-daily.yml` | 区分流程失败与数据不足，摘要缺失时失败并上传诊断产物 |
| `nq_sentinel_pro/sentinel/crs/cli.py` | CLI退出码与流程状态一致 |
| `nq_sentinel_pro/sentinel/crs/actions_summary.py` | Summary字段及来源失败明细 |
| `nq_sentinel_pro/sentinel/crs/collector.py`、`fred.py`、`prices.py` | 来源元数据、缺失状态与代理属性 |
| `nq_sentinel_pro/sentinel/crs/config.py`、`crs_v1.json`、`engine.py` | 关键指标门槛和原始覆盖率门槛 |
| `nq_sentinel_pro/sentinel/crs/metrics.py`、`manual.py`、`storage.py` | 保留派生数据来源时间及质量/许可元数据 |
| `nq_sentinel_pro/sentinel/crs/report.py`、`runner.py` | 显示数据状态、来源诊断和状态机原因 |
| `nq_sentinel_pro/sentinel/crs/backtest.py` | 拒绝缺少结构化点时证据的回测样本 |
| `nq_sentinel_pro/sentinel/crs/state.py` | 修正L4评分触发依赖并记录信用/流动性原因码 |
| `nq_sentinel_pro/tests/test_crs_engine.py` | 增加覆盖边界、状态机、来源、CLI和PIT测试 |
| `docs/CRS_DATA_COVERAGE_MATRIX.md` | 逐源列出可用性、限制及接入状态 |
| `docs/CRS_BACKTEST_READINESS.md` | 列出历史可用性与PIT阻断证据 |
| `docs/CRS_PHASE2_TEST_LOG.txt` | 保存本轮测试实际结果 |
| `docs/CRS_PHASE2_AUDIT.md` | 汇总审计结论、范围、限制与修改理由 |
