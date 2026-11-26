# Remote-compatible integration

Base: 296e7f7ce0fd5713268c6ab048369275c0b485cb, independent branch codex/frie-aswm-unified.
The portable market_risk/frie and market_risk/aswm packages are added without changing frozen sentinel/crs production functions or weights. The old dated local dashboard observation is replaced with a value-free hub to avoid publishing restricted credit observations. Real user configuration, values, source payloads and credentials are not copied.

Run `python -m market_risk.aswm serve` from repository root. Existing nq_sentinel_pro remains unchanged. The new workflow runs the shared research tests and existing CRS tests in separate jobs, no market collection, credentials or score activation.

The parent workspace historical audit report remains a record of that workspace, not a claim that its unrelated dirty V3 changes are part of this branch. For final commit/CI status see the delivery report accompanying the final answer.
