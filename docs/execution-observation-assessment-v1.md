# Operational assessment of a recorded observation

`EXECUTION_OBSERVATION_ASSESSMENT_V1` annotates an explicitly approved historical
runner observation that recorded `INPUT_OR_FIT_UNAVAILABLE` as an `INCONCLUSIVE`
result. It does not replace a verdict, reopen a test, change a scientific design,
or create an execution attempt. Ordinary scientific inconclusive results remain
in their existing cohorts.

## Evidence and authority boundary

The existing Pantheon collector owns GitHub metadata and archive verification.
Its reviewed descriptor list identifies the allowed run, artifact, ZIP hash,
member hash, test, attempt, recipe and canonical observation hash. The collector
retrieves the original artifact and emits the operation only after those checks.
The bounded migration can be disabled after readback without deleting its
approved descriptors or changing any schedule.

The Writer accepts `nexo_operation: EXECUTION_OBSERVATION_ASSESSMENT` only through
the internally assigned `RUNNER_OBSERVATION` source. Drive, GitHub inbox and
Gateway messages cannot claim that source: their ingestion adapters assign their
actual origin. A serialized generic mutation cannot write or remove
`execution_assessment`; only the validated Writer operation has its in-process
write capability.

The TCC module checks the member bytes, exact receipt membership, original
observation, attempt/recipe provenance, explicit technical-failure decision and
absence of scientific estimates. It relies on the collector for the GitHub
archive/metadata attestation; it does not claim an independent network fetch.
Both boundaries are required.

## Atomic append and replay

The approved descriptor has `expected_version` and `expected_observation_hash`.
The observation hash commits the canonical `verdict`, `decision`, `statistics`,
`result_summary`, `executed_at` and `reproducibility` fields. The Writer checks the
receipt against those fields, then appends one assessment under the TEST version
CAS. A concurrent change is rejected. Exact replay is a no-op; a different proof
cannot overwrite an existing assessment, including an unknown existing format.

The private assessment retains the descriptor, fetched member text, evidence
fingerprint and real Writer observation time. The source artifact remains the
original artifact; no old receipt or timestamp is rewritten. The raw terminal
result remains protected by the existing integrity rules.

## Public projection and scientific learning

Only a validated assessment appears in the public TEST projection:

- `contract: EXECUTION_OBSERVATION_ASSESSMENT_V1`
- `classification: OPERATIONAL_FAILURE_RECORDED_AS_RESULT`
- `scientific_result_eligible: false`
- `reason_code: INPUT_OR_FIT_UNAVAILABLE`
- `recorded_at`: the Writer's new assessment time

The raw verdict remains visible. Private member text, artifact descriptors and
hashes are not copied to this public overlay. Invalid or unknown assessments do
not produce the overlay or exclude a record. Their absence does not itself prove
scientific validity.

The procedural learning cohort excludes only validated operational assessments
and reports `evaluated.excluded_operational`. Autonomy V2 metrics continue to
count raw verdict records with their existing explicit denominators. The public
runner applies the same validated public contract when selecting observations
for scientific learning/calibration; legitimate inconclusive results are not
blanket-excluded.
