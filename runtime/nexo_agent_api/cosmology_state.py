"""Public cosmological synthesis. Literature is orientation; Tower remains authority.

The bounded historical reservoir is an audited extract, never an operational
import. Current entities supersede matching historical IDs. Test verdicts do not
become global consensus: only an explicit, audited Tower synthesis can replace
literature-level state. Every NEXO interpretation carries evidence references.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from typing import Any

DATA = Path(__file__).with_name('cosmology')
LABELS = {'SOLID': 'Sólido', 'TENSION': 'Tensão', 'OPEN': 'Aberto'}
OPERATIONAL = {'READY', 'RUNNING', 'CHECKPOINTED', 'BLOCKED', 'DRAFT', 'QUEUED', 'DISPATCHED'}


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def _signature(item: dict) -> str:
    # Never merge distinct nulls, selections, estimands or final decisions.
    audit = item.get('provenance', {}).get('audit', {})
    parts = [item.get(k) or audit.get(k) for k in
             ('question', 'dataset', 'selection', 'method', 'estimand', 'null', 'rival')]
    prereg = item.get('prereg') or {}
    parts += [audit.get('dataset_stack'), item.get('datasets'), {k: v for k, v in prereg.items() if k not in {'hash', 'at', 'test_id'}}, item.get('verdict')]
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _meaning(test: dict) -> str:
    semantic = test.get('semantic') or {}
    return str(test.get('result_meaning') or semantic.get('result_meaning') or '')


def _verdict(test: dict) -> str:
    status = str(test.get('status') or test.get('state') or '').upper()
    review = str(test.get('review_state') or '').upper()
    if status in OPERATIONAL:
        return 'OPEN'
    # A review closure plus a frozen contract/result is the current audit gate.
    if review in {'CONFIRMED', 'REFUTED'} and (test.get('prereg') or {}).get('hash') and _meaning(test):
        return review
    if review in {'PENDING_REVIEW', 'CONTESTED', 'REFEREE1_PASSED'} or test.get('verdict') == 'PROMOTED':
        return 'REVIEW'
    return 'INCONCLUSIVE'


def build_cosmology_state(root: Path, tests: list[dict], campaigns: list[dict], roadmaps: list[dict]) -> dict:
    baseline = _read(root / 'science/cosmology_world_model.json', _read(DATA / 'baseline.json', {}))
    reservoir = _read(DATA / 'historical_evidence.json', {'evidence': []})
    current = {str(t['id']): t for t in tests if t.get('id') and not t.get('private')}
    # Published history is small, scientific and immutable; no old queues enter.
    history = [dict(e, historical=True, kind='TEST', synthesis_eligible=True,
                    evidence_signature=_signature(e)) for e in reservoir['evidence']]
    historical_tests = []
    for e in history:
        if e['id'] not in current:
            historical_tests.append({
                'id': e['id'], 'display_name': e['title'], 'question': e['question'],
                'result_meaning': e['meaning'], 'status': 'DONE', 'review_state': e['verdict'],
                'domain': 'SCIENCE', 'historical': True, 'provenance': e['provenance'],
                'source_url': e.get('source_url'), 'limitations': [e.get('limitations') or 'Escopo histórico; não reativa a Tower antiga.'],
                'claim_boundary': 'Resultado histórico no escopo do contrato; não constitui consenso global.',
            })
    fronts = []
    canonical = _read(root / 'evolution/cosmology_state.json', {}).get('frontiers', [])
    overrides = {f['id']: f for f in canonical if f.get('id')}
    campaign_ids = {str(c.get('campaign_id') or c.get('id')) for c in campaigns}
    for source in baseline.get('frontiers', []):
        front = {k: source[k] for k in ('id', 'title', 'state', 'summary', 'literature_baseline', 'confidence', 'qualification', 'open_questions', 'next_discriminants') if k in source}
        pattern = re.compile(source.get('match_pattern', r'(?!)'), re.I)
        material_pattern = re.compile(source.get('material_test_pattern', r'(?!)'))
        historical_ids = {e['id'] for e in history if front['id'] in e['frontier_ids']}
        matches = [t for t in current.values() if t['id'] in historical_ids or material_pattern.search(t['id']) or front['id'] in (t.get('cosmology_frontier_ids') or []) or pattern.search(' '.join(str(t.get(k) or '') for k in ('question', 'title', 'id')) + ' ' + str((t.get('semantic') or {}).get('question_plain') or ''))]
        evidence = []
        historical = [e for e in history if front['id'] in e['frontier_ids']]
        # Keep old evidence as historical even if the current Tower revises it.
        for t in matches:
            verdict = _verdict(t)
            explicitly_material = (t.get('cosmology_material') is True or material_pattern.search(t['id']) or t['id'] in historical_ids or t['id'] in (source.get('context_test_ids') or []) or t['id'] in overrides.get(front['id'], {}).get('evidence_ids', []))
            if not explicitly_material:
                continue
            if verdict == 'OPEN' or not _meaning(t):
                continue
            evidence.append(dict(id=t['id'], kind='TEST', title=t.get('display_name') or t.get('question') or t['id'],
                                 verdict=verdict, meaning=_meaning(t), historical=False,
                                 synthesis_eligible=verdict in {'CONFIRMED', 'REFUTED'},
                                 limitations=t.get('limitations') or [],
                                 provenance={'origin': 'CURRENT_TOWER', 'prereg_hash': (t.get('prereg') or {}).get('hash')},
                                 evidence_signature=_signature(dict(t, verdict=verdict))))
        evidence += [e for e in historical if e['id'] not in current]
        groups = {}
        for e in evidence:
            signature = e['evidence_signature']
            if signature not in groups:
                groups[signature] = dict(e, member_ids=[e['id']])
            else:
                groups[signature]['member_ids'].append(e['id'])
        evidence = list(groups.values())
        override = overrides.get(front['id'], {})
        refs = override.get('evidence_ids') or []
        eligible = {e['id'] for e in evidence if e['synthesis_eligible'] and not e['historical']}
        # Global transitions are an explicit Tower decision, never a count or a
        # sigma threshold inferred by the presentation. The gate requires a
        # scoped material synthesis and more than one independent closed test.
        signatures = {e['evidence_signature'] for e in evidence if e['id'] in refs and e['id'] in eligible}
        valid_override = (override.get('scope') == 'GLOBAL_SYNTHESIS' and override.get('material') is True and override.get('global_significance_reviewed') is True and override.get('independent_support') is True
                          and override.get('state') in LABELS and len(signatures) >= 2
                          and set(refs).issubset(eligible) and bool(override.get('summary')))
        if valid_override:
            for key in ('state', 'summary', 'why', 'qualification', 'confidence'):
                if key in override:
                    front[key] = override[key]
        terminal = [e for e in evidence if e['synthesis_eligible']]
        interpretation = []
        # A short orientation preserves both support and refutation; full
        # evidence and historical contradictions remain available below it.
        for verdict in ('CONFIRMED', 'REFUTED'):
            candidates = [e for e in terminal if e['verdict'] == verdict]
            if candidates:
                interpretation.append(candidates[0])
        scoped = next((e for e in terminal if not e['historical']), terminal[0] if terminal else None)
        summary_refs = []
        if not valid_override and scoped:
            front['summary'] += ' NEXO: ' + scoped['meaning']
            summary_refs = scoped['member_ids']
        front.update(state_label=LABELS[front['state']], literature_source=baseline.get('source'),
                     synthesis_basis='TOWER_AUDITED_SYNTHESIS' if valid_override else 'LITERATURE_WITH_SCOPED_TOWER_EVIDENCE',
                     synthesis_evidence_ids=refs if valid_override else summary_refs,
                     why=front.get('why') or 'O estado é uma síntese de nível superior; vereditos individuais e sinais isolados não equivalem a consenso.',
                     evidence_counts={k: sum(e['verdict'] == v for e in evidence) for k, v in [('confirmed','CONFIRMED'), ('refuted','REFUTED'), ('review','REVIEW'), ('inconclusive','INCONCLUSIVE')]},
                     key_evidence=evidence,
                     historical_lessons=[dict(e, superseded_by_current=e['id'] in current) for e in historical],
                     nexo_interpretation=[{'text': e['meaning'], 'evidence_ids': e['member_ids']} for e in interpretation],
                     campaign_ids=sorted({str(t.get('campaign_id')) for t in matches if str(t.get('campaign_id')) in campaign_ids}),
                     roadmap_ids=sorted({str(r.get('roadmap_id') or r.get('id')) for r in roadmaps if set(r.get('test_ids') or []).intersection(t['id'] for t in matches)}),
                     active_tests=[{'id': t['id'], 'title': t.get('display_name') or t.get('question') or t['id']} for t in matches if _verdict(t) in {'OPEN','REVIEW'}])
        front['evidence_counts']['open'] = len(front['active_tests'])
        fronts.append(front)
    return {'model': 'COSMOLOGY_STATE_V1', 'authority': 'TOWER', 'projection_only': True,
            'literature_source': baseline.get('source'), 'historical_reservoir_sha256': reservoir.get('archive_sha256'),
            'frontiers': fronts, 'historical_tests': historical_tests}
