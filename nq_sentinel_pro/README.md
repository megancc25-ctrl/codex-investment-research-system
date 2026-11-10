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
