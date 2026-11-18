# CRS 1.0 数据覆盖与来源矩阵

审计目标：`feature/crs-v1.0`。本矩阵区分了“代码中配置/接入”与“已现场验证可用”。此次未能取得完整实时采集，因此除 FRED OAS 页面明确披露的限制外，不推断实际下载的首末观测日期。

| 指标 | 当前来源/代码 | 数据观察范围 | 发布时点/修订 | 质量与许可 | CRS处理与当前状态 |
|---|---|---|---|---|---|
| 市场广度（breadth above 200DMA） | 配置规则存在；无成分股及广度数据适配器 | 无已接入观测 | 不适用 | MISSING；无许可来源 | 关键评分指标；缺失时禁止发布完整分数 |
| MOVE | 配置规则存在；FRED/Yahoo 白名单未接入 MOVE | 无已接入观测 | 不适用 | MISSING；无许可来源 | 关键评分指标；缺失时禁止发布完整分数 |
| Repo 利率/成交量 | 有 repo percentile 评分规则；无连续利率/成交量采集。手工 `repo_extreme` 仅是事件标记 | 无连续观测 | 手工事件时间可验证，但不构成序列 | MISSING；手工源需单独审查 | 关键评分指标；缺失时禁止发布完整分数 |
| CDX IG/HY | 无自动 CDX 源；仅有可人工提供的 `cdx_hy_widening` 布尔事件 | 无点位/历史序列 | 手工事件可提供发布/检索时间；没有可回溯序列 | MISSING；授权/来源依输入确认 | 不得将手工布尔事件描述为 CDX 点位或历史数据 |
| DXY | 优先使用 FRED `DTWEXBGS` 广义美元指数；另有 Yahoo `DX-Y.NYB` | FRED实际下载日期未现场核验；Yahoo请求参数为 `period=10y`，实际首末观测未保存为验证证据 | FRED当前 vintage，无发布日期；Yahoo发布日期/修订时点未知 | FRED许可逐序列复核；Yahoo为未核验代理 | 广义贸易加权美元不是 ICE DXY；Yahoo报价也标为代理/待核验 |
| 美国国债总回报 | Yahoo `IEF` ETF价格 | 请求最近10年；准确观测起止日期未现场核验 | 无逐条发布时间或历史修订证据 | 未核验供应商代理；许可条款需审查 | 只能标成 IEF 债券价格代理，不是广义国债总回报 |
| 黄金 | Yahoo `GLD` ETF价格 | 请求最近10年；准确观测起止日期未现场核验 | 无逐条发布时间或历史修订证据 | 未核验供应商代理；许可条款需审查 | 只能标成 GLD 代理，不是现货黄金总回报 |
| 房地产 | FRED `CSUSHPISA`、`EXHOSLUSM495S`、`MORTGAGE30US`、`CPIAUCSL` | 美国月度/周度序列；实际首末观测本轮未拉取核验 | 当前 vintage；数据修订和发布时间历史未接入 | FRED逐序列授权需审查 | 仅美国住宅市场代理，不代表全球房地产；未证明PIT |
| HY OAS | FRED/ICE `BAMLH0A0HYM2` | FRED说明自2026-04起仅保留三年观察值；实际下载边界未现场核验 | 当前 vintage；适配器 `published_at=null` | `LICENSE_RESTRICTED`；分发受限制 | 禁止据此声称完整2008/2020历史或外部分发原始/派生数值；[FRED系列说明](https://fred.stlouisfed.org/series/BAMLH0A0HYM2) |
| IG OAS | FRED/ICE `BAMLC0A0CM` | FRED说明自2026-04起仅保留三年观察值；实际下载边界未现场核验 | 当前 vintage；适配器 `published_at=null` | `LICENSE_RESTRICTED`；分发受限制 | 不具备旧历史的当前FRED CSV vintage；[FRED系列说明](https://fred.stlouisfed.org/series/BAMLC0A0CM) |
| CCC OAS | FRED/ICE `BAMLH0A3HYC` | FRED序列接入；实际下载边界本轮未核验 | 当前 vintage；无发布版本存档 | `LICENSE_RESTRICTED` | 仅作为源级输入，不应暗示其已单独进入CRS评分规则 |
| 其他利率/流动性 | FRED `DGS10`、`DGS30`、`DFII10`、`SOFR`、`IORB`、`NFCI`、`STLFSI4`、`WRESBAL`、`RRPONTSYD`、`WTREGEN`、`VIXCLS` | 当前FRED CSV；各序列起始日不一致，未现场盘点 | `published_at=null`；当前 vintage 可能修订 | 除显式OAS许可限制外仍须逐序列审查 | 不能仅凭下载当前观测构建点时历史 |

## 运行报告元数据

修正后的采集/特征结构应为每个已接入来源写明 `source`、`observation_date`、`published_at`、`retrieved_at`、`quality`、`license_status`。当前系统缺少的来源须以 MISSING 或明确的代理/范围状态呈现；没有可验证发布时点时 `published_at` 保持空值。FRED API响应中的许可备注不是再分发许可。

历史范围字段中“请求最近10年”或“3年保留限制”不能替代实际数据首末日期。未来建立历史矩阵时应保存每次数据快照的首末观察日期、哈希、抓取时间和许可记录。
