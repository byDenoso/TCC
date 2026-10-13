"""Deterministic, read-only WORK obligations from one canonical file revision.

This view never grants execution eligibility, changes ownership or decides
science. Consumers filter it by their existing ACL before returning context.
"""
from __future__ import annotations
from collections import Counter

TERMINAL = frozenset({'DONE', 'VERIFIED', 'REJECTED', 'FAILED', 'SUPERSEDED',
                     'CANCELLED', 'CANCELED', 'ARCHIVED', 'COMPLETED',
                     'CLOSED_VERIFIED', 'DISCARDED', 'WITHDRAWN'})
ALIASES = {'ENGINEER': 'ADVISOR', 'REFEREE_1': 'REFUTADOR'}


def canonical_role(value):
    role = str(value or '').upper()
    return ALIASES.get(role, role)


def latest_handoffs(files):
    """Use the same logical-path order as the canonical handoff reader."""
    latest = {}
    for path in sorted(files):
        entry = files[path]
        if not isinstance(entry, dict) or entry.get('encoding') != 'json':
            continue
        value = entry.get('value')
        if path.startswith('events/') and isinstance(value, dict) and value.get('handoff_id'):
            latest[str(value['handoff_id'])] = (path, value)
    return latest


def derive_work_queue(files, *, handoffs=None):
    """One obligation per WORK; parallel offers cannot override valid acceptance.

    Exact dependencies and recorded readiness reasons are preserved. A terminal
    recovery WORK stays terminal even when its TEST is READY: these are separate
    obligations, and this function does not dispatch TESTs.
    """
    works = {path: entry['value'] for path, entry in files.items()
             if path.startswith('entities/work/') and isinstance(entry, dict)
             and entry.get('encoding') == 'json' and isinstance(entry.get('value'), dict)
             and entry['value'].get('id')}
    by_id = {str(value['id']): value for _, value in sorted(works.items())}
    identity_counts = Counter(str(value['id']) for value in works.values())
    events = latest_handoffs(files) if handoffs is None else handoffs
    by_work = {}
    for item in events.values():
        by_work.setdefault(str(item[1].get('entity_ref') or ''), []).append(item)
    rows = []
    for path, work in sorted(works.items()):
        identity = str(work['id'])
        owner = canonical_role(work.get('owner_role'))
        state = str(work.get('status') or '').upper()
        recovery = work.get('recovery') or {}
        if not isinstance(recovery, dict):
            recovery = {}
        offers = []
        for source_path, event in by_work.get(identity, []):
            if recovery:
                envelope = event.get('work_envelope') or {}
                if not isinstance(envelope, dict):
                    continue
                route = envelope.get('recovery') or {}
                if (event.get('handoff_type') != 'BLOCKER_RECOVERY'
                        or event.get('recovery_fingerprint') != recovery.get('fingerprint')
                        or canonical_role(event.get('to_role')) != canonical_role(recovery.get('target_role'))
                        or not isinstance(route, dict)
                        or route.get('route_generation') != recovery.get('route_generation')
                        or envelope.get('test_id') != work.get('test_id')):
                    continue
            offers.append((source_path, event))
        accepted = []
        for source_path, event in offers:
            if event.get('state') not in {'ACK', 'DONE'} or canonical_role(event.get('to_role')) != owner:
                continue
            event_version, current_version = event.get('entity_version'), work.get('entity_version')
            if (type(event_version) is int and type(current_version) is int
                    and event_version > current_version):
                continue
            if recovery:
                source = recovery.get('acceptance_source') or {}
                if (not isinstance(source, dict) or recovery.get('ownership_state') != 'ACCEPTED'
                        or any(source.get(key) != event.get(key)
                               for key in ('handoff_id', 'request_id', 'from_role', 'to_role'))):
                    continue
            accepted.append((source_path, event))
        pending = [event for _, event in offers if event.get('state') == 'PENDING']
        dependencies = work.get('depends_on') or []
        invalid_dependencies = not isinstance(dependencies, list) or any(not isinstance(ref, str) or not ref for ref in dependencies)
        dependency_rows = []
        if not invalid_dependencies:
            for ref in sorted(set(dependencies)):
                dependency = by_id.get(ref)
                dependency_state = str((dependency or {}).get('status') or '').upper()
                if identity_counts[ref] > 1:
                    dependency_state = 'AMBIGUOUS'
                dependency_rows.append({'ref': ref, 'state': dependency_state or 'UNKNOWN',
                                        'satisfied': dependency_state in {'DONE', 'VERIFIED', 'COMPLETED', 'CLOSED_VERIFIED'}})
        readiness = work.get('readiness') or {}
        reasons = recovery.get('reasons') or (readiness.get('reasons') if isinstance(readiness, dict) else ['READINESS_REASONS_INVALID']) or []
        reasons = sorted(set(str(reason) for reason in reasons)) if isinstance(reasons, list) else ['READINESS_REASONS_INVALID']
        # Stable precedence is part of the view's contract; never pick an old
        # READY event over the current lifecycle state.
        exclusion = ('WORK_TERMINAL' if state in TERMINAL else
                     'WORK_IDENTITY_AMBIGUOUS' if identity_counts[identity] > 1 else
                     'WAIT_HUMAN_DECISION' if work.get('human_action_required') is True else
                     'OWNER_MISSING' if not owner else
                     'DEPENDENCIES_INVALID' if invalid_dependencies else
                     'WAIT_DEPENDENCY' if any(not item['satisfied'] for item in dependency_rows) else
                     'WAIT_ACCEPTANCE' if (pending or recovery) and not accepted else
                     'WORK_IN_PROGRESS' if state == 'RUNNING' else
                     'WORK_WAIT_DEPENDENCY' if state == 'WAIT_DEPENDENCY' and work.get('kind') != 'DEPENDENCY_RECOVERY' else
                     'WORK_STATE_NOT_ACTIONABLE' if state not in {'READY', 'CHECKPOINTED', 'WAIT_DEPENDENCY'} else None)
        # A repair remains actionable by its accepted owner while its target
        # TEST is blocked. Those reasons describe the repair, not a new TEST.
        if exclusion is None and work.get('blocker') and work.get('kind') != 'DEPENDENCY_RECOVERY':
            exclusion = 'WORK_BLOCKED'
        row = {'id': identity, 'source_path': path, 'status': state, 'kind': work.get('kind'),
               'owner_role': owner, 'priority': work.get('priority') or 'P1',
               'entity_version': work.get('entity_version'), 'test_id': work.get('test_id'),
               'acceptance': 'ACCEPTED' if accepted else 'ASSIGNED_UNACCEPTED',
               'accepted_handoff_ids': sorted(str(event['handoff_id']) for _, event in accepted),
               'dependencies': dependency_rows, 'readiness_reasons': reasons,
               'human_action_required': work.get('human_action_required') is True,
               'dependency_class': work.get('dependency_class'),
               'dependency_classes': work.get('dependency_classes'),
               'auto_retry_eligible': work.get('auto_retry_eligible'),
               'next_action': work.get('next_action'),
               'next_step': 'WAIT_HUMAN_DECISION' if exclusion == 'WAIT_HUMAN_DECISION' else 'ACK_HANDOFF' if exclusion == 'WAIT_ACCEPTANCE' else 'CONTINUE_WORK' if exclusion is None else 'REVALIDATE_DEPENDENCY' if exclusion == 'WAIT_DEPENDENCY' else 'NONE',
               'first_exclusion_reason': exclusion,
               'actionable': exclusion is None, 'execution_authorization': False}
        rows.append(row)
    return sorted(rows, key=lambda row: (str(row['priority']), row['id'], row['source_path']))
