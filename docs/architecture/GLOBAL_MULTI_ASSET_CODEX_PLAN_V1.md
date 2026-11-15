# Global Multi-Asset v1.0 — Codex Execution Plan

Status: execution plan; Phase 0 must be completed and reviewed before implementation.
Branch: feature/global-allocation-rmb-v1
Specification: docs/architecture/GLOBAL_MULTI_ASSET_RESEARCH_SPEC_V1.md
Parent architecture: docs/architecture/NQ_SENTINEL_GLOBAL_ALLOCATION_V1.md

## Operating rules

1. Work in the branch named above. Do not merge to the base branch.
2. Read both architecture specifications before changing code.
3. Preserve the original NQ-Sentinel six-module weights (25/25/20/15/10/5), indicator definitions, historical scores and semiconductor position-state transitions. Add regression fixtures before any integration.
4. Reuse validated existing data adapters; do not duplicate FRED, SEC, SOX or AI-capex pipelines.
5. No live allocation percentages, automatic trades, FX conversion or remittance.
6. No missing-value zero fill, fabricated consensus revisions, forward P/E, fair value, FX equilibrium or AI monetization metrics.
7. Every new signal must expose source, as-of time, publication time, retrieval time, freshness, coverage, methodology, config version and invalidation conditions.
8. All threshold configuration starts provisional and disabled for live actions. User-specific thresholds require a completed IPS.
9. Do not silently substitute third-party scraped data for an official source. Document access, licensing and historical-vintage constraints.
10. Run tests after each phase and report exact commands, outcomes and remaining failures.

## Phase 0 — reconnaissance (first task; stop for review)

Inspect the repository and produce `docs/implementation/PHASE0_RECONNAISSANCE.md`.

Required output:
- Repository tree, language, runtime, package manager and test/lint commands.
- Existing NQ-Sentinel architecture and exact six-module weights / state transitions with file and line references.
- Existing FRED, SEC, SOX, AI infrastructure, FX, rates and reporting pipelines.
- Existing schemas, persistence layer, configuration conventions and scheduling.
- Current report format and safe integration point.
- Reusable code versus missing code.
- Source availability, licensing, API stability, publication lag and point-in-time history blockers.
- Proposed module mapping and dependency graph.
- Exact Phase 1 files to add/change.
- A testable checklist and explicit “no production changes made” statement.

Do not implement Phase 1 until the user reviews Phase 0.

## Phase 1 — common contracts and deterministic functions

Implement only after Phase 0 approval:
- Canonical observation / source / universe / instrument / sleeve-state / threshold / scenario schemas.
- FX conversion with explicit CNY-per-foreign-currency convention and optional hedge-cost model.
- Common returns, volatility, drawdown, percentile, freshness and coverage functions.
- YAML/JSON config schema; live actions disabled.
- Unit tests using hand-calculated fixtures.
- Regression tests proving original NQ scores and state transitions are unchanged.

Exit gate:
- All relevant tests pass.
- FX sign convention tests pass.
- Missing/stale data tests return N/A or INSUFFICIENT_DATA.
- No production allocation recommendation is enabled.

## Phase 2 — defensive asset data adapters

Implement in order:
1. U.S. Treasury 0–1, 1–3 and 3–7 year yield / duration / real-yield data.
2. RMB cash, deposit, money-market and government bond reference data.
3. Gold USD and RMB prices, real-yield context and positioning/flows where reliable.

For every adapter:
- Validate endpoint and metadata.
- Store raw immutable snapshot and hash.
- Preserve observation, publication and retrieval timestamps.
- Validate units, calendar, revision and freshness.
- Add adapter fixtures, integration tests and diagnostics.
- Use controlled official-file import when a documented stable API is unavailable.

Exit gate: repeatable source ingestion, transparent missing-data behavior, validated formulas and reproducible raw snapshots.

## Phase 3 — equity research adapters

Implement:
1. U.S. mega-cap / AI infrastructure, reusing existing SEC / SOX / AI pipelines.
2. Global ex-U.S. quality equities.
3. China quality equities.

Requirements:
- Point-in-time issuer universes and canonical issuer identity.
- Reported fundamentals separated from consensus estimates.
- Coverage denominator for all breadth metrics.
- Valuation methodology and history explicitly recorded.
- No consensus data unless a complete defensible source exists.
- De-duplicate ADRs, share classes, ETF holdings and overlapping universes.

Exit gate: issuer-level point-in-time fixtures, coverage reports, valuation methodology tests and no survivorship leakage.

## Phase 4 — portfolio look-through and risk engine

Implement:
- Asset / issuer / sector / country / currency look-through.
- Hedged versus unhedged FX exposure.
- Bond duration, key-rate duration and credit-spread exposure.
- Liquidity ladder and issuer / bank concentration.
- Portfolio covariance and component risk contribution with sample-size controls.
- Joint stress scenarios and global state aggregation with hard overrides / hysteresis.
- IPS policy interface, with personalized allocation disabled until policy fields exist.

Exit gate: exposure reconciliation to NAV, no double counting, reproducible scenario results and verified hard-override behavior.

## Phase 5 — reporting and decision audit

Implement:
- Daily monitoring report for six sleeves.
- Weekly cross-asset relative-value and risk-change report.
- Monthly RMB return attribution and performance report.
- Immutable investment thesis / decision journal.
- Recommendation audit trail containing inputs, formulas, rule IDs, policy dependencies and invalidation conditions.

Exit gate: report can be regenerated from stored data and exact model/config versions.

## Phase 6 — validation, shadow mode and release

- Walk-forward and expanding-window backtests.
- Sensitivity analysis and regime-specific stress tests.
- Include distributions, costs, fees, taxes where known, FX conversion / hedging and realistic execution assumptions.
- Compare static benchmark, periodic rebalance, staged allocation and no-overlay baselines.
- Run 4–8 weeks in shadow mode with no live allocation actions.
- Publish data gaps, state stability, false-trigger analysis, turnover and net performance.
- Promote only sleeves that pass their acceptance gates; descriptive-only sleeves remain non-actionable.

## Definition of done

The project is not “complete” merely because code runs or a dashboard renders. A sleeve is decision-support ready only when:
- source provenance and coverage are sufficient;
- point-in-time and survivorship checks pass;
- formulas and unit tests pass;
- walk-forward tests and sensitivity analysis are documented;
- thresholds are calibrated and frozen before test periods;
- reports are reproducible;
- limitations and failure modes are visible;
- live actions remain bounded by the approved IPS.

No direct trade execution is in scope.
