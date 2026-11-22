# G1_DECISION_REPORT

G1: PARTIAL (investigation delivered; live data admission NO_GO).
G2/G3: NOT_STARTED. Formal score: N/A. Real coverage: N/A.

ALLOWED describes the published permission within its recorded scope, not project approval or accepted terms.

| Source | Access | Analysis | Automation | Memory | Local | GitHub | HTML/JSON | Redistribution | Interface |
|---|---|---|---|---|---|---|---|---|---|
| treasury | ALLOWED | ALLOWED | UNKNOWN | ALLOWED | ALLOWED | ALLOWED | ALLOWED | ALLOWED | OFFLINE_ONLY_NOT_ADMITTED |
| new_york_fed | ALLOWED | ALLOWED | ALLOWED | ALLOWED | ALLOWED | UNKNOWN | ALLOWED | ALLOWED | OFFLINE_ONLY_NOT_ADMITTED |
| chicago_fed | ALLOWED | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | RESTRICTED | RESTRICTED | RESTRICTED | OFFLINE_ONLY_NOT_ADMITTED |
| cboe | ALLOWED | UNKNOWN | UNKNOWN | UNKNOWN | RESTRICTED | RESTRICTED | RESTRICTED | RESTRICTED | OFFLINE_ONLY_NOT_ADMITTED |
| sec | ALLOWED | UNKNOWN | ALLOWED | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | OFFLINE_ONLY_NOT_ADMITTED |
| microsoft_ir | ALLOWED | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | RESTRICTED | RESTRICTED | RESTRICTED | OFFLINE_ONLY_NOT_ADMITTED |
| census | ALLOWED | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | OFFLINE_ONLY_NOT_ADMITTED |
| bis | ALLOWED | ALLOWED | ALLOWED | ALLOWED | ALLOWED | UNKNOWN | ALLOWED | ALLOWED | OFFLINE_ONLY_NOT_ADMITTED |
| nasdaq | ALLOWED | RESTRICTED | RESTRICTED | RESTRICTED | RESTRICTED | RESTRICTED | RESTRICTED | RESTRICTED | OFFLINE_ONLY_NOT_ADMITTED |
| blackrock_etf | ALLOWED | UNKNOWN | RESTRICTED | UNKNOWN | UNKNOWN | RESTRICTED | RESTRICTED | RESTRICTED | OFFLINE_ONLY_NOT_ADMITTED |

## treasury
Catalogued nominal and real Treasury curve datasets are marked CC0. This is evidence of existing dataset reuse rights, not a new project license or verification of modern-feed identity.

Evidence: [treasury_nominal_catalog](https://catalog.data.gov/dataset/interest-rate-statistics-daily-treasury-yield-curve-rates), [treasury_real_catalog](https://catalog.data.gov/dataset/daily-treasury-real-yield-curve-rates), [treasury_docs](https://home.treasury.gov/developer-notice-xml-changes)

Gaps: Reconcile old catalog resource IDs with current XML feed; Confirm automated-access service conditions; Live schema, pagination and source authenticity not tested

## new_york_fed
Published terms expressly permit personal/business reuse, automated access, storage and distribution subject to general and reference-rate conditions. None has been activated for CRS.

Evidence: [ny_terms](https://www.newyorkfed.org/privacy/termsofuse), [ny_spec](https://markets.newyorkfed.org/static/docs/markets-api.yml), [ny_release](https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates)

Gaps: Project authorization to accept applicable conditions not granted; Implement exact reference-rate attribution/disclaimers before any presentation; GitHub hosting/sublicensing treatment unresolved; No live response or release-vintage validation

## chicago_fed
Weekly data are publicly documented. The limited written-material exception does not establish permission for automated investment analysis; wider republication/distribution needs permission.

Evidence: [chicago_terms](https://www.chicagofed.org/utilities/legal-notices), [chicago_docs](https://www.chicagofed.org/research/data/nfci/current-data)

Gaps: Clarify NFCI/ANFCI data-file rights for internal investment use and machine processing; Concrete download route/CSV headers not verified; Historical revisions need vintages

## cboe
Daily history has an official public link. A single personal copy exception does not establish recurring analytics/cache/report rights; no fair-use entitlement is presumed.

Evidence: [cboe_terms](https://www.cboe.com/terms/), [cboe_docs](https://www.cboe.com/tradable-products/vix/vix-historical-data)

Gaps: Clarify permission for systematic risk analytics and historical persistence; Resolve data-product-specific terms before any request; No live CSV validation

## sec
SEC documents unauthenticated JSON data APIs and fair-access scripting. This does not make all issuer-authored filing content or copied documents public-domain material.

Evidence: [sec_docs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [sec_access](https://www.sec.gov/about/developer-resources), [sec_terms](https://www.sec.gov/about/privacy-information)

Gaps: Truthful bot contact/identity not configured; Determine exact extracted-fact storage/report rights separately from full filings; Filed date is not first-available timestamp; preserve accession and restatements; Accounting periods/tags require manual mapping before FCF computation

## microsoft_ir
Microsoft is the bounded issuer-IR pilot. General document permissions are conditional and do not establish automated redistribution or permission for all AI-company IR sites.

Evidence: [ir_terms](https://www.microsoft.com/en-us/legal/terms-of-use)

Gaps: Verify applicable IR-specific terms and exact document scope; No financial-report endpoint/schema verified; Other companies are not covered by this review

## census
Official API directory and public-use citation guidance found. Residential construction is not existing-home sales, rent or global property prices; it cannot silently replace those CRS inputs.

Evidence: [census_citation](https://www.census.gov/about/policies/citation.html), [census_docs](https://api.census.gov/data/timeseries/eits/resconst.html)

Gaps: Complete dataset-specific use, automation, international scope and hosting review; Validate query variables, units and release calendar; No live API response verified

## bis
Statistics-specific terms permit conditional reuse and API access. The exact property-price SDMX flow/key and national-series limitations remain to be verified; general publication terms are not substituted for statistics terms.

Evidence: [bis_stats_portal_terms](https://data.bis.org/help/legal), [bis_docs](https://stats.bis.org/api-doc/v2/)

Gaps: Project authority to accept API conditions absent; Validate current SDMX endpoint/version, flow key, country units and vintages; GitHub hosting terms and any series-specific limitation unresolved

## nasdaq
Nasdaq general website terms restrict extraction and data-analysis software use absent permission. A public historical page is not an index-data license.

Evidence: [nasdaq_legal](https://www.nasdaq.com/legal)

Gaps: Identify a separately licensed index feed or approved broker/provider entitlement; No index endpoint admitted or probed

## blackrock_etf
BlackRock corporate terms include automatic-device copying restrictions; web-rendered and direct-origin text differed. These corporate terms are not silently applied as an iShares data license.

Evidence: [blackrock_terms](https://www.blackrock.com/corporate/compliance/terms-and-conditions)

Gaps: Verify regional iShares-specific terms and ownership; Find approved price/total-return endpoint, corporate actions and adjustment method; Resolve origin/rendered terms discrepancy before permission decisions

## Scope, evidence integrity and execution boundary
Ten bounded candidates were investigated; this is not an exhaustive inventory of issuers or national property agencies.
No numerical data feed was fetched. Only official documentation, terms, developer specifications and catalog metadata were read. No credentials, consent forms or paid services were used.
Evidence records distinguish complete origin-response hashes from short web-rendered excerpt hashes. Raw page bodies are not redistributed. Origin request timestamps identify request start; exact response-completion time was not captured.
Published permissions do not change the 19 FRED baseline restrictions. Treasury CC0 is scoped to the named catalog datasets; modern-feed mapping and service automation conditions remain gaps.
Five source-family parser contracts (Treasury, New York Fed, Chicago Fed, Cboe, SEC) use synthetic payloads. Chicago CSV headers remain an unverified candidate schema; remaining five candidates are catalog/investigation only. No parser test is a live interface acceptance.
Expected release time, filed date, observation date and fetched time never become first-available proof. All parser outputs remain NOT_VERIFIED for PIT.

## Verification
Baseline: 132 existing tests retained. G1: 23 additional tests. Full suite expected total: 155; actual local/hosted results and commit SHA are reported in the final delivery. CI configuration alone is not evidence of success.
The unchanged seven-module engine/configuration/state machine and CRS 1.1 branch remain frozen. G1 CI is a new separate workflow.

## Minimal user decision
| Decision | Narrow option | Safe default |
|---|---|---|
| Authorize bounded live interface validation and applicable existing terms | New York Fed SOFR/TGCR/BGCR only; after implementing required notices, one bounded read-only request, memory-only, no GitHub cache or public numerical report; not G2 scheduling | Do not perform until explicitly authorized |

There is no need to buy data, configure a FRED key, approve 19 series, contact owners, or enable G2/G3 now. Cboe/Chicago permissions and other unresolved sources remain disabled; any later request to owners must be separately authorized.

## Unchanged FRED series
RESTRICTED: BAMLH0A0HYM2, BAMLC0A0CM, BAMLH0A3HYC
REVIEW_REQUIRED: DGS10, DGS30, DFII10, VIXCLS, SOFR, IORB, NFCI, WRESBAL, RRPONTSYD, WTREGEN, DTWEXBGS, CSUSHPISA, EXHOSLUSM495S, MORTGAGE30US, CPIAUCSL, STLFSI4
