"""CRS L0-L4 state machine with confirmation, hysteresis, and an explicit emergency override."""
STATE_ORDER = ("L0", "L1", "L2", "L3", "L4")
STATE_LABELS = {
    "L0": "NORMAL", "L1": "RISK_ACCUMULATION", "L2": "CROSS_ASSET_REPRICING",
    "L3": "SYSTEMIC_SPREAD", "L4": "SEVERE_CREDIT_OR_LIQUIDITY_CRISIS",
}

def candidate_state(score_result, emergency_market_failure=False):
    modules = score_result.get("modules", {})
    if emergency_market_failure:
        return "L4"
    score = score_result.get("score")
    if score is None:
        return "INSUFFICIENT_DATA"
    credit = modules.get("credit", {}).get("score") or 0
    liquidity = modules.get("liquidity", {}).get("score") or 0
    other = [v.get("score") for k, v in modules.items()
             if k not in ("credit", "liquidity") and v.get("score") is not None]
    high_independent = sum(v.get("score") is not None and v["score"] >= 50 for v in modules.values())
    if score >= 80 and max(credit, liquidity) >= 85:
        return "L4"
    if score >= 60 and max(credit, liquidity) >= 70 and any(v >= 60 for v in other):
        return "L3"
    if score >= 40 and high_independent >= 2:
        return "L2"
    if score >= 25 or sum(v.get("score", 0) >= 25 for v in modules.values()) >= 2:
        return "L1"
    return "L0"

def candidate_reasons(score_result, emergency_market_failure=False):
    """Explain L4 credit/liquidity score triggers or the manual emergency override."""
    if emergency_market_failure:
        return ["MANUAL_EMERGENCY_MARKET_FAILURE"]
    score = score_result.get("score")
    if score is None or score < 80:
        return []
    modules = score_result.get("modules", {})
    reasons = []
    for module, code in (("credit", "CREDIT_MODULE_SCORE"), ("liquidity", "LIQUIDITY_MODULE_SCORE")):
        value = modules.get(module, {}).get("score")
        if value is not None and value >= 85:
            reasons.append(code)
    return reasons

def transition_state(raw_candidate, history=None, emergency_market_failure=False, candidate_reason_codes=None):
    history = list(history or [])
    candidate_reason_codes = list(candidate_reason_codes or [])
    if emergency_market_failure:
        return {"state": "L4", "raw_candidate": "L4", "transition": "EMERGENCY_OVERRIDE",
                "confirmations": 1, "required_confirmations": 1,
                "candidate_reason_codes": ["MANUAL_EMERGENCY_MARKET_FAILURE"]}
    if raw_candidate == "INSUFFICIENT_DATA":
        return {"state": raw_candidate, "raw_candidate": raw_candidate,
                "transition": "DATA_GATE", "confirmations": 0, "required_confirmations": None,
                "candidate_reason_codes": candidate_reason_codes}
    previous = next((x.get("state") for x in reversed(history) if x.get("state") in STATE_ORDER), "L0")
    old_idx, new_idx = STATE_ORDER.index(previous), STATE_ORDER.index(raw_candidate)
    if new_idx > old_idx:
        count = 1
        for item in reversed(history):
            if item.get("raw_candidate") == raw_candidate:
                count += 1
            else:
                break
        needed = 2
        state = raw_candidate if count >= needed else previous
        return {"state": state, "raw_candidate": raw_candidate,
                "transition": "UPGRADE_CONFIRMED" if state == raw_candidate else "UPGRADE_PENDING",
                "confirmations": count, "required_confirmations": needed,
                "candidate_reason_codes": candidate_reason_codes}
    if new_idx < old_idx:
        count = 1
        for item in reversed(history):
            if item.get("raw_candidate") == raw_candidate:
                count += 1
            else:
                break
        needed = 5
        state = raw_candidate if count >= needed else previous
        return {"state": state, "raw_candidate": raw_candidate,
                "transition": "DEESCALATION_CONFIRMED" if state == raw_candidate else "DEESCALATION_PENDING",
                "confirmations": count, "required_confirmations": needed,
                "candidate_reason_codes": candidate_reason_codes}
    return {"state": previous, "raw_candidate": raw_candidate,
            "transition": "UNCHANGED", "confirmations": 0, "required_confirmations": 0,
            "candidate_reason_codes": candidate_reason_codes}
