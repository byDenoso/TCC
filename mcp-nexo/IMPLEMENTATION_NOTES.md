# PR 184 — private catalog discovery patch

Base reviewed: `byDenoso/TCC` PR 184, head `53d5a2cc1bc7b1995f24fca059a3a3c4415d6189`.
This patch extends that implementation, not a replacement MCP service.

## Verified locally

- All ten original file blob hashes matched the remote head before changes.
- Baseline suite: 16/16 passing, including actual local HTTP MCP requests with JWTs and simulated upstreams.
- Final suite: 42/42 passing. New behavior developed with failing tests followed by implementation.
- Node syntax checks and `git diff --check` passed.
- Independent review findings corrected with regression tests: oversized/non-string IDs, concurrent cache rollback, invalid UTF-8 changing provenance bytes, sparse LOOKUP tail truncation and mixed-snapshot status across TTL expiry.
- Local parser also exercised on the authorized private runtime catalog, dataset CSV and LOOKUP export. Private inputs/results are intentionally absent from this repository.

## Boundary

This is implemented and tested discovery, not production-connected Google/OAuth/Vercel or solver execution. Configuration remains external and fail-closed. No production credentials, deploy, merge, campaign dispatch, Tower write or private data publication occurred.

The existing public staging operations are unchanged. A `PUBLIC:` marker remains the pre-existing operator assertion, not an automatic data-loss-prevention classifier. Operators must not submit private payloads to those tools.

## Apply/review

Apply to the same PR branch only after confirming its head has not changed. No new branch, database, catalog mirror or service is required. Run `npm ci && npm test` in `mcp-nexo`, then perform explicitly authorized staging/provider validation before deployment. Preserve the original frozen scientific contracts. Rollback is to the reviewed head above; no source data migration is involved.
