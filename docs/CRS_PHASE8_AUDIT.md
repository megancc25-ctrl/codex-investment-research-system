# CRS 1.0 第八阶段：FRED链路、数据源健康与PIT准备审计

审计日期：2026-11-18
分支目标：`feature/crs-v1.0`
范围：FRED请求诊断与韧性、健康监控、历史vintage存储准备。没有新增风险指标，没有修改七模块结构、权重、评分阈值、60/40评分方法、85%门槛、关键指标门槛或NQ-Sentinel规则。

## 结论

第八阶段加入了有界重试、官方FRED observations API适配、带新鲜度上限的DuckDB缓存回退、30个报告日的数据源健康统计，以及日期级FRED vintage快照表。缺失源仍然保持缺失；缓存结果明确标记为 `AVAILABLE_CACHED`，对应请求失败仍被计入健康失败率。

**FRED链路目前仍未通过稳定性验收。** 本地环境没有配置 `FRED_API_KEY`。单独一次Graph CSV请求成功，但批量探测19个系列时19项都在4秒单次请求窗口内超时；无密钥的官方API请求快速返回HTTP 400。该结果不能证明FRED永久不可用，也不能证明新增API密钥路径已成功运行。仓库Secret是否已经设置不可从当前连接检查。

**没有建立真实的2022、2020或2008点时数据集。** API vintage查询与分表只提供获取和保留能力；`published_at`仍未知，OAS授权仍待核实。本报告没有将任何数据标成 `PIT_VERIFIED`，也没有生成危机回测成绩。系统状态继续为 `PROVISIONAL_RESEARCH_ONLY`。

## FRED链路诊断

本机诊断只读取密钥是否存在，不输出密钥值：`FRED_API_KEY=UNSET`。

| 探测 | 请求设置 | 结果 | 解释 |
|---|---|---|---|
| FRED Graph CSV单序列 | DGS10，as-of 2026-11-17，8秒超时 | HTTP 200，约0.99秒 | 单次连通成功；不能证明19源并发稳定 |
| 官方FRED observations API无密钥 | DGS10 JSON，as-of 2026-11-17，8秒超时 | HTTP 400，约0.54秒 | API密钥必需；快速错误说明主机可达，不等于API取数成功 |
| FRED Graph CSV批量 | 19个allowlist系列，4个并发，单次4秒超时、无重试，as-of 2026-11-17 | 0/19成功、19/19读取超时，总计约20.83秒 | 诊断探测比生产请求超时更严格；提示批量链路承压。此前P7保存的19请求超时记录与此方向一致 |

FRED官方文档说明，`fred/series/observations` 支持JSON、`realtime_start` / `realtime_end` vintage日期参数，且需要注册API key。[FRED observations API文档](https://fred.stlouisfed.org/docs/api/fred/series_observations.html)

### 已实现的数据请求行为

- 设置 `FRED_API_KEY` 时优先请求FRED官方JSON observations API，并请求as-of vintage日期；未设置时保留公开Graph CSV路径。
- 每次最多2次尝试，默认单次超时15秒，第一次失败后短暂退避；不做无限重试。
- 失败信息不包含API key；每个FRED序列的异常仍相互隔离。
- fetch失败后，只有DuckDB中已有且观察日期未超过上限的序列才允许作为缓存回退。缓存年龄上限：日频默认14天，周频35天，月频120天。过期缓存不会进入特征。
- 报告把缓存写成 `AVAILABLE_CACHED`，保留上次检索时间与哈希，并仍报告本次抓取失败原因。缓存值并不代表本轮实时采集成功，也不用于冒充历史点时数据。
- `.github/workflows/crs-daily.yml` 从 `${{ secrets.FRED_API_KEY }}` 注入变量。代码无法读取或判断仓库Secret是否已配置。没有在功能分支之外改动任何分支。

本地完整采集仍没有执行，因为批量源诊断已表明连接不稳定；本轮不报告新的CRS总体覆盖率或分数。P7历史报告中的38.5%覆盖率是此前一次运行记录，不应与本轮单源探测混合。

## 数据源健康监控

新增 `source_health.json` 仅存储每个报告日期的source status，不保存原始市场序列、DuckDB、Parquet或私人持仓。报告最多汇总最近30个不同as-of报告日，并输出：

- 实时成功率、缓存使用数、失败数、超时数与连续失败次数；
- 最新观察日期和观察滞后天数；
- 成功/缓存采集中 `published_at` 缺失率；
- 最新数据质量、授权状态和失败原因。

GitHub Actions缓存单独包含状态机JSON与来源健康JSON；不会缓存包含受限OAS数据的DuckDB。新健康指标没有被用于改变评分。

## 历史PIT准备度

`crs_fred_vintages` 按指标、观察日期、来源ID和FRED vintage日期保存不同版本，避免同一观察日的后续版本覆盖旧版本。只有官方API路径返回的数据才进入此表。当前CSV路径仍写入常规当前观察表。数据库表的测试记录全部是合成测试行，本轮没有真实FRED API key，因此未写入真实vintage。

FRED vintage日期只能表达数据在某个日期版本下的值，不证明精确盘中发布时间。各FRED序列的修订行为、历史覆盖和使用授权仍需单独验证；ICE BofA OAS仍标记为受限。Yahoo代理数据不具备完整点时快照。因此：

| 历史时期 | 数据状态 | PIT状态 | 回测状态 |
|---|---|---|---|
| 2022加息/债券压力 | 未创建真实数据集；只有FRED日期级存储支持和合成结构测试 | `NOT_PIT_VERIFIED` | 不可进行可信CRS回测 |
| 2020疫情冲击 | 未创建真实数据集；关键发布版本、代理快照及授权未证实 | `NOT_PIT_VERIFIED` | 不可进行可信CRS回测 |
| 2008金融危机 | 未创建真实数据集；OAS历史范围和完整跨资产PIT来源不足 | `NOT_PIT_VERIFIED` | 不可进行可信CRS回测 |

2022被列为下一步优先研究窗口，但没有把当前修复包装成“已建成2022数据集”。须先配置密钥，逐条核验历史覆盖与revision vintage、首次可得发布时间、授权范围及供应商原始快照，然后才可将经过审计的输入标成点时可用。

## 验证记录

- `compileall`：通过。
- 完整本地离线 `unittest`：104项通过（详见 `CRS_PHASE8_TEST_LOG.txt`）。
- 新增第八阶段测试：9项，通过重试与密钥脱敏、API as-of参数、缓存回退/新鲜度、跨vintage保存、30期健康统计、三种报告格式保留等边界。
- 实时FRED探测：单次CSV成功、19源短超时探测失败；这是网络诊断，不是单元测试，也不是完整CRS运行。
- GitHub Actions远端CI：本轮未触发、未验证。不能将本地通过称作远端CI通过。
- 完整CRS评分：本轮没有运行完整价格与全部来源采集，没有发布新分数。

## 修改文件与理由

| 文件 | 修改理由 |
|---|---|
| `nq_sentinel_pro/sentinel/crs/fred.py` | 官方API JSON读取、as-of vintage请求、有界重试、错误密钥脱敏；CSV仍作无密钥路径 |
| `nq_sentinel_pro/sentinel/crs/collector.py` | 单源失败隔离，标记新鲜缓存回退与实时请求失败 |
| `nq_sentinel_pro/sentinel/crs/storage.py` | 记录FRED溯源元数据、限制缓存年龄、新增独立日期级vintage表 |
| `nq_sentinel_pro/sentinel/crs/health.py` | 计算可审计的30报告日源健康统计并保存仅含状态的快照 |
| `nq_sentinel_pro/sentinel/crs/runner.py` | 读取DuckDB缓存、报告源健康状态；评分路径保持不变 |
| `nq_sentinel_pro/sentinel/crs/report.py` | Markdown和HTML来源健康表 |
| `nq_sentinel_pro/tests/test_crs_phase8.py` | 新增8项第八阶段自动化测试 |
| `.github/workflows/crs-daily.yml` | 安全注入可选的FRED_API_KEY，并缓存来源健康状态JSON |
| `docs/CRS_BACKTEST_READINESS.md` | 更新日期级vintage存储的能力边界，保持全部危机时期未验证 |
| `docs/CRS_PHASE8_TEST_LOG.txt` | 保存本轮compile与完整单测日志 |
| `docs/CRS_PHASE8_AUDIT.md` | 记录诊断、实现、限制和未完成验收项 |

## 修改边界与未完成项

- 七模块权重、指标集合、固定阈值、60/40规则、85%覆盖率门槛、关键数据发布门槛未修改。
- NQ-Sentinel原有评分和权重未修改。
- 没有执行交易、没有修改 `main`、没有合并或创建PR。
- 需要在GitHub仓库设置 `FRED_API_KEY` Secret 后，才能验证官方API运行；密钥不应写入仓库、报告或聊天。
- 远端CI、Actions运行、API密钥路径真实取数、每日稳定成功率、2022/2020/2008 PIT数据集及危机回测仍未验证。
- CRS保持 `PROVISIONAL_RESEARCH_ONLY`。
