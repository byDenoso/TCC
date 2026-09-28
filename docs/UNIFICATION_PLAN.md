# NEXO — plano de unificação (Claude × GPT, 2026-09-28)

Objetivo: backend, automações, conversas com o GPT e site como **um sistema**. Repositório é detalhe de implementação.

## Quatro invariantes (valem durante toda a migração)
1. **1 autoridade** — Tower (Drive).
2. **1 esquema de comando** — proposals tipados num envelope comum.
3. **1 escritor** — NEXO Writer robot.
4. **1 compilador de leitura** — projeção Python; o site só desenha.

Regra absoluta: nunca existe mais de uma resposta para "quem recebe comandos?", "quem escreve a Tower?", "quem interpreta a Tower?". Split-brain é o risco nº 1.

## Decisões
- `nexo-core` **privado** (runtime, contratos, prompts, skills, testes) + `nexo-web` **público** (site + `system.json`). Fusão só depois de auditar o histórico Git.
- **Uma fila lógica** (`TCC@nexo-inbox`), vários transportes: GitHub (primário) → Vercel (fallback, sai primeiro) → Drive (emergência).
- Conversas geram proposals **tipados** direto. `CONVERSATION_REQUEST` só para texto livre vindo do site.
- **Semântica em Python.** O front ordena, filtra, formata e desenha; nunca decide veredito, contestação ou domínio.
- `activity[]` é **observabilidade derivada**, não barramento: `{event_id, event_type, actor, entity_id, occurred_at, tower_head, source_ref}`.
- Remoção em três estados: `ACTIVE → SHADOWED → REMOVED` (corta consumidor, mede, só então apaga).

## Ordem
| Fase | O quê | Dono | Aceite |
|---|---|---|---|
| 1 | Golden tests Tower→projection + `contracts/proposal.schema.json` | GPT | 100% verdes no runtime atual, sem tocar Tower/site |
| 2 | CI de drift contrato ↔ prompts ↔ skills (detecta, não gera) | GPT | CI falha em divergência de schedule/kinds/versão |
| 3 | Inbox lógico único; adaptadores antigos terminam no mesmo envelope | GPT | Todo produtor chega em `nexo-inbox` |
| 4 | `system-v2.json` em shadow com `display_verdict`, `contest_of`, `domain` + envelope de evento; diff automático vs atual | GPT | Diff zero em entidades, estados, relações, frontier |
| 5 | Site lê só `system-v2.json`; `/api/system` apenas espelha; apagar `verdictOf()`/regex de contestação do React; lint anti-domínio | Claude | Nenhuma regra científica no front |
| 6 | Remover `build-pages-system`, `science-projection-v1`, `server/compiler/*` | Claude | Nenhum consumidor restante |
| 7 | Aposentar Vercel após janela sem uso; Drive fica como emergência | GPT | Zero entregas via Vercel na janela |
| 8 | Limpeza física (Vault no Pages, atlas-control-tower, canaries calendar/sheet, Galáxia antiga) e só então reorganizar repos | Claude + GPT | Busca de referências limpa |

Dener aprova cada fase; nenhum passo exige mais que isso.

## Fase 1 — entregáveis (GPT)
- `tests/golden/tower_to_projection/*.json` — fixtures cobrindo CONFIRMED, REFUTED, review, contest, blocked, discarded.
- `tests/test_public_projection_golden.py` — Tower → projection determinístico.
- `contracts/proposal.schema.json` + `tests/test_proposal_schema.py` — envelope comum, kinds, actor, source_ref, tower_head, idempotência; casos negativos.
- `tests/fixtures/contest_resolution.json` — `contest_of` inclusive para IDs fora da regex histórica.
- Golden inclui `display_verdict`, `contest_of`, `domain` resolvidos só no backend; teste de determinismo por ordem de entrada.
