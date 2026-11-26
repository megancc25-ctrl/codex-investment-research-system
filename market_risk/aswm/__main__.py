"""Local CLI reuses FRIE server/storage and never contacts market data providers."""
import argparse,json
from pathlib import Path
from datetime import datetime,timezone
from market_risk.frie.server import strict_json
from market_risk.frie.storage import Store
from .web import ResearchAPI
from .reporting import write_reports
from .registry import REGISTRY

def main():
    p=argparse.ArgumentParser(description='ASWM 1.0 offline research NOT_VALIDATED')
    sub=p.add_subparsers(dest='command',required=True)
    e=sub.add_parser('evaluate');e.add_argument('--input');e.add_argument('--db',default='data/frie/research.sqlite');e.add_argument('--private-config');e.add_argument('--output',default='outputs/aswm');e.add_argument('--redact',action='store_true')
    s=sub.add_parser('serve');s.add_argument('--port',type=int,default=8765);s.add_argument('--db',default='data/frie/research.sqlite');s.add_argument('--private-config')
    sub.add_parser('registry')
    v=sub.add_parser('validate');v.add_argument('--input',required=True);v.add_argument('--upside-threshold',type=float,required=True);v.add_argument('--output',default='outputs/aswm/validation.json')
    a=p.parse_args()
    if a.command=='registry':print(json.dumps([s.to_dict() for s in REGISTRY],ensure_ascii=False,indent=2));return
    if a.command=='serve':
        from market_risk.frie.server import create_server
        server=create_server(a.db,a.port,private_config_path=a.private_config)
        print(f'ASWM local research: http://127.0.0.1:{server.server_port}/aswm.html',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close()
        return
    if a.command=='validate':
        from .validation import run_validation
        result=run_validation(strict_json(Path(a.input).read_text(encoding='utf-8-sig')),upside_threshold=a.upside_threshold)
        target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        print(json.dumps({'output':str(target.resolve()),'status':result['status'],'model_status':'NOT_VALIDATED'}));return
    api=ResearchAPI(a.db,Store(a.db),a.private_config)
    body=strict_json(Path(a.input).read_text(encoding='utf-8-sig')) if a.input else {'schema_version':'aswm-1.0','assessments':[]}
    result=api.evaluate_body(body);write_reports(result,a.output,redact=a.redact)
    print(json.dumps({'output':str(Path(a.output).resolve()),'growth':result['growth']['state'],'admission':result['admission']['state'],'model_status':'NOT_VALIDATED','hash':result['snapshot_hash']}))
if __name__=='__main__':main()
