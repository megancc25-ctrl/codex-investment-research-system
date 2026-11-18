# CRS 1.0 research prototype

CRS is implemented as an independent research module in `sentinel/crs/`. It does not change the NQ-Sentinel score or weights.

## Run a daily monitor

From `nq_sentinel_pro/`:

```powershell
python -m pip install -r requirements.txt
python -m sentinel.crs.cli --as-of 2026-11-18
```

This downloads FRED public series and Yahoo Finance price proxies, writes JSON / Markdown / HTML reports under `reports/crs/`, and stores normalized observations, features, and report payloads in DuckDB under `data/crs/`. Parquet exports are written beside the database. These generated data directories are ignored by Git.

The command returns 0 when it successfully writes a diagnostic report, even if the score gate fails; the JSON report then says `pipeline_status=PIPELINE_SUCCESS` and `score_status=DATA_INSUFFICIENT`. A publishable score says `score_status=SCORE_PUBLISHED`. Runtime errors return 1 and print `PIPELINE_FAILED`; CLI usage errors retain argparse's exit code 2. The GitHub Actions Summary lists coverage, missing critical metrics/modules, score, state, and failed/unconnected sources.

The `CRS cross-asset risk monitor` GitHub Actions workflow supports manual dispatch and weekday scheduling after the US close. GitHub only runs scheduled workflows from the repository's default branch, so the schedule becomes active after this branch is reviewed and merged. The workflow stores only the small state-machine history in Actions cache and uploads redacted JSON / Markdown / HTML reports; it does not upload DuckDB or Parquet, which may contain raw licensed inputs.

## Source and score policy

- Official public data are preferred. FRED values retain source units; ICE BofA OAS values are percent and are converted to basis points before applying thresholds.
- FRED's current CSV is a current vintage. The OAS series have a three-year observation limit since April 2026. Current data cannot reconstruct their historical publication vintages.
- Daily NDX / SOX, IEF, GLD and Yahoo DXY are third-party proxies until independently reconciled. IEF and GLD are traded proxies, not a complete Treasury or physical-gold total-return index.
- FRED series that carry third-party copyright restrictions are marked LICENSE_RESTRICTED. Raw values are kept in the local DuckDB but redacted from the JSON report. Check each data provider's terms before external redistribution.
- MOVE, CDX, repo volume/rates, market depth, constituent breadth, delinquency/default histories and GPU rental prices require licensed or separately verified inputs. Do not substitute made-up values.
- A missing feature is never zero. Coverage below 85%, missing credit/liquidity modules, or any configured critical metric (breadth, MOVE, Repo percentile, HY OAS, IG OAS) produces `DATA_INSUFFICIENT` and no full score. Monitoring gaps such as CDX are separately shown and are not silently replaced with proxies.
- Fixed cutoffs, 60/40 threshold-percentile mix, 5-year percentile window, and module weights are development parameters, not validated.
- Reports are research descriptors; a score is not a probability and does not issue a position instruction.
- Every report records the SHA-256 hash of the versioned scoring configuration used for its thresholds and weights.
- No actual holdings are loaded by the cloud runner. Any portfolio profile belongs in an ignored local file and is processed only by `local_crs_portfolio.py`.

## Local portfolio overlay

Copy `local_templates/crs.private.example.json` outside the repository, fill in actual assets and explicit stress scenarios locally, then run:

```powershell
python local_crs_portfolio.py --vault "D:\\Obsidian\\MyVault" --profile "D:\\Private\\crs.private.json" --market-report "reports\\crs\\CRS_DAILY_2026-11-18.json"
```

The local command checks weights, computes scenario losses and risk-budget utilization only when the user supplied a budget. It writes a private note under the Obsidian vault. It makes no network calls and creates no orders.

## Historical validation

`sentinel.crs.backtest.evaluate_crisis_backtest` accepts predeclared event windows and per-date score snapshots. It refuses to report results unless coverage is at least 85% and every input is explicitly marked point-in-time verified. No 2008 / 2020 / 2022 backtest result is claimed by this prototype; there is not enough authorized, release-vintaged credit and funding history in the repository.
