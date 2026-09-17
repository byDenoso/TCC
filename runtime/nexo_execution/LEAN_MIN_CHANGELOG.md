# NEXO Lean-MIN runtime cut

This branch removes administrative existence gates from the execution path while preserving frozen science, explicit authorization boundaries, irreversible-conflict protection, output validation, persistence, and canonical readback.

Key runtime changes:

- CHECKPOINTED work is resumable and does not consume active compute capacity.
- `test_group` is accepted as the canonical campaign representation without duplicate campaign writes.
- Executor admission no longer requires duplicated operational flags such as `binding_verified`, `dependencies_resolved`, `runtime_available`, `resource_lock_available`, or `validation_ref`.
- Allowlisted runtime tasks remain executable even when a capability manifest copy is absent.
- Only blocker classes `SCIENTIFIC_DEFINITION_MISSING`, `AUTHORIZATION_MISSING`, and `IRREVERSIBLE_CONFLICT` are hard execution gates.
- Verified provenance plus integrity can bind evidence without a manually registered `evidence_id`.
- Recipe identities are derivable and scientific contracts only require fields materially present for that producer.
- Missing repairable operational dependencies become `RESOLVE_OPERATIONAL`, not `NEEDS_RECIPE`.
