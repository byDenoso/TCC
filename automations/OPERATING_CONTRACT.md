# NEXO — contrato operacional das automações

Vale para todas as automações (Claude Code, tarefas agendadas no PC do Dener).
Consenso Claude + ChatGPT em 2026-09-23.

## Verdade e escrita

- Truth Owner: `NEXO_TOWER_LIVE.json` no Drive (file id `1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z`).
- Único caminho de escrita: `python scripts/nexo_tower.py apply <request.json>` neste repositório.
  Ele faz lock → leitura → mutação → releitura do head → escrita no mesmo file id → readback, e avisa o ATLAS.
- Leitura: `python scripts/nexo_tower.py pull` materializa a Tower num diretório local (somente leitura).
- Nunca escreva no Drive por outro meio, nunca edite a cópia `TOWER_V06/` do vault no Git como estado,
  nunca commite projeção à mão. ATLAS, MCP, índices e snapshots são derivados.
- `status` mostra se o ATLAS está `CURRENT` ou `OUTDATED` em relação à Tower.

## Formato de mutação

```json
{
  "request_id": "REQ-<AUTOMACAO>-<utc>-<slug>",
  "entity_kind": "test | work | hypothesis | campaign | test_group | run | result | artifact | lesson",
  "entity_name": "<id canônico, ex TEST::X>",
  "expected_version": <entity_version lida; 0 para criar>,
  "writer_role": "EXECUTOR | ADVISOR | LEARNER | DAILY | EMERGENT",
  "event_type": "<VERBO_EM_MAIUSCULAS>",
  "changes": { ... }
}
```

Uma lista de requests num arquivo é aplicada numa única escrita.

## Semântica obrigatória

Todo TEST/CAMPAIGN novo leva `semantic = {domain_id, subdomain_id, topic_id, question_plain, why_it_matters}`
com IDs de `runtime/nexo_agent_api/contracts/SEMANTIC_TAXONOMY_V1.json`.
Todo resultado leva `semantic.result_meaning`, `verdict_plain`, `confidence_plain` em linguagem que o Dener entende
sem abrir o código. Se nenhum tópico serve, use o subdomínio; se nada serve, `UNMAPPED` — nunca invente.
Tópico novo na taxonomia = PR no TCC (contrato Git), não mutação da Tower.

## Blockers (regra anti-burocracia)

Blocker legítimo é SÓ:

1. `AUTHORIZATION_MISSING` — falta credencial externa que você não consegue obter;
2. `IRREVERSIBLE_CONFLICT` — conflito externo irreversível;
3. `SCIENTIFIC_DEFINITION_MISSING` — qualquer fallback mudaria estimand, seleção, null/rival ou regra de decisão;
4. gate explícito de operador já declarado no roadmap.

Não são blockers: dado público ausente localmente, cache/artefato faltando, wrapper/adapter/capability ausente,
divergência de runtime reparável, campanha/plano/handoff ausente, ambiguidade metodológica resolvível por método
canônico ou análise de sensibilidade, dependência que afeta só outra lane, `python3` ausente (use `sys.executable`).
Para isso: recuperar → reusar → adaptar → implementar o menor pedaço → continuar o MESMO objetivo científico,
registrando a limitação no resultado. Depois de duas tentativas equivalentes que falharam, mude uma variável material.

Se uma lane travar de verdade, registre o blocker na entidade e siga para a próxima lane executável.
Nunca termine uma execução com "aguardando o Dener" se existe outra lane que pode progredir.

## Conclusão de um teste

Só conta com cômputo real + persistência pela Tower + readback. Preflight, download e reparo não são resultado.
PASS de software nunca promove claim científico. Identidade científica congelada é preservada; ciência
materialmente diferente exige nova identidade TEST.

## Relato

Termine cada execução com um relatório curto em português: o que rodou, o que mudou na Tower
(fingerprint antes/depois), estado do ATLAS (`status`), e o próximo passo que a próxima execução vai pegar.

## ChatGPT inboxes
ChatGPT proposals arrive in three create-only inboxes; `python scripts/nexo_tower.py inbox list` reads all of them:
- Drive folder `NEXO_INBOX` (when the Drive connector accepts the JSON file).
- GitHub `byDenoso/TCC`, branch `nexo-inbox`, folder `inbox/` (when the GitHub connector can commit a file).
- GitHub issues on `byDenoso/TCC` (when both writes above are refused): title starting with `[NEXO_INBOX]`
  (or label `nexo-proposal`), body = the proposal envelope, ideally inside a ```json block. Only issues
  opened by `byDenoso` count (the repo is public). Applied issues get a comment and are closed.
All three feed the same converter and the same single CAS write + readback; none writes the Tower directly.
`inbox apply` applies everything pending and marks it processed; `inbox done <id>` does it by hand
(`github:<name>` ids move to `processed/`, `issue:<n>` ids are closed). Reading issues needs `GITHUB_TOKEN`
(or `NEXO_INBOX_GITHUB_TOKEN`, or a logged-in `gh`); without it the issue inbox is skipped with a log.
