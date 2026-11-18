"""Render a concise GitHub Actions run summary from a CRS report JSON file."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

def _safe(value):
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")

def render_summary(report):
    score = report["score_result"]
    state = report["state_machine"]
    score_value = score.get("score")
    lines = [
        f"## CRS daily report — {report.get('asof', 'unknown')}", "",
        f"- Pipeline status: **{report.get('pipeline_status', 'UNKNOWN')}**",
        f"- Score status: **{report.get('score_status', 'UNKNOWN')}**",
        f"- Data coverage: **{score.get('data_coverage_pct', 0):.1f}%**",
        f"- Metric coverage: **{score.get('metric_coverage_pct', score.get('data_coverage_pct', 0)):.1f}%**; group coverage: **{score.get('group_coverage_pct', 0):.1f}%**; weighted module metric coverage: **{score.get('weighted_module_coverage_pct', 0):.1f}%**",
        f"- Full CRS score published: **{'YES' if score_value is not None else 'NO'}**",
        f"- CRS score: **{score_value if score_value is not None else 'N/A'}**",
        f"- State machine: **{state.get('state', 'UNKNOWN')}** ({state.get('label', '')})",
        f"- L4 trigger reasons: **{', '.join(state.get('candidate_reason_codes', [])) or 'none'}**",
        f"- Critical modules missing: **{', '.join(score.get('critical_modules_missing', [])) or 'none'}**",
        f"- Critical metrics missing: **{', '.join(score.get('critical_metrics_missing', [])) or 'none'}**",
        "", "### Failed or unavailable sources", "",
    ]
    failures = [(key, value) for key, value in report.get("source_status", {}).items()
                if value.get("status") != "AVAILABLE"]
    if failures:
        lines.extend(f"- `{_safe(key)}`: {_safe(value.get('reason', value.get('status', 'MISSING')))}"
                     for key, value in failures)
    else:
        lines.append("- None")
    lines += ["", "### Module metric coverage", "", "| Module | Metrics | Available | Missing | Metric coverage | Group coverage |", "|---|---:|---:|---:|---:|---:|"]
    for name, item in score.get("modules", {}).items():
        lines.append(f"| {_safe(name)} | {item.get('metric_count', 0)} | {item.get('available_metric_count', 0)} | {item.get('missing_metric_count', 0)} | {item.get('metric_coverage_pct', 0):.1f}% | {item.get('group_coverage_pct', 0):.1f}% |")
    return "\n".join(lines) + "\n"

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args(argv)
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    Path(args.summary).write_text(render_summary(report), encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
