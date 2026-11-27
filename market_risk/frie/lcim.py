"""LCIM 1.0 offline candidates; supplied input must be licensed and PIT qualified.

Raw functions assume already admitted inputs; use evaluate_envelope for audited
entry. No network, automatic scoring, publication, trading or inferred leverage.
"""
from datetime import date, timedelta
from math import isfinite
from .engine import timestamp
from .research_modules import lcim_ratios

L=['保证金借方余额','借方余额/GDP（名义SAAR）','借方余额/M2','借方余额/股市市值','借方余额同比','借方余额环比及三月变化','借方余额距历史峰值','净信用余额','净信用余额/市值']
I=['IPO年度累计融资','IPO年度累计/市值','滚动12月IPO融资与强度','IPO数量及未盈利占比','IPO前2/5融资集中度','排除前2后的融资强度','增发与净股票发行','科技债发行','高收益债发行及融资成本','Form4异常净减持','IPO 5/20日基准调整收益','撤回、延期及融资失败']
def registry():
 return [dict(id=f'{p}{i:02}',name=n,source=('FINRA/BEA/Fed H6/获准市值' if p=='L' else 'SEC EDGAR/获准发行数据'),unit=('USD_BN' if i==1 else 'ratio_or_explicit'),formula=n,threshold='CANDIDATE_UNVALIDATED',frequency='monthly' if p=='L' else 'event',ttl_days=45 if p=='L' else 370,license_status='UNKNOWN',missing='UNKNOWN',dedup_group='FRIE_leverage' if p=='L' else 'issuance',version='lcim-1.0.0') for p,names in [('L',L),('I',I)] for i,n in enumerate(names,1)]
def percentile(value,history,as_of):
 if value is None:return {'percentile':None,'sample_count':0}
 _finite(value); cutoff=timestamp(as_of);h=[]
 for row in history:
  if timestamp(row['available_at'])<=cutoff:
   _finite(row['value']);h.append(row['value'])
 return {'percentile':100*sum(v<=value for v in h)/len(h) if len(h)>=120 else None,'sample_count':len(h),'tie_rule':'less_than_or_equal','as_of':cutoff.isoformat()}
def _finite(x):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not isfinite(x):raise ValueError('finite numeric required')
def _ratio(a,b):
 if a is None or b is None:return None
 _finite(a);_finite(b)
 return a/b if b>0 else None
def _change(now,previous):
 r=_ratio(now,previous)
 return r-1 if r is not None else None
def _out(value,reason='input unavailable'):
 return {'value':value,'status':'UNKNOWN' if value is None else 'OBSERVED','reason':reason if value is None else 'offline research input; not independently verified'}
def _events(rows,cutoff,unit):
 unique={}
 for e in rows:
  if timestamp(e['available_at'])>cutoff:continue
  if e.get('unit')!=unit:raise ValueError('issuance unit mismatch')
  k=e.get('economic_event_id') or e.get('event_id')
  if not k:raise ValueError('event identity required')
  if k in unique and unique[k]!=e:raise ValueError('ambiguous duplicated event/revision; resolve PIT vintage first')
  unique[k]=e
 return list(unique.values())
def evaluate(data,as_of):
 cutoff=timestamp(as_of);today=cutoff.date();result={x['id']:_out(None) for x in registry()}
 m=data.get('margin') or {};debt=m.get('debt');unit=m.get('unit')
 if debt is not None:
  if unit!=m.get('denominator_unit'):raise ValueError('denominator unit mismatch')
  rat=lcim_ratios(debt,m.get('gdp_saar'),m.get('m2'),m.get('market_cap'),unit='billions' if unit=='USD_BN' else unit,denominator_unit='billions' if unit=='USD_BN' else unit)
  for key,value in {'L01':debt,'L02':rat['debt_gdp'],'L03':rat['debt_m2'],'L04':rat['debt_market_cap'],'L05':_change(debt,m.get('prior_year_debt')),'L06':{'month':_change(debt,m.get('prior_month_debt')),'three_month':_change(debt,m.get('prior_3month_debt'))},'L07':_change(debt,m.get('historical_peak'))}.items():result[key]=_out(value)
  cash=m.get('cash_credit');credit=m.get('margin_credit')
  if cash is not None and credit is not None:
   _finite(cash);_finite(credit);net=cash+credit-debt;result['L08']=_out(net);result['L09']=_out(_ratio(net,m.get('market_cap')))
 offerings=_events(data.get('offerings',[]),cutoff,data.get('unit'))
 def completed(e):return e.get('event_type')=='IPO' and e.get('status')=='COMPLETED' and e.get('offering_type')=='IPO'
 ipos=[e for e in offerings if completed(e) and date.fromisoformat(e['event_date'])<=today]
 def window(e,start):return start<=date.fromisoformat(e['event_date'])<=today
 ytd=[e for e in ipos if window(e,date(today.year,1,1))]
 trailing=[e for e in ipos if window(e,today-timedelta(days=365))]
 def total(events):
  if not events or any(e.get('gross_proceeds') is None for e in events):return None
  for e in events:_finite(e['gross_proceeds'])
  return sum(e['gross_proceeds'] for e in events)
 y=total(ytd);t=total(trailing);cap=data.get('market_cap')
 result['I01']=_out(y);result['I02']=_out(_ratio(y,cap));result['I03']=_out({'gross':t,'market_ratio':_ratio(t,cap)} if t is not None else None)
 if ytd:
  known=[e for e in ytd if e.get('profitability') in {'LOSS','PROFIT'}]
  result['I04']=_out({'count':len(ytd),'loss_share':sum(e['profitability']=='LOSS' for e in known)/len(known) if len(known)==len(ytd) else None})
  values=sorted((e['gross_proceeds'] for e in ytd if e.get('gross_proceeds') is not None),reverse=True)
  if y and len(values)==len(ytd):
   result['I05']=_out({'top2':sum(values[:2])/y,'top5':sum(values[:5])/y})
   result['I06']=_out(_ratio(sum(values[2:]),cap))
 for key,source in [('I07','equity_issuance'),('I08','technology_bonds'),('I09','high_yield_issuance')]:
  value=data.get(source)
  if value is not None and isinstance(value,dict) and value.get('available_at') and timestamp(value['available_at'])<=cutoff:result[key]=_out(value)
 records=data.get('form4',[])
 known=[e for e in records if timestamp(e['available_at'])<=cutoff and e.get('context') in {'TAX','OPTION_EXERCISE','10B5_1','DISCRETIONARY'}]
 if records and len(known)==len(records):result['I10']=_out({'records':known,'warning':'context reviewed; abnormality requires independent baseline'})
 performance=data.get('ipo_performance')
 if isinstance(performance,dict) and performance.get('available_at') and timestamp(performance['available_at'])<=cutoff:result['I11']=_out(performance)
 failed=[e for e in offerings if e.get('status') in {'WITHDRAWN','POSTPONED','FAILED'}]
 if failed:result['I12']=_out({'count':len(failed),'event_ids':[e['event_id'] for e in failed]})
 return {'schema_version':'lcim-1.0','as_of':cutoff.isoformat(),'indicators':result,'model_status':'NOT_VALIDATED','production_scoring':False,'auto_trading':False,'limitations':['counts reflect admitted input only; incomplete coverage is not zero','issuance and leverage are research references, not separate additive risk votes']}
def evaluate_envelope(envelope,as_of):
 from types import SimpleNamespace
 from .engine import _eligible
 e=dict(envelope,status='CONFIRMED');reason=_eligible(e,SimpleNamespace(ttl_days=45),timestamp(as_of))
 if reason:return {'status':'UNKNOWN','reason':reason,'model_status':'NOT_VALIDATED'}
 return evaluate(e.get('facts',{}),as_of)
