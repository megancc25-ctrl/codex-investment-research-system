# CRS 1.0 第四阶段审计与修正报告

## 范围与结论

本阶段仅处理数据溯源列语义和三资产同步下跌证据语义。未改变七模块结构、模块权重、固定阈值、60/40评分方法、85%覆盖门槛、关键指标门槛、NQ-Sentinel规则或L0-L4确认规则；未新增风险指标、未接入新的外部数据源、未发出交易指令。

结论：两项缺陷已修复并添加单元及端到端回归覆盖。合成数据端到端结果因不足21个共同交易日而保持 `DATA_INSUFFICIENT`，未发布完整CRS分数。产品状态仍为 `PROVISIONAL_RESEARCH_ONLY`；没有完成历史危机回测。

## P1-1：DuckDB来源字段

### 修正

- `crs_features.source_id` 现读取派生记录的 `source_id`；缺失时写 `UNKNOWN`。
- `crs_features.source_url` 仅读取单独的 `source_url` 字段；未提供可信链接时使用 SQL `NULL`。
- 来源显示名称、来源ID和ticker分别保存在metadata的 `source`、`source_id`、`ticker` 中。元数据继续保存 `raw_sha256`、`observation_date`、`published_at`、`retrieved_at` 和 `license_status`。
- `crs_observations` 的行情来源ID不再从symbol猜测；来源链接只有显式可信的HTTPS URL才写入。FRED来源链接在确认是HTTPS链接时写入URL列，来源显示值留在metadata。空值使用 `UNKNOWN` / `NULL`，不会伪造来源URL。

### 回读结果

DuckDB回读测试通过，五个独立证券来源ID保持一一对应：

| 特征 | 预期 source_id | ticker |
|---|---|---|
| NDX | `yahoo:^NDX` | `^NDX` |
| SOX | `yahoo:^SOX` | `^SOX` |
| IEF | `yahoo:IEF` | `IEF` |
| GLD | `yahoo:GLD` | `GLD` |
| DXY proxy | `yahoo:DX-Y.NYB` | `DX-Y.NYB` |

测试还验证来源名称没有写入 `source_id`、无可信指标级URL时为NULL、metadata中的来源和证券标识彼此一致，及原始快照哈希与各时间/授权字段均可读回。行情观察表的五个证券来源ID也通过独立回读断言。

## P1-2：同步下跌证据语义

`runner._evidence()` 根据特征状态和值区分证据：

- `AVAILABLE` 且值为 `true`：记录为支持证据。
- `AVAILABLE` 且值为 `false`：只在反向证据中记录“有效共同日期样本内未确认同步下跌”。
- `INSUFFICIENT_DATA`：记录在 `data_limits`，说明共同日期样本不足、无法判断。
- `MISSING`、特征不存在或值未知：记录在 `data_limits`，说明数据缺失、无法判断。

Markdown、JSON和HTML报告都包含独立的“Evidence limits”区块；不足/缺失不会进入反向证据。旧版没有显式状态但有非空布尔值的特征兼容推断为 `AVAILABLE`。

语义回归测试覆盖：共同样本可判定为false、可判定为true、少于21个共同日期导致不足、缺少特征、显式 `INSUFFICIENT_DATA` 和显式 `MISSING`。只有前者允许出现“没有确认同步下跌”的反向证据。

## 端到端验证

集成测试使用本地模拟的五类行情序列和FRED响应，经过 `collect()` 特征派生、DuckDB落库及回读，再生成JSON、Markdown和HTML。样例故意只提供20个共同日期，系统输出 `DATA_INSUFFICIENT`、`score=null`，并在三种报告中显示不能判断的限制；报告不生成错误的低风险反向证据。该测试不访问实时数据源。

NQ-Sentinel权重回归测试通过，既有规则文件没有被本阶段修改。

## 文件修改清单及理由

| 文件 | 修改理由 |
|---|---|
| `nq_sentinel_pro/sentinel/crs/storage.py` | 修正 observations/features 的 source_id、source_url、source显示名称字段映射；保留 provenance metadata。 |
| `nq_sentinel_pro/sentinel/crs/runner.py` | 将同步下跌特征按 AVAILABLE / INSUFFICIENT_DATA / MISSING 分流，避免缺失值成为反向证据。 |
| `nq_sentinel_pro/sentinel/crs/report.py` | 展示单独的数据限制区，确保JSON、Markdown、HTML呈现一致。 |
| `nq_sentinel_pro/tests/test_crs_engine.py` | 新增来源字段数据库回读、证据语义矩阵及collect-to-report端到端回归测试。 |
| `docs/CRS_PHASE4_AUDIT.md` | 记录本阶段改动、边界、验证结果和状态限制。 |
| `docs/CRS_PHASE4_TEST_LOG.txt` | 保存要求的编译与完整测试运行日志。 |

## 验收状态（彼此独立）

| 项目 | 状态 | 说明 |
|---|---|---|
| 本地离线测试 | 通过 | compileall成功；unittest 77项通过。完整输出见 `CRS_PHASE4_TEST_LOG.txt`。 |
| GitHub Actions远端CI | 未验证 | 本次没有取得关联远端workflow run的成功记录；本地测试不等于远端CI。 |
| 实时数据采集 | 未验证 | 端到端流程只使用测试夹具；不能据此声称实时采集成功。 |
| 完整CRS评分可发布 | 否（本次测试运行） | 样例不足21个共同交易日，并存在未接入关键源；结果为 `DATA_INSUFFICIENT`，score为空。 |
| 研究状态 | `PROVISIONAL_RESEARCH_ONLY` | 阈值和权重未经验证；未完成2008、2020、2022或其他历史危机PIT回测。 |

## 剩余限制

当前生产数据连接仍缺MOVE、市场广度、连续Repo利率/成交量、CDX IG/HY等关键源；DXY、IEF和GLD仍是标明的代理。当前-vintage FRED与未验证的Yahoo历史记录不构成已验证的PIT历史。不得把本次模拟测试描述成实时验证或历史危机回测。
