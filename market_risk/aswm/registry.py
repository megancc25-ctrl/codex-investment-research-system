"""SW definitions are new-version research rules, never auto-migrated from O01–10."""
from market_risk.frie.registry import Signal, WATCHLIST
_ROWS=[
('AI重大商业化突破',10,'commercial','真实付费商业模式的重大突破，不能只用下载/Token','event',30),
('企业真实付费、续费及ROI',10,'commercial','至少两家独立企业同口径付费/续费/ROI改善','quarterly',120),
('AI应用收入与单位经济性',15,'commercial','AI专属收入及贡献经济性改善，持续性需两季度','quarterly',120),
('推理算力实际需求',10,'transmission','工作负载调整实际推理需求增长；硬件订单另核','quarterly',120),
('云巨头现金流与投资回报',10,'capital','OCF驱动FCF改善，区分削减CapEx，ROIC另核','quarterly',120),
('真实订单驱动第二轮CapEx',10,'transmission','独立外部订单转换与利用率；循环融资不可替代','event',120),
('科技企业信用风险改善',10,'credit','同评级同期限科技利差稳定/20日收窄；HY代理不替代','daily',7),
('市场信息反应逆转',10,'reaction','最近5次独立利好1日行业调整收益>=3正且中位数>0','event',30),
('软件与半导体市场趋势',5,'reaction','SOX连续10日未新创20日低点；50DMA上5日、SOX/NDX和广度','daily',7),
('半导体盈利预测与利润',10,'transmission','半导体EPS修正企稳/上调，订单与毛利共同改善','quarterly',120)]
REGISTRY=tuple(Signal(f'SW{i:02d}',n,'opportunity',module,w,formula,
 'CANDIDATE_UNVALIDATED：见facts与阶段约束',('SEC/IR','获准行业行情/预期/信用源'),freq,ttl,f'aswm_{i}',version='aswm-1.0.0',test_case='tests/test_aswm_signals.py')
 for i,(n,w,module,formula,freq,ttl) in enumerate(_ROWS,1))
BY_ID={s.id:s for s in REGISTRY}
