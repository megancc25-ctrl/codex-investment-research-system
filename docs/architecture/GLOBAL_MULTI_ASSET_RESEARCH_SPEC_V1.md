# Global Multi-Asset Research Specification v1.0
## Six asset sleeves for an RMB-based personal investment operating system

Status: engineering specification for staged implementation. Not a live investment recommendation.
Target branch: feature/global-allocation-rmb-v1
Related design: docs/architecture/NQ_SENTINEL_GLOBAL_ALLOCATION_V1.md

---

## 1. Purpose, scope and non-negotiable boundaries

This specification adds six independently researched asset sleeves to the RMB Global Allocation engine:

1. U.S. mega-cap technology and AI infrastructure equities.
2. U.S. short- and intermediate-duration Treasury securities.
3. Global quality equities excluding the U.S. sleeve to prevent overlap.
4. Gold.
5. China quality equities.
6. RMB cash and fixed-income assets.

The system is for decision support, portfolio monitoring and research audit. It must not place trades, exchange currencies, remit funds, or infer user-specific allocation weights without a complete and approved Investment Policy Statement (IPS).

### Compatibility constraints

- Do not alter the original NQ-Sentinel U.S. equity six-module weights (25/25/20/15/10/5), their indicators, historical scores, or semiconductor position-state transitions.
- Reuse existing NQ-Sentinel U.S. technology, semiconductor, AI infrastructure, FRED and SEC data pipelines where validated. Do not create duplicate pipelines for the same source series.
- Global Allocation and the six asset sleeves run in parallel to the existing U.S. equity risk engine.
- No hard-coded personal allocation percentages.
- No missing-value zero fill; no fabricated forward P/E, earnings-consensus revision, fair value, or FX equilibrium value.
- Every observation must be point-in-time auditable, with source, publication time, retrieval time, vintage/revision, freshness and quality state.
- A sleeve may be GREEN on asset quality and RED on entry attractiveness. Keep those dimensions separate.

## 2. Common data and state contract

Every observation must include:

| Field | Meaning |
|---|---|
| observation_id | Stable unique record identifier |
| instrument_id / universe_id | Canonical security or index universe |
| metric_id | Stable metric name |
| value, unit | Numeric value and explicit unit |
| currency, quote_convention | Currency and FX quote convention |
| observation_date | Date the observation describes |
| publication_timestamp | When it became public |
| retrieved_at | When the pipeline retrieved it |
| source_id, source_url | Source provenance |
| source_methodology | Calculation / index / accounting methodology |
| vintage_id / revision | Point-in-time vintage where available |
| coverage_count, coverage_denominator | Coverage and denominator, when relevant |
| freshness_status | FRESH / STALE / MISSING / INVALID |
| quality_status | PASS / WARN / FAIL |
| raw_snapshot_hash | Hash of archived raw source payload |
| model_version | Calculation version |

Do not use retrieval time as a substitute for publication time. Revised macro data must not leak into historical backtests before the revision was published.

### Common return convention

All asset sleeves report local-currency total return and RMB investor total return.

For an asset denominated in foreign currency C, where FX(CNY per C) means RMB per one unit of foreign currency:

R_RMB = (1 + R_local) * FX_exit / FX_entry - 1

For USD assets, FX is USD/CNY. For EUR assets, it is EUR/CNY, etc. A decline in CNY per foreign currency means RMB appreciation and reduces the RMB value of an unhedged foreign asset.

For partially hedged exposure, use:
R_RMB_hedged = (1 + R_local) * (1 + R_FX_hedge_return) - 1 - hedge_cost
Do not approximate a hedge as a perfect elimination of currency risk. Store hedge ratio, instrument, roll dates, basis, collateral and costs.

If total-return series already include distributions, do not add dividends/coupons again.

### Common rolling statistics

- Daily total return: P_t / P_(t-1) - 1, adjusted for distributions and corporate actions.
- Annualized volatility: stdev(daily returns) * sqrt(252) for daily trading series; use actual observation frequency and appropriate annualization for non-daily data.
- Maximum drawdown: min_t(P_t / running_max(P) - 1).
- Rolling return: P_t / P_(t-n) - 1.
- Historical percentile: empirical percentile of the current observation against a documented trailing window, calculated only from observations available at that date.
- Correlation: rolling correlation of synchronized total-return observations; publish sample count and do not interpret low sample counts.
- Real return approximation: (1 + nominal total return) / (1 + inflation over same horizon) - 1. Label CPI proxy and lag; do not treat a lagged CPI print as contemporaneous inflation.

### Common state semantics

Each sleeve outputs:
- quality_state: GREEN / YELLOW / RED / INSUFFICIENT_DATA
- entry_attractiveness: GREEN / YELLOW / RED / INSUFFICIENT_DATA
- risk_state: GREEN / YELLOW / RED / INSUFFICIENT_DATA
- confidence: HIGH / MEDIUM / LOW
- coverage_ratio and required_fields_passed
- reasons[], triggered_rules[], invalidation_conditions[]
- allowed_action: ADD_WITHIN_POLICY / STAGE_OR_WAIT / PAUSE_NEW_RISK / REVIEW_EXISTING / NO_DECISION

Overall state must not be an arithmetic average that hides a hard risk. Apply hard overrides first, then required-data gates, then sleeve rules. A critical missing input produces INSUFFICIENT_DATA unless a separately evidenced hard risk override is active.

### Threshold governance

No universal threshold is assumed to be valid for every asset and regime. Each rule must declare one of:
- HARD: economically or contractually defined threshold (e.g. credit default, policy risk limit).
- CALIBRATED: rolling percentile / regime distribution, fitted only on training history and frozen for the test period.
- USER_POLICY: investor-specific limit supplied in IPS.
- PROVISIONAL: development-only value; cannot drive live actions.

Default calibration windows: 5 years where sufficient data exist; 10 years for long-cycle sensitivity; 20 years only where data quality and comparability permit. Require at least 756 daily observations for daily 3-year statistics, or an explicit lower-frequency minimum. For fundamentals, require at least 8 quarterly observations for trend claims; longer histories are preferred. A percentile is not valid if methodology or universe composition changes are unadjusted.

For calibrated directional metrics:
- GREEN: favorable 0–60th percentile of the risk metric, or 60–100th percentile of an attractiveness metric.
- YELLOW: middle / warning band, normally 60–85th percentile of a risk metric.
- RED: adverse extreme, normally above 85th/90th percentile of a risk metric, but only with corroboration unless it is a documented hard override.
The polarity must be defined per metric. Never apply percentile direction blindly.

Persistence / hysteresis:
- Non-hard YELLOW: require 2 consecutive valid observations, or 2 of last 3.
- Non-hard RED: require 3 consecutive valid observations, or 3 of last 5, and at least two independent evidence families.
- Hard RED: immediate.
- De-escalation: require at least 5 consecutive valid observations below release threshold; hard overrides require explicit resolution.
- Record first_triggered_at, last_triggered_at, consecutive_count, release_condition and prior_state.

## 3. Sleeve A — U.S. mega-cap technology and AI infrastructure

### Universe definition

Maintain separate but linked universes:
- U.S. mega-cap technology: constituents of a documented large-cap U.S. technology / platform universe.
- AI infrastructure: semiconductor compute, networking, memory, foundry/equipment, cloud hyperscalers, data-center power/cooling and selected infrastructure suppliers.
- Benchmarks: Nasdaq-100 and SOX (or a documented total-return equivalent). Do not use S&P 500 valuation as a proxy for Nasdaq-100 or SOX.
- Company-level records use canonical issuer_id and security_id. ADRs and multiple share classes map to the same issuer for concentration calculations.

Universe membership must be point-in-time. Do not backtest current constituents as if they existed historically.

### Primary sources

1. SEC EDGAR Company Facts / submissions and issuer 10-K, 10-Q, 8-K filings: reported revenue, operating income, cash flow, capex, debt, share count and segment disclosures.
2. Company investor-relations earnings releases, presentations and transcripts: capex guidance, cloud growth, AI product revenue disclosure, backlog, utilization and management commentary. Archive source and publication timestamp.
3. FRED / U.S. Treasury: risk-free yields and real yields used in valuation context.
4. Official index providers for index constituents, weights and methodology, subject to licensing. If a free public source is used, record its coverage and limitations.
5. Exchange data / issuer filings for prices, shares and corporate actions. Public free price feeds may be used for research prototypes only after validation; record adjusted/unadjusted status and licensing limitations.

Do not represent SEC reported data as sell-side consensus revisions. Consensus estimates require a licensed or demonstrably complete source. If unavailable, consensus_revision = N/A.

### Required metrics and formulas

Company fundamentals:
- Revenue growth YoY = revenue_t / revenue_t-4Q - 1.
- Operating margin = operating_income / revenue.
- FCF = cash_from_operations - capital_expenditure.
- FCF margin = FCF / revenue.
- Capex intensity = capex / revenue.
- Capex-to-CFO = capex / cash_from_operations, only if CFO > 0.
- Net debt = total debt - cash_and_short_term_investments.
- Net debt / EBITDA, only when EBITDA is positive and comparable.
- Incremental FCF conversion = change in FCF / change in revenue; suppress when denominator is near zero or sign-changing.
- ROIC = NOPAT / average invested capital, with documented NOPAT and invested-capital definitions.

AI infrastructure:
- Cloud revenue growth, capex growth and capex/revenue.
- FCF after capex = CFO - capex (do not subtract capex twice).
- AI-specific revenue / backlog only when separately disclosed and definitions are stable.
- Power / data-center capacity, GPU utilization, rental prices and residual values are optional vendor/industry indicators; mark coverage and source quality. Never infer actual utilization or unit economics from anecdotal listings.
- Capex payback proxy: incremental operating profit or cash flow attributable to investment / incremental capex. If attribution is unavailable, show N/A rather than fabricate AI ROI.

Valuation:
- Trailing P/E = market capitalization / trailing 12-month net income; suppress for negative/near-zero earnings.
- FCF yield = trailing 12-month FCF / market capitalization; show negative values.
- EV/EBITDA = enterprise value / trailing EBITDA, only if EBITDA positive.
- Forward P/E only from a named, timestamped, documented estimate source with universe coverage.
- Valuation percentile compares like-for-like methodology and universe history; index changes and sector mix must be disclosed.
- Equity expected-return range = starting earnings yield or FCF yield + conservative nominal per-share earnings/FCF growth + valuation-multiple change + dividend yield, less fees/tax. Do not add both earnings yield and FCF yield as if independent. Use one primary valuation framework per model.

Breadth and concentration:
- Positive fundamental breadth = issuers with improving FCF margin or positive YoY FCF / issuers with valid observations.
- Earnings revision breadth only if true consensus revisions exist: positive revisions count / valid covered issuers.
- Top-5 and top-10 issuer weight; effective number of holdings = 1 / sum(weight_i^2).
- Report mega-cap and AI sleeve overlap with existing semiconductor exposure.

### State rules

Quality GREEN:
- Revenue / FCF and margins stable or improving over at least 2–4 quarters.
- No broad deterioration in balance-sheet or cash conversion metrics.
- AI capex growth is accompanied by evidence of monetization, utilization, or credible cash-flow capacity; capex growth alone is not a positive signal.

Quality YELLOW:
- Revenue growth decelerates, FCF margin compresses, capex rises faster than revenue for multiple quarters, or breadth weakens.
- AI revenue / utilization claims lack sufficient coverage.
- Concentration becomes materially higher than the historical universe distribution.

Quality RED:
- At least two independent evidence families deteriorate persistently: e.g. revenue growth and FCF/margins; or broad reported fundamentals and balance-sheet stress.
- A single high valuation percentile is not sufficient to label business quality RED.

Entry attractiveness:
- GREEN: valuation percentile <= 60th and base-case RMB expected return exceeds the IPS hurdle rate with a positive margin of safety; bear-case loss fits risk budget.
- YELLOW: valuation percentile 60th–85th, or base-case RMB return is close to hurdle, or FX sensitivity materially changes the result.
- RED: valuation percentile > 85th/90th AND base-case RMB return is below the IPS hurdle or bear-case loss breaches approved risk budget.
- If no IPS hurdle is configured, show expected-return range and percentile but entry_attractiveness = INSUFFICIENT_DATA / POLICY_NOT_SET; do not invent a personal hurdle.

Hard / risk overrides:
- Accounting restatement, going-concern warning, material fraud allegation confirmed by filing/regulator, covenant breach or severe liquidity event triggers issuer-level RED pending review.
- Portfolio concentration limits are USER_POLICY, not generic market thresholds.

### Report outputs

- Benchmark price/total-return, 1D/20D/60D/252D return, volatility and drawdown.
- Valuation metrics and historical percentiles with methodology/source.
- Revenue, operating margin, FCF, FCF margin, capex and ROIC trends.
- AI capex vs monetization evidence; disclose what is not observable.
- Fundamental breadth, universe coverage denominator and top issuer weights.
- Base / bull / bear local and RMB expected-return ranges; terminal FX assumptions.
- Sleeve state, issuer-level red flags, overlap with existing SOX/semiconductor exposure.
- Action constraints and exact conditions for reassessment.

## 4. Sleeve B — U.S. short- and intermediate-term Treasuries

### Maturity buckets

Keep separate sleeves:
- T-bills / cash equivalents: 0–1 year.
- Short Treasuries: 1–3 years.
- Intermediate Treasuries: 3–7 years.
Do not label 3–7 year exposure as cash-like. Use maturity-matched Treasury total-return series or a transparent duration-matched benchmark.

### Primary sources

- U.S. Treasury daily par yield curve and auction data.
- FRED Treasury constant maturity series, TIPS real yields and breakeven inflation series.
- Treasury FiscalData for issuance, outstanding debt and auction details where relevant.
- Federal Reserve / FRED for policy rates and financial conditions.
- A validated total-return index source for realized bond total returns; yield series alone are not total return.

Candidate FRED series IDs to validate during adapter implementation include DGS3MO, DGS1, DGS2, DGS5, DFII5, DFII10 and T10YIE. These are examples, not a guarantee of current availability or identical publication schedules. Verify metadata and units before use.

### Required metrics and formulas

- Yield-to-maturity / par yield by maturity bucket; distinguish par yield from an instrument's actual yield-to-maturity.
- Real yield = nominal yield - matched breakeven inflation, where maturity and date are comparable. For TIPS use quoted real yield directly where appropriate.
- Term spread = 10Y yield - 2Y yield (context only; not a standalone recession timer).
- Duration price approximation: bond price return ≈ -modified_duration * change_in_yield + 0.5 * convexity * (change_in_yield)^2.
- Expected holding-period return = carry + roll-down + estimated price return from yield-curve scenario - transaction costs - taxes. Avoid double counting coupon and yield.
- Reinvestment risk proxy = proportion of portfolio maturing within horizon and scenario yield available at reinvestment.
- Curve slope / butterfly and 20/60/252-day changes.
- Realized total return, annualized volatility, drawdown and correlation with equities/gold.

### State rules

Entry attractiveness GREEN:
- Starting yield / real yield is attractive versus its own comparable-history distribution and the user's RMB return hurdle after USD/CNY scenarios.
- Duration stress loss under +50bp / +100bp yield shocks fits the approved risk budget.
- Credit risk is sovereign USD exposure; still monitor market liquidity, inflation and term premium.

YELLOW:
- Yield is near the middle of historical distribution; or rate volatility / term premium rises; or RMB-adjusted expected return is highly sensitive to FX terminal value.
- Intermediate bucket has materially greater duration risk than user policy permits.

RED:
- Base-case RMB expected return is below the configured hurdle and bear-case rate/FX loss breaches risk budget; or market liquidity / settlement stress hard override is triggered.
- Low yield alone is an unattractive entry signal, not a systemic default signal.

Required scenario shocks:
- Parallel yield curve +50bp, +100bp, -50bp, -100bp.
- Bear steepener and bull steepener scenarios.
- USD/CNY terminal FX shocks from historical percentile and IPS-defined stress.
- Joint equity drawdown + rates up scenario; do not assume bonds always hedge equities.

Report:
- Yield, real yield, duration, convexity, curve shape and percentile.
- 0–1, 1–3 and 3–7-year bucket comparison.
- Expected holding-period return range and reinvestment risk.
- RMB return scenarios and FX sensitivity.
- Duration stress losses and liquidity notes.

## 5. Sleeve C — Global quality equities (ex-U.S.)

### Universe definition

This sleeve is global developed and emerging-market listed equities excluding U.S.-domiciled issuers already counted in Sleeve A or the existing U.S. equity engine. Maintain explicit country and currency buckets. If an ETF / index includes U.S. holdings, either remove them via look-through or disclose the residual overlap and do not count the exposure twice.

Candidate benchmark families: MSCI World ex USA / ACWI ex USA, FTSE Global ex-US or documented regional benchmarks. Index constituent and valuation data may be licensed; if unavailable, use transparent ETF holdings and issuer filings as proxies, label them as such, and do not claim full-universe coverage.

### Primary sources

- Company annual / interim reports, local exchange filings and issuer investor relations.
- SEC EDGAR for foreign issuers filing with SEC, but not as a complete global source.
- Official index provider methodology and constituents, subject to licensing.
- Central bank / official FX sources for EUR, JPY, GBP, CHF, CAD, AUD and relevant emerging currencies.
- National statistics agencies and central banks for inflation / rates where needed.
- ETF issuer holdings and factsheets for look-through exposure; archive timestamp and holdings date.

### Required metrics and formulas

Use the same company-level metrics as Sleeve A: revenue growth, operating margin, FCF margin, net debt/EBITDA, ROIC, dividend payout and valuation. Adapt accounting definitions to local reporting standards and document comparability limits.

Additional metrics:
- Country weight and currency weight = sum of security weights by domicile / primary revenue currency / trading currency; report these three separately.
- Unhedged FX exposure = market value by currency after look-through and hedge adjustments.
- Dividend sustainability = dividends / FCF, only when FCF positive; payout ratio = dividends / net income, with negative earnings flagged.
- Quality composite is diagnostic only: standardized ROIC, FCF stability, leverage, margin stability and governance flags. Do not use an opaque composite as an automatic buy signal.
- Local expected equity return = earnings or FCF yield + conservative per-share growth + valuation change + dividend yield, with a single consistent framework.
- RMB expected return = currency-by-currency conversion using the common FX formula; do not use USD/CNY for EUR or JPY holdings.

### State rules

Quality GREEN:
- Positive and stable FCF, sustainable leverage, defensible profitability and no material governance/accounting red flag across adequate coverage.

YELLOW:
- Weakening FCF conversion, margin compression, rising leverage, deteriorating dividend coverage, or incomplete country/company coverage.

RED:
- Broad and persistent fundamental deterioration across multiple countries / sectors, or issuer-level hard events. A country-wide risk event may trigger a country sleeve override but must not automatically label every issuer in that country as financially insolvent.

Entry attractiveness:
- GREEN: valuation is <= 60th percentile of comparable history and base-case RMB return clears the IPS hurdle, with bear-case loss within budget.
- YELLOW: valuation 60th–85th percentile, return close to hurdle, or currency uncertainty dominates.
- RED: valuation >85th/90th percentile AND expected RMB return fails hurdle / risk budget.
- Without a configured IPS hurdle, no personalized GREEN entry state.

Report:
- Ex-U.S. benchmark and country/sector weights.
- Top holdings and overlap with U.S. mega-cap / China equity sleeves.
- ROIC, FCF, leverage, margins and dividend sustainability coverage.
- Country, revenue and trading currency exposure.
- Local and RMB expected return scenarios by major currency.
- Valuation percentile and data coverage limitations.

## 6. Sleeve D — Gold

### Instrument and price definition

Track separately:
- International spot / benchmark gold price in USD per troy ounce.
- RMB gold price per gram (onshore benchmark where reliable).
- Investable vehicle total return (ETF / physical gold / other product) including fees, tracking difference, bid-ask, storage, insurance and taxes where applicable.
Do not assume spot gold return equals investor product return.

### Primary sources

- World Gold Council: demand, supply, central-bank purchases and ETF flows, subject to report frequency and methodology.
- LBMA benchmark data subject to access and licensing; do not scrape restricted data.
- CME / CFTC: futures positioning and open interest, with reporting lags.
- ETF issuer daily holdings / flows and factsheets.
- FRED / Treasury: U.S. real yields, nominal yields, breakeven inflation and broad USD.
- Official onshore exchange / benchmark sources for RMB gold price; validate access and product specification.

### Required metrics and formulas

- USD gold spot return and RMB gold return.
- Real gold price = nominal gold price / relevant CPI index; disclose CPI geography and lag.
- Gold / silver ratio and gold / broad commodity ratio as context only.
- Real-yield change, DXY change and gold return rolling correlation.
- ETF flow = change in reported holdings / prior holdings; use consistent flow/holdings methodology.
- Central-bank net purchases from published data; record release lag.
- Futures speculative net position = non-commercial longs - non-commercial shorts, scaled by open interest; preserve CFTC category definitions.
- Gold volatility, drawdown and trend.
- Physical / ETF implementation cost and tracking difference.

Gold has no contractual cash flow. Do not value it using P/E, earnings yield or bond YTM. Do not infer intrinsic value from one real-yield regression.

### State rules

Attractiveness GREEN:
- RMB gold valuation / trend is not at an extreme adverse percentile; real-yield and USD conditions are supportive or neutral; portfolio hedge benefit is evidenced by rolling and stress correlation; expected RMB scenario return is positive relative to the IPS hurdle or its insurance value is explicitly accepted in IPS.

YELLOW:
- Price / momentum is extended; speculative positioning or ETF flows are crowded; real yields / USD are moving against gold; or RMB gold price is diverging from USD gold because of FX.

RED:
- Extreme price / positioning conditions coincide with adverse real-yield / USD regime and bear-case RMB loss breaches the user's risk budget; or investable vehicle has severe liquidity / custody / tracking issue.
- High price alone does not equal RED. Gold can remain a strategic hedge even when entry attractiveness is low.

Risk/hedge function:
- Estimate rolling correlation with equity and bond sleeves at 60/120/252 sessions where data support.
- Stress test 2008-style liquidity shock, 2020-style rate shock and inflation / real-rate shock using observed historical episodes and explicit hypothetical shocks. Do not assume stable negative correlation.

Report:
- USD/oz and RMB/g prices, 1D/20D/60D/252D returns.
- Real-yield and DXY context.
- Central bank purchases, ETF holdings/flows and CFTC positioning with report dates.
- Volatility, drawdown, percentile and correlation / hedge effectiveness.
- Product-level tracking cost and custody / liquidity caveats.
- RMB base / bull / bear return range.

## 7. Sleeve E — China quality equities

### Universe definition

Separate:
- Broad market benchmarks: CSI 300, CSI A500 and/or another documented broad benchmark.
- Quality / dividend / value factor universes as separate screens, not interchangeable with broad market.
- Issuer universe across Shanghai, Shenzhen and STAR Market as appropriate; Hong Kong-listed Chinese issuers should be a separate jurisdiction/currency sleeve unless explicitly included with HKD exposure and governance treatment.

### Primary sources

- CSRC, SSE, SZSE, BSE and official issuer announcements / filings.
- China Securities Index Co. (CSI) / China Securities Index and index provider methodology, constituent and valuation statistics where public.
- National Bureau of Statistics (NBS): CPI, PPI, industrial and macro series.
- PBOC: policy rates, aggregate financing and monetary statistics.
- ChinaBond / China Central Depository & Clearing / NIFC / CFETS: bond and rate reference data, subject to endpoint and licensing validation.
- Issuer annual / quarterly reports and exchange inquiry / regulatory notices.

Do not rely on scraped financial portals as the canonical source for audited financial statements if exchange filings are available. If third-party data are used for convenience, cross-check material fields against issuer filings.

### Required metrics and formulas

Company quality:
- Revenue growth YoY, operating margin, FCF, FCF margin, ROIC, ROE and leverage.
- ROE must be interpreted with leverage and asset quality; high ROE alone is not quality.
- Net cash / net debt and interest coverage.
- Dividend yield = trailing cash dividends / market cap; dividend payout / FCF only if FCF positive.
- Shareholder dilution / buybacks / dividends; distinguish cash dividend from special one-off distribution.
- Related-party transactions, pledge ratio, audit opinion, regulatory penalties and material litigation flags.

Market valuation:
- Trailing P/E, P/B, dividend yield and FCF yield at index and constituent levels, with source methodology.
- P/E invalid for negative earnings; P/B can be misleading for asset-light firms and financials; banks/insurers need sector-specific metrics.
- Historical valuation percentile by index and sector; avoid mixing changing index methodology without adjustment.
- Earnings breadth = companies with positive YoY net income / valid reporting companies; also track FCF-positive breadth.
- Market breadth = constituents above 50/200-day moving average / constituents with valid prices.
- Turnover / market cap and financing balance are context indicators, not standalone buy signals.

### State rules

Quality GREEN:
- Positive / stable FCF, sustainable leverage, reasonable returns on capital, sound audit / governance status, and broadening earnings quality.

YELLOW:
- Valuation is cheap but earnings quality / cash conversion weak; policy dependence high; margin or FCF breadth deteriorates; governance coverage incomplete.

RED:
- Multiple independent indicators show broad earnings / FCF deterioration; severe credit / governance / regulatory event; or portfolio country / sector / issuer limit breached.
- Low P/E by itself is never GREEN; cheapness with structural decline can remain RED.

Entry attractiveness:
- GREEN: sector-adjusted valuation <= 60th percentile, fundamentals stable, base-case RMB expected return clears IPS hurdle and bear loss fits risk budget.
- YELLOW: 60th–85th percentile, or valuation appears cheap but earnings / governance evidence is incomplete.
- RED: expensive valuation >85th/90th percentile combined with deteriorating earnings / FCF or expected return below hurdle; alternatively, a hard issuer or market access risk.
- Require sector comparisons; do not compare bank P/B directly with software P/B.

Report:
- Index valuation percentiles and methodology.
- Earnings / FCF breadth and reporting coverage.
- Sector and issuer concentration, market breadth and liquidity.
- Quality screens and governance flags.
- Dividend / FCF sustainability.
- RMB return scenarios and downside stress.
- Separate A-share and HK-listed China exposure where relevant.

## 8. Sleeve F — RMB cash and fixed income

### Product buckets

Do not treat all “cash and fixed income” as equivalent. Separate:
- Bank deposits: demand / time deposits, by bank and maturity; record deposit insurance eligibility and limit.
- Money-market funds: NAV / 7-day annualized yield / liquidity and redemption rules.
- Central-government bonds: maturity buckets and total return.
- Policy-bank / local-government bonds: issuer and implicit/explicit guarantee assumptions must be explicit.
- High-grade financial / corporate credit: issuer-level credit risk and spread.
- Lower-grade / perpetual / subordinated / wealth-management products: excluded from core defensive sleeve unless separately approved and fully modeled.

### Primary sources

- PBOC and NBS for policy rates, interbank rates and inflation.
- ChinaBond / China Central Depository & Clearing / NIFC / CFETS for government and credit yield curves, subject to API and licensing validation.
- Ministry of Finance for central-government bond issuance and terms.
- Deposit rates published by individual banks; archive dated rate sheets and conditions.
- Money-market fund prospectus, daily NAV, portfolio reports and risk disclosures from fund managers / official disclosures.
- CSRC / AMAC / exchange disclosures for fund and product rules.
- Issuer financial statements, rating reports and bond prospectuses for credit.

If a free, stable, documented API is unavailable, support controlled manual import of official CSV/PDF with source file hash and publication date. Do not pretend a manually copied rate is a real-time API.

### Required metrics and formulas

Cash:
- Net nominal yield = quoted yield - product fees - known tax / withholding.
- Ex-ante real yield proxy = net nominal yield - expected inflation; expected inflation source and horizon must be stated.
- Ex-post real return = (1 + realized net return) / (1 + realized CPI) - 1.
- Liquidity access: redemption cutoff, settlement days, gates, early withdrawal penalty and principal guarantee status.
- Deposit concentration by bank and insured / uninsured amount.

Bonds:
- Yield to maturity, modified duration, convexity, accrued interest and total-return history.
- Credit spread = instrument yield - maturity-matched government curve; adjust for seniority, liquidity and optionality.
- Expected holding-period return = carry + roll-down + duration/convexity price effect - expected credit loss - fees/taxes.
- Expected credit loss proxy = probability of default * loss given default * exposure; only if defensible issuer / rating data exist. Otherwise show rating and spread risk without fabricated PD.
- Credit migration / downgrade / default events and issuer leverage / interest coverage.
- Liquidity premium proxy: bid-ask spread, turnover, days-to-liquidate or reliable fund redemption terms.

### State rules

Cash attractiveness GREEN:
- Net yield is positive in real terms on a comparable horizon, liquidity terms match the user's cash need, counterparty concentration is within IPS limit, and principal risk is low / contractually clear.

YELLOW:
- Real yield is near zero or negative; deposit concentration approaches policy limit; redemption terms or product portfolio are not sufficiently transparent.

RED:
- Principal guarantee / custody assumption is false or materially impaired; bank / issuer credit or liquidity event occurs; uninsured concentration exceeds user limit; product has gates / suspension or severe mismatch with required liquidity.
- Negative real yield alone is not a default RED; it is a purchasing-power warning and may still be acceptable for emergency liquidity.

Fixed income attractiveness:
- GREEN: after-tax / fee-adjusted expected RMB return clears IPS hurdle with acceptable duration, credit and liquidity stress.
- YELLOW: return near hurdle or material uncertainty in credit / liquidity / inflation.
- RED: expected return fails hurdle and downside / liquidity stress breaches IPS risk budget.

Report:
- Deposit / fund / bond maturity ladder and weighted average maturity.
- Net nominal and real yield assumptions.
- Credit quality, issuer concentration, insured/uninsured bank exposure.
- Duration, spread duration, stress loss and liquidity days.
- Expected return after fees / tax and inflation.
- Cash available within 1 day / 7 days / 30 days.

## 9. Cross-sleeve portfolio analytics

These analytics are mandatory before the system can make portfolio-level allocation suggestions.

### Look-through and de-duplication

- Canonical issuer_id across direct shares, ETFs, funds, ADRs and multiple share classes.
- Canonical underlying exposure_id for index / fund holdings.
- De-duplicate issuer exposure for concentration while preserving each holding's market value and wrapper costs.
- U.S. mega-cap / AI sleeve is separate from global ex-U.S. sleeve; remove U.S. holdings from ex-U.S. exposure or report residual overlap.
- China A-shares and Hong Kong-listed China issuers must be separated by currency, jurisdiction and trading / custody constraints.

### Exposure measures

- Asset-class weight, country domicile weight, revenue geography weight, sector weight, issuer weight.
- Currency exposure by economic exposure and settlement currency; show hedged and unhedged.
- Bond duration, key-rate duration, credit spread duration and issuer exposure.
- Gold physical / financial wrapper exposure.
- Cash liquidity ladder.
- Effective number of holdings = 1 / sum(weight_i^2), computed at issuer level and separately by asset class.

### Risk contribution

Use portfolio covariance where reliable:
- Portfolio variance = w' Σ w.
- Marginal contribution to risk = (Σw)_i / portfolio_volatility.
- Component contribution to risk = w_i * (Σw)_i / portfolio_volatility.
- Normalize only for presentation; retain signed contributions.
Do not use covariance estimates with inadequate observations. Publish sample size and use stress tests alongside covariance because correlations are regime-dependent.

### Required joint stress scenarios

At minimum:
1. Global growth shock: equities down, credit spreads wider, USD and JPY scenarios separately modeled, gold not assumed to hedge.
2. Inflation / real-rate shock: nominal yields and real yields rise, duration assets fall, equity valuation compression.
3. Recession / disinflation: earnings fall, yields fall, credit risk rises; Treasury gains are scenario-dependent.
4. USD/CNY appreciation and depreciation shocks: apply to all unhedged foreign currency exposures, not just U.S. assets.
5. China domestic risk shock: A-share drawdown, RMB and domestic credit/liquidity shock.
6. Liquidity shock: bid-ask spreads widen, redemption / settlement delays and haircuts on less liquid assets.
7. Correlation breakdown: stress equity / bond / gold correlations using adverse historical and hypothetical matrices.

Each scenario must state shock sizes, horizon, data source, rationale and whether historical or hypothetical. No single “worst case” should be described as a forecast.

## 10. Red / yellow / green configuration contract

All thresholds live in versioned configuration, not hard-coded in business logic.

Each rule:
- rule_id, sleeve_id, metric_id
- polarity (higher_is_riskier / higher_is_better / banded)
- threshold_type (HARD / CALIBRATED / USER_POLICY / PROVISIONAL)
- green_rule, yellow_rule, red_rule
- lookback_window, minimum_observations, minimum_coverage
- persistence_count, release_count
- override_priority
- effective_from, effective_to
- provisional, enabled_for_live_action
- rationale, source_methodology, owner_review_date

Initial v1.0 live action policy:
- All percentile thresholds are CALIBRATED and disabled until walk-forward tests pass.
- All user loss, concentration, liquidity and return hurdle thresholds are USER_POLICY and disabled until IPS is completed.
- Provisional thresholds may render diagnostic colors in a clearly labeled sandbox only; never create live buy/sell/position percentages.
- Hard contractual / data integrity events may trigger RED immediately when evidence is verified.
- A metric's state cannot be aggregated when required coverage is below its configured minimum.

## 11. History, backtesting and validation

### Data history requirements

- Prices / total-return proxies: target 10+ years where available, minimum 5 years for basic rolling analysis; shorter histories must be explicitly labeled.
- Rates / yields: use the longest consistent official history available; maintain series-definition changes.
- Company fundamentals: point-in-time filings and publication timestamps; use only data available as of each simulated decision date.
- Index constituents / weights: point-in-time constituents to avoid survivorship bias.
- Fund holdings: historical holdings snapshots where available; current holdings must not be projected backward.
- FX: matched observation calendars and quote conventions; avoid forward-filling over market holidays without an explicit calendar policy.

### Backtest design

1. Define a strategic benchmark only after IPS; before then, evaluate sleeves independently and do not invent a personal portfolio.
2. Walk-forward: train/calibrate on prior history, freeze rules, evaluate next period; roll forward.
3. Use monthly or quarterly allocation decision frequency for strategic/tactical overlays; daily data may monitor risk but must not imply daily reallocation.
4. Compare:
   - buy-and-hold / static benchmark;
   - periodic rebalancing;
   - signal-based staged allocation;
   - signal-based pause / risk reduction;
   - cash-only or domestic low-risk comparator where relevant.
5. Include dividends/coupons, distributions, corporate actions, fund expense ratios, bid-ask, turnover, taxes where known, FX conversion and hedge costs.
6. Report gross and net results separately.
7. Metrics: CAGR in RMB, volatility, max drawdown, downside deviation, Sharpe/Sortino, worst rolling 12-month return, recovery time, turnover, transaction cost, time in each state, false-positive / false-negative state rate, and benchmark-relative return.
8. Evaluate opportunity cost of waiting / staged entry, not only drawdown reduction.
9. Stress test at least the 2000–02 tech bust, 2008 crisis, 2013 taper episode, 2015–16 China / RMB volatility, 2018 tightening / trade tensions, 2020 pandemic, 2022 inflation / rate shock, and later available episodes. Event windows are tests, not proof of future behavior.
10. Use block bootstrap / regime resampling for uncertainty where appropriate. Report confidence intervals; do not present a single backtest result as expected future performance.

### Acceptance gates

A sleeve is research-ready only if:
- Required data source metadata and licenses / terms are documented.
- At least 95% of required daily observations are present for daily metrics, or a documented lower-frequency exception is approved.
- Fundamental coverage denominator is visible; no broad-market conclusion with inadequate coverage.
- No look-ahead, survivorship, stale-data or revised-vintage leakage is detected.
- Formula unit tests and hand-calculated fixtures pass.
- Threshold rules are stable under reasonable lookback / parameter sensitivity.
- Results survive walk-forward testing after costs, or the sleeve is explicitly designated descriptive-only.
- Report can be reproduced from archived raw inputs and model version.

Passing acceptance gates does not prove alpha. It only establishes that the system is reproducible and sufficiently validated for its stated use.

## 12. Daily / weekly / monthly report contract

### Daily dashboard (monitoring, not daily forced trading)

Header:
- As-of timestamp and timezone.
- Data completeness and stale-source list.
- Model/config version.
- Overall Global Allocation state and confidence.
- Explicit note if portfolio holdings are unavailable.

For each of six sleeves:
- quality_state / risk_state / entry_attractiveness.
- Key price / yield / valuation.
- 1D / 20D / 60D / 252D change where appropriate.
- Fundamental trend and coverage.
- Local return and RMB return scenario range.
- Top 3 positive drivers and top 3 risks.
- Red / yellow trigger and invalidation condition.
- Allowed action and policy dependency.

Portfolio section:
- Asset class / country / sector / issuer / currency look-through.
- RMB NAV, cash available 1/7/30 days, unhedged FX exposure.
- Risk contribution, drawdown, stress losses.
- Current vs strategic weight and policy bands (only if IPS exists).
- Rebalance required? yes/no/insufficient data, with exact trigger.

### Weekly report

- Cross-asset relative value ranking (not a buy list).
- Changes in earnings / rates / FX / gold / credit evidence.
- Risk concentration and correlation changes.
- Candidate opportunities and disconfirming evidence.
- Actions due for review, not automatic execution.

### Monthly report

- RMB net performance attribution: local asset return, FX contribution, income, fees/taxes, trading.
- Benchmark comparison and risk-adjusted performance.
- State hit-rate and stability.
- Strategic / tactical allocation drift.
- Investment decision journal review and model error analysis.

## 13. Codex implementation plan

### Phase 0 — repository reconnaissance and invariants

- Read existing repository architecture, data adapters, config, tests, daily report and NQ-Sentinel score implementation.
- Record exact original six-module weights and current state machine as immutable regression fixtures.
- Map existing reusable sources; do not duplicate existing FRED, SEC, SOX, AI-capex pipelines.
- Add architecture decision record describing the six-sleeve boundaries and currency convention.
- Output: implementation inventory and dependency map. No production code changes before inventory is reviewed.

### Phase 1 — common contracts and deterministic calculations

- Add schemas for observations, source metadata, asset universe, sleeve states, thresholds, FX scenarios and portfolio exposures.
- Implement currency conversion / hedge-aware return calculation.
- Implement common rolling metrics, percentile calculation, freshness and coverage gates.
- Add unit tests with hand-calculated fixtures and sign convention tests.
- Add versioned YAML/JSON configuration with all live actions disabled.
- Acceptance: all tests pass; original NQ score and position-state fixtures unchanged.

### Phase 2 — defensive assets first

Implement:
1. U.S. Treasury maturity buckets.
2. RMB cash / deposits / money-market / government bond buckets.
3. Gold price and hedge metrics.

Reason: these build yield, duration, real-return, liquidity and FX primitives needed by the other sleeves.

Each adapter must:
- validate official source metadata;
- archive raw payload and hash;
- store publication / observation / retrieval times;
- expose stale/missing status;
- provide deterministic normalized output.

Acceptance: source diagnostics, reproducible raw snapshots, calculation tests, and no silent fill.

### Phase 3 — equity research sleeves

Implement:
1. U.S. mega-cap / AI infrastructure, reusing NQ/SOX and SEC pipelines.
2. Global ex-U.S. quality equities.
3. China quality equities.

Prioritize issuer-level filings and look-through. Consensus estimates, AI revenue, GPU utilization, global valuation and China valuation series remain N/A unless source coverage and methodology are proven.

Acceptance: issuer identity de-duplication, point-in-time universe, fundamental coverage denominator, valuation methodology and data quality tests.

### Phase 4 — cross-sleeve portfolio engine

- Build issuer / sector / country / currency look-through.
- Add duration / credit / liquidity exposures.
- Add risk contribution and joint stress scenarios.
- Add strategic / tactical policy interface, but require IPS before personalized weights.
- Add global allocation state aggregator with hard overrides and hysteresis.

Acceptance: exposure totals reconcile to NAV within configured tolerance; overlapping issuers are not double counted; stress outputs reproduce.

### Phase 5 — reports and decision audit

- Add daily six-sleeve report, weekly relative-value report and monthly attribution report.
- Add investment memo / decision log with immutable original thesis.
- Add recommendation audit: source inputs, rule IDs, calculations, policy dependencies and invalidation conditions.
- No direct trade execution.

Acceptance: deterministic report regeneration from stored data and config.

### Phase 6 — backtest, shadow operation and release

- Run walk-forward backtests and sensitivity analysis.
- Run at least 4–8 weeks of shadow mode without live allocation actions.
- Compare report stability, missing-data rate, false triggers and decision usefulness.
- Promote only validated sleeves; leave descriptive-only sleeves clearly labeled.
- Do not enable a live allocation rule merely because code is deployed.

## 14. Suggested repository layout

Adapt to existing project conventions after Phase 0; do not force this tree if an equivalent architecture already exists.

- docs/architecture/GLOBAL_MULTI_ASSET_RESEARCH_SPEC_V1.md
- docs/architecture/GLOBAL_MULTI_ASSET_CODEX_PLAN_V1.md
- config/global_allocation/sleeves.yaml
- config/global_allocation/thresholds.yaml
- config/global_allocation/sources.yaml
- src/global_allocation/contracts/
- src/global_allocation/fx/
- src/global_allocation/metrics/
- src/global_allocation/sleeves/us_tech_ai/
- src/global_allocation/sleeves/us_treasuries/
- src/global_allocation/sleeves/global_ex_us_equity/
- src/global_allocation/sleeves/gold/
- src/global_allocation/sleeves/china_equity/
- src/global_allocation/sleeves/rmb_fixed_income/
- src/global_allocation/portfolio/
- src/global_allocation/reports/
- tests/unit/global_allocation/
- tests/integration/global_allocation/
- tests/backtest/global_allocation/
- data/raw/global_allocation/ (or existing configured storage; never commit secrets or large raw data)

## 15. First Codex task prompt

You are working in repository megancc25-ctrl/codex-investment-research-system on branch feature/global-allocation-rmb-v1.

Read:
- docs/architecture/NQ_SENTINEL_GLOBAL_ALLOCATION_V1.md
- docs/architecture/GLOBAL_MULTI_ASSET_RESEARCH_SPEC_V1.md
- docs/architecture/GLOBAL_MULTI_ASSET_CODEX_PLAN_V1.md

Task: execute Phase 0 only. Inspect the repository and report:
1. existing architecture, language, package manager and test commands;
2. current NQ-Sentinel six-module weights and state machine, with file/line references;
3. existing data adapters and reusable FRED / SEC / SOX / AI infrastructure pipelines;
4. current daily report structure and integration point;
5. proposed mapping from this specification to existing modules, avoiding duplicate pipelines;
6. missing source access, licensing or historical-vintage blockers;
7. exact files to be added/changed in Phase 1.

Do not implement production code, do not change original weights / indicators / scores / position transitions, do not add live thresholds, and do not create allocation percentages. Produce docs/implementation/PHASE0_RECONNAISSANCE.md and a testable Phase 1 checklist. Stop for review after Phase 0.
