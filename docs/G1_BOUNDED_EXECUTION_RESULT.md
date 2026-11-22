# G1 bounded execution result

Authority: Issue #4 comment 7077794290; fixed packet fc08dff.

Batch status: PARTIAL_STOP. Authority consumed; no second batch authorized.

| Rate | Request attempted | HTTP | Schema | Unit | Error |
|---|---|---|---|---|---|
| SOFR | Yes | 200 | FAIL | NOT_RUN | SCHEMA_MISMATCH |
| TGCR | No | N/A | NOT_RUN | NOT_RUN | Stopped after SOFR |
| BGCR | No | N/A | NOT_RUN | NOT_RUN | Stopped after SOFR |

SOFR started 2026-11-22T10:29:18.867371Z, completed 2026-11-22T10:29:19.945313Z. Response size 230 bytes; elapsed 1077 ms. No claim about observation-date or unit verification is made. No response body, rate, percentile, volume or body hash is retained or published. The precise unexpected response fields are not logged; do not infer them from HTTP success.

OpenAPI digest and four required notice-template digests matched the fixed packet before the batch. Source templates were handled in private process memory; no market numbers were displayed. Standard HTTPS transport has no redirects, retry, cookies, environment proxies, netrc or credential lookup. The consumption marker was reserved before transport; it remains in ignored local data/crs-g1-private. Typed local diagnostics must be removed within seven days; retain the nonnumerical consumption marker to prevent reuse.

G1 real admission: NO-GO. G2/G3: NOT_STARTED; G2 NOT_AUTHORIZED. Formal CRS score: N/A. Global source flags remain false. No main, CRS 1.1, model or account changes.

Local regression: 166 tests passed (163 existing plus three one-off contract tests). Hosted CI result and exact delivery SHA are provided in the delivery message. CI does not run the real entry point. Subsequent transport, schema repair and real retest are not authorized by this consumed batch.
