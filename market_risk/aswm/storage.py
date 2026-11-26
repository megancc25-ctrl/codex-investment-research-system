"""ASWM state history reuses FRIE append-only persistence in a separate namespace."""
from market_risk.frie.storage import Store
from market_risk.frie.engine import timestamp
from .engine import evaluate

def transition(previous,current):
    before=previous['growth']['state'] if previous else None;after=current['growth']['state']
    since=previous.get('transition',{}).get('since',previous['as_of']) if previous and before==after else current['as_of']
    if previous is None:kind='INITIAL'
    elif before!=after:
        if after=='UNKNOWN':kind='INVALIDATED'
        elif before=='UNKNOWN':kind='BECAME_ASSESSABLE'
        else:kind='UPGRADED' if int(after[1])>int(before[1]) else 'DOWNGRADED'
    elif previous['material_fingerprint']!=current['material_fingerprint']:kind='MATERIAL_EVIDENCE_OR_ADMISSION_CHANGED'
    else:kind='UNCHANGED'
    prior_ids={a['economic_event_id'] for s in previous['signals'] for a in s['usable_evidence']} if previous else set()
    new=[s['id'] for s in current['signals'] if any(a['economic_event_id'] not in prior_ids for a in s['usable_evidence'])]
    return {'type':kind,'from':before,'to':after,'since':since,'duration_seconds':(timestamp(current['as_of'])-timestamp(since)).total_seconds(),
            'new_signals':new,'opportunity_change':{'from':previous['growth']['score'] if previous else None,'to':current['growth']['score']},
            'admission_change':{'from':previous['admission'] if previous else None,'to':current['admission']},'notification':'LOCAL_ONLY'}

class ASWMStore(Store):
    def __init__(self,path):super().__init__(path,namespace='aswm',evaluator=evaluate,transition_fn=transition)
