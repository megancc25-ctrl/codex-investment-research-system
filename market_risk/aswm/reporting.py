"""Local ASWM reports; public export deliberately omits private account figures."""
from copy import deepcopy
from html import escape
import json
from pathlib import Path
from market_risk.frie.engine import digest

def public_snapshot(snapshot):
    s=deepcopy(snapshot)
    s['budget']={'status':'PRIVATE_REDACTED','reason':'private configuration and account math omitted from shareable report'}
    s.pop('history',None)
    s.pop('material_fingerprint',None);s.pop('snapshot_hash',None)
    # Transition may contain private prior admission parameters in future versions.
    if 'transition' in s:s['transition']={k:v for k,v in s['transition'].items() if k!='admission_change'}
    s['public_snapshot_hash']=digest(s)
    return s

def markdown(s):
    lines=['# ASWM 1.0 独立研究栏目',f"\n截至 {s['as_of']}；NOT_VALIDATED；自动交易关闭。",
      f"\nAI增长阶段：{s['growth']['state']}；候选分数：{s['growth']['score']}；区间：{s['growth']['score_interval']}。",
      f"\n应用层：{s['applications']['status']}；硬件传导：{s['hardware']['status']}。",
      f"\n仓位准入：{s['admission']['state']}；阻断：{', '.join(s['admission']['blockers'])}。",
      f"\n数量覆盖：{s['growth']['count_coverage']}%；权重覆盖：{s['growth']['weight_coverage']}%。",
      '\n|ID|指标|权重|状态|原因|','|---|---|---|---|---|']
    clean=lambda x:escape(str(x)).replace('|','\\|').replace('\n',' ')
    for r in s['signals']:
        lines.append('|'+ '|'.join(clean(r[k]) for k in ('id','name','weight','status','reason'))+'|')
        for a in r['evidence']:lines.append(f"\n证据 {clean(a.get('evidence_id'))}：{clean(a.get('rationale'))}；来源 {clean(a.get('source_url'))}；反证 {clean(a.get('counter_evidence','未提供'))}。")
    lines.extend(['\n## 阶段要求',json.dumps(s['growth']['stage_requirements'],ensure_ascii=False),
      '\n## 风险预算（仅数学上限，非执行许可）',json.dumps(s['budget'],ensure_ascii=False),
      '\n## 下一验证事件',json.dumps(s.get('catalysts',[]),ensure_ascii=False),
      '\n真实PIT历史验证尚未完成；不得将合成正确性测试视为投资有效性。'])
    return '\n'.join(lines)

def html(s):return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>ASWM研究日报</title><style>body{font:15px/1.7 system-ui;background:#101820;color:#e6edf3;padding:30px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><pre>'+escape(markdown(s))+'</pre></html>'

def write_reports(snapshot,directory,*,redact=False):
    s=public_snapshot(snapshot) if redact else snapshot
    p=Path(directory);p.mkdir(parents=True,exist_ok=True)
    (p/'aswm.json').write_text(json.dumps(s,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (p/'aswm.md').write_text(markdown(s),encoding='utf-8')
    (p/'aswm.html').write_text(html(s),encoding='utf-8')
