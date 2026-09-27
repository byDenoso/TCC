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

## Coordenação canônica entre automações

A/B/C se comunicam pelo bus privado já existente em `events/`, nunca por texto solto em relatório como substituto de estado.

- Ler fila do próprio papel: `python scripts/nexo_tower.py handoff list --role <EXECUTOR|ADVISOR|LEARNER>`.
- Ao assumir um item, marque o recebimento com `handoff ack <handoff_id> --role <papel>`. O código `ACK` significa apenas “recebi e assumi este trabalho”.
- Só depois de persistir a ação ou resultado e confirmar pela releitura da Tower, use `handoff done <handoff_id> --role <papel>`. `DONE` significa “concluído e confirmado na fonte canônica”.
- Use `handoff fail` apenas quando a execução realmente falhar ou houver bloqueio legítimo. `FAILED` significa “não foi possível concluir”. Somente o destinatário pode alterar esses estados técnicos.
- Envio novo: grave um JSON privado e rode `python scripts/nexo_tower.py handoff create <arquivo.json>`.
  O envio material usa o mesmo writer lock, o mesmo file id canônico da Tower, CAS, readback e sinalização do ATLAS de `apply`.
- `request_id` é chave idempotente estável: retry do MESMO envio reutiliza exatamente o mesmo `request_id`; conteúdo diferente exige novo `request_id`.
- Campos obrigatórios do envelope: `request_id`, `from_role`, `to_role`, `handoff_type`, `entity_ref`, `thread_id`,
  `summary_plain`, `why_it_matters`, `next_action`. Os três últimos são texto para leitura humana:
  diga primeiro o fato concreto, depois por que isso importa e por fim a ação específica. Não copie IDs, códigos de estado
  ou nomes internos de campos para esse texto. Se um termo técnico científico for necessário, explique-o em linguagem comum na mesma frase.
- Opcionais: `objective_ref`, `confidence_plain`, `evidence_refs` estruturado, `source_links`,
  `correlation_id`, `parent_handoff_id`. `confidence_plain` deve dizer em português o grau de confiança e a razão,
  por exemplo “Confiança moderada porque a fonte mede X, mas ainda não testa Y”. Nunca use apenas rótulos como HIGH/LOW.
- Cada `source_links[]` tem no mínimo `label`, `url`, `access_date`; quando vier de pesquisa pública, registre também,
  quando disponíveis, `publisher`, `authors`, `date`, `supports`, `uncertainty`, `next_test_impact`.
- Os repasses entre automações ficam privados na Tower. Texto livre, URLs, `topic_id`, contexto causal e refs canônicas
  nunca são superfície pública do ATLAS. Os campos técnicos continuam existindo para rastreabilidade, mas não devem ser repetidos dentro do texto humano.
- O runtime suprime da inbox trabalho que ficou stale/terminal ou mudou de owner; não ressuscite handoff antigo manualmente.

### Pesquisa pública direcionada

As automações podem pesquisar a internet quando isso responde a um objetivo NEXO atual e melhora uma decisão/teste discriminante concreto.

1. Prefira paper primário, release original de survey/missão/colaboração e dado oficial. Review ou notícia serve para descoberta, não como evidência final quando a fonte primária existe.
2. Para cada fonte usada, guarde URL, publisher/autores, data da fonte, data de acesso, o que ela sustenta, incerteza/limite e como altera o próximo teste discriminante.
3. Resumo da web nunca é RESULT científico. Só resultado produzido pelo teste canônico, com cômputo e persistência, pode alterar veredito.
4. Pesquisa externa não reescreve hipótese, null/rival, seleção, success/kill, decision rule ou claim boundary já congelados. Se a nova fonte exige desenho materialmente diferente, abra nova identidade TEST/HYPOTHESIS.
5. Não declare “progresso” por ter lido fontes. Há progresso somente quando a nova evidência foi ligada por ref/source link a uma mudança rastreável de priorização, hipótese, teste, handoff ou resultado persistido.
6. Quando uma pesquisa for útil ao próximo papel, passe-a via handoff com `objective_ref`, `evidence_refs` e `source_links`; preserve incerteza explícita.

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

## Limite do runtime ChatGPT

- **Proposal e handoff são objetos diferentes.** Proposal entra pelos inboxes de proposals e nunca significa ACK, DONE nem comunicação dirigida entre papéis. Handoff é comunicação privada dirigida entre papéis e continua exclusivamente em `python scripts/nexo_tower.py handoff ...` (ou interface equivalente), sempre com lock, CAS e readback.
- O repositório `byDenoso/TCC`, o branch `nexo-inbox` e as issues do repositório são publicamente legíveis. Uma **proposal sem conteúdo confidencial** pode seguir a ordem de inboxes já definida abaixo, começando pelo GitHub canônico, mas só depois de saneada para exposição pública: sem dados privados ou pessoais, credenciais ou segredos, conteúdo confidencial da Tower ou conteúdo de handoff privado.
- Uma **proposal que precise preservar conteúdo não público** pode usar o fallback privado da pasta Drive `NEXO_INBOX` somente quando o runtime tiver writer autorizado para essa pasta e conseguir confirmar readback exato. Ela continua sendo proposal: a persistência nesse inbox não cria ACK, DONE nem aplicação na Tower.
- Se uma proposal não puder ser saneada sem perder significado e o runtime não tiver writer autorizado com readback exato para o Drive `NEXO_INBOX`, declare o bloqueio e não publique o conteúdo como fallback no GitHub `nexo-inbox` nem em issue pública. Da mesma forma, se o runtime não expuser writer de handoff compatível, não simule ACK/DONE e não converta handoff em proposal.
- Para conteúdo que pode ser publicado, preserve a ordem existente em **ChatGPT inboxes** abaixo. `create_file` seguido de `fetch_file` com conteúdo exatamente igual confirma apenas **PERSISTED no inbox**; não significa ACK, DONE nem aplicação na Tower. A semântica e a autoridade da Tower permanecem inalteradas.
- Não dependa de branch intermediária, relay ou "wake" para considerar uma proposal persistida quando o inbox escolhido já teve readback exato. A ausência de consumidor verificável não deve transformar persistência confirmada em `STAGED_PENDING_RELAY` ou `PERSISTED_WAKE_PENDING`.

## ChatGPT inboxes
ChatGPT proposals arrive in three create-only inboxes; `python scripts/nexo_tower.py inbox list` reads all of them.
Use them in this order (the first is canonical; the others are fallbacks only when the one above is refused):
1. **Canonical:** GitHub `byDenoso/TCC`, branch `nexo-inbox`, folder `inbox/`.
2. Fallback: Drive folder `NEXO_INBOX` (when the Drive connector accepts the JSON file).
3. Last resort: GitHub issues on `byDenoso/TCC` (when both writes above are refused): title starting with `[NEXO_INBOX]`
  (or label `nexo-proposal`), body = the proposal envelope, ideally inside a ```json block. Only issues
  opened by `byDenoso` count (the repo is public). Applied issues get a comment and are closed.
All three feed the same converter and the same single CAS write + readback; none writes the Tower directly.
`inbox apply` applies everything pending and marks it processed; `inbox done <id>` does it by hand
(`github:<name>` ids move to `processed/`, `issue:<n>` ids are closed). Reading issues needs `GITHUB_TOKEN`
(or `NEXO_INBOX_GITHUB_TOKEN`, or a logged-in `gh`); without it the issue inbox is skipped with a log.

### Tower upload bridge (ChatGPT runtime)
When the ChatGPT runtime applies the inbox itself, the Tower file is updated only through this path:
1. Keep the applied Tower as a preserved TXT file (never import a temporary TXT directly: the runtime blocks it).
2. Reference it as `sediment://...`.
3. `update_file` on the **same canonical Tower file_id** (never create a new file).
4. Readback of that file_id: fingerprint must equal the locally projected one.
5. Only then move the inbox JSONs to `processed/` and update `tower-head.json`, then re-read it.

Failure rule: without step 4 PASS, the report says "não afirmo que chegou à Tower", keeps the JSONs in
`inbox/`, and reports the projected fingerprint separately from the real one. Never report a projected
fingerprint as the Tower head.
