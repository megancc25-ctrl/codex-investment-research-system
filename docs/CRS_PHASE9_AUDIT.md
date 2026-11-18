# CRS 1.0 第九阶段：跨运行缓存与状态语义审计

审计日期：2026-11-18
工作分支：`feature/crs-v1.0`
本阶段目标：对第八轮审计提出的问题进行代码核验和可安全实施的修复，不增加指标、不改变CRS权重/评分门槛，不改变NQ-Sentinel评分规则。

## 审计结论

第八轮审计的核心技术判断合理：

1. 第八阶段云端工作流没有恢复或保存DuckDB，而缓存回退依赖DuckDB，因此跨运行云端缓存此前并未建立。
2. FRED官方API密钥路径没有真实运行证据；本机密钥未配置，GitHub Secret状态不可见。代码适配不等于数据验收。
3. 流动性告警此前只读取布尔值，没有统一检查状态；`value=false`配上 `MISSING` 状态仍可能进入告警层。
4. 第八阶段审计正文将测试数写为104，而日志是105。已纠正审计正文为105；本轮本地重跑也确认此前105项通过。
5. 历史PIT数据与危机回测仍未建立，结论合理。

修复跨运行缓存的工程路径已完成，但有意保持**空的许可批准清单**。目前没有任何FRED序列获准写入Actions缓存，因此缓存数据库可以恢复，但默认不会持久化未经审核的序列值。FRED API条款指出，FRED API提供数据并不会覆盖第三方数据所有者的版权和限制；因此不能把“API可下载”当作上传/缓存授权。[FRED API使用条款](https://fred.stlouisfed.org/docs/api/terms_of_use.html)

## 第九阶段修改

### 1. DuckDB跨运行持久化，按许可隔离

- 新增独立的 `data/crs/fred_cache.duckdb`，与主 `crs.duckdb`、状态机JSON及来源健康JSON分开管理。
- GitHub Actions为该数据库配置独立缓存步骤、独立键和同分支restore-key。状态机、健康快照和FRED缓存不会互相覆盖。
- 只有 `license_status=APPROVED_FOR_INTERNAL_CACHE`、`cache_authorization`明确批准，且series ID匹配allowlist、source URL是对应FRED系列页、SHA-256格式正确、检索时间不晚于as-of、观察值日期有效的实时序列才可写入缓存。
- 每个缓存批次另算规范化观察日/数值SHA-256；恢复时重算校验。供应商响应SHA-256单独保留，但不声称能由它重建未归档的原始HTTP字节。
- `CACHE_LICENSE_APPROVALS` 默认为空；受限OAS无论如何都拒绝。只有逐系列许可审查完成后，才可显式更新批准表。
- 读缓存时检查来源ID、来源URL、质量、授权标记及原始响应SHA-256字段的格式/行间一致性，并重新计算规范化序列SHA-256。原始HTTP响应字节未归档，因此不能重算原始响应SHA-256，也不能把它表述为原始来源真实性证明。超过日频14天、周频35天、月频120天的新鲜度上限时不回退，并计入过期数量。
- `crs_fred_vintages` 仍是历史vintage表；独立FRED缓存仅保留每个获准序列的最新抓取批次，不替代历史PIT存档。

### 2. 采集结果逐项计数

报告JSON、Markdown和HTML共用的内容现包括：

- FRED预期系列数；
- 实时成功数；
- 缓存回退数；
- 过期缓存系列数；
- 来源/授权/溯源不合格而拒绝缓存的系列数；
- 完全缺失数；
- 实际写入独立缓存数据库的系列数。

缓存回退状态仍为 `AVAILABLE_CACHED`，并保留实时请求失败原因。缓存失败不会被报告为实时成功。缓存被拒绝或过期时，指标继续保持缺失/不足，评分门槛不变。

### 3. 流动性告警状态与数值统一

新增共享 `read_feature`，由 `alerts.py` 和 `runner.py` 共用：

- 只有 `AVAILABLE`、值非空且符合预期类型时，才将特征值交给告警逻辑；
- `MISSING`、`INSUFFICIENT_DATA`、未知状态、状态与值不匹配、过期值都不用于确定性告警；
- `synchronized_three_asset_down_20d` 必须是布尔值；未知或不匹配状态使流动性状态回到 `INSUFFICIENT_DATA`，并写入数据限制；
- 已确认的融资异常仍可作为独立 `FUNDING_STRESS_ONLY` 观察，不把未知的同步状态补成false。

告警阈值及合并规则未改。

### 4. 测试数字与审计文档

- 第八阶段审计报告中104项数字已改为105项，与第八阶段测试日志一致。
- 第九阶段新增7项测试，覆盖状态和值不匹配、stale状态、授权过滤、来源/哈希验证、缓存过期计数、运行级采集计数与报告输出。

## 仍未通过的验收

| 验收项 | 本轮状态 | 说明 |
|---|---|---|
| FRED 19系列 | 未验收 | 第八轮本地短超时探测为0/19；本轮没有API密钥，未重新跑完整19系列生产时限请求 |
| FRED API密钥路径 | 未验收 | 本机 `FRED_API_KEY=UNSET`；仓库Secret不可读取 |
| 云端跨运行缓存 | 代码配置完成，端到端未验收 | `.github/workflows/crs-daily.yml` 已分开缓存数据库；当前许可批准清单为空，没有任何FRED值被允许上传缓存 |
| 连续两次Actions恢复 | 未验收 | 没有两次可核验Actions运行；默认分支仍没有CRS workflow。GitHub规定workflow_dispatch文件必须存在于默认分支，故本轮不改main、不声称能触发云端验收。[GitHub手动运行workflow说明](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow) |
| 完整CRS评分 | 未通过 | 没有运行完整实时采集；未取得覆盖率与关键指标完整性通过证据，不发布分数 |
| 2022/2020/2008历史PIT | 未通过 | 没有真实历史数据集；vintage日期不等于首次公开时刻，原始供应商响应尚未归档，授权未逐项审核 |
| 危机回测 | 未完成 | 未报告召回率、误报率、提前量或危机识别准确率 |

本阶段没有把单元测试通过当成数据、授权或云端运行验收。CRS继续保持 `PROVISIONAL_RESEARCH_ONLY`。

## 测试结果

- `python -m compileall -q sentinel tests local_crs_portfolio.py`：PASS。
- `python -m unittest discover -s tests -v`：112项通过。
- 完整控制台日志：`docs/CRS_PHASE9_TEST_LOG.txt`。
- GitHub Actions：本轮没有真实运行记录；本地测试与远端CI明确分开。

## 修改文件及理由

| 文件 | 理由 |
|---|---|
| `nq_sentinel_pro/sentinel/crs/feature_status.py` | 统一状态和值解析，未知、stale或不匹配时fail-closed |
| `nq_sentinel_pro/sentinel/crs/alerts.py` | 告警层使用共享状态解析，报告同步状态与数据限制 |
| `nq_sentinel_pro/sentinel/crs/runner.py` | 创建并恢复独立缓存数据库；报告实时、缓存、过期、不合格和缺失计数；证据层复用状态解析 |
| `nq_sentinel_pro/sentinel/crs/storage.py` | 独立缓存DB schema；保存/加载授权通过且溯源完整的数据；校验规范化内容哈希；拒绝过期、restricted和不完整来源 |
| `nq_sentinel_pro/sentinel/crs/fred.py` | 加入默认空的许可批准映射；受限系列不可通过映射绕过 |
| `nq_sentinel_pro/sentinel/crs/collector.py` | 报告缓存授权状态，不混淆live与cached |
| `nq_sentinel_pro/sentinel/crs/report.py` | 展示FRED本次采集及缓存计数 |
| `.github/workflows/crs-daily.yml` | 将FRED数据缓存与状态/健康文件分开管理 |
| `nq_sentinel_pro/tests/test_crs_phase8.py` | 更新独立缓存数据库接口的回归测试 |
| `nq_sentinel_pro/tests/test_crs_phase9.py` | 新增第九阶段状态、许可、溯源、持久化及计数测试 |
| `docs/CRS_PHASE8_AUDIT.md` | 更正105项测试数并补记第九阶段复核 |
| `docs/CRS_PHASE9_AUDIT.md` | 记录核验判断、修复范围和未通过的验收项 |
| `docs/CRS_PHASE9_TEST_LOG.txt` | 保存完整本地测试运行日志 |

七模块、评分权重、阈值、85%门槛、60/40方法和NQ-Sentinel评分规则均未修改；没有修改main、创建或合并PR，也没有真实交易。

## 第十阶段补充核验

缓存新鲜度分成不同概念：原有的缓存有效性门槛仍按最新观察值年龄计算；第十阶段新增 `cache_retrieval_age_days`，反映检索日期距as-of日期的天数。来源诊断另外提供 `observation_age_days` 和 `publication_lag_days`。如果来源没有真实 `published_at`，发布时间滞后保持 `null`，不以观察日推算。哈希仅用于发现保存后规范化值变化；数据和摘要同处可修改数据库，不构成独立防篡改证据。
