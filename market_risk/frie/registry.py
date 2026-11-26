"""Versioned research definitions; qualitative rules require explicit reviewed assessments.

TTLs and factor aggregation are implementation research choices, not backtested
trading parameters. Source names are an inventory, never a grant of data rights.
"""
from dataclasses import asdict, dataclass

MODULE_WEIGHTS = {'reaction':20,'structure':15,'liquidity':20,'capex':15,'credit':20,'industry':10}
MODULE_NAMES = {'reaction':'市场信息反应与预期','structure':'估值与市场结构','liquidity':'杠杆与流动性','capex':'资本支出与融资','credit':'信用风险与传染','industry':'产业周期与商业化'}

@dataclass(frozen=True)
class Signal:
    id: str
    name: str
    kind: str
    module: str
    weight: int
    formula: str
    threshold: str
    sources: tuple[str,...]
    frequency: str
    ttl_days: int
    dedup_group: str
    unit: str = 'reviewed_state'
    license_status: str = 'UNKNOWN_REQUIRES_ADMISSION'
    version: str = 'frie-1.0.0'
    missing: str = 'UNKNOWN_NO_VOTE'
    test_case: str = 'tests/test_frie_engine.py::EngineTests.test_registry_complete'

    def to_dict(self):
        return asdict(self)

_RISK = [
('F01','利好钝化','reaction','最近5次独立重大利好中非正异常收益次数','>=3/5；采用已完成1日窗口','IR,授权行情','event',30,'reaction'),
('F02','估值透支','structure','历史估值分位与隐含增长要求联合审核','90%–95%分位且增长要求过高；历史窗口待校准','授权估值数据库','daily',7,'valuation'),
('F03','交易拥挤','liquidity','持仓集中度及资金流历史分位','>=90%分位；样本范围待校准','基金管理人,授权持仓数据','weekly',14,'leverage'),
('F04','低波动高杠杆','liquidity','波动率分位<20%且杠杆分位>90%','联合条件；分位窗口待校准','Cboe,FINRA','monthly',45,'leverage'),
('F05','利率敏感度恶化','reaction','科技股收益对实际利率变化OLS斜率的窗口差','显著负向增强；窗口与显著性研究参数','授权行情,FRED','daily',7,'rates'),
('F06','自由现金流恶化','capex','同口径FCF同比下降连续两季的云厂商数量','>=2家；FCF=经营现金流−现金CapEx','SEC EDGAR,IR','quarterly',120,'capex_financing'),
('F07','外部融资依赖','capex','CapEx/经营现金流上升且净债务增长','联合审核；经营现金流<=0单独标记','SEC EDGAR,IR','quarterly',120,'capex_financing'),
('F08','信用风险扩大','credit','HY OAS水平或20交易日变化，单位bp','>400bp 或20日扩大>=100bp','获准FRED信用源,授权信用数据库','daily',7,'credit_spread'),
('F09','循环融资风险','capex','应收账款/担保/供应商融资/交叉投资事件审核','异常与独立终端需求缺失需原始披露确认','SEC EDGAR,IR','event',120,'circular_financing'),
('F10','硬件产业成熟','industry','订单/毛利率/售价多项恶化联合审核','多项条件；可比口径和数值阈值待校准','IR,授权产业数据库','quarterly',120,'hardware_cycle'),
('F11','AI商业化遇阻','industry','付费增长不足及单位经济性恶化','收入/续费/利润证据联合审核','SEC EDGAR,IR','quarterly',120,'commercialization'),
('F12','龙头滞涨及题材扩散','reaction','龙头相对收益弱+广度差+边缘题材上涨','三条件联合审核；窗口待校准','授权行情,授权广度数据','daily',7,'reaction'),
('F13','盈利预测提前下修','structure','Forward EPS/修正广度/指引变化','当时可得预期连续下修；阈值待校准','授权一致预期数据库,IR','daily',7,'earnings'),
('F14','市场流动性恶化','liquidity','价差/深度/冲击成本恶化','统一时段同口径审核；阈值待校准','授权盘口数据','daily',2,'market_liquidity'),
('F15','波动率期限结构倒挂','credit','VIX/VIX3M及VXN/偏度联合审核','倒挂持续时间待校准；不凭单点自动触发','Cboe','daily',2,'volatility'),
('F16','跨资产风险共振','credit','股债信用黄金美元异常联动','独立资产与融资证据联合；阈值待校准','授权行情,授权信用数据','daily',7,'contagion'),
('F17','全球美元融资压力','credit','SOFR−IORB/回购/美元融资/套利平仓审核','期限及基点同口径；阈值待校准','NY Fed,Federal Reserve','daily',7,'dollar_funding'),
('F18','指数内部结构恶化','structure','50/200日均线上占比/新高新低/等权相对收益','点时成分股联合审核；阈值待校准','授权点时成分与行情','daily',7,'breadth'),
]
_OPP = [
('现象级商业化突破',10,'真实持续付费、规模化与盈利模式'),
('企业AI投资回报率',10,'试点转部署、续费和可量化净收益'),
('AI应用收入与利润增长',15,'同口径AI收入连续两季加速且利润改善'),
('推理需求及单位经济性',10,'任务量增长抵消单位算力下降且付费可持续'),
('云厂商现金流拐点',10,'经营现金流增长驱动FCF改善；区分削减CapEx'),
('真实需求驱动资本支出',10,'独立终端付费、利用率和真实订单支持CapEx'),
('信用风险改善',10,'科技信用利差收窄且融资能力改善'),
('市场信息反应逆转',10,'重大信息后1/5/20日异常收益持续改善'),
('软件应用股相对强弱',5,'IGV/SMH等突破200日均线持续20日且盈利支持'),
('盈利预测上修',10,'点时盈利预测广泛上调，非仅估值扩张'),
]
REGISTRY = tuple(Signal(i,n,'risk',m,0,f,t,tuple(src.split(',')),freq,ttl,d) for i,n,m,f,t,src,freq,ttl,d in _RISK) + tuple(
    Signal(f'O{i:02d}',n,'opportunity','opportunity',w,f,'证据审核；UNKNOWN/未触发/改善/确认',
           ('IR','SEC EDGAR','授权行情/一致预期/信用数据'), 'quarterly' if i<=6 else 'daily',120 if i<=6 else 7,f'opportunity_{i}')
    for i,(n,w,f) in enumerate(_OPP,1))
BY_ID = {s.id:s for s in REGISTRY}
WATCHLIST = {'compute':['NVDA','AMD'],'memory':['MU','SNDK','WDC','STX'],
             'network':['AVGO','MRVL','COHR','LITE','ANET','CRDO'],'foundry':['TSM'],
             'cloud':['MSFT','GOOGL','AMZN','META','ORCL'],'applications':['PLTR','NOW','CRM','ADBE','INTU'],
             'benchmarks':['NDX','SOX','QQQ','SMH','IGV']}
