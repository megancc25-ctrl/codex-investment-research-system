# NQ-Sentinel Global Allocation 1.0
## RMB Investor Cross-Currency Asset Allocation Engine

Status: design specification; not production-ready until data coverage, tests, and backtests pass.
Target branch: feature/global-allocation-rmb-v1
Base: fix/v2-risk-scoring-engine

## 1. Purpose and boundaries

Add a parallel decision engine for an RMB-based investor. The existing NQ-Sentinel U.S. equity risk engine remains authoritative for U.S. equity/semiconductor market risk and its existing six-module weights (25/25/20/15/10/5). This module must not change those weights, indicators, historical scores, or position-state transitions.

The new engine answers:
- What is the risk-adjusted attractiveness of holding USD assets when measured in RMB?
- Is the FX move driven by RMB fundamentals, broad USD weakness, rate differentials, or risk aversion?
- Are U.S. asset valuations and earnings expectations attractive enough to offset FX risk?
- Should new global allocations be accelerated, staged, paused, or reviewed?

It is a decision-support overlay, not an automatic FX forecast, not a currency trading signal, and not an instruction to remit funds. It must respect applicable capital-control, tax, custody, and product-access rules.

## 2. Core design principles

1. Separate FX regime from underlying asset valuation. A strong RMB does not make an expensive U.S. equity cheap.
2. Measure every foreign asset in both its local currency and RMB total-return terms.
3. Use point-in-time data, publication timestamps, source provenance, freshness, coverage, and revision history.
4. Missing or stale data are N/A, never zero risk and never silently carried forward beyond configured limits.
5. Do not create a single blended score that hides a critical red flag. Preserve sub-scores and hard overrides.
6. No hard-coded allocation percentages in v1.0. Output actions and constraints; personal weights require the user's complete balance sheet, liabilities, horizon, liquidity needs, and risk budget.
7. Do not change existing NQ-Sentinel risk scores or semiconductor trim/re-entry rules.

## 3. Engine architecture

Run four independent sub-engines plus a data-quality gate:

### A. RMB / USD FX regime
Measure:
- USD/CNY spot and 20/60/120/252 trading-day changes.
- 20-day and 60-day annualized realized FX volatility.
- USD broad index (DXY or FRED broad trade-weighted USD index).
- RMB CFETS basket index where a stable, documented free source is available.
- China-US 2-year and 10-year government yield differentials, with consistent maturity and observation dates.
- China trade/current-account and cross-border flow indicators only where official, comparable, and timely data exist.

Interpretation:
- USD/CNY falling means RMB appreciation against USD.
- Distinguish broad USD weakness from RMB-specific strength by comparing USD/CNY with broad USD indices and RMB basket measures.
- Do not infer undervaluation from spot momentum alone. A valuation label requires a documented equilibrium/valuation methodology; otherwise label it “momentum/regime”, not “cheap/expensive”.

### B. U.S. asset valuation and expected-return engine
Track separately by asset class:
- U.S. broad equities: trailing and forward valuation where source coverage is reliable; valuation percentile versus own history; earnings yield and a clearly specified risk-free comparison.
- Nasdaq-100 / semiconductor exposure: own valuation and concentration risk, never substitute S&P 500 valuation.
- U.S. Treasury bills/notes/bonds: maturity-specific yield, real yield, duration, term premium where available, and expected holding-period price sensitivity.
- Cash-like USD instruments: current yield and reinvestment risk.
- Gold/global ex-U.S. assets only as separately defined sleeves if/when added; do not assume they are USD risk-free assets.

Expected-return estimate must be a range, not a point forecast:
- Equity: earnings/dividend yield + conservative real earnings growth + valuation change assumption.
- Bond: starting yield + roll/carry + estimated duration contribution from yield changes - credit/fee effects where relevant.
- FX translation: convert local-currency return to RMB return using the same horizon and consistent USD/CNY convention.
- Publish base / optimistic / pessimistic assumptions and sensitivity to terminal USD/CNY.

Do not use an index forward P/E unless the source, timestamp, index coverage, and methodology are recorded. If only trailing P/E is available, label it accordingly; do not fabricate forward estimates.

### C. U.S. earnings and fundamentals
Track:
- S&P 500 and Nasdaq-100 earnings growth/revisions only where licensed or public data genuinely cover the universe.
- Semiconductor earnings revisions and guidance as a separate industry sleeve.
- Revenue growth, operating margin, free cash flow, capex intensity, and dispersion for major index constituents from SEC filings/XBRL where feasible.
- Breadth: share of covered companies with positive revisions / improving margins, with coverage denominator shown.

Free-data limitation:
SEC filings provide reported fundamentals, not a complete consensus estimate history. If consensus revisions cannot be sourced reliably, show “coverage incomplete” and use explicitly labeled reported-fundamental proxies. Never present those proxies as consensus revisions.

### D. Rates, real yields and systemic USD-asset stress
Track:
- U.S. nominal Treasury yields by maturity.
- TIPS real yields and breakeven inflation.
- China government yields by comparable maturity.
- China-US rate differential and its 20/60/252-day changes.
- Credit spreads (e.g. U.S. high-yield OAS), Treasury market liquidity proxies, volatility, and funding stress indicators where reliable.
- USD funding / broad dollar stress only where a source and definition are documented.

A high real yield can improve prospective bond carry but does not automatically mean long-duration bonds are attractive; duration and term-premium risk must be shown.

## 4. RMB investor return calculation

For a USD asset with local-currency total return R_USD and USD/CNY expressed as CNY per USD:

R_RMB = (1 + R_USD) * (USD/CNY at exit / USD/CNY at entry) - 1

Equivalent FX-only contribution over the period is:
FX_factor = (USD/CNY at exit / USD/CNY at entry)

This convention is mandatory. A falling USD/CNY reduces the RMB value of an unhedged USD holding; a rising USD/CNY increases it. Show:
- local-currency total return;
- FX contribution;
- RMB total return;
- fees/taxes/withholding assumptions;
- hedged versus unhedged status.

Do not combine yield and price return twice. For bonds, use total return or a clearly decomposed carry/roll/price model.

## 5. State machine: green / yellow / red

Each sub-engine produces its own state, confidence, data coverage, reasons, and triggered conditions. The overall state is the most conservative of:
- hard risk overrides;
- FX state;
- valuation/expected-return state;
- earnings state;
- rates/systemic-stress state.

### GREEN — staged increase in global allocation may be considered
Conditions should generally include:
- FX valuation is not stretched against the investor's horizon; if valuation methodology is unavailable, no green valuation claim is allowed.
- U.S. asset valuation is reasonable versus its own history and expected return is positive after plausible FX translation.
- Earnings growth and fundamentals are healthy, with adequate coverage.
- Real yields/carry are attractive relative to duration and credit risk.
- No systemic USD-asset stress override.
Action: allow planned, staged allocation within the user's pre-approved risk budget. Green is not a “buy immediately” signal.

### YELLOW — stage, slow, or hold planned allocation
Possible triggers:
- RMB appreciation is unusually rapid versus its own historical distribution.
- U.S. equity valuation is elevated.
- China-US rate differential is moving sharply against the intended currency exposure.
- Expected RMB-denominated return has compressed or become highly sensitive to terminal FX.
- Earnings breadth weakens or data coverage is incomplete.
Action: use smaller tranches, lengthen execution window, retain liquidity, and require updated expected-return analysis. Do not automatically sell existing long-term assets.

### RED — stop chasing and prioritize risk control
Hard triggers may include:
- U.S. asset valuation reaches an extreme historical percentile AND expected return is poor.
- Broad earnings revisions/fundamentals deteriorate materially and persistently.
- Systemic USD-asset stress / funding / credit liquidity indicators trigger.
- FX volatility or adverse FX move breaches the investor's pre-set loss budget.
Action: suspend new discretionary risk additions; assess concentration, liquidity, and hedging/rebalancing. Red does not automatically mean liquidate all USD assets or predict RMB appreciation.

### Important state logic
- A single weak indicator should not create red unless it is a documented hard override.
- Multiple yellow conditions can elevate overall status to red only under explicit, backtested rules.
- A missing critical input produces “INSUFFICIENT_DATA” / N/A, not green.
- State transitions should use persistence / hysteresis to avoid daily color flicker. Store trigger start date, consecutive observations, release condition, and prior state.

## 6. Threshold calibration

Do not invent universal fixed thresholds for RMB appreciation speed, valuation extremes, rate-differential moves, or FX volatility.

Initial thresholds should be configurable and calibrated using:
- rolling historical percentiles (e.g. 5/10/20-year windows where data support);
- regime-aware comparison;
- out-of-sample testing;
- sensitivity analysis;
- minimum history and coverage requirements.

The first implementation may ship with conservative provisional thresholds marked provisional=true. They must not drive live automated allocation until validation is complete.

## 7. Data-source plan and limitations

Prefer official/free sources and retain raw snapshots:
- FRED: USD/CNY series where available, broad USD index, Treasury nominal yields, TIPS real yields, breakeven inflation, HY OAS, policy rates.
- U.S. Treasury / Treasury FiscalData: official Treasury yield curve and auction/reference data where appropriate.
- Federal Reserve / FRED: rates and financial stress series.
- SEC EDGAR/XBRL: issuer-reported revenue, earnings, cash flow, capex and balance-sheet fundamentals.
- SAFE / PBOC / CFETS / NBS: RMB fixing, FX regime, official reserves/flows, trade and macro data, subject to endpoint availability and release lag.
- Official index providers or documented public sources for index valuation; record methodology and licensing constraints.

For each series store: source_id, series_id, source_url, observation_date, publication_timestamp, retrieved_at, value, unit, currency, frequency, revision/vintage, quality_status, and raw_snapshot_hash.

Never scrape or rely on undocumented endpoints as if they were official APIs. If a source is unstable, cache validated raw data and expose freshness status.

## 8. Data model additions

Suggested tables / schemas:
- fx_observations: pair, quote_convention, observation_date, value, source_id, vintage, retrieved_at, quality_status.
- macro_rate_observations: country, tenor, nominal_yield, real_yield, breakeven, observation_date, source_id.
- asset_valuation_observations: asset_universe, metric, value, methodology, percentile, observation_date, source_id, coverage.
- earnings_fundamental_observations: universe, metric, period, actual_value, revision_value_nullable, coverage_count, denominator, source_id.
- cross_currency_return_scenarios: asset_id, horizon, local_return_scenario, fx_entry, fx_exit, rmb_return, fee_assumptions, scenario_name.
- global_allocation_states: as_of, fx_state, valuation_state, earnings_state, rates_state, systemic_state, overall_state, confidence, coverage, triggers, action_constraints, model_version.
- allocation_policy_config: thresholds, lookback, persistence, minimum_coverage, override_rules, provisional flag, effective_from.

All records must be point-in-time and auditable.

## 9. Daily report output

Add a separate section to the existing daily report:

### RMB Global Allocation
- Overall state: GREEN / YELLOW / RED / INSUFFICIENT_DATA
- Confidence and data coverage
- USD/CNY: current, 1D, 20D, 60D, 252D changes
- FX regime attribution: broad USD vs RMB-specific evidence
- China-US rate differential and trend
- U.S. equity valuation and percentile
- Earnings/fundamental trend and coverage
- U.S. Treasury nominal / real yield and duration context
- Expected RMB return ranges for relevant assets: base / bull / bear
- Key triggers and what would invalidate the current state
- Action: stage / slow / pause new risk / review concentration; no automatic portfolio percentage without user policy inputs

### Portfolio overlay
If user holdings and cost basis are available, show:
- asset and currency exposure look-through;
- unhedged FX exposure;
- concentration by issuer, sector, country, currency;
- RMB-denominated portfolio value and drawdown;
- scenario impact under FX and asset-price shocks.

If holdings are unavailable, explicitly state “portfolio-level FX exposure not calculated”.

## 10. Tests and acceptance criteria

Required tests:
1. FX sign convention: USD/CNY falls -> unhedged USD asset RMB translation is negative.
2. FX sign convention: USD/CNY rises -> unhedged USD asset RMB translation is positive.
3. RMB total return matches hand-calculated fixtures.
4. Missing/stale FX or valuation inputs -> N/A / INSUFFICIENT_DATA.
5. No missing input is silently zero-filled.
6. No new module changes existing six-module weights or historical risk scores.
7. Hard red overrides work and are explainable.
8. Hysteresis prevents unstable daily state flipping.
9. Point-in-time backtest prevents look-ahead / revised-data leakage.
10. Scenario ranges and sensitivity outputs reproduce from stored inputs.
11. Coverage denominator is visible for earnings breadth.
12. Daily report includes source provenance, as-of date, freshness, and model version.

Backtest:
- Use rolling/expanding windows and walk-forward validation.
- Compare staged allocation vs lump-sum allocation and no-FX-overlay baseline.
- Include RMB total returns, fees, taxes where known, and realistic FX conversion assumptions.
- Evaluate drawdown, volatility, downside capture, turnover, regret/cost of delayed entry, and state stability.
- Do not optimize thresholds solely on full-sample performance.
- Do not claim alpha unless it survives out-of-sample testing and costs.

## 11. Implementation sequence

Phase 1 — specification and schema:
- Add this design document.
- Add config schema with provisional thresholds disabled for live actions.
- Add FX conversion function and deterministic unit tests.

Phase 2 — reliable official data:
- Implement FRED FX/rates/real-yield/stress adapters.
- Implement official China rate/fixing sources only after endpoint and vintage validation.
- Persist raw snapshots and provenance.
- Add data freshness and coverage diagnostics.

Phase 3 — valuation and earnings:
- Add valuation data only with explicit methodology and source.
- Add SEC/XBRL fundamental proxies.
- Keep consensus revisions N/A until a defensible source is available.

Phase 4 — state engine and report:
- Add independent sub-states and hard overrides.
- Integrate a separate report section.
- Preserve all existing NQ-Sentinel scores and position state machine.

Phase 5 — validation:
- Unit/integration tests, point-in-time checks, walk-forward backtest, and report reproducibility.
- Only then enable live decision support; no automatic trades.

## 12. Explicit non-goals for v1.0

- No automatic FX trading or remittance.
- No automatic conversion of all RMB cash into USD.
- No fixed universal recommended USD allocation.
- No changes to original six-module score weights.
- No changes to current SOX/semiconductor trim or re-entry rules.
- No unsupported forward P/E, earnings-consensus, or RMB fair-value estimates.
