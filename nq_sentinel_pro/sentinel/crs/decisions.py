"""Conservative generic actions. This module never creates or executes orders."""
ACTION_BY_STATE = {
    "L0": ("MONITOR", "No add or trim solely because the score is low."),
    "L1": ("PAUSE_AGGRESSIVE_ADDS", "Review exposures and data quality; no automatic reduction."),
    "L2": ("REVIEW_RISK_BUDGET", "Assess concentration and stress loss; any candidate trim needs local portfolio inputs."),
    "L3": ("PREPARE_RISK_REDUCTION_REVIEW", "Consider reductions only after credit/liquidity confirmation and portfolio stress analysis."),
    "L4": ("PRIORITIZE_LIQUIDITY_AND_HUMAN_REVIEW", "Emergency review; no automated trading."),
    "INSUFFICIENT_DATA": ("NO_POSITION_ACTION", "Critical data or coverage gate failed; do not infer a safe state."),
}

def decision_for_state(state, portfolio_status="NOT_PROVIDED"):
    action, rationale = ACTION_BY_STATE.get(state, ACTION_BY_STATE["INSUFFICIENT_DATA"])
    return {"action": action, "rationale": rationale, "portfolio_status": portfolio_status,
            "candidate_reduction_percentage_points": None, "orders_created": False,
            "human_approval_required": True, "personalized": False}
