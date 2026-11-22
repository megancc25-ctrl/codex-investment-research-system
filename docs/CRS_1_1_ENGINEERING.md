# CRS 1.1 engineering delivery

Baseline: `feature/crs-v1.0` at `afd68242123b6de8dd10d93525bb4620641382cd`.
Development branch: `codex/crs-1.1`. Engineering acceptance is separate from investment/model acceptance.

## Scope and operating commands

From `nq_sentinel_pro`, install `requirements.txt` in an isolated Python environment, then run:

```text
python -m unittest discover -s tests -v
python -m sentinel.crs.delivery --replay --output reports/crs
python -m sentinel.crs.delivery --report-date 2026-11-22 --output reports/crs
```

`delivery` is the 1.1 engineering entry point. The legacy engine/runner remain for regression tests; they are not the 1.1 formal investment publication interface. Default FRED and vendor price collection are denied before network/credential access. An explicitly injected FRED transport remains available for offline parser/retry contract tests. It does not grant a live license. No real source is admitted and no API key is inspected, created or uploaded.

The existing daily workflow now uses the blocked-data engineering entry point, restores only its engineering report archive, and has no FRED secret or raw-data cache step. Its existing schedule is retained. This branch does not deploy to main or establish scheduled execution. GitHub scheduling and the user-confirmed ChatGPT daily 08:00 task are independent; no ChatGPT task was changed. Neither this workflow nor an HTML file creates a new ChatGPT conversation.

## Seven-module baseline

| Module | Weight |
|---|---:|
| equity | 15% |
| rates | 15% |
| usd_gold | 10% |
| credit | 20% |
| liquidity | 20% |
| real_estate | 10% |
| contagion | 10% |

There is no specified lossless six-dimension mapping. All seven are displayed independently. `crs_v1.json`, `engine.py`, thresholds, group caps, indicators and weights remain unchanged. The configuration byte hash is pinned in acceptance tests. Research diagnostics invoke the unchanged engine; the formal report score remains null/N/A regardless of synthetic coverage. Synthetic module numbers and four alerts are examples, not validated market risk conclusions. State and action remain unavailable/no position action.

## Archive and replay

Report date is Beijing time; observation date is separate. `YYYY-MM-DD.json` and `.html` are immutable first versions. Repeated runs create `.v2`, `.v3`, etc. `index.json` lists dates, observation dates, versions, quality and file names. A directory lock rejects concurrent writers explicitly; an interrupted lock requires inspection before retry. Original report bytes are not replaced. If interrupted partway through a version, partial artifacts remain visible and a retry selects a new version; multi-file archival is not a filesystem transaction.

Replay uses three consecutive report dates, 2026-11-19/20/21, and observation dates 2026-11-18/19/20. Fixed synthetic values, timestamps and fixture hashes make JSON outputs reproducible. Previous-report research module deltas are included; the comparison explicitly does not assert that an arbitrary previous report equals the prior trading session. Report metadata includes report_date, observation_date, retrieved_at, generated_at, source, quality_status and license_status. A blocked diagnostic has retrieved_at=null because nothing was collected.

Generated samples are ignored by Git and available locally under `nq_sentinel_pro/reports/crs/`; hosted CI uploads synthetic reports as an Artifact. **Three-date synthetic replay is not three days of live operation. Real-data coverage is N/A.**

## Data status and admission

The report registers all 19 FRED series, native units/frequencies, source links, engineering freshness budgets, missing reasons, possible official alternatives and next steps. Release-calendar details remain NOT_VERIFIED rather than invented. The status classifier permits combinations of LICENSE_BLOCKED, CREDENTIAL_MISSING, COLLECTION_FAILED, EXPECTED_LAG, SOURCE_UNAVAILABLE, VALID and STALE. Missing credentials are only reported when explicitly known absent; this run uses NOT_INSPECTED, not a claim about remote Secrets. Freshness budgets are engineering defaults, not verified publication schedules. Synthetic per-metric diagnostics are distinct from the blocked real-source matrix.

Restricted: `BAMLH0A0HYM2`, `BAMLC0A0CM`, `BAMLH0A3HYC`.

Review required: `DGS10`, `DGS30`, `DFII10`, `VIXCLS`, `SOFR`, `IORB`, `NFCI`, `WRESBAL`, `RRPONTSYD`, `WTREGEN`, `DTWEXBGS`, `CSUSHPISA`, `EXHOSLUSM495S`, `MORTGAGE30US`, `CPIAUCSL`, `STLFSI4`.

Treasury, New York Fed, Chicago Fed and Cboe are registered as candidate alternatives with no FRED-key dependency. Their current endpoints and owner terms were not verified in this engineering phase. None is enabled or marked allowed. Future admission requires separate review of access/internal analysis/storage/publication rights, source-specific adapter and unit/release validation, and PIT evidence. Credential provisioning is source-specific, not a prerequisite for the entire system.

## Verification and limitations

Local full suite: 114 existing tests plus 18 engineering tests = 132 passing. The installed pandas version emits an upstream timezone-array deprecation warning. Added checks cover module/config preservation, no live calls or credential reads, date separation, holiday/weekend resolution, three-date reproducibility, composable missing states, offline retry/timeout compatibility, stale exclusion, wrong units, future data, provenance conflicts, nonfinite values, publication blocking, immutable versions, and archive contention. Existing 114 tests are unmodified.

CI `.github/workflows/crs-engineering.yml` installs full dependencies on Python 3.11, runs every test, generates the three-date replay twice to verify versioned reruns, and uploads only generated engineering reports. Actual hosted run status is reported separately with its run URL; configuration alone is not a pass.

Formal investment acceptance remains incomplete: real coverage N/A, no newly admitted live sources, no live three-day stability evidence, and no PIT/backtest/out-of-sample model validation. No holdings, 10% risk policy, production trading switch, NQ/PIOS business logic, or main branch was changed.
