# G1_NEXT_DECISION_READINESS

Review date 2026-11-22; Issue #4 comment 7077904717. Preparation only, no new authorization requested or exercised.

**Readiness: PARTIAL. A second real batch is not ready for approval. G1 real admission NO-GO; G2/G3 NOT_STARTED; formal score N/A.**

## Sufficiently established

The official [OpenAPI](https://markets.newyorkfed.org/static/docs/markets-api.yml) was reviewed again, documentation only. Its SHA256 remains 5dbb331d86b91bfc115be9b5fe9c46735833a4f7280d33e4327e8acf7ad30d2b. The secured JSON contract has a refRates array and per-rate effectiveDate, type and numeric percent. Its synthetic examples are documentation examples, not proof of any live response. No alternate live paths or historical observations were fetched.

The official [reference-rate methodology](https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates) defines the published secured rates as volume-weighted medians rounded at publication to a basis point. That describes the benchmark and rounding, not an independently verified conversion of this API field in the discarded response. OpenAPI has no explicit percentage/basis-point unit declaration for the reviewed field. No automatic division/multiplication is justified by these documents alone. Unit remains UNKNOWN.

The first batch is consumed. Its HTTP200/schema failure is established; its precise envelope and failure subtype are unrecoverable. Current run_once always rejects before network or filesystem access. This does not make historical source-code copies technically incapable of requests; operator authorization rules and controlled environments remain essential.

## Offline diagnostic minimum

Synthetic counterexamples exercise JSON_INVALID, CONTAINER_MISSING, CONTAINER_TYPE, ROW_COUNT, RATE_FIELD_TYPE, DATE_FIELD_TYPE and DATE_FORMAT. Schema/date/unit states remain separate. An unfamiliar envelope is rejected, not guessed. No raw field, value, body hash or exception text is emitted by these assessments.

The existing approved diagnostic allowlist does NOT include the richer reason/date-validation fields. Tests ensure safe_diagnostic rejects them. The offline assessment is not permission to log these fields during a future real batch. A future authorization must explicitly enumerate any added nonnumerical enums; unknown keys must not be silently passed through.

## Logging, version and consumption review

The original metadata-only local diagnostics were already deleted in the prior review; the original nonnumerical consumption marker and public historical result remain. No new private log was created. Prior 7-day retention is an upper bound, not permission to retain indefinitely. There is no new scheduled cleanup/collection task.

Future approval would need to bind a new unique authorization ID to a canonical request-plan digest, source-document version, parser version and permitted diagnostic schema. It would also require a process-independent atomic consumption ledger in a fixed controlled location, reserved before any request, with no replay after failure or directory changes. Current work does not implement or enable that future execution path and never revives 7077794290.

## Missing minimum evidence and next decision

1. Obtain official documentation or a provider clarification that unambiguously maps the returned rate field to its unit/scale for a named API version. Benchmark rounding and a field name alone are insufficient.
2. Confirm any official static response example and its version/provenance. Do not call a numerical API to obtain a supposed documentation example without authorization.
3. Freeze a no-value diagnostic schema with separate envelope, field/type, date and unit-evidence classifications; specify which metadata may be retained. Current synthetic tests prove classification behavior only.

A fresh real sample may eventually be necessary to establish actual transport/envelope compatibility, because the original body cannot be recovered. It would NOT by itself establish unit semantics or model validity. There is presently insufficient justification to request that sample before the preceding unit/diagnostic evidence is prepared.

If those prerequisites are later satisfied, the minimum independent proposal should start with ONE fixed-date SOFR GET, memory-only, no retry/redirect/fallback, explicit metadata enums, exact notice/version binding, a new consumed-on-start authorization ID, and immediate stop on uncertainty. Do not automatically include TGCR/BGCR, reuse the former batch, or treat a successful single request as permission for G2. This paragraph is a proposal outline, not a request for current approval.

## Delivery validation

Existing 170 tests retained; three new readiness regressions bring the suite to 173. Actual local/hosted results, commit SHA and CI URL are supplied in the delivery response. No production/model/main/CRS1.1/Agent Reach changes. No new total-control issue or source inventory was created.
