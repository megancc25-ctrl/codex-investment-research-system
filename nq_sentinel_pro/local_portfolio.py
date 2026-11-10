"""Local-only Obsidian holdings overlay. No network calls or uploads."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

def validate(profile):
    a=profile.get("semiconductor_fund_weight")
    b=profile.get("remaining_weight")
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not 0<=v<=1 for v in (a,b)):
        raise ValueError("Invalid portfolio weights")
    if abs(a+b-1)>1e-8 or profile.get("semiconductor_proxy")!="SOX":
        raise ValueError("Weights must sum to 1 and proxy must be SOX")
    if profile.get("remaining_asset_type") not in ("UNKNOWN","CASH"):
        raise ValueError("Remaining asset type must be UNKNOWN or CASH")
    return profile

def scenario_table(profile):
    validate(profile)
    return [{"sox_shock_pct":v,
             "semiconductor_contribution_pct":round(profile["semiconductor_fund_weight"]*v,2),
             "total_nav_change_pct":round(profile["semiconductor_fund_weight"]*v,2)
                if profile["remaining_asset_type"]=="CASH" and profile.get("leverage")=="NONE" else None}
            for v in (-5,-10,-15,-20,-30)]

def write_obsidian(vault, profile_path, market_report=None):
    profile=validate(json.loads(Path(profile_path).read_text(encoding="utf-8")))
    public=json.loads(Path(market_report).read_text(encoding="utf-8")) if market_report else None
    asof=(public or {}).get("market_date",profile.get("asof"))
    try:
        datetime.strptime(asof,"%Y-%m-%d")
    except (TypeError,ValueError):
        raise ValueError("Expected ISO market date; invalid report date")
    out=Path(vault).expanduser().resolve()/"AI-Investment-Research"/"NQ-Sentinel"/"Local Portfolio"
    out.mkdir(parents=True,exist_ok=True)
    text=[f"# NQ-Sentinel local portfolio | {asof}","",
          "> PRIVATE: Do not upload this note or your profile to GitHub.",
          f"> Generated UTC {datetime.now(timezone.utc).isoformat()}","",
          f"- Semiconductor fund weight: {profile['semiconductor_fund_weight']:.1%}",
          "- Risk proxy: SOX, **not actual fund NAV**",
          f"- Remaining weight: {profile['remaining_weight']:.1%} ({profile['remaining_asset_type']})",
          f"- Leverage: {profile.get('leverage','UNKNOWN')}","",
          "| SOX scenario | Fund contribution to total assets | Total portfolio change |",
          "|---:|---:|---:|"]
    for r in scenario_table(profile):
        total="UNKNOWN" if r["total_nav_change_pct"] is None else f"{r['total_nav_change_pct']:+.2f}%"
        text.append(f"| {r['sox_shock_pct']:+}% | {r['semiconductor_contribution_pct']:+.2f}% | {total} |")
    if public:
        signal=public.get("signal",{})
        text+=["","## Public research signal",
               f"- Level: {signal.get('level','UNKNOWN')} (unvalidated)",
               f"- Model risk weight: {signal.get('model_risk_weight','UNKNOWN')} (not a personalized recommendation)",
               f"- Data quality: {public.get('data_quality','UNKNOWN')}"]
    text+=["","The unknown remaining assets must not be assumed to be cash. No real fund NAV, fees, subscriptions, FX or risk forecast is inferred."]
    dest=out/(asof+"-private-risk.md")
    dest.write_text("\n".join(text)+"\n",encoding="utf-8")
    return dest

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--vault",required=True)
    p.add_argument("--profile",required=True)
    p.add_argument("--market-report")
    a=p.parse_args()
    print(write_obsidian(a.vault,a.profile,a.market_report))
