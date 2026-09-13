# NEXO state artifacts

Campaign and test state is explicit and machine-readable. GitHub job color is not scientific state.

Campaign path: `PLANNED -> READY -> RUNNING -> VALIDATING -> LEARNING -> CLOSED`, with `BLOCKED` and `FAILED` fail-closed branches.

Test path: `PLANNED -> READY -> DISPATCHED -> RUNNING -> VALIDATING -> PASSED`, with terminal `NOT_PROMOTED`, `FAILED`, or `BLOCKED` outcomes.

`PASSED` is reserved for results that satisfy the registered scientific promotion validator. `NOT_PROMOTED` means execution produced usable output but the promotion contract did not pass.
