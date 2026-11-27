"""LCIM point-in-time contracts: source records are separately licensed and immutable."""
from datetime import date
from math import isfinite
from pathlib import Path
import json, sqlite3
from .engine import timestamp,digest
from .lcim import registry
from .scheduler import AlertTransitions

REQUIRED=('indicator_id','observation_date','published_at','available_at','retrieved_at','vintage','source','source_url','license','license_ref','unit','universe','quality','event_id')
def select_vintages(records,as_of,*,event_mode=False):
 cutoff=timestamp(as_of);grouped={}
 for r in records:
  if any(not r.get(k) for k in REQUIRED):continue
  if r['license']!='ADMITTED' or r['quality']!='VERIFIED':continue
  published,available,retrieved=(timestamp(r[k]) for k in ('published_at','available_at','retrieved_at'))
  if available<published or retrieved<available:raise ValueError('invalid provenance order')
  if available>cutoff or retrieved>cutoff:continue
  key=(r['indicator_id'],r['event_id'] if event_mode else r['observation_date']);grouped.setdefault(key,[]).append(r)
 out={}
 for key,group in grouped.items():
  newest=max(timestamp(r['available_at']) for r in group);latest=[r for r in group if timestamp(r['available_at'])==newest]
  if len({digest(r) for r in latest})>1:raise ValueError('conflicting point-in-time vintages')
  out[key]=latest[0]
 return out

def ytd_comparison(rows,as_of):
 cutoff=timestamp(as_of);current=cutoff.date();eligible=[]
 for r in rows:
  day=date.fromisoformat(r['date'])
  if (day.month,day.day)==(current.month,current.day) and day.year<current.year and timestamp(r['available_at'])<=cutoff:eligible.append(r['value'])
 if any(isinstance(v,bool) or not isinstance(v,(float,int)) or not isfinite(v) for v in eligible):raise ValueError('finite values required')
 return {'values':eligible,'sample_count':len(eligible),'percentile':None,'reason':'same calendar day only; minimum 120 monthly comparable observations remains mandatory'}

def _val(r):return r.get('value') if r else None

def evaluate_pit(records,events,as_of):
 cutoff=timestamp(as_of);selection=select_vintages(records,cutoff);out={r['id']:{'indicator_id':r['id'],'value':None,'unit':r['unit'],'quality':'MISSING','license':'UNKNOWN','historical_percentile':None,'sample_count':0,'event_id':None} for r in registry()}
 def latest(name):
  rows=[r for (s,_),r in selection.items() if s==name]
  return max(rows,key=lambda r:r['observation_date']) if rows else None
 def write(id,value,source,extra=()):
  if not source or value is None:return
  deps=[source,*extra];out[id].update({k:source[k] for k in REQUIRED if k in source});out[id].update(indicator_id=id,value=value,quality='VERIFIED',license='ADMITTED',historical_percentile=None,sample_count=0,event_id=source['event_id'],dependency_event_ids=[r['event_id'] for r in deps])
 debt=latest('debt');value=_val(debt);write('L01',value,debt)
 for name,id in [('gdp','L02'),('m2','L03'),('market_cap','L04')]:
  denominator=latest(name);dv=_val(denominator)
  if value is not None and isinstance(dv,(float,int)) and not isinstance(dv,bool) and isfinite(dv) and dv>0 and debt['unit']==denominator['unit'] and debt['universe']==denominator['universe']:
   write(id,value/dv,debt,[denominator])
 for key,id in [('prior_year_debt','L05'),('prior_month_debt','L06'),('peak_debt','L07')]:
  prior=latest(key);v=_val(prior)
  if value is not None and isinstance(v,(int,float)) and not isinstance(v,bool) and isfinite(v) and v>0 and debt['unit']==prior['unit'] and debt['universe']==prior['universe']:
   write(id,value/v-1,debt,[prior])
 c=latest('cash_credit');m=latest('margin_credit');cap=latest('market_cap')
 if all(x is not None for x in (debt,c,m)) and len({x['unit'] for x in (debt,c,m)})==1 and len({x['universe'] for x in (debt,c,m)})==1:
  n=c['value']+m['value']-value;write('L08',n,debt,[c,m])
  if cap and cap['unit']==debt['unit'] and cap['universe']==debt['universe'] and isinstance(cap['value'],(int,float)) and cap['value']>0:write('L09',n/cap['value'],debt,[c,m,cap])
 # Events remain separately quality/rights gated; no complete universe is inferred.
 ev=select_vintages(events,cutoff,event_mode=True)
 return {'schema_version':'lcim-pit-1.0','as_of':cutoff.isoformat(),'indicators':out,'admitted_event_records':len(ev),'model_status':'NOT_VALIDATED','auto_trading':False,'production_scoring':False}

def issuance_metrics(events,as_of,*,market_cap=None,complete_universe=False):
 cutoff=timestamp(as_of); selected=select_vintages(events,cutoff,event_mode=True)
 selected_events={}
 for r in selected.values():
  eid=r['event_id']
  if eid in selected_events and selected_events[eid]!=r:raise ValueError('event id reused across records')
  selected_events[eid]=r
 current=cutoff.date();ytd=[];trailing=[];failed=[]
 for r in selected_events.values():
  day=date.fromisoformat(r['observation_date'])
  if day>current:continue
  if r.get('status') in {'FAILED','WITHDRAWN','POSTPONED'}:failed.append(r)
  if r.get('event_type')!='IPO' or r.get('offering_type')!='IPO' or r.get('status')!='COMPLETED':continue
  if r['unit']!='USD_BN':raise ValueError('IPO amounts must use USD_BN')
  val=r.get('value')
  if isinstance(val,bool) or not isinstance(val,(float,int)) or not isfinite(val) or val<0:raise ValueError('nonnegative amount required')
  if day.year==current.year:ytd.append(r)
  from datetime import timedelta
  if current-timedelta(days=365)<=day<=current:trailing.append(r)
 def val(number,deps):
  return {'value':number if deps or complete_universe else None,'quality':'MISSING' if number is None else 'VERIFIED' if complete_universe else 'PARTIAL','sample_count':len(deps),'event_ids':[r['event_id'] for r in deps],'unit':'ratio_or_USD_BN','license':'ADMITTED','historical_percentile':None}
 total=sum(r['value'] for r in ytd);series=sorted((r['value'] for r in ytd),reverse=True)
 trailing_total=sum(r['value'] for r in trailing)
 ratio=lambda n:n/market_cap if market_cap is not None and isfinite(market_cap) and market_cap>0 else None
 profits=[r.get('profitability') for r in ytd]
 output={'I01':val(total,ytd),'I02':val(ratio(total),ytd),'I03':val({'gross':trailing_total,'market_ratio':ratio(trailing_total)} if trailing or complete_universe else None,trailing),
  'I04':val({'count':len(ytd),'loss_share':sum(p=='LOSS' for p in profits)/len(profits) if profits and all(p in {'LOSS','PROFIT'} for p in profits) else None},ytd),
  'I05':val({'top2':sum(series[:2])/total,'top5':sum(series[:5])/total} if total>0 else None,ytd),
  'I06':val(ratio(sum(series[2:])),ytd),'I12':val({'count':len(failed),'event_ids':[r['event_id'] for r in failed]},failed)}
 for k in ('I07','I08','I09','I10','I11'):output[k]={'value':None,'quality':'MISSING','reason':'requires admitted transaction-level cash flow and matched historical baseline'}
 return output

def secondary_metrics(records,as_of,*,complete_universe=False):
 selected=list(select_vintages(records,as_of,event_mode=True).values());selected=[r for r in selected if r['observation_date']<=timestamp(as_of).date().isoformat()]
 def group(k):return [r for r in selected if r.get('event_type')==k]
 def sum_values(rows):
  for r in rows:
   if r['unit']!='USD_BN' or isinstance(r.get('value'),bool) or not isinstance(r.get('value'),(int,float)) or not isfinite(r['value']) or r['value']<0:raise ValueError('finite nonnegative USD_BN amounts required')
  return sum(r['value'] for r in rows)
 def output(value,rows):return {'value':value,'quality':'MISSING' if value is None else 'VERIFIED' if complete_universe else 'PARTIAL','license':'ADMITTED','sample_count':len(rows),'event_ids':[r['event_id'] for r in rows],'historical_percentile':None}
 issuances=group('equity_issuance');buybacks=group('buyback')
 gross=sum_values(issuances) if issuances else (0 if complete_universe else None)
 repurchases=sum_values(buybacks) if buybacks else (0 if complete_universe else None)
 net=gross-repurchases if gross is not None and repurchases is not None else None
 tech=group('tech_bond');hy=group('hy_bond');insiders=group('form4_sale');r5=group('ipo_return_5');r20=group('ipo_return_20')
 def performance(rows):
  values=[]
  for r in rows:
   if r['unit']!='return_fraction':raise ValueError('explicit return_fraction units required')
   if r.get('benchmark_return') is not None:values.append({'event_id':r['event_id'],'excess_return':r['value']-r['benchmark_return']})
  return values
 matched=all(r.get('context') in {'TAX','OPTION_EXERCISE','10B5_1','DISCRETIONARY'} for r in insiders)
 return {'I07':output({'gross_issuance':gross,'buybacks':repurchases,'net':net} if gross is not None or repurchases is not None else None,issuances+buybacks),
 'I08':output({'gross':sum_values(tech)} if tech else None,tech),
 'I09':output({'gross':sum_values(hy),'yields_bp':[r.get('yield_bp') for r in hy]} if hy else None,hy),
 'I10':output({'sales_by_context':{k:sum_values([r for r in insiders if r['context']==k]) for k in ('TAX','OPTION_EXERCISE','10B5_1','DISCRETIONARY')},'abnormality':'UNKNOWN_NO_BASELINE'} if insiders and matched else None,insiders),
 'I11':output({'5d':performance(r5),'20d':performance(r20),'method':'aligned supplied event-window excess; prices not inferred'} if r5 or r20 else None,r5+r20)}

def historical_percentile(current,records,as_of):
 values=select_vintages(records,as_of)
 series={r['indicator_id'] for r in values.values()};units={r['unit'] for r in values.values()};universes={r['universe'] for r in values.values()}
 if len(series)>1 or len(units)>1 or len(universes)>1:raise ValueError('history must be comparable')
 months={}
 for r in values.values():
  key=r['observation_date'][:7]
  if key in months:raise ValueError('duplicate month in history')
  months[key]=r['value']
 vals=list(months.values())
 if any(isinstance(v,bool) or not isinstance(v,(float,int)) or not isfinite(v) for v in vals):raise ValueError('finite history required')
 return {'sample_count':len(vals),'percentile':100*sum(v<=current for v in vals)/len(vals) if len(vals)>=120 else None,'tie_rule':'less_than_or_equal','window_start':min(months) if months else None,'window_end':max(months) if months else None}

def make_report(body,as_of):
 base=evaluate_pit(body.get('records',[]),body.get('events',[]),as_of)
 cap=base['indicators']['L04'];debt=base['indicators']['L01']
 market_cap=debt['value']/cap['value'] if cap['value'] else None
 issuance=issuance_metrics(body.get('events',[]),as_of,market_cap=market_cap,complete_universe=body.get('complete_universe') is True)
 base['indicators'].update(issuance)
 base['indicators'].update(secondary_metrics(body.get('events',[]),as_of,complete_universe=body.get('complete_universe') is True))
 for sid in ('L02','L03','L04','I02','I03'):
  base['indicators'][sid]['historical_percentile']=None
 base['candidate_states']=candidate_states({},None)
 base['consumers']={'NQ':'shared research JSON','CRS':'shared research JSON; external native adapter pending'}
 base['coverage']=sum(v.get('quality')=='VERIFIED' for v in base['indicators'].values())/21
 base['limitations']=['I07-I11 admitted synthetic event aggregation exists; company scope and abnormality verification pending','no historical forecast validation','source permissions asserted by input, not independently verified','no production scoring or trading']
 base['snapshot_hash']=digest(base)
 return base

def candidate_states(facts,independent):
 p=facts.get('peak_drawdown');lever=facts.get('leverage_percentiles') or {};ipo=facts.get('ipo_percentile')
 risk=any(lever.get(k) is not None and lever[k]>=t for k,t in (('gdp',95),('m2',95),('market_cap',90)))
 enough=any(lever.get(k) is not None for k in ('gdp','m2','market_cap'))
 if p is None:d='UNKNOWN'
 elif p<.05:d='NOT_TRIGGERED'
 elif p<.10:d='OBSERVE'
 elif independent is None or independent.get('independent') is not True or independent.get('signal') not in {'credit','breadth'} or not independent.get('event_id'):d='UNKNOWN'
 else:d='ESCALATED'
 return {'high_leverage':'OBSERVE' if risk else 'NOT_TRIGGERED' if enough else 'UNKNOWN','deleveraging':d,'issuance_boom':'OBSERVE' if ipo is not None and ipo>=90 else 'NOT_TRIGGERED' if ipo is not None else 'UNKNOWN','issuance_failure':'OBSERVE' if facts.get('issuance_failure') is True else 'NOT_TRIGGERED' if facts.get('issuance_failure') is False else 'UNKNOWN','model_status':'NOT_VALIDATED'}

class AlertLog:
 def __init__(self,path):self.delegate=AlertTransitions(path)
 def record(self,key,state,as_of):
  if state=='UNKNOWN':return False
  return self.delegate.record('LCIM:'+key,state,as_of)
 def close(self):self.delegate.close()


def markdown(report):
 lines=['# LCIM 1.0 研究日报',f"截至 {report['as_of']} · NOT_VALIDATED · 无生产评分和自动交易",f"覆盖率 {report['coverage']*100:.1f}%",'|编号|值|质量|证据|','|---|---|---|---|']
 for key,row in report['indicators'].items():
  def cell(x):return str(x).replace('|','\\|').replace('\n',' ')
  lines.append('|'+ '|'.join(cell(x) for x in (key,row.get('value'),row.get('quality'),row.get('event_id',row.get('event_ids'))))+'|')
 lines.extend(['\n## 候选状态',json.dumps(report['candidate_states'],ensure_ascii=False),'\n## 局限']+['- '+x for x in report['limitations']])
 return '\n'.join(lines)
