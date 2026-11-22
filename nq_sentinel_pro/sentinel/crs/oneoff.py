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
    # Authority is irreversibly consumed in the audited repository history.
    # No cwd, missing local file, clone or caller boolean can revive it.
    raise PermissionError('AUTHORIZATION_CONSUMED: 7077794290; no live execution path')


def assess_body(body, kind):
    """Offline-only structured assessment; never promote a numeric field to unit proof."""
    result = {'schema_validation':'FAIL','date_validation':'NOT_RUN',
              'unit_validation':'UNKNOWN','reason':'JSON_INVALID'}
    try:
        payload=json.loads(body)
    except Exception:
        return result
    if not isinstance(payload,dict) or 'refRates' not in payload:
        result['reason']='CONTAINER_MISSING';return result
    rows=payload['refRates']
    if not isinstance(rows,list):
        result['reason']='CONTAINER_TYPE';return result
    result['record_count']=len(rows)
    if len(rows)!=1:
        result['reason']='ROW_COUNT';return result
    row=rows[0]
    if not isinstance(row,dict):
        result['reason']='ROW_TYPE';return result
    if row.get('type')!=kind.upper():
        result['reason']='RATE_TYPE';return result
    value=row.get('percent')
    if type(value) not in (int,float) or not math.isfinite(value):
        result['reason']='RATE_FIELD_TYPE';return result
    if not isinstance(row.get('effectiveDate'),str):
        result['reason']='DATE_FIELD_TYPE';return result
    try:
        from datetime import date
        date.fromisoformat(row['effectiveDate'])
    except ValueError:
        result['reason']='DATE_FORMAT';return result
    result['schema_validation']='PASS'
    result['observation_date']=row['effectiveDate']
    result['date_validation']='PASS' if row['effectiveDate']=='2026-11-19' else 'FAIL'
    result['reason']='UNIT_EVIDENCE_MISSING' if result['date_validation']=='PASS' else 'DATE_MISMATCH'
    return result
