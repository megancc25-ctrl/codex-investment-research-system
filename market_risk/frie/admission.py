"""Shared per-source, per-purpose activation gate. Rights != project authorization."""
def check_access(matrix,source_id,purpose,*,project_authorized=False,g1_passed=False):
    source=next((s for s in matrix.get('sources',[]) if s.get('id')==source_id),None)
    if source is None:return {'allowed':False,'reason':'source_unknown'}
    use=source.get('uses',{}).get(purpose,{})
    status=use.get('status') if isinstance(use,dict) else use
    if status!='ALLOWED':return {'allowed':False,'reason':'purpose_restricted_or_unknown'}
    if project_authorized is not True or g1_passed is not True or source.get('live_enabled') is not True:
        return {'allowed':False,'reason':'project_or_g1_activation_missing'}
    return {'allowed':True,'reason':'specific_source_purpose_project_gate_passed'}
