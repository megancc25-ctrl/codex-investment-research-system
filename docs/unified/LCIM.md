# LCIM 1.0 离线实现与剩余条件

Issue #6 的 LCIM 补充任务在共享 FRIE 包中新增 L01–L09、I01–I12 注册表、统一证据信封和离线研究输出。运行：

```powershell
python -m market_risk.frie lcim --input data/lcim/input.json --output outputs/lcim/report.json
```

输入 `envelope` 沿用 FRIE 的 evidence_id、economic_event_id、source_url、observed_at、available_at、expires_at、quality、license_status、license_ref、rationale 字段；facts 为线下已获准数据。证据信封不通过时输出 UNKNOWN，不访问网络。`evaluate` 是底层纯函数，调用者必须自行进行逐条时点与用途许可检查；`evaluate_envelope` 校验外层证据，不构成子记录逐源独立准入证明。

L01–L09提供债务、同量纲GDP/M2/市值比率、同比、环比、三月变化、峰值回撤、净信用余额。历史分位至少120个已可得样本，同值按小于等于计；并列、统计窗口和可比性须由使用者提供、证明。GDP输入为名义SAAR。缺分母不计算；不同数量级单位拒绝。

I01–I06提供已明确输入的IPO年度累计、12个月融资、数量/亏损占比、头部集中度和去头部强度；仅将完成的普通IPO计入，明确排除SPAC/直接上市，实际披露的发行人所得、二级出售、超额配售必须由记录分别提供和核验。同日YTD与可比市值、同期滚动数据需要上游提供独立时点数据，本版不自动验证。无完整覆盖证明不能把未录入事件当作真实零发行。

I07–I12作为带available_at的明细输入或上下文记录展示：增发与净发行、科技债、高收益债及成本、Form 4原因、IPO基准收益、撤回/延期/失败。**这些目前是数据契约和输入呈现，未实现全部自动归因、跨年可比、净发行计算与异常判定。** 输入可得不代表实时数据已准入，也不代表风险预警已确认。后续应引入逐笔修订、按发行实际完成日期及首次可得时间选择、完整IPO universe与交易日价格数据。

阈值P95/P90和5%/10%峰值回撤均为未验证候选；当前不自动提升FRIE等级、不改变生产分数或交易。尚未实现完整LCIM状态机、事件独立性报警、NQ/CRS原生日报接入及真实历史回测。待有合规数据后进行；FRIE已有独立报警机制但不能冒充LCIM完整集成。
