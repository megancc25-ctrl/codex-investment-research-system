"""Single authorized batch. No CLI auto-execution and no persistent market body."""
import http.client
import json
import math
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from .authorization import load_plan, safe_diagnostic

AUTHORITY = '7077794290'

def check_body(body, kind):
    try:
        rows = json.loads(body)['refRates']
        if not isinstance(rows,list) or len(rows)!=1:
            return 'SCHEMA_MISMATCH'
        row=rows[0]
        if row.get('type')!=kind.upper():
            return 'UNEXPECTED_RATE_TYPE'
        if row.get('effectiveDate')!='2026-11-19':
            return 'DATE_MISMATCH'
        value=row.get('percent')
        if type(value) not in (int,float) or not math.isfinite(value):
            return 'SCHEMA_MISMATCH'
        return 'NONE'
    except Exception:
        return 'SCHEMA_MISMATCH'

def run_once(authority, preflight_verified=False):
    if authority!=AUTHORITY or preflight_verified is not True:
        raise PermissionError('Explicit authority and verified preflight required')
    plan=load_plan()
    private=Path('data/crs-g1-private');private.mkdir(parents=True,exist_ok=True)
    # Atomic reservation before any data request; all outcomes consume authority.
    marker=private/(AUTHORITY+'.consumed')
    with marker.open('x',encoding='utf-8') as f:
        f.write('Single authorized batch reserved; never rerun. Delete diagnostics within 7 days; retain this nonnumerical consumption marker.\n')
    results=[];start=time.monotonic()
    for request in plan['requests']:
        if results:time.sleep(2)
        if time.monotonic()-start>=45:break
        kind=request['rate_type'];stamp=datetime.now(timezone.utc).isoformat()
        diag={'rate_type':kind,'started_at':stamp,'schema_validation':'NOT_RUN','unit_validation':'NOT_RUN','error_code':'NETWORK_FAILURE'}
        body=None;conn=None
        try:
            target=urlsplit(request['url'])
            conn=http.client.HTTPSConnection(target.hostname,timeout=min(5,45-(time.monotonic()-start)),context=ssl.create_default_context())
            conn.connect()
            conn.sock.settimeout(min(10,45-(time.monotonic()-start)))
            conn.request('GET',target.path+'?'+target.query,headers=plan['headers'])
            response=conn.getresponse();diag['http_status']=response.status
            if response.status!=200:
                diag['error_code']='REDIRECT_BLOCKED' if 300<=response.status<400 else 'HTTP_FAILURE'
            else:
                body=bytearray()
                while len(body)<=262144:
                    remaining=45-(time.monotonic()-start)
                    if remaining<=0:raise TimeoutError()
                    conn.sock.settimeout(min(10,remaining))
                    chunk=response.read1(min(8192,262145-len(body)))
                    if not chunk:break
                    body.extend(chunk)
                diag['bytes_received']=min(len(body),262144)
                diag['error_code']='RESPONSE_TOO_LARGE' if len(body)>262144 else check_body(body,kind)
                diag['schema_validation']='PASS' if diag['error_code']=='NONE' else 'FAIL'
                if diag['error_code']=='NONE':
                    diag.update(record_count=1,observation_date='2026-11-19',unit_validation='PASS')
        except TimeoutError:
            diag['error_code']='TIMEOUT'
        except Exception:
            # Never capture or stringify exception/server content.
            diag['error_code']='NETWORK_FAILURE'
        finally:
            if body is not None:body.clear()
            if conn:conn.close()
        diag['completed_at']=datetime.now(timezone.utc).isoformat()
        diag['elapsed_ms']=min(45000,int((time.monotonic()-start)*1000))
        results.append(safe_diagnostic(diag))
        (private/(AUTHORITY+'.diagnostics.json')).write_text(json.dumps(results,indent=2),encoding='utf-8')
        if diag['error_code']!='NONE':break
    return results
