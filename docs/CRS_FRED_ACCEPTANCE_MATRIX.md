# CRS FRED 19系列验收与授权矩阵

审查基准：2026-11-18  
适用分支：`feature/crs-v1.0`  
目的：在运行19系列真实验收前，分别确认访问、数据质量、持久化授权及PIT可用性。此表是验收清单，不是法律意见或授权证明。

## 当前门槛

- 本地 `FRED_API_KEY` 状态：`UNSET`。密钥值不写入代码、审计日志或报告；仓库 Secret 状态不能从当前集成中读取。
- 官方 FRED observations API 使用注册 API key。现有代码在密钥缺失时走 FRED graph CSV 当前版本回退；该回退不提供所需的历史 vintage 证明。
- `CACHE_LICENSE_APPROVALS` 目前为空。没有任何系列获准写入跨运行 GitHub Actions 缓存。
- FRED API 接入不自动授予底层第三方系列的缓存、内部研究或再分发权。需逐系列核对数据所有者条款。OAS 三个系列在代码中已固定标记受限，不进入缓存批准。
- 发布完整 CRS 分数、缓存许可和 PIT 资格是三个独立验收，不得互相推导。

## 逐系列矩阵

“FRED页面”链接到对应系列元数据页；“系列所有者/许可”需要根据页面来源说明及所有者条款完成核验。未完成的项目保持 `REVIEW_REQUIRED`。

| CRS key | FRED series ID | 数据用途 | FRED页面 | 当前缓存许可 | 实时采集验收 | PIT资格 |
|---|---|---|---|---|---|---|
| `hy_oas` | `BAMLH0A0HYM2` | HY OAS | [页面](https://fred.stlouisfed.org/series/BAMLH0A0HYM2) | `RESTRICTED`；拒绝云缓存 | 未验收 | `NOT_PIT_VERIFIED` |
| `ig_oas` | `BAMLC0A0CM` | IG OAS | [页面](https://fred.stlouisfed.org/series/BAMLC0A0CM) | `RESTRICTED`；拒绝云缓存 | 未验收 | `NOT_PIT_VERIFIED` |
| `ccc_oas` | `BAMLH0A3HYC` | CCC及更低评级OAS | [页面](https://fred.stlouisfed.org/series/BAMLH0A3HYC) | `RESTRICTED`；拒绝云缓存 | 未验收 | `NOT_PIT_VERIFIED` |
| `ust10y` | `DGS10` | 10年期国债收益率 | [页面](https://fred.stlouisfed.org/series/DGS10) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `ust30y` | `DGS30` | 30年期国债收益率 | [页面](https://fred.stlouisfed.org/series/DGS30) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `real10y` | `DFII10` | 10年期实际利率 | [页面](https://fred.stlouisfed.org/series/DFII10) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `vix` | `VIXCLS` | VIX收盘值 | [页面](https://fred.stlouisfed.org/series/VIXCLS) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `sofr` | `SOFR` | SOFR | [页面](https://fred.stlouisfed.org/series/SOFR) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `iorb` | `IORB` | 准备金余额利率 | [页面](https://fred.stlouisfed.org/series/IORB) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `nfci` | `NFCI` | 芝加哥联储金融状况指数 | [页面](https://fred.stlouisfed.org/series/NFCI) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `reserves` | `WRESBAL` | 联储银行储备余额 | [页面](https://fred.stlouisfed.org/series/WRESBAL) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `rrp` | `RRPONTSYD` | 隔夜逆回购余额 | [页面](https://fred.stlouisfed.org/series/RRPONTSYD) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `tga` | `WTREGEN` | 财政部一般账户 | [页面](https://fred.stlouisfed.org/series/WTREGEN) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `broad_usd` | `DTWEXBGS` | 广义贸易加权美元指数（不是ICE DXY） | [页面](https://fred.stlouisfed.org/series/DTWEXBGS) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `case_shiller` | `CSUSHPISA` | 美国Case-Shiller房价指数 | [页面](https://fred.stlouisfed.org/series/CSUSHPISA) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `home_sales` | `EXHOSLUSM495S` | 美国成屋销售 | [页面](https://fred.stlouisfed.org/series/EXHOSLUSM495S) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `mortgage30y` | `MORTGAGE30US` | 30年固定按揭利率 | [页面](https://fred.stlouisfed.org/series/MORTGAGE30US) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `cpi` | `CPIAUCSL` | 美国CPI | [页面](https://fred.stlouisfed.org/series/CPIAUCSL) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |
| `stlfsi` | `STLFSI4` | St. Louis Fed金融压力指数 | [页面](https://fred.stlouisfed.org/series/STLFSI4) | `REVIEW_REQUIRED` | 未验收 | `NOT_PIT_VERIFIED` |

## 每个系列必须补齐的审核证据

对每行系列，授权审核人应记录：

1. FRED页面显示的原始数据来源/所有者和使用条款链接；
2. 允许的用途（访问、内部分析、缓存、Artifact/报告展示、再分发）及期限；
3. 数据频率、实际历史首末日期、缺失和修订/vintage机制；
4. 首次公开时间能否验证；若不能，明确不能作为严格PIT输入；
5. 批准人、审核日期、证据链接/版本，以及是否可存入GitHub Actions缓存。

只有缓存授权明确通过的独立系列，才可加入 `CACHE_LICENSE_APPROVALS`。拒绝、未知、过期许可均保持不缓存。即使缓存许可通过，也不自动升级为 `PIT_VERIFIED`。

## 19系列真实运行记录模板

真实运行后，每个系列一行记录，且不记录密钥或原始数值：

| 字段 | 内容 |
|---|---|
| run URL / run ID / commit SHA | 真实GitHub Actions引用 |
| run started / completed UTC | 真实运行时间 |
| series key / series ID | 与上表一致 |
| auth mode | `FRED_API_KEY` / CSV fallback；只记模式，不记录值 |
| HTTP status / elapsed_ms / attempt_count | 请求层结果 |
| observations_count / latest_observation_date | 统计信息，不包含原始序列值 |
| vintage/as-of | API返回且代码保存的版本标识；不得称首次发布时间 |
| parse/quality/status | 成功、空值、结构错误、超时等明确状态 |
| license/cache authorization | 与本表审核结论一致 |
| failure_reason | 去密钥、去查询参数的安全错误摘要 |

运行报告只保存脱敏诊断。是否上传报告Artifact需先审核其中的源元数据和许可；禁止上传密钥、主数据库、FRED缓存数据库或原始序列文件。

## 下一步闸门

先由有仓库权限的操作者在 GitHub Actions Secrets 中设置 `FRED_API_KEY`，然后只回复“已配置”，不要在聊天中发送密钥。授权负责人逐条审核并填写允许用途。在密钥未配置前不开始19系列真实采集；在许可未明确前不启用任何FRED缓存。随后才进行单次逐系列脱敏诊断，再进入稳定性与跨运行缓存验证。
