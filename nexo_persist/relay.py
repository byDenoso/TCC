#!/usr/bin/env python3
"""Scheduled relay entry point; shared semantics live in _relay_shared."""

try:
    from ._relay_shared import (
        MAX_ATTEMPTS,
        ContentConflict,
        GitHubContents,
        ReadFailure,
        ReceiptLedgerUnavailable,
        RelayError,
        StableIdConflict,
        StableIdValidationError,
        TerminalReceiptError,
        TerminalTransportError,
        WriterReceipts,
        classify,
        collect_changed_paths,
        decoded,
        load_request,
        main,
        readback,
        relay_one,
        target_for_stable_id,
        validate_stable_id_collisions,
    )
except ImportError:  # direct execution as `python3 nexo_persist/relay.py`
    from _relay_shared import (
        MAX_ATTEMPTS,
        ContentConflict,
        GitHubContents,
        ReadFailure,
        ReceiptLedgerUnavailable,
        RelayError,
        StableIdConflict,
        StableIdValidationError,
        TerminalReceiptError,
        TerminalTransportError,
        WriterReceipts,
        classify,
        collect_changed_paths,
        decoded,
        load_request,
        main,
        readback,
        relay_one,
        target_for_stable_id,
        validate_stable_id_collisions,
    )

collect_changed = collect_changed_paths

if __name__ == "__main__":
    main()
