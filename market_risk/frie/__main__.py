"""python -m market_risk.frie: local research tooling."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from .engine import evaluate
from .registry import REGISTRY, WATCHLIST
from .reporting import write_reports
from .server import create_server, strict_json, validate_request
from .storage import Store

def main():
    parser=argparse.ArgumentParser(description='FRIE offline research — NOT_VALIDATED, no trading')
    sub=parser.add_subparsers(dest='command',required=True)
    serve=sub.add_parser('serve');serve.add_argument('--port',type=int,default=8765);serve.add_argument('--db',default='data/frie/research.sqlite')
    run=sub.add_parser('evaluate');run.add_argument('--input');run.add_argument('--as-of');run.add_argument('--output',default='outputs/frie');run.add_argument('--db',default='data/frie/research.sqlite')
    sub.add_parser('registry')
    validation=sub.add_parser('validate');validation.add_argument('--input',required=True);validation.add_argument('--output',default='outputs/frie/validation.json')
    mrm=sub.add_parser('mrm');mrm.add_argument('--input',required=True);mrm.add_argument('--db',default='data/frie/research.sqlite');mrm.add_argument('--output',default='outputs/frie/mrm.json')
    indicator=sub.add_parser('indicator');indicator.add_argument('--id',required=True);indicator.add_argument('--input',required=True)
    lcim=sub.add_parser('lcim');lcim.add_argument('--input',required=True);lcim.add_argument('--output',default='outputs/lcim/report.json')
    modules=sub.add_parser('modules');modules.add_argument('--input',required=True);modules.add_argument('--output',default='outputs/unified')
    args=parser.parse_args()
    if args.command=='serve':
        server=create_server(args.db,args.port)
        print(f'FRIE local research: http://127.0.0.1:{server.server_port}/frie.html',flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()
    elif args.command=='registry':
        print(json.dumps({'signals':[s.to_dict() for s in REGISTRY],'watchlist':WATCHLIST},ensure_ascii=False,indent=2))
    elif args.command=='validate':
        from .validation import run_validation
        result=run_validation(strict_json(Path(args.input).read_text(encoding='utf-8-sig')))
        target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        print(json.dumps({'output':str(target.resolve()),'model_status':'NOT_VALIDATED','status':result['status']}))
    elif args.command=='mrm':
        from .intake import mrm_report
        result=mrm_report(strict_json(Path(args.input).read_text(encoding='utf-8-sig')),args.db)
        target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=lambda x:x.isoformat(),allow_nan=False),encoding='utf-8')
        print(json.dumps({'output':str(target.resolve()),'reactions':len(result['reactions']),'model_status':'NOT_VALIDATED'}))
    elif args.command=='indicator':
        from . import indicators
        names={'F02':'f02_valuation_growth','F03':'f03_crowding','F04':'f04_volatility_leverage',
               'F06':'f06_fcf_declines','F07':'f07_capex_debt','F08':'f08_hy_oas',
               'F15':'f15_vix_term','F18':'f18_breadth','O09':'o09_relative_strength'}
        if args.id not in names: parser.error('indicator requires reviewed qualitative evidence or MRM; no numeric rule configured')
        body=strict_json(Path(args.input).read_text(encoding='utf-8-sig'))
        print(json.dumps(getattr(indicators,names[args.id])(**body),ensure_ascii=False,allow_nan=False))
    elif args.command=='lcim':
        from .lcim import evaluate_envelope
        body=strict_json(Path(args.input).read_text(encoding='utf-8-sig'))
        as_of=validate_request({'as_of':body.get('as_of')})
        report=evaluate_envelope(body.get('envelope',{}),as_of)
        target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        print(json.dumps({'output':str(target.resolve()),'model_status':'NOT_VALIDATED'}))
    elif args.command=='modules':
        from .pipeline import evaluate_modules
        body=strict_json(Path(args.input).read_text(encoding='utf-8-sig'))
        as_of=validate_request({'as_of':body.get('as_of')} )
        report=evaluate_modules(body,as_of)
        target=Path(args.output);target.mkdir(parents=True,exist_ok=True)
        (target/'research.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        rows=['# 六大研究模块（NOT_VALIDATED）',f"截至 {report['as_of']}；自动交易关闭。"]
        for name,value in report['modules'].items():rows.extend(['\n## '+name,'```json',json.dumps(value,ensure_ascii=False,indent=2),'```'])
        (target/'research.md').write_text('\n'.join(rows),encoding='utf-8')
        print(json.dumps({'output':str(target.resolve()),'usable_modules':report['usable_modules'],'model_status':'NOT_VALIDATED'}))
    else:
        body=strict_json(Path(args.input).read_text(encoding='utf-8-sig')) if args.input else {}
        if args.as_of: body['as_of']=args.as_of
        as_of=validate_request(body)
        snapshot=Store(args.db).save(body.get('assessments',[]),as_of,catalysts=body.get('catalysts',[]),portfolio=body.get('portfolio'))
        write_reports(snapshot,args.output)
        print(json.dumps({'output':str(Path(args.output).resolve()),'risk':snapshot['risk']['level'],
                          'hash':snapshot['snapshot_hash'],'model_status':'NOT_VALIDATED'},ensure_ascii=False))

if __name__=='__main__': main()
