"""Markdown, JSON and HTML reports with raw licensed series values redacted."""
from __future__ import annotations
import html
import json
from pathlib import Path
from datetime import datetime, timezone

def _public_copy(report):
    public = json.loads(json.dumps(report))
    details = public.get("score_result", {}).get("metric_details", {})
    for item in details.values():
        if item.get("quality") == "LICENSE_RESTRICTED":
            item["value"] = None
            item["raw_value_redacted"] = True
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
        f"# CRS 1.0 Daily Cross-Asset Risk Report  {report['asof']}", "",
        f"- Pipeline status: **{report.get('pipeline_status', 'UNKNOWN')}**; score status: **{report.get('score_status', 'UNKNOWN')}**",
        f"- Score: **{score['score'] if score['score'] is not None else 'N/A'} / 100**",
        f"- Score status: **{score['status']}**",
        f"- System state: **{state['state']}** ({state.get('label', state['state'])})",
        f"- Data coverage: **{score['data_coverage_pct']:.1f}%**; confidence: **{score['data_confidence']}**",
        f"- Critical missing metrics: **{', '.join(score.get('critical_metrics_missing', [])) or 'none'}**",
        f"- Generated: {report['generated_at']}", "",
        "> Research-only descriptor. The score is not a crisis probability or a trading instruction.", "",
        "## Seven modules", "",
        "| Module | Weight | Score | Coverage | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for name, item in score["modules"].items():
        lines.append(f"| {name} | {item['weight_pct']}% | {item['score'] if item['score'] is not None else 'N/A'} | {item['coverage_pct']:.1f}% | {item['status']} |")
    lines += ["", "## Combination alerts", ""]
    for name, item in report.get("alerts", {}).items():
        lines.append(f"- **{name}: {item.get('state', 'UNKNOWN')}**  {item.get('rule', item.get('note', ''))}")
    lines += ["", "## Evidence supporting elevated risk", ""]
    support = report.get("evidence", {}).get("supporting", [])
    lines.extend([f"- {x}" for x in support] or ["- No elevated-risk evidence is currently confirmed from available inputs."])
    lines += ["", "## Evidence against the elevated-risk conclusion", ""]
    against = report.get("evidence", {}).get("against", [])
    lines.extend([f"- {x}" for x in against] or ["- Insufficient current data to list meaningful counter-evidence."])
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
              "| Source / indicator | Status | Observation | Published | Retrieved | Quality | License | Reason |",
              "|---|---|---|---|---|---|---|---|"]
    for key, item in report.get("source_status", {}).items():
        lines.append("| " + " | ".join(str(value or "—").replace("|", "\\|").replace("\n", " ") for value in (
            key, item.get("status"), item.get("observation_date"), item.get("published_at"),
            item.get("retrieved_at"), item.get("quality"), item.get("license_status"),
            item.get("reason"))) + " |")
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
