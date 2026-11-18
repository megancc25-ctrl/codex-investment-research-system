"""Local-only private portfolio overlay for an Obsidian vault. No network or GitHub calls."""
from __future__ import annotations
import argparse, hashlib, json, math
from datetime import date, datetime, timezone
from pathlib import Path

def load_profile(path):
    profile_path = Path(path).expanduser().resolve()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assets = profile.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("Profile must contain an explicit assets list")
    total = 0.0
    for item in assets:
        weight = item.get("weight")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or not 0 <= weight <= 1:
            raise ValueError("Each asset weight must be a finite number from 0 to 1")
        if not item.get("asset_class"):
            raise ValueError("Each asset requires an asset_class")
        total += weight
    if abs(total - 1.0) > 1e-6:
        raise ValueError("Asset weights must sum to 1.0")
    budget = profile.get("max_loss_budget_pct")
    if budget is not None and (isinstance(budget, bool) or not isinstance(budget, (int, float)) or not 0 < budget <= 1):
        raise ValueError("max_loss_budget_pct must be a fraction in (0, 1]")
    return profile, profile_path

def calculate_stress(profile, scenarios):
    rows = []
    for scenario in scenarios:
        total_loss, missing = 0.0, []
        breakdown = []
        shocks = scenario.get("returns_by_asset_class", {})
        for asset in profile["assets"]:
            asset_class, weight = asset["asset_class"], asset["weight"]
            shock = shocks.get(asset_class)
            if not isinstance(shock, (int, float)) or isinstance(shock, bool):
                missing.append(asset_class)
                continue
            contribution = weight * shock
            total_loss += contribution
            breakdown.append({"asset_class": asset_class, "weight": weight,
                              "shock": shock, "nav_contribution": contribution})
        complete = not missing
        loss = -total_loss if complete else None
        budget = profile.get("max_loss_budget_pct")
        rows.append({"scenario": scenario["name"], "complete": complete,
                     "missing_asset_classes": sorted(set(missing)),
                     "projected_nav_loss_pct": loss,
                     "risk_budget_utilization": loss / budget if loss is not None and budget else None,
                     "remaining_risk_capacity_pct": budget - loss if loss is not None and budget else None,
                     "breakdown": breakdown})
    return rows

def write_obsidian(vault, profile_path, market_report_path):
    profile, profile_file = load_profile(profile_path)
    report_path = Path(market_report_path).expanduser().resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    asof = report.get("asof") or report.get("market_date")
    date.fromisoformat(asof)
    scenarios = profile.get("stress_scenarios", [])
    if not scenarios:
        raise ValueError("Profile must provide explicitly approved stress_scenarios")
    stress = calculate_stress(profile, scenarios)
    dest_dir = Path(vault).expanduser().resolve() / "AI-Investment-Research" / "CRS" / "Local Portfolio"
    dest_dir.mkdir(parents=True, exist_ok=True)
    profile_hash = hashlib.sha256(profile_file.read_bytes()).hexdigest()
    lines = [f"# CRS local portfolio overlay | {asof}", "",
             "> PRIVATE. This file and profile stay in the local Obsidian vault; do not upload them.",
             f"> CRS state: {report.get('state_machine', {}).get('state', 'UNKNOWN')}",
             f"> CRS score: {report.get('score_result', {}).get('score', 'N/A')} (research-only; not a probability)",
             f"> Profile SHA-256: {profile_hash}", ""]
    for row in stress:
        lines += [f"## Scenario: {row['scenario']}", "",
                  f"- Complete: {row['complete']}",
                  f"- Projected NAV loss: {row['projected_nav_loss_pct'] if row['projected_nav_loss_pct'] is not None else 'N/A'}",
                  f"- Risk-budget utilization: {row['risk_budget_utilization'] if row['risk_budget_utilization'] is not None else 'N/A'}",
                  f"- Missing asset classes: {', '.join(row['missing_asset_classes']) or 'none'}", ""]
    lines += ["No order or personalized reduction amount was generated. Human approval is required."]
    target = dest_dir / f"CRS-private-risk-{asof}.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--market-report", required=True)
    args = parser.parse_args()
    print(write_obsidian(args.vault, args.profile, args.market_report))
