# PIOS 1.0 — Personal Investment Policy Statement & Implementation Blueprint
Version: 1.0-draft | Date: 2026-11-15
Repository: megancc25-ctrl/codex-investment-research-system
Branch: feature/global-allocation-rmb-v1

## 0. Executive decision

PIOS (Personal Investment Operating System) is the user's capital-allocation and investment-governance system. It connects the household balance sheet, cash-flow capacity, investment objectives, risk budget, strategic allocation, six asset research sleeves, NQ-Sentinel, and Codex implementation.

PIOS is a decision-support system. It does not place trades, exchange currencies or remit funds. Human approval is required for every investment action.

### PIOS versus PRS

- PIOS owns investable capital, investment holdings, transactions, portfolio construction, asset research, allocation and investment performance.
- PRS 1.0 is the broader personal risk system (household, career, education, retirement and other life risks). PIOS may provide approved financial summaries to PRS, but must not absorb unrelated PRS modules.
- One fact has one system of record. PIOS owns investment transactions; PRS consumes approved summaries.

## 1. Known user facts and missing information

### 1.1 Previously stated facts — refresh before live use

- The user previously reported a semiconductor active fund at approximately 80% of total assets, using SOX as a risk proxy; the fund name is intentionally not required.
- The user reported executing a first 20% reduction and keeping proceeds as cash.
- The remaining 20% in the earlier portfolio description was not sufficiently characterized. Do not assume it is all cash.
- The user is researching a self-occupied home purchase in Zhuhai. Down payment, taxes, fees, renovation, furnishing and moving costs must be treated as planned liquidity obligations once dates and amounts are known.
- Preferred deployment is cloud + local hybrid: cloud monitors public market data; actual holdings and personal financial records stay local in Obsidian / local storage.
- A strict risk preference and a maximum additional tolerable loss of 10% of then-current portfolio NAV were previously stated in the NQ-Sentinel context. Store this as a provisional portfolio-level cap pending reaffirmation. Do not reinterpret it as a 10% household-net-worth drawdown limit.
- Missing data must be N/A / UNKNOWN / INSUFFICIENT_DATA, never zero-filled.

These are dated records, not proof of today's exact weights. Require a new holdings snapshot before live portfolio calculations.

### 1.2 Missing information that blocks personalized target weights

Collect locally:
- Household assets by owner, currency, liquidity, market value and valuation date.
- Liabilities by balance, currency, interest rate, fixed/floating status, payment schedule and maturity.
- Monthly after-tax income by source and currency; essential and discretionary expenses.
- Emergency reserve and its liquidity.
- Zhuhai home purchase budget, target date, all-in cash required, expected mortgage amount/rate/term and renovation costs.
- Other known 1–5 year obligations.
- Investment horizon and withdrawal schedule for each goal.
- Tax residence, account jurisdiction, product access and FX / remittance constraints.
- Desired real RMB return and acceptable shortfall probability.
- Confirmation of the 10% loss limit, its reference point and whether it remains active.
- Current post-trim positions, units and market values. Fund name may remain anonymized.

Do not infer any missing amount.

## 2. Household balance sheet and cash-flow policy

### 2.1 Maintain two balance sheets

A. Household net-worth balance sheet:
- All material assets, including owner-occupied home, deposits, investments and other assets.
- All liabilities, including mortgage, consumer debt, private loans and accrued obligations.
- Household net worth = total assets - total liabilities.

B. Investable balance sheet:
- Eligible financial assets that can be allocated or liquidated under known terms.
- Less ring-fenced reserves and obligations.
- Exclude the primary residence from investable capital unless a deliberate home-equity policy is approved.
- Investable capital = eligible financial assets - protected reserves - near-term committed liabilities.

The home purchase is a household capital-allocation decision with a deadline, not an ordinary portfolio rebalance.

### 2.2 Asset record schema

Each asset record must include:
asset_id, owner_alias, asset_type, account_alias, currency, jurisdiction, market_value, valuation_date, source, liquidity_bucket, settlement_days, redemption_terms, guarantee_status, insured_amount, cost_basis_if_available, investable_flag, restricted_flag, collateral_flag, source_document_ref, verified_at, confidence.

Asset taxonomy:
- RMB demand / term deposits and money-market funds.
- RMB government, policy-bank and credit fixed income.
- USD cash and cash equivalents.
- U.S. Treasuries by maturity.
- U.S. mega-cap / AI / semiconductor equities and funds.
- Global ex-U.S. equities.
- China A-shares and Hong Kong-listed China equities as separate jurisdiction/currency exposures.
- Gold by wrapper (physical, ETF, account gold).
- Owner-occupied real estate and other illiquid assets.

### 2.3 Liability record schema

liability_id, currency, principal_outstanding, interest_rate, fixed_or_floating, next_reset_date, payment_amount, payment_frequency, maturity_date, collateral_asset_id, prepayment_penalty, arrears_status, source_document_ref, verified_at.

### 2.4 Cash-flow calculations

Monthly:
- Net operating surplus = after-tax recurring income - essential expenses - recurring obligations.
- Savings rate = net operating surplus / after-tax recurring income, only if income > 0.
- Fixed-obligation coverage = liquid low-risk assets / essential monthly outflows.
- Debt-service ratio = monthly debt service / after-tax recurring income.
- Goal funding ratio = dedicated liquid assets / required cash for the goal at target date.

Forecast 1, 3, 6, 12, 24 and 36 months under base, income shock, expense inflation, home purchase, debt refinancing and concurrent investment drawdown scenarios.

Do not fund a fixed-date home purchase with volatile equities unless the user explicitly accepts the quantified risk.

### 2.5 Liquidity buckets

- L0: same-day / demand.
- L1: within 7 calendar days.
- L2: within 30 days.
- L3: 1–12 months.
- L4: over 12 months / illiquid.

Reserve amounts must be calculated from actual obligations:
- Emergency reserve = user-approved months of essential outflows, adjusted for income stability, dependents, insurance, debt and access to credit. Unset until approved.
- Home reserve = down payment + taxes/fees + renovation/furnishing + moving + contingency - committed financing.
- Other known 1–3 year obligations are funded separately.
- Only residual investable capital enters strategic asset allocation.

## 3. Investment objectives and measurement

### 3.1 Objective hierarchy

1. Preserve ability to meet essential household obligations and home-purchase plan.
2. Avoid permanent capital impairment and forced selling.
3. Match currency and liquidity to known RMB liabilities.
4. Grow real RMB purchasing power over the long term.
5. Seek additional returns only within approved risk budgets.

### 3.2 Base currency and return

Primary unit of account: RMB.

For foreign currency C quoted as CNY per one unit of C:
R_RMB = (1 + R_local) * (FX_exit / FX_entry) - 1.

For USD holdings use USD/CNY; for EUR, JPY, GBP and other currencies use their own CNY cross rates. Report local return, FX contribution, income, costs and net RMB total return separately. Do not add dividends/coupons twice when total-return data already include them.

### 3.3 Return hurdle

Required real RMB return must be derived from goal amount, goal date and available capital. Nominal hurdle = (1 + required real return) * (1 + expected RMB inflation) - 1.

Until goal amounts, dates and inflation assumptions are known, return_hurdle = NOT_SET. No personalized GREEN entry signal may be issued without an approved hurdle.

## 4. Risk budget and loss controls

### 4.1 Three separate risk budgets

A. Household liquidity / solvency risk: ability to meet essential expenses and liabilities after income interruption and market drawdown.

B. Investable portfolio drawdown risk: previously stated maximum additional loss of 10% of then-current portfolio NAV, provisional and subject to confirmation. Define reference NAV date, high-water mark, flow adjustment, and whether the 10% means peak-to-trough or loss from current NAV before treating it as final.

C. Position / factor / currency concentration: limits set in the IPS after balance-sheet review. Semiconductor exposure is a known concentration and must be measured through underlying issuer and factor look-through. Multiple funds with the same holdings are not true diversification.

### 4.2 Risk measurements

Daily:
- RMB portfolio NAV, 1D / 20D / 60D / 252D return.
- Drawdown from high-water mark and realized volatility.
- Issuer, sector, country and currency concentration.
- Unhedged FX exposure and liquidity ladder.

Weekly / monthly:
- Marginal and component risk contribution where covariance sample size is adequate.
- Historical expected shortfall / tail loss with sample and limitations.
- Stress losses, liquidity haircuts, correlation regime and concentration drift.

Risk tolerance (psychological willingness), risk capacity (objective ability to absorb loss) and risk requirement (return needed for goals) must be separate. The binding limit is the most restrictive of capacity, approved tolerance and liquidity constraints.

### 4.3 Required stress tests

- SOX / U.S. technology: -20%, -30%, -40%.
- Global equities: -20%, -30%.
- China equities: -20%, -30%.
- USD/CNY: ±5%, ±10%; other currency shocks modeled independently.
- U.S. Treasury yields: +50bp, +100bp, +150bp and -50bp, -100bp.
- RMB rates and credit spreads widen.
- Gold: -15%, -25%; do not assume it hedges.
- Combined risk-off and inflation shock.
- Household income interruption: 3, 6, 12 months.
- Home purchase coincides with risk-asset drawdown.
- Redemption gate / settlement delay for illiquid products.

These are hypothetical stress scenarios, not forecasts.

### 4.4 Operational risk states

- GREEN: within risk budget, liquidity funded, data sufficient.
- YELLOW: provisional warning when risk budget usage reaches 70–90%, concentration rises, or data quality deteriorates. Review and pause discretionary additions pending analysis.
- RED: approved loss limit breached or projected to breach; household liquidity shortfall; forced-sale risk; verified severe credit, custody or market-access event. Pause new risk and review reductions / liquidity.
- INSUFFICIENT_DATA: no allocation increase based on missing critical inputs.

The 70–90% warning band is provisional and configurable, not a calibrated market threshold.

## 5. Strategic asset allocation policy

### 5.1 No target weights until the household data are complete

The sequence is mandatory:
1. Reconcile household assets and liabilities.
2. Ring-fence emergency, home-purchase and near-term obligation reserves.
3. Calculate residual investable capital.
4. Define goal horizons and withdrawal schedules.
5. Assess risk capacity and currency liabilities.
6. Only then set strategic weights and policy bands.

Do not import a generic 60/40 portfolio or let current market forecasts dictate long-term strategic weights.

### 5.2 Three-layer capital structure

Layer 1 — liability-matching / reserve capital:
emergency reserve, home-purchase reserve, near-term RMB obligations, debt-service and tax reserves. Excluded from the six-sleeve risk allocation.

Layer 2 — strategic long-term portfolio:
diversified multi-asset core, strategic weights based on goals and risk capacity, rebalanced within approved bands.

Layer 3 — tactical / opportunity allocation:
limited risk budget for valuation and cycle opportunities, funded from within the strategic policy (not leverage). Every change needs thesis, catalyst, RMB expected return, downside, size and invalidation criteria.

### 5.3 Six asset sleeves

1. U.S. mega-cap technology and AI infrastructure.
2. U.S. short- and intermediate-term Treasuries.
3. Global quality equities ex-U.S.
4. Gold.
5. China quality equities.
6. RMB cash and fixed income.

Each sleeve outputs quality_state, risk_state, entry_attractiveness, local and RMB expected-return ranges, FX exposure, liquidity, risk contribution, overlap, source coverage and confidence.

A sleeve RED state restricts new risk and triggers review; it does not mechanically liquidate every holding. GREEN permits consideration within policy; it is not a buy command.

### 5.4 Target-weight calculation

After IPS completion:
- Estimate forward RMB return ranges, volatility, drawdown and stress losses.
- Estimate covariance / tail dependence with sample-size controls.
- Optimize subject to liquidity, loss, concentration, currency and access constraints.
- Compare robust optimization with a simple diversified policy benchmark.
- Sensitivity-test expected returns and covariance.
- Prefer a robust, explainable policy portfolio over the highest historical Sharpe ratio.
- Set strategic weights, tolerance bands, review date and rationale.

Do not rely on a single mean-variance optimizer.

### 5.5 Rebalancing

- Full review quarterly.
- Trigger review when policy bands or risk limits are breached.
- Use new contributions and distributions before selling.
- No rebalancing during critical data failure or market-access disruption.
- Include tax, fees, spread, redemption terms and FX costs.
- Every rebalance has before/after risk and liquidity reports.

## 6. Six-sleeve research integration

Detailed source, metric, formula, state, backtest and report requirements are defined in:
docs/architecture/GLOBAL_MULTI_ASSET_RESEARCH_SPEC_V1.md

PIOS consumes the sleeve outputs; it must not duplicate their calculation logic.

| Sleeve | Fundamental / quality | Valuation / income | Key risks |
|---|---|---|---|
| U.S. mega-cap & AI | Revenue, FCF, margins, capex, ROIC, monetization evidence | P/E / FCF yield / valuation percentile | Issuer concentration, capex payback, USD/CNY |
| U.S. Treasuries | Curve, liquidity, real yields | Yield, carry, roll-down | Duration, convexity, FX, reinvestment |
| Global ex-U.S. quality | ROIC, FCF, leverage, governance | Sector/country-adjusted valuation, dividend sustainability | Country, issuer and currency |
| Gold | Supply/demand, ETF holdings, central-bank purchases, positioning | No P/E or contractual yield | Real yields, USD, volatility, custody |
| China quality | FCF, ROIC, leverage, governance, audit | Sector-adjusted P/E / P/B / FCF yield / dividend | Earnings breadth, governance, policy concentration |
| RMB cash & fixed income | Counterparty, issuer, credit, liquidity | Net yield, real yield, spread, carry | Duration, default, redemption, bank concentration |

Do not label an asset “quality” solely because an index or fund uses that word. Preserve issuer-level definitions and look-through.

## 7. NQ-Sentinel integration

NQ-Sentinel remains the specialized U.S. equity / semiconductor market-risk engine. PIOS consumes its outputs but does not rewrite them.

Immutable:
- Preserve original six NQ-Sentinel module weights: 25/25/20/15/10/5.
- Preserve existing indicators, historical scores and semiconductor position-state logic.
- Do not conflate NQ score with PIOS global allocation score.
- SOX is a risk proxy, not the user's actual fund price. Track proxy basis / tracking error if data permit.
- Record the first 20% reduction as a dated transaction only after its amount and calculation basis are verified locally. Do not infer current holdings from an old percentage.

PIOS synthesis order:
1. NQ-Sentinel U.S. equity state.
2. Six asset sleeve states.
3. Household liquidity / liability state.
4. Portfolio risk-budget usage.
5. Policy constraints and data quality.
6. Human-approved action eligibility.

U.S. equities RED while Treasuries or RMB cash are attractive does not imply selling all USD exposure. Separate equity risk from currency and cash-equivalent risk.

## 8. Investment decision and behavior protocol

Every material decision records:
decision_id, date, instrument, proposed / actual action, thesis, facts, inferences, assumptions, base/bull/bear cases, expected RMB return range, holding horizon, downside, position size, catalyst, monitoring metrics, invalidation conditions, disconfirming evidence, strongest counterargument, source snapshots, model/config version, user approval and review date.

Rules:
- No position increase solely because price fell.
- No sale solely because a color changed without checking source, rule and portfolio context, except a pre-approved hard limit.
- No averaging down without a fresh thesis and risk recalculation.
- No chasing a rally without return and size review.
- Model score is evidence, not authority.
- Record policy deviations and review monthly.

## 9. Reporting cadence

### Daily monitoring
- As-of timestamp, data coverage, stale sources, model/config versions.
- Household liquidity alerts and upcoming obligations.
- RMB NAV, drawdown, risk budget, concentration, FX and liquidity.
- Six sleeve quality / risk / entry states, indicators, RMB scenarios and triggers.
- NQ-Sentinel score and unchanged position-state output.
- Cross-asset stress losses as % of investable NAV and household net worth.
- Allowed action: ADD_WITHIN_POLICY / STAGE / HOLD / PAUSE_NEW_RISK / REVIEW / INSUFFICIENT_DATA.
- Evidence, rule IDs, invalidation and human approval requirement.

### Weekly research
Earnings / estimate changes (consensus only if source verified), rates, real yields, FX, credit, gold, relative RMB return, correlation, concentration, catalysts and strongest counterevidence.

### Monthly performance and governance
RMB net return attribution (local return, FX, income, fees, taxes), benchmark comparison, risk-budget usage, drawdown, policy drift, decision-journal and model-error review.

### Quarterly IPS review
Reconcile balance sheet / cash flow, home plan, goals, risk capacity, strategic weights, bands and policy exceptions.

## 10. Data architecture and privacy

Cloud:
- public market data, macro, rates, FX, index and public filings;
- public-data calculations and source-health monitoring.

Local:
- actual holdings and transactions;
- household balance sheet, liabilities, income / expenses;
- home-purchase funding, tax / account details;
- personal risk budget, target weights and decision journal.

Do not upload raw personal financial records to cloud by default. Only send approved aggregated exposures with explicit opt-in.

Obsidian is the human-readable knowledge base. A structured local database is the system of record for balances, holdings, transactions, scenarios and audit events. Markdown reports are generated views, not the sole database.

Encrypt sensitive local data and backups. Never commit holdings, account IDs, passwords, personal documents or API keys to Git. Keep public market cache separate from the private personal database.

Every market observation stores source, series/instrument ID, observation date, publication timestamp, retrieval timestamp, revision/vintage, unit, currency, freshness, quality, raw hash and model version.

## 11. Codex implementation plan

Target branch: feature/global-allocation-rmb-v1.
Read the three existing architecture documents and this blueprint before code changes.

### Phase 0 — repository reconnaissance (first; stop for review)

Create docs/implementation/PIOS_PHASE0_RECONNAISSANCE.md documenting:
- architecture, language, dependencies and test commands;
- original NQ invariants and regression fixtures;
- existing adapters and reusable code;
- report, scheduler, storage and configuration;
- local privacy boundary and database design;
- missing sources, licensing and point-in-time limitations;
- module dependency map;
- exact Phase 1 files and test plan.

No production code changes in Phase 0.

### Phase 1 — local household ledger and IPS schema

Implement asset / liability / cash-flow / goals / liquidity / IPS / risk-budget schemas; local persistence; manual CSV and user-entered import; validation, reconciliation, versioned policy and audit trail.

Acceptance:
- assets minus liabilities reconcile to net worth;
- investable capital excludes ring-fenced reserves;
- unknown values remain null / UNKNOWN;
- tests prove personal data does not leave local environment;
- import/export reproducible;
- approvals and policy versions recorded.

### Phase 2 — liquidity and risk-budget engine

Implement emergency / home / near-term reserves, cash-flow forecast, risk capacity / tolerance separation, drawdown and scenario-loss budget, concentration and FX exposure.

Acceptance:
- risky assets are never treated as guaranteed liquidity;
- home reserve excluded from equity allocation;
- holding-level stress losses reconcile;
- prior 10% loss cap remains provisional until semantics are confirmed.

### Phase 3 — strategic allocation

Only after household data and IPS are complete: goal horizons, target weights / bands, robust portfolio comparison, scenario constraints and cash-flow-first rebalancing.

Acceptance:
- no target weights while required IPS fields are missing;
- sensitivity and rationale accompany optimized outputs;
- no automatic trades.

### Phase 4 — six sleeves and NQ integration

Use GLOBAL_MULTI_ASSET_RESEARCH_SPEC_V1.md and existing NQ pipelines. Preserve original NQ scores and position logic.

Acceptance:
- all six sleeves expose standard contracts;
- local / RMB returns reconcile;
- overlap and currency look-through work;
- NQ regression tests remain unchanged.

### Phase 5 — reports and decision journal

Implement daily / weekly / monthly / quarterly reports, recommendation audit and decision journal. Personal reports local by default.

### Phase 6 — backtest, shadow mode and controlled release

Run point-in-time walk-forward, survivorship / look-ahead, costs / tax / FX and sensitivity tests; shadow-run 4–8 weeks; publish data gaps and false triggers. No live allocation before user approval of IPS and sleeve validation.

## 12. Safe initial configuration

base_currency: CNY
personal_data_storage: local_only
cloud_personal_data_sync: disabled
auto_trade: disabled
auto_fx_conversion: disabled
target_weights: null
return_hurdle: null
emergency_reserve_months: null
home_purchase_budget: null
strategic_review_frequency: quarterly
nq_sentinel_original_weights: [25, 25, 20, 15, 10, 5] (immutable)
prior_max_additional_loss_pct: 10 (provisional; confirm definition and applicability)
threshold_live_actions: disabled
missing_data_policy: null_not_zero
portfolio_state_without_holdings: INSUFFICIENT_DATA
personal_allocation_without_complete_ips: DISABLED

## 13. Definition of done

PIOS 1.0 is ready for controlled personal use only when:
1. Household balance sheet and cash flow reconcile with current as-of dates.
2. Emergency, home and near-term reserves are separately funded.
3. Risk capacity and tolerance are documented.
4. Strategic weights and rebalancing bands are user-approved.
5. Six sleeves have validated sources, coverage and formulas.
6. NQ-Sentinel original scoring and position logic are regression-identical.
7. RMB returns, FX attribution, overlap and risk contribution reconcile.
8. Stress tests cover investment and household liquidity shocks.
9. Backtests are point-in-time and include realistic costs where available.
10. Local privacy and backups are tested.
11. Reports are reproducible.
12. No trade or FX action occurs without explicit human approval.

## 14. Minimum information needed to personalize the IPS

Enter locally in broad RMB-equivalent figures; do not share account numbers, passwords, exact fund name or identifying documents:
- total household financial assets by currency and asset class;
- total liabilities and monthly debt service;
- monthly after-tax income and essential expenditure;
- Zhuhai home purchase target date, total cash required and expected mortgage;
- current post-trim semiconductor position as % of investable assets, cash and other holdings;
- investment horizon and confirmation of whether the prior 10% maximum additional loss remains binding.

Until these fields are populated, PIOS may monitor markets and calculate scenarios but must not publish personalized strategic target weights.
