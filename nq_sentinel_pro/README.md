# NQ-Sentinel Pro — GitHub + local Obsidian

**Research-only prototype.** Github hosts public-market analysis code, daily scheduled research and artifacts; Windows Obsidian holds all private positions. There is no trading integration, no live tick feed, and no independently validated predictive track record.

## GitHub cloud
1. Open the repository **Actions** tab and enable workflows if prompted.
2. Choose **NQ Sentinel public market report** -> **Run workflow** to test.
3. Inspect the run log: unit tests and vendor download must succeed. Yahoo can rate-limit or omit the `^SOX` index; in that case the workflow intentionally fails.
4. Download the successful **nq-sentinel-market-report** ZIP artifact, containing date-stamped public Markdown/JSON reports.
5. The workflow runs at **23:30 UTC Monday–Friday**, after the US close, subject to GitHub scheduling delays and holiday calendars. This is **not** a live alert.

## Local Obsidian (Windows; no GitHub upload)
Install Python 3.11+, download/copy the `nq_sentinel_pro` source folder to your PC, and copy `local_templates/portfolio.private.example.json` to **outside the Git repo** (for example `D:\\Private\\portfolio.private.json`). Fill in your actual weights locally; the public example numbers are synthetic.

Run:

```powershell
cd D:\\Projects\\codex-investment-research-system\\nq_sentinel_pro
python local_portfolio.py --vault "D:\\Obsidian\\MyVault" --profile "D:\\Private\\portfolio.private.json" --market-report "D:\\Downloads\\2026-11-10.json"
```

Omit `--market-report` if no GitHub report has been downloaded yet. Local output:
`<Vault>\\AI-Investment-Research\\NQ-Sentinel\\Local Portfolio\\YYYY-MM-DD-private-risk.md`.

## Development checks
```bash
cd nq_sentinel_pro
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python run_daily.py --download --out reports
```

Historical vendor Yahoo data are **unverified third-party proxies**. SOX and NDX are not directly tradable. Backtest uses QQQ next-session opening prices, fixed candidate thresholds, commission/slippage assumptions, and a **single fixed chronological holdout**, not true rolling walk-forward tuning. No actual active-fund NAV, transaction availability, taxes, fund FX, portfolio-level stress test or authoritative cross-venue reconciliation.

Never claim model risk weights are personal trade advice. A 5/10/20% SOX hypothetical shock is only a scenario, not a forecast. Until actual fund rules and independently checked data are available, no personal sell/buy instructions should be automated.

**Security:** Repository is public. Do not push personal portfolios, an Obsidian vault, broker data, tokens or `*.private.json` files. Obsidian and GitHub Actions cannot directly share a private local folder without an explicitly configured local downloader.


## V2 six-module risk scoring (research-only; added 2026-11-12)

Daily workflow runs `python run_daily.py --download --official --out reports`.
The existing Level 0-3 is preserved as an **unvalidated legacy technical signal**.
The separate `risk_v2` object in date-stamped JSON contains:
- `score` (0..100 or null), `version`, `status`, `coverage_pct`,
  `verified_coverage_pct`, `module_details`, `previous_score`,
  `delta`, `comparable`, and `partial_contribution_sum_NOT_SCORE`.
- Candidate weights 25% fundamentals, 25% trend/breadth, 20% credit,
  15% liquidity/leverage, 10% valuation/earnings, 5% sentiment/options.
- A publishable score requires >=80% verified module weight **and**
  independently verified trend, credit, and fundamentals modules.
- Unverified Yahoo technical proxies do not qualify as VERIFIED.
  Missing observations remain null, not zero. Partial sums are not scores.
- FRED official CSV series (HY/IG/CCC OAS, nominal and real 10Y yields,
  VIX, initial claims, Fed balance sheet, GDP) are fetched with
  date/freshness guards. FRED data are publication-lagged, not intraday.
  FRED OAS are percentage points, not CDX HY price points.
- Credit module uses preliminary fixed thresholds and is UNVALIDATED.
  VIX without term structure is an incomplete sentiment proxy.
  A single yield level or balance sheet snapshot does not establish
  the liquidity/leverage module.
- Missing automated official FINRA monthly balances, semiconductor EPS
  revisions, cloud CapEx/FCF, SOX/NDX full constituent breadth,
  VIX futures structure and independently verified valuation data
  prevent a fully populated score today. **Do not fabricate these inputs.**

### Engineering status and release gate

Run `python -m unittest discover -s tests -v` or check the PR CI workflow.
The V2 framework and official FRED adapter are implemented; this is
**not** a validated complete-data market risk model. Formal score may
remain null until independently verified coverage meets the quality gate.
Do not equate successful GitHub Actions with validated forecasts.

Public GitHub contains **no private holdings**, account data or Obsidian vault.
No trading integrations, new schedules, or historical score overwrites.
