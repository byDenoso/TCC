# Automação B — Transferência de método + integridade do NEXO

Leia primeiro `automations/OPERATING_CONTRACT.md`.

## Parte 1 — Integridade (sempre primeiro)

1. Código fresco (`git pull --ff-only` em TCC, Pantheon, vault).
2. `python scripts/nexo_tower.py status`.
   - `OUTDATED`: dispare o Pages (`NEXO_PAGES_DISPATCH_TOKEN`/`GITHUB_TOKEN` se houver; senão
     `workflow_dispatch` do workflow "NEXO ONE GitHub Pages" pela UI do GitHub no navegador) e confira de novo
     em 10 min. Se o build falhar, leia o job, corrija a causa no código (PR) — não force exportação manual.
3. `python -m pytest -q` no TCC e `npm test` em `Pantheon/nexo-one`. Falha nova = corrigir (PR) ou registrar.
4. Auditoria da Tower (materialize com `pull`):
   - IDs duplicados, referências quebradas (`campaign_id`, `hypothesis_id`, `depends_on`, `test_refs`);
   - TEST/CAMPAIGN sem `semantic` explícito → preencha pelo backfill da taxonomia (basis ≠ UNMAPPED)
     via `apply` com `event_type: SEMANTIC_BACKFILL`; UNMAPPED fica listado no relatório;
   - TEST concluído sem `semantic.result_meaning` → escreva, a partir do resultado já persistido
     (estatísticas, veredito, claim_boundary), `result_meaning`, `verdict_plain` e `confidence_plain` em português
     simples; nunca reinterprete nem promova o claim — só traduza o que já está lá (`event_type: RESULT_MEANING_BACKFILL`);
   - `status` e `state` divergentes na mesma entidade → alinhe `status` ao lifecycle real;
   - índices (`indexes/*.json`) apontando para entidades inexistentes → corrija o índice (índice é derivado).
   Correções derivadas/determinísticas: aplique direto. Qualquer coisa que mude significado científico: não.
5. Pantheon `nexo-one/scripts/tower-consistency.mjs` também audita; rode-o se existir e compare.

## Parte 2 — Transferência de metodologia

1. Liste resultados novos desde o último pulso (TEST/RESULT com `updated_at` > último relatório em
   `%USERPROFILE%/.nexo/reports/B-*.md`).
2. Para cada um, pergunte: o **método** (não o achado) resolve um problema aberto em outro subdomínio da
   taxonomia? Ex.: null calibrado de H0 → change-point em composição corporal; leave-one-out de LSS → avaliação de agentes.
3. Se a transferência for plausível e testável, registre:
   - uma HYPOTHESIS no domínio-alvo (com `semantic`, critério de sucesso/kill congelado);
   - uma relação interdomínio (`entities/interdomain`, `relation_type: METHOD_TRANSFER`, `source_domains`,
     `target_domains`, `test_refs`) — é isso que aparece como filamento no ATLAS/Learning.
4. No máximo 3 transferências por pulso; qualidade > volume. Nada de transferência só por analogia verbal.

## Relatório

Contrato + lista: problemas de integridade achados/corrigidos, transferências propostas, UNMAPPED restantes.
Salve cópia em `%USERPROFILE%/.nexo/reports/B-<utc>.md`.
