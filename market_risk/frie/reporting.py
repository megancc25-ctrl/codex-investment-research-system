"""Escaped standalone reports for both research consumers; no remote publication."""
from html import escape
import json
from pathlib import Path

def markdown(snapshot):
    r=snapshot['risk']; o=snapshot['opportunity']
    lines=['# FRIE 1.0 研究日报',f"\n截至 {snapshot['as_of']} · NOT_VALIDATED · 自动交易关闭",
           f"\n风险：{r['level']}，得分 {r['score']}，覆盖率 {r['coverage']}%",
           f"\n机会：{o['score']}，覆盖率 {o['coverage']}%；两项分数独立，不相抵。",
           '\n|编号|信号|状态|原因|','|---|---|---|---|']
    def cell(x): return str(x).replace('|','\\|').replace('\n',' ')
    for s in snapshot['signals']:
        lines.append('|'+ '|'.join(cell(s[k]) for k in ('id','name','status','reason'))+'|')
    lines.extend(['\n## 证据与反证'])
    for s in snapshot['signals']:
        for a in s['evidence']:
            lines.append(f"- {cell(s['id'])} / {cell(a.get('evidence_id',''))}: {cell(a.get('rationale',''))}; 来源 {cell(a.get('source_url',''))}; 反证 {cell(a.get('counter_evidence',''))}")
    lines.extend(['\n## 状态变化',json.dumps(snapshot.get('transition',{}),ensure_ascii=False),
                  '\n## 下一催化事件',json.dumps(snapshot.get('catalysts',[]),ensure_ascii=False),
                  '\n## 压力测试与条件性预算',json.dumps(snapshot.get('stress'),ensure_ascii=False),
                  '\n## 边界','真实历史验证 NOT_RUN；CRS 外部消费者尚未连接。候选阈值不构成生产规则。'])
    if snapshot.get('aswm'):
        from market_risk.aswm.reporting import markdown as aswm_markdown
        lines.append('\n'+aswm_markdown(snapshot['aswm']))
    if snapshot.get('unified'):
        from .unified import markdown as unified_markdown
        lines.append('\n'+unified_markdown(snapshot['unified']))
    return '\n'.join(lines)

def render_html(snapshot):
    rows=''.join('<tr>'+''.join(f'<td>{escape(str(s[k]))}</td>' for k in ('id','name','status','reason'))+'</tr>' for s in snapshot['signals'])
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>FRIE 研究日报</title><style>body{background:#101820;color:#e6edf3;font:15px/1.7 system-ui;max-width:1200px;margin:40px auto;padding:20px}td,th{border-bottom:1px solid #344454;padding:10px;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>FRIE 研究日报</h1><table><thead><tr><th>ID</th><th>信号</th><th>状态</th><th>质量原因</th></tr></thead><tbody>'+rows+'</tbody></table><pre>'+escape(markdown(snapshot))+'</pre></html>'

def write_reports(snapshot,directory):
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    (directory/'frie.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (directory/'frie.md').write_text(markdown(snapshot),encoding='utf-8')
    (directory/'frie.html').write_text(render_html(snapshot),encoding='utf-8')
