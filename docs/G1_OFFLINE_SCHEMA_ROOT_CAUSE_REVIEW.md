# G1_OFFLINE_SCHEMA_ROOT_CAUSE_REVIEW

2026-11-22. Authority: Issue #4 comment 7077852495. Offline work only.

## Conclusion

Offline remediation PASS; actual-response root cause UNKNOWN; real admission NO-GO. G2/G3 NOT_STARTED; formal score N/A. No new numerical-data endpoint was requested.

## Confirmed

The historical SOFR request returned HTTP 200 and failed the project validator. Its body was not retained and is unavailable for reconstruction. The historical report is unchanged.

The original checker collapsed JSON, container, count and numeric-field failures into SCHEMA_MISMATCH. Its executor assigned unit_validation=PASS solely from checker success, without independent unit evidence. It also used a cwd-relative consumption marker, which could permit reuse from another directory or clone. These are confirmed implementation defects, not evidence of an official API change.

The original record_count=1 and observation_date constant were set only after the old checker tested those exact predicates. They were not arbitrary values, but the implementation coupled stages and failed to expose independent outcomes.

## Official contract comparison

Documentation only: https://markets.newyorkfed.org/static/docs/markets-api.yml . Retrieved again on 2026-11-22; SHA256 remains 5dbb331d86b91bfc115be9b5fe9c46735833a4f7280d33e4327e8acf7ad30d2b.

The documented secured/search route permits sofr/tgcr/bgcr, JSON, inclusive startDate/endDate and type=rate. The documented response uses refRates and numeric percent, with effectiveDate and type. There is no documented contradiction establishing that the exact original URI was invalid. A field named percent and a numeric type describe the intended contract but do not independently demonstrate the scale of an unseen actual response. No percent/basis-point conversion is inferred.

## Plausible, unconfirmed

JSON parsing failure, a different envelope, empty/multiple records, a missing field or unexpected numeric type can reproduce the same old error using synthetic payloads. A successful HTTP response can contain unexpected content. None of these hypotheses is established for the discarded real body. The response length cannot identify its contents. No rate value, response hash or supposed actual field is reconstructed.

## Fixes

Added offline assess_body with separate schema_validation, date_validation and unit_validation. Container/count/row/field/date failures have distinct non-sensitive reason codes. Record count and observation date are extracted from synthetic payloads. Numeric validity alone leaves unit UNKNOWN; a future independently reviewed field-to-unit/source-version evidence mechanism is required before unit PASS can exist.

The old check_body remains a compatibility-only structural predicate for historical tests; it is not a complete admission decision. No executor uses it to grant unit PASS.

Removed the real network execution path for consumed authority 7077794290. run_once now raises AUTHORIZATION_CONSUMED before any filesystem or transport access, regardless of cwd, clone, local marker presence or preflight boolean. Repository history and the existing nonnumerical marker preserve consumption; deleting a log cannot revive authorization. Any future batch needs a different explicit authorization and separately reviewed execution path.

Private diagnostic retention remains at most seven days; the existing metadata-only diagnostics were deleted during this review, while the nonnumerical consumed marker was retained. Historical public audit summaries were not changed.

## Tests and remaining evidence

170 tests pass locally: previous 166 plus four new regressions covering numeric-not-unit evidence, date/schema separation, distinct failure reasons and cwd-independent consumed-authority denial before transport. Hosted CI and exact SHA are supplied in the final delivery message; CI never calls a real rate endpoint.

A new real batch is not requested in this review. Before deciding one is necessary, define a separately authorized nonnumerical failure taxonomy and independently justified unit contract, validate them with synthetic counterexamples, and assess whether a documentation correction suffices. Any future real response collection or retest requires new specific authority; the previous batch cannot be reused.

main, CRS 1.1, model weights, production switches and Agent Reach remain unchanged.
