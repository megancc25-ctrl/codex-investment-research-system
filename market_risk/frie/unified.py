"""Four-project audit projection, not another risk-scoring engine."""
from pathlib import Path
import json
from .pipeline import evaluate_modules
from .engine import timestamp

def snapshot(as_of):
    root=Path(__file__).resolve().parents[2]
    data=root/'data/research/modules.json'
    try:body=json.loads(data.read_text(encoding='utf-8')) if data.exists() else {}
    except (OSError,ValueError):body={}
    if not isinstance(body,dict):body={}
    modules=evaluate_modules(body,as_of)
    delivery=root/'outputs/unified/remote-delivery.json'
    try:ci=json.loads(delivery.read_text(encoding='utf-8')) if delivery.exists() else {'this_checkout':'NOT_PUBLISHED','remote_delivery':'SEE_FINAL_ACCEPTANCE'}
    except (OSError,ValueError):ci={'remote_delivery':'UNKNOWN'}
    return {'schema_version':'research-control-1.0','as_of':timestamp(as_of).isoformat(),
      'projects':{
        'FRIE':{'state':'OFFLINE_RESEARCH_IMPLEMENTED','model':'NOT_VALIDATED'},
        'ASWM':{'state':'OFFLINE_RESEARCH_IMPLEMENTED','model':'NOT_VALIDATED'},
        'CRS':{'baseline_sha':'296e7f7ce0fd5713268c6ab048369275c0b485cb','G1':'NO_GO','G2':'NOT_STARTED','G3':'NOT_STARTED','production_score':None},
        'UST':{'baseline_sha':'3617b373b863c99a99a07eafe286539141149e43','state':'DESIGN_AUDITED_WITH_EXTERNAL_BLOCKERS',
               'runtime_security':'UNVERIFIED_PRIOR_RESTRICTED_PROFILE_FAILURES','real_ingestion':'NOT_AUTHORIZED'}},
      'six_modules':modules['modules'],'module_input_coverage':modules['usable_modules']/6,
      'live_data_coverage':0,'live_data_coverage_scope':'new unified monitor; no real source activated',
      'auto_trading':False,'production_scoring':False,'model_status':'NOT_VALIDATED',
      'ci':ci,
      'decision':'NO_GO_FOR_REAL_COLLECTION_AND_PRODUCTION'}

def markdown(r):
    lines=['# 四项目统一研究控制台',f"\n截至 {r['as_of']}；NOT_VALIDATED；真实采集/生产 NO-GO。",
       '\n|项目|状态|','|---|---|']
    for name,p in r['projects'].items():lines.append('|'+name+'|'+json.dumps(p,ensure_ascii=False)+'|')
    lines.extend(['\n|六大模块|状态|质量|','|---|---|---|'])
    for name,p in r['six_modules'].items():lines.append(f"|{name}|{p.get('status',p.get('accumulation',p.get('risk_status','UNKNOWN')))}|{p.get('quality','MISSING')}|")
    lines.append('\n新监测真实数据覆盖率：0%；没有用旧数据或合成样本冒充实采。')
    return '\n'.join(lines)
