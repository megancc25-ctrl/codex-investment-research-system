"""Markdown, JSON and HTML reports with raw licensed series values redacted."""
from __future__ import annotations
import html
import json
from pathlib import Path
from datetime import datetime, timezone

def _public_copy(report):
    public = json.loads(json.dumps(report))
    details = public.get("score_result", {}).get("metric_details", {})
    blocked = False
    for item in details.values():
        if item.get("quality") == "LICENSE_RESTRICTED" or (item.get("value") is not None and
                item.get("license_status") not in ("APPROVED", "SYNTHETIC")):
            blocked = True
            item["value"] = None
            item["raw_value_redacted"] = True
            for field in ("score", "threshold_score", "percentile_score"):
                if field in item:
                    item[field] = None
    if blocked:
        score = public["score_result"]
        score["score"] = None
        for field in ("partial_contribution_sum_not_score", "renormalized_diagnostic_not_validated"):
            if field in score:
                score[field] = None
        for module in score.get("modules", {}).values():
            module["score"] = None
            module["group_scores"] = {}
        public["score_status"] = "LICENSE_BLOCKED"
        public["alerts"] = {}
        public["evidence"] = {"supporting": [], "against": [], "data_limits": ["Unapproved source-derived conclusions withheld."]}
        public["state_machine"] = {"state": "INSUFFICIENT_DATA"}
        public["decision"] = {"action": "NO_POSITION_ACTION", "rationale": "Unapproved source-derived conclusions withheld."}
    public["report_data_policy"] = {
        "raw_market_series_included": False,
        "licensed_metric_values_redacted": True,
        "personal_portfolio_data_included": False,
        "licensing_review_required": True,
    }
    return public

def render_markdown(report):
    score = report["score_result"]
    state = report["state_machine"]
    lines = [
        f"# CRS Daily Cross-Asset Risk Report — {report['asof']}", "",
        f"- Pipeline status: **{report.get('pipeline_status', 'UNKNOWN')}**; score status: **{report.get('score_status', 'UNKNOWN')}**",
        f"- Score: **{score['score'] if score['score'] is not None else 'N/A'} / 100**",
        f"- Score status: **{score['status']}**",
        f"- System state: **{state['state']}** ({state.get('label', state['state'])})",
        f"- Data coverage: **{score['data_coverage_pct']:.1f}%**; confidence: **{score['data_confidence']}**",
        f"- Metric coverage: **{score.get('metric_coverage_pct', score['data_coverage_pct']):.1f}%**; group coverage: **{score.get('group_coverage_pct', 0):.1f}%**; weighted module metric coverage: **{score.get('weighted_module_coverage_pct', 0):.1f}%**",
        f"- Critical missing metrics: **{', '.join(score.get('critical_metrics_missing', [])) or 'none'}**",
        f"- Generated: {report['generated_at']}", "",
        "> Research-only descriptor. The score is not a crisis probability or a trading instruction.", "",
        "## Seven modules", "",
        "| Module | Weight | Score | Metrics available / total | Metric coverage | Group coverage | Status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, item in score["modules"].items():
        lines.append(f"| {name} | {item['weight_pct']}% | {item['score'] if item['score'] is not None else 'N/A'} | {item.get('available_metric_count', 0)} / {item.get('metric_count', 0)} | {item.get('metric_coverage_pct', 0):.1f}% | {item.get('group_coverage_pct', 0):.1f}% | {item['status']} |")
    lines += ["", "## Combination alerts", ""]
    for name, item in report.get("alerts", {}).items():
        lines.append(f"- **{name}: {item.get('state', 'UNKNOWN')}** — {item.get('rule', item.get('note', ''))}")
    lines += ["", "## Evidence supporting elevated risk", ""]
    support = report.get("evidence", {}).get("supporting", [])
    lines.extend([f"- {x}" for x in support] or ["- No elevated-risk evidence is currently confirmed from available inputs."])
    lines += ["", "## Evidence against the elevated-risk conclusion", ""]
    against = report.get("evidence", {}).get("against", [])
    lines.extend([f"- {x}" for x in against] or ["- Insufficient current data to list meaningful counter-evidence."])
    lines += ["", "## Component observations", ""]
    component_evidence = report.get("evidence", {}).get("component_evidence", [])
    lines.extend([f"- {x}" for x in component_evidence] or ["- No component-level observations were recorded."])
    lines += ["", "## Evidence limits", ""]
    limits = report.get("evidence", {}).get("data_limits", [])
    lines.extend([f"- {x}" for x in limits] or ["- No additional evidence limits were recorded for this feature."])
    lines += ["", "## Decision output", "",
              f"- Action: **{report['decision']['action']}**",
              f"- Rationale: {report['decision']['rationale']}",
              "- Personal holdings were not loaded into the cloud report.",
              "- No orders were created; human review is required.", "",
              "## Data gaps and source diagnostics", ""]
    gaps = score.get("critical_modules_missing", [])
    lines.append("- Critical modules missing: " + (", ".join(gaps) if gaps else "none"))
    lines.append("- Critical metrics missing: " + (", ".join(score.get("critical_metrics_missing", [])) if score.get("critical_metrics_missing") else "none"))
    lines.append("- Missing metrics: " + (", ".join(score.get("missing_metrics", [])) if score.get("missing_metrics") else "none"))
    lines += ["", "### Source provenance", "",
              "| Source / indicator | Status | Observation | Published | Retrieved | Observation age (days) | Retrieval age (days) | Cache retrieval age (days) | Publication lag (days) | Quality | License | Reason |",
              "|---|---|---|---|---|---:|---:|---:|---:|---|---|---|"]
    for key, item in report.get("source_status", {}).items():
        lines.append("| " + " | ".join(str(value or "—").replace("|", "\\|").replace("\n", " ") for value in (
            key, item.get("status"), item.get("observation_date"), item.get("published_at"),
            item.get("retrieved_at"), item.get("observation_age_days", item.get("cache_age_days")),
            item.get("retrieval_age_days"), item.get("cache_retrieval_age_days"), item.get("publication_lag_days"),
            item.get("quality"), item.get("license_status"),
            item.get("reason"))) + " |")
    lines += ["", "### Rolling source health (up to 30 report dates)", "",
              "| Source | Runs | Live success | Cached | Failures | Timeouts | Consecutive failures | Observation lag days | Missing published time | Quality | License | Latest reason |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|"]
    for key, item in report.get("source_health", {}).get("sources", {}).items():
        values = (key, item.get("window_runs"), item.get("live_success_rate_pct"), item.get("cache_uses"),
                  item.get("failures"), item.get("timeouts"), item.get("consecutive_failures"),
                  item.get("observation_lag_days"), item.get("published_at_missing_rate_pct"),
                  item.get("latest_quality"), item.get("latest_license_status"), item.get("latest_reason"))
        lines.append("| " + " | ".join(str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ") for value in values) + " |")
    collection = report.get("source_collection_summary", {})
    if collection:
        lines += ["", "### FRED collection and cache counts", "",
                  f"- Expected series: **{collection.get('fred_expected_count', 0)}**",
                  f"- Live successes: **{collection.get('live_success_count', 0)}**",
                  f"- Cache fallbacks: **{collection.get('cache_fallback_count', 0)}**",
                  f"- Expired cache series: **{collection.get('cache_expired_count', 0)}**",
                  f"- Ineligible cache series: **{collection.get('cache_ineligible_count', 0)}**",
                  f"- Series persisted to cache: **{collection.get('cache_saved_count', 0)}**",
                  f"- Missing series: **{collection.get('missing_count', 0)}**",
                  f"- Cache store: **{collection.get('cache_database', 'UNKNOWN')}**"]
    lines += ["", "## Governance", ""]
    lines.extend(f"- {note}" for note in score.get("notes", []))
    lines += ["", "No historical crisis validation is implied by this daily report."]
    return "\n".join(lines) + "\n"

def write_reports(report, directory):
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    public = _public_copy(report)
    stem = f"CRS_DAILY_{report['asof']}"
    json_path = out / f"{stem}.json"
    md_path = out / f"{stem}.md"
    html_path = out / f"{stem}.html"
    json_path.write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = render_markdown(public)
    md_path.write_text(markdown, encoding="utf-8")
    html_path.write_text("<!doctype html><meta charset='utf-8'><title>CRS report</title><pre>" +
                         html.escape(markdown) + "</pre>\n", encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path), "html": str(html_path)}
