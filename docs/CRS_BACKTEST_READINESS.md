# CRS 1.0 历史回测准备度

## 当前判定

**2008、2020、2022三段均未达到可审计的 point-in-time 回测就绪状态。** 本文没有生成、填补或推断任何历史 CRS 评分。没有真实 vintage、发布时间和可追溯快照的数据不得标记 `PIT_VERIFIED`。

| 数据组 | 适配器/来源 | 可核实的历史范围 | 发布时点可验证 | 修订/vintage | 授权限制 | PIT判定 |
|---|---|---|---|---|---|---|
| HY/IG/CCC OAS | FRED ICE BofA序列 | HY/IG 页面说明自2026年4月起FRED只保留三年观察值；当前实际导出首末日未现场采集 | 否；适配器 `published_at=null` | 第八阶段加入FRED API按as-of查询和 `crs_fred_vintages` 日期级快照；尚无真实API数据写入 | LICENSE_RESTRICTED；内部使用及再分发限制须单独审查 | NOT_PIT_VERIFIED |
| 10年/30年/实际利率、VIX、SOFR/IORB、NFCI/STLFSI、准备金等 | FRED CSV回退；配置 `FRED_API_KEY` 后使用官方 observations API | API可按as-of vintage日期查询；实际历史覆盖尚未逐序列实测 | 否；`published_at`仍为null，日期级vintage不等于盘中首次发布日期 | 第八阶段增加以指标、观察日、来源、vintage日为键的快照表；当前没有实际回填2022 vintage | 需逐序列及API条款确认 | NOT_PIT_VERIFIED |
| NDX、SOX、IEF、GLD、DX-Y.NYB | Yahoo Finance/yfinance最近10年请求 | 配置请求窗口约为运行日往前10年；实际首末观测、复权和历史修订未独立核验 | 否 | 当前下载历史可能随供应商调整；没有历史下载时间证据 | 需审查供应商条款 | NOT_PIT_VERIFIED |
| 美国住宅价格、销售、CPI、按揭 | FRED月度/周度当前 vintage | 本轮未逐序列实测起止日期 | 否；没有逐次发布日期 | 可能修订；未存 vintage | 需逐序列确认 | NOT_PIT_VERIFIED |
| 市场广度、MOVE、Repo连续数据、CDX IG/HY | 无自动适配器 | 无已接入历史 | 否 | 无 | 需要授权或可信来源 | NOT_AVAILABLE |

## 事件窗口可用性

| 危机期间 | 现有系统的覆盖可能性 | PIT判断 | 是否可做有效CRS回测 |
|---|---|---|---|
| 2008全球金融危机 | Yahoo最近10年请求不覆盖；FRED OAS当前可见历史也不覆盖2008；若外部授权归档不可用则关键数据不可恢复 | NOT_PIT_VERIFIED | 否 |
| 2020疫情冲击 | 价格供应商回溯数据可能包含该期间，但无当时抓取/发布时间证据；FRED宏观数据当前 vintage 不能证明当日可得值；OAS历史受限 | NOT_PIT_VERIFIED | 否 |
| 2022利率/信用重定价 | 价格供应商回溯数据可能包含该期间，但无当时抓取/发布时间证据；当前 vintage与发布版本不等价 | NOT_PIT_VERIFIED | 否 |

“可能包含”只表示供应商历史窗口可能覆盖，不构成观察值存在、授权有效或PIT合格的证明。需要逐源实测后才能把可用性升级。

## 当前回测实现的限制

第八阶段的存储改进只提供了日期级FRED vintage快照能力。运行环境未设置 `FRED_API_KEY`，本轮没有取得或保存2008、2020、2022的FRED vintage 数据；Yahoo代理也没有点时归档。`crs_fred_vintages` 中的合成测试行只验证键和保留行为，不是市场数据。故危机数据集仍为空，三个时期状态不变。

目前也没有保存供应商原始HTTP响应字节；SHA-256只校验当时输入载荷的摘要，不能从摘要还原数据。因此即便之后产生FRED API vintage行，还需设计受控、授权的不可变原始载荷归档，才能支持完整字节级复核。

`evaluate_crisis_backtest` 要求显式 `decision_at`、来源证据、观察/发布/检索时间、vintage ID、SHA-256和授权状态，并拒绝只有 `pit_verified=true` 的行。它会检查元数据结构和时间先后关系，但不会从供应商独立重取文件来证明哈希真实性，也不能单靠代码证明授权声明属实；仍需审计人员验证证据源。没有真实历史发布版本、时间戳证据及可审计授权的数据不得标成 PIT_VERIFIED。

达到回测准备度前，最少应归档：

1. 每条输入的 as-of 时间、观察时间、首次公开时间、下载时间和来源；
2. 可重放的原始文件/供应商 vintage ID、SHA-256及不可变存档位置；
3. 授权/再分发范围和数据修订记录；
4. 对应评分配置哈希、缺失门槛版本和无未来信息证明；
5. 预先登记且不随结果调参的事件窗口、阈值和样本外区间。

达到这些条件前，报告必须保持 `NOT_PIT_VERIFIED` 或 `BLOCKED`，不展示命中率、预警提前量或误报率为模型有效性证据。
