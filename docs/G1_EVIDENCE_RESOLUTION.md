# G1_EVIDENCE_RESOLUTION

2026-11-22. Issue #4 comment 7077970249. **STOP_DOC_RESEARCH** for the unresolved NY Fed field-scale/actual-envelope questions. G1 real admission NO-GO; G2/G3 NOT_STARTED; formal score N/A. No new market-data requests or second-batch application.

## New official evidence and its limits

| Official static source | Location / conclusion | Capture UTC | SHA256 |
|---|---|---|---|
| https://markets.newyorkfed.org/static/docs/markets-api.yml | info version 1.0; documented update June 12, 2026; components/schemas/refrates-sec-json and sofr-record: refRates array, numeric percent. No explicit field-scale declaration found. |2026-11-22T10:49:12.297583Z|5dbb331d86b91bfc115be9b5fe9c46735833a4f7280d33e4327e8acf7ad30d2b|
| https://www.newyorkfed.org/medialibrary/microsites/arrc/files/2019/Templates_for_Using_SOFR.pdf | Official-hosted 2019 SOFR template presentation, SOFR Publication section: publication table labels rate as percent and discusses API access. It does not bind the current API's percent field to a versioned scale. |2026-11-22T10:49:13.143106Z|7b54671063afa113c21940a2079deda35167b13f6585126f8eec6a0ba15a90d0|

The presentation improves evidence for the **published benchmark's percentage convention**, beyond an inference from 1bp rounding. It still is not an explicit current API field-to-unit mapping. Field-unit judgment remains UNKNOWN; no conversion is introduced.

Official schema examples FOUND: embedded per-property OpenAPI examples. Official static complete JSON confirmed as an actual API response: NOT_FOUND within the reviewed API documentation, official static presentation and targeted official-domain searches. NOT_FOUND is a bounded search result, not proof that no such example exists anywhere. Search results from third-party clients are not accepted as official definitions or real-response evidence and were not used to infer the discarded response.

Synthetic payloads remain synthetic. The first real response is unavailable; its exact failure subtype remains UNKNOWN. No claim that the provider changed fields, no reconstruction of values and no retroactive LIVE PASS.

## Evidence boundary reached

Do not repeat the same public-document search or add tests merely to increase a count. A provider clarification or newly published versioned static response/field dictionary is now the minimum useful external evidence. Existing synthetic regression covers mapping, independent date checks, unit UNKNOWN and error categories; no further implementation changes are justified in this round.

### Unsent support inquiry draft

Recipient: New York Fed Markets Data API/reference-rate support; verified destination to be selected before any future authorized send. No mail drafted in an external mailbox or sent.

Subject: Clarification of secured-rate API field scale and versioned static JSON example

Hello,

We are reviewing the public Markets Data API specification (info version 1.0, documented update June 12, 2026) without making further numerical-data API requests.

1. For the secured-rate search JSON contract, what exact unit and scale does refRates[].percent use? Is it a percentage-point representation, a decimal fraction, or another convention? Please identify the applicable API version and authoritative field definition, including any distinction from percentRate.
2. Is there an official static complete JSON response suitable for offline validation, with its source/version and an explanation of whether it is illustrative or an actual response sample? Please confirm the top-level envelope and rate/date field definitions.

We do not require current rates, private transaction data, credentials or a paid service. A public documentation link or written clarification would be sufficient.

Thank you.

## Existing-source functional coverage — no repeated source inventory

This is a functional projection of the already reviewed candidates, not new permission or collection.

| Existing source / module | Independent contribution | Permission / operational gate |
|---|---|---|
| Treasury / rates | 10Y and 30Y nominal, 10Y real-yield changes can support three configured rate metrics independently of SOFR | Named catalog datasets marked CC0; current payload equivalence and service/access conditions still need validation. No live enabling. MOVE remains absent; do not call the whole rates module complete. |
| NY Fed / liquidity | SOFR/TGCR/BGCR funding observations, once qualified | Unit/envelope evidence, new interface authority, ongoing-use scope and PIT are distinct; old authority consumed. SOFR alone also does not supply IORB or a full repo-stress history. |
| Chicago Fed / liquidity | Weekly NFCI/ANFCI financial-conditions evidence | Internal automated investment-use/republication scope and historical revisions remain unresolved. |
| BIS / property | Country/series-level property indicators | Conditional statistical reuse; specific flow/key/unit, vintage and operating scope unverified. |
| SEC / AI satellite | Issuer cash-flow/capital-expenditure facts | Exact fact/period/rights mapping and filing first-available evidence required. Not a substitute for missing credit or market indicators. |
| Existing Cboe/index/ETF candidates | Volatility, trend and correlation components | Existing license and source-verification gaps retained; no public-page-to-license inference. |

No reweighting, relaxed coverage threshold, missing-value zero-fill or fabricated real score. Partial non-SOFR metrics can advance independently only within their own evidence/permission boundaries.

## Blocker classes and release conditions

| Class | Minimum release evidence |
|---|---|
| Technical contract | Versioned official static envelope/example, then separately authorized live compatibility evidence if necessary |
| Unit evidence | Explicit provider mapping from specific API field/version to scale; benchmark rounding alone insufficient |
| Source rights | Exact requested use and required notices confirmed; unknown uses remain denied |
| Continuous collection rights | Separate G2 scope covering schedule, processing, storage and reporting; single probe cannot grant it |
| PIT availability | Value-version-specific first-available/revision evidence; observation and retrieval dates insufficient |

## Whether another test is needed

Not ready to request one now. Provider documentation should be resolved first. If it settles units/envelope but cannot establish real transport compatibility, a later new single-source, single-date, single-request proposal may be justified, with explicit nonnumerical diagnostic enums and consumption/version binding. This is conditional planning only, not an authorization request or permission to run. Do not resume the former SOFR batch or send its remaining two requests.

## Delivery

Documentation-only change; no new test-count target. The existing 173-test full regression and hosted CI are run for this commit; actual SHA/results/CI link are delivered in the final response. No message sent, terms accepted, data source enabled, model/main/CRS1.1/account/production switch or Agent Reach modified.
