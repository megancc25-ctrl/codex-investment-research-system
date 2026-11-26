# ASWM 1.0 — AI增长与再入场研究

正式规格：[Issue #5](https://github.com/megancc25-ctrl/codex-investment-research-system/issues/5)。本轮连续开发亦纳入[Issue #6](https://github.com/megancc25-ctrl/codex-investment-research-system/issues/6)统一控制。

## 使用

根目录运行：

```powershell
./.venv-market-risk/Scripts/python.exe -m market_risk.aswm serve --port 8765
```

访问 `http://127.0.0.1:8765/aswm.html`。与FRIE使用同一回环HTTP服务和SQLite文件，不创建第三套采集服务。总览和FRIE页面已有入口。运行时必须在仓库根目录，或使用明确的数据库/输出绝对路径。

```powershell
./.venv-market-risk/Scripts/python.exe -m market_risk.aswm evaluate
./.venv-market-risk/Scripts/python.exe -m market_risk.aswm evaluate --input data/aswm/input.json
./.venv-market-risk/Scripts/python.exe -m market_risk.aswm evaluate --redact --output outputs/aswm-shareable
./.venv-market-risk/Scripts/python.exe -m market_risk.aswm registry
./.venv-market-risk/Scripts/python.exe -m market_risk.aswm validate --input data/aswm/history.json --upside-threshold 0.10
./.venv-market-risk/Scripts/python.exe -m market_risk.frie modules --input data/research/modules.json
```

报告生成在被Git忽略的outputs目录，真实输入在data目录。`--redact`移除预算和绑定私人预算的摘要hash；它只是隐私处理，不授予来源数据公开分发权。没有采集器、付费调用、外部通知或自动交易。

## 三问分开

1. `growth`与`applications`：AI商业化是否有持续付费与单位经济性证据？
2. `hardware`：推理需求是否传到外部订单和半导体盈利/毛利？
3. `admission`与`budget`：估值、FRIE/CRS和私人预算是否允许增加风险？

**设计裁定：**用户明确要求产业周期与估值/仓位准入不能混为一谈。Issue中的S3合理估值要求保留为独立准入门槛，不用估值失败抹去已经成立的产业S3。这不改变候选45/65/80阈值；S3与BLOCKED完全可以并存。

S0等待、S1领先、S2产业确认、S3持续增长及UNKNOWN是研究阶段。BLOCKED是另一条准入轴。模型恒为NOT_VALIDATED，执行恒false。可产生“研究候选”而不产生任何买入指令或生产仓位。

数量覆盖不足80%、关键信用/反应未知时不输出完整等级。分别报告数量和权重覆盖、固定100分分母上的下上界；未知项不被断言为0或重新分配权重。CONFIRMED候选强度1、IMPROVING强度0.5、NOT_TRIGGERED强度0；这是未校准研究参数。每个经济事件只能支持一个计分归属，按权重降序/编号稳定选择，不依录入顺序。

五个不同市场确认日必须同时存在于显式exchange_session_closes和condition_met=true的session_confirmations中；重复跑五次或重复同日不算五日。两个季度必须为不同YYYYQn、已可得且可比披露。原始事实在该证据available_at冻结，未来季度或未成熟收益不能事后自动补入同一证据。

## 输入事实字典

外层证据沿用FRIE：signal_id/evidence_id/economic_event_id/source_url/quality/license_status/license_ref/observed_at/available_at/expires_at/rationale/counter_evidence/supersedes_evidence_id，增加facts对象。人工status不能越过事实计算，CONFLICT可以显式冻结判断。

|SW|facts字段（true/false/null严格区分）|
|---|---|
|01|commercial_breakthrough、paid_business_model|
|02|businesses数组：business_id、paid_growth、renewal_improving、roi_positive；至少2个独立企业|
|03|businesses数组：business_id、ai_revenue_growth、unit_economics_improving；至少2个独立企业|
|04|actual_workload_growth、compute_demand_growth、hardware_orders_growth；token_only=true不算确认|
|05|ocf_growth、fcf_growth、capex_change有限增长率，roic_improving；FCF因削减CapEx改善不等于硬件利好|
|06|independent_external_orders、order_conversion、utilization_improving；circular_financing_only=true不支持|
|07|spread_type=TECH_MATCHED、matched_rating/matched_maturity、spreads_bp至少21个已完成匹配交易日、sustained_credit_stability；HY_PROXY不替代|
|08|one_day_reactions：economic_event_id、positive_surprise、industry_adjusted、matured、contaminated、excess_return；event_time、expectation_available_at、end_time、available_at均有时区且顺序合法。至少5独立利好，>=3正且中位数>0；five_day_improving/twenty_day_improving和对应matured_at，bad_news_muted另核|
|09|sox_closes、ndx_closes显式完成交易日同序列，breadth_improving、medium_term_trend；仅IGV/SMH不充分|
|10|scope=SEMICONDUCTOR、eps_revision_trend=DOWN/STABILIZING/UP、orders_improving、margins_improving|

持续披露字段：quarterly_releases=[{period:YYYYQn,available_at:带时区ISO}]、comparable_quarters。未完整定量的指标是有源审核事实，不能被称作独立实采或供应商已验证。

## 私人预算与外部约束

运行时只从本地 `data/aswm/private.json` 读取账户参数；模板位于 `config/aswm/private.example.json`，不含真实值。未知净值/压力/费用/汇率/流动性不填0。已确认的持仓摘要仅保存本地；没有推断净值或币种。

TOTAL_ACCOUNT代表从当前NAV起，全部现有与新增仓位共同消耗预算：上限=min(1,流动性限额,(损失预算−其他资产/FX/费用/不确定性准备)/半导体压力损失率)。INCREMENTAL_ADDITIONAL则明确只给新增仓位预算，上限增加现有权重，不能混用这两种语义。剩余空间为上限减当前权重，下限0；金额计算还需要真实NAV。无杠杆，已完成减仓不生成新的待办。

浏览器POST拒绝账户/私人配置；通过CLI读取绝对外部私有路径时须显式指定，仓库内只接受data/aswm。未保存任何凭据。私人配置错误只阻止预算，不中止其他研究。

风险上下文crs/valuation必须有与信号相同的审计来源、质量、准入和时间字段。CRS缺失/严重、估值FAIL/UNKNOWN、FRIE缺失/L3/L4、预算不足都阻止准入。浏览器不能伪造本地FRIE等级，服务器从真实本地证据重新计算；CRS外部实时接口尚未获准，不假装已连接。

## 历史、API与验证

原有SQLite审计新增aswm命名空间，原FRIE和V3数据不迁移或覆盖。历史可复算；新证据ID显式替代同信号旧记录，过期不复活旧判断。状态可降级/失效，只有阶段/实质证据/准入/预算变化记录本地通知；同一经济事件重复来源和重复运行不累计报警。

GET `/api/aswm/snapshot|history|registry|template`、`/api/aswm/report.json|md|html`；POST `/api/aswm/evaluate`。GET `/api/research/snapshot`给出四项目和六模块状态。原NQ `/api/report.*`新增独立ASWM栏目和统一状态，原风险分数不相加。

验证工具支持多个扩展训练滚动切分、各窗口的purge和指标、独立留出、买入持有/SMA/趋势基准、下一收盘执行、费用、回撤、Sharpe（显式频率和无风险率）、错过上涨、误报/漏报和可选事件提前时间。缺失信号不补持仓，缺口存在则不生成完整ASWM策略路径。消融使用调用者按相同历史门槛重新计算的阶段数组；不是任意扣分代替阶段重算。

目前只完成合成正确性验证，真实历史PIT、独立事件提前量、市场误报/漏报均未验证，不给编造数值。所有报告保持NOT_VALIDATED。
