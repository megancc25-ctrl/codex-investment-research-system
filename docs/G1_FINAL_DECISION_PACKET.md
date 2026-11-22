# G1_FINAL_DECISION_PACKET

2026-11-22；唯一依据：Issue #4，V2评论7074985967。本文件为最终集中决策入口；已有G1调查报告是历史交付，不重做十个来源调查。

**文档收口完成；G1真实准入NO-GO；G2/G3 NOT_STARTED；正式评分N/A。** 没有接受条款、读取凭据、发送行情请求或启用来源。本文件不是授权。

## 唯一待批准动作

是否允许按下述不可扩大的范围，完成一次纽约联储只读、内存处理的真实接口验证？一次测试批次最多3次GET，不是连续采集授权。

| 顺序 | URL | 数据日期 | 最大请求数 |
|---|---|---|---:|
|1|https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?startDate=2026-11-19&endDate=2026-11-19&type=rate|2026-11-19|1|
|2|https://markets.newyorkfed.org/api/rates/secured/tgcr/search.json?startDate=2026-11-19&endDate=2026-11-19&type=rate|2026-11-19|1|
|3|https://markets.newyorkfed.org/api/rates/secured/bgcr/search.json?startDate=2026-11-19&endDate=2026-11-19&type=rate|2026-11-19|1|

执行日期未安排，仅在明确批准后执行一次。数据日期固定，不自动改为最新日期；无HEAD探测、重试、重定向、替代域名或补充请求。任何失败立即结束批次。精确机器约束及证据哈希见 [nyfed_bounded_test_plan.json](../nq_sentinel_pro/sentinel/crs/nyfed_bounded_test_plan.json)。当前approved=false；纯离线校验器没有HTTP执行入口。

## 条款、声明与身份

[官方条款](https://www.newyorkfed.org/privacy/termsofuse)的Permissible Use明确涉及自动访问，但附带Conditions、Reference Rates专用声明、免责及Indemnification条件；本轮没有代表用户接受这些义务。条款原始响应SHA256为f94b131d66b80609dd192d5ce3520f1d48ab759b9e82ef7370111d2739392277，抓取时间2026-11-22T05:56:55.751766Z。

必须应用四类声明：Conditions第1段的来源版权与链接；Use Restrictions / Reference Rates中按数据名称和发布者填写的专用声明；使用参考利率名称描述产品时的非关联声明；SOFR/BGCR涉及DTCC Solutions上游数据的来源及责任声明。各原文位置、规范化模板哈希、变量填写方式已逐项登记在机器授权包。摘要不能替代正式声明；执行前须在私有操作环境核对并展示适用完整声明，不在公开日志展示行情数值。

上游条款说明纽约联储使用DTCC许可的输入，不构成CRS取得底层逐笔交易数据许可。本测试仅针对已发布参考利率输出；底层输入用途仍UNKNOWN且排除。若出现额外权利要求立即停止，批准不能覆盖未知用途。

[官方OpenAPI](https://markets.newyorkfed.org/static/docs/markets-api.yml)哈希5dbb331d86b91bfc115be9b5fe9c46735833a4f7280d33e4327e8acf7ad30d2b，核查时间2026-11-22T05:55:14.052419Z。文档确认search日期参数包含首尾日期，rate类型以及percent字段。此前合成percentRate字段不是当前文档定义，已补充percent解析并显式标记旧别名；若真实响应与文档不同，停止，不猜测映射。

请求Accept=application/json；User-Agent=CRS-G1-ReadOnly-Validation/1.2。未在所审文档中发现强制User-Agent格式或联系邮箱要求，此标识是项目自定控制；不套用SEC访问规则。不要携带身份凭据、Cookie或认证头，不读取环境、netrc、keyring或代理认证配置。

## 数据处理与停止条件

串行请求，间隔至少2秒；连接超时5秒、读取超时10秒，批次绝对上限45秒；每次响应上限256KiB、最多1条匹配记录。保持TLS校验，拒绝重定向。响应仅供应用内存解析，结束或异常即释放；禁止原始响应、利率、分位数、交易量、响应哈希或错误正文进入文件、数据库、缓存、聊天、工具输出、GitHub、日志或公开Artifact。

唯一允许留存的是经过类型校验的本地诊断：rate_type、http_status、record_count、observation_date、started_at、completed_at、elapsed_ms、bytes_received、schema_validation、unit_validation、error_code。错误只存枚举，不保存异常字符串。位置限定为Git忽略的nq_sentinel_pro/data/crs-g1-private，7日内删除，不上传。内存限制指应用层不主动持久化，不声称已控制操作系统分页或所有崩溃设施。

批准缺失或撤回、条款变化、额外许可要求、连接/TLS失败、超时、HTTP非200、跳转、超量、空响应、条数异常、类型/日期/单位/schema不符、请求预算耗尽，均立即停止；不自动更换入口、时间范围或重新授权。结果不能形成PIT历史证明、正式总分或生产状态。

## Treasury文档级补充

[官方迁移通知](https://home.treasury.gov/developer-notice-xml-changes)明确记录2022年旧data.treasury.gov接口退役及名义/实际收益率现代XML替代路径；数据家族对应关系已有文档支持，实时载荷等价与接口可用性未验证。原目录CC0仅对应已列名数据集，不泛化至所有服务。

2026-11-22T05:57:18.507763Z读取的[robots.txt](https://home.treasury.gov/robots.txt)为Allow /，响应哈希d1a6768683ed6be840be9e836e1d941677eca2bbda66cf5fa291365060b21aab。爬虫规则不等于数据许可或无限自动请求权；自动采集用途仍UNKNOWN，live_enabled保持false。未请求XML行情载荷，不以FRED密钥解释阻断。

其余八个既有通道沿用原证据和限制，没有仅凭公开页面升级授权；未增加新的候选源。19个FRED系列保持3项RESTRICTED、16项REVIEW_REQUIRED。

## 批准与不批准两条路径

| 决定 | 后续 |
|---|---|
|明确批准本包的条款范围和一次批次|先离线落实声明及全部控制，再仅执行上述至多3次请求；仅报告非敏感诊断。失败保持NO-GO；成功最多标注“有界接口验证通过”，持续G2权限仍未取得。|
|不批准、未回答或附加条件尚未满足|不发送任何真实请求，保留文档成果；G1真实准入NO-GO，G2/G3不启动。|

## 验证与冻结

原155项回归保留，新增8项授权包/日志边界/字段契约测试；完整目标为163项。实际测试、托管CI、提交SHA在最终交付消息中列示，以运行结果为准。CI只上传文档和离线审计产物，不配置密钥，不执行真实测试。

CRS 1.1基线81edbaa、main、七模块权重/阈值/状态机、持仓与生产开关不修改。Agent Reach安装升级保持停止，不是本阶段门槛。
