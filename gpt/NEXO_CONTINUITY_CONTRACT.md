# NEXO: continuidade privada e preparação ENXAME

Esta extensão funciona dentro do Writer existente. Não cria outro banco de verdade,
agendador, runtime de execução nem serviço de transporte. `CONTROL.json` vigente
continua definindo autoridade, ingresso e permissões. A Tower é canônica; índices e
Atlas são reconstruíveis. Os cinco papéis são papéis lógicos do mesmo proprietário,
não cinco revisores humanos independentes.

## Operações reais

São **kinds de envelope do Writer**, não novas ferramentas MCP:

| Kind | Source | Efeito |
|---|---|---|
| `ENXAME_EVENT` | A1–A5, conforme evento | Acrescenta evento privado imutável |
| `ENXAME_REGISTER_TEST` | A5 | Cria um TEST DRAFT para a SPEC congelada |
| `NEXO_MEMORY_ENTRY` | DENER, CHATGPT, ATLAS_OWNER ou papel existente autorizado | Acrescenta memória privada por escopo |
| `NEXO_PROJECT_EVENT` | Mesmas fontes de memória | Acrescenta etapa de projeto com predecessor explícito |

Formato comum: `{kind, source, intent_id, created_at, payload}`. `intent_id` é estável;
o retry preserva os bytes, inclusive timestamp. O ingresso é o Drive privado
declarado no CONTROL. `_inbox_source` é metadata confiável do loader, não campo
autorizável pelo cliente. O Writer conserva CAS, savepoint, receipts e readback.
Git é código/proveniência; conteúdo desses envelopes nunca vai ao inbox público.

`inbox_client.prepare(envelope, runtime_role=source, allowed_kinds={kind})` prepara e
valida. As operações de entrega e reconciliação são as existentes no inbox_client
e em `gpt/NEXO_DRIVE_BRIDGE.md`. `DELIVERED` não significa `APPLIED`. Releia a entidade
canônica e o receipt antes de concluir ou reenviar. Cliente sem acesso retorna erro;
não deve publicar uma proposta privada em outro transporte.

## ENXAME_EVENT

Payload permitido:
`{event_id,event_type,scope_id,scope_version,card_id?,spec_version?,expected_head,body,sources}`.
`expected_head` é o hash do último evento deste escopo/versão; use null somente no
primeiro. `sources` é lista de até 32 `{path,sha256}`: o digest é SHA256 do JSON
canônico Python da fonte existente (`memory.canonical`: UTF-8, chaves ordenadas,
sem espaços, sem NaN). Não é o hash do arquivo indentado nem ATLAS_JSON_V1.

O escopo é `roadmaps/<scope_id>.json`, precisa estar ACTIVE e sua `entity_version`
ou `version` precisa ser exatamente `scope_version`. Ausência de versão usa o
legado 1, sem autorizar incrementos inventados. IDs são `[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}`.

| Papel | Eventos permitidos |
|---|---|
| A1 | CLAIM, OBJECAO, ENDOSSO, SINAL, LINK, LICAO, CONFLITO, CANARIO |
| A2 | SPEC, RESPOSTA, SINAL, LICAO, CONFLITO, CANARIO |
| A3 | OBJECAO, ENDOSSO, SINAL, LICAO, CONFLITO, CANARIO |
| A4 | LINK, SINAL, CONFLITO, EMERGENTE, ENDOSSO, LICAO, CANARIO |
| A5 | FREEZE, REGISTRO, FIM, SINAL, CONFLITO, CANARIO |

- CLAIM: `body.claim`, fontes verificadas. `classification:NAO_TESTAVEL` exige
  `reason`. `legacy_test_ref` é caminho de TEST existente, imutável; não cria endossos.
- SPEC: `body.spec`, `spec_version` anterior+1, conteúdo materialmente diferente.
  Essenciais: question, null, rival, method, dataset_and_selection, success_criteria,
  kill_criteria, implementation. `requirements` descreve observable, likelihood,
  parameters_and_priors, statistic, threshold, multiplicity, attempts, systematics,
  degeneracies, null_expected, dependencies, cost. Cada item usa
  `{status:DEFINED,value:...}` ou `{status:NOT_APPLICABLE,reason:...}`. `gaps` lista
  lacunas explícitas; SPEC parcial é aceita, mas não congela.
- OBJECAO: `body.text`, SPEC atual. RESPOSTA: `body.objection_id`, text, fontes e
  SPEC atual. ENDOSSO: rationale e resolves opcional. Só o autor da objeção pode
  aceitar uma resposta material sobre a SPEC atual. Nova SPEC invalida endossos e freeze.
- CONFLITO: text; `resolves` só pelo autor, com fontes. LINK: target_card,
  relation, reason e fontes. EMERGENTE: claim, origin_cards, risk e fontes.
  Dedupe de emergentes é exata por claim normalizada+origens; equivalência semântica
  ainda exige consulta e revisão. Não há teto de três cards nem cota rígida de 30%.
- SINAL: weight entre 0 e 100. Pressão tem meia-vida de 24h e zera no freeze.
  Cobrança usa charge_key derivado, pending, owner, last_evidence e next_action;
  requer dois pulsos anteriores sem avanço e atraso material superior a duas horas.
  Uma situação gera uma cobrança.
- FREEZE: spec_sha256 exato e quorum A3+(A1 ou A4), sem lacunas/objeções/conflitos.
  REGISTRO: test_id canônico e `readback:{source_revision,entity_version,content_sha256}`
  da Tower já relida. String PASS, versão declarada ou recibo isolado não bastam.
- FIM: somente todos registrados/referências legadas/não testáveis, sem contestação
  pendente. Reabertura requer versão legítima nova do escopo. CANARIO não prova ciência.

Eventos ficam em `evolution/enxame/events/<digest>.json`, sem cap de 300; sequence,
previous_hash e sha256 permitem reconstrução e verificação integral. Falha de
um envelope fica no seu savepoint e não impede envelopes independentes.

## Registro e passagem à execução

`ENXAME_REGISTER_TEST.payload`:
`{scope_id,scope_version,card_id,spec_version,spec_sha256,expected_head,proposed_test_id?}`.
O ID oficial deriva de escopo/versão/card/SPEC/sha256. proposed_test_id não muda essa
identidade. Retry após criação relê o TEST e não cria outra entidade.

Registro mantém `scientific_evidence:[]`, sem veredito e sem executar. Conserva SPEC,
freeze e hash padrão de pré-registro do NEXO, `readiness` e preparação com próximo
responsável ADVISOR. Receita, params, inputs/version/sha256 e política de execução
precisam ser ligados pelo fluxo existente RECIPE_BIND/DATA_BINDING; reserva é BATTERY.
O preparo é privado. A política existente `PUBLIC_RECIPE_ONLY` impede sua execução
até revisão de escopo e autorização explícita de visibilidade. Esta extensão não
relaxa esse controle nem muda critérios para tornar uma fila executável.

Uma receita ligada não prova resultado: tentativa, artefato, fingerprints, runner
receipt, interpretação e revisão continuam sujeitos à integridade científica existente.
O hash da SPEC inteira e o prereg_hash de oito campos são contratos distintos.

## Memória e projetos gerais

Escopos: SCIENCE, WORK, PERSONAL, CLIENT:<id>. Todos os registros são owner-private,
com allowed_roles vazio; o nome de um humano nunca vira um papel do índice científico.
Categorias: USER_PREFERENCE, USER_DECISION, PROJECT_CONTEXT, SCIENTIFIC_EVIDENCE,
OPERATIONAL_LESSON. Payload memória:
`{event_id,scope,category,text,sources?,applicability?,contradicts?,supersedes_record_id?,valid_from?,valid_until?}`.
Evidências e lições exigem fontes+limites. Correção referencia registro do mesmo
escopo/categoria. Não apaga o anterior. `supersedes_record_id` é distinto do campo
de supersession de receipts. Síntese nunca recebe autoridade científica independente.

Payload projeto:
`{event_id,scope,project_id,title,action,text,expected_previous,sources?,owner?,next_action?,depends_on?,delivery?,decision?}`.
Ações: CREATED, PROGRESS, BLOCKED, DELIVERY, DECISION_REQUIRED, DECISION, COMPLETED,
REOPENED. expected_previous é ID do evento anterior, null na criação. Progresso,
entrega, decisão e conclusão exigem fonte canônica. BLOCKED exige responsável,
dependência e próxima ação. DELIVERY.source_path precisa estar nas fontes verificadas.
Conclusão só reabre com evidência. Projetos comuns não exigem H0/H1 nem quorum.

## Leitura por runtime e Atlas

```text
python gpt/nexo_gpt_writer.py continuity inspect TOWER.json --after 0 --limit 100
python gpt/nexo_gpt_writer.py continuity prepare envelope.json --role A1
python gpt/nexo_memory.py search TOWER.json CACHE --role LEARNER --query "..." --mode auto
```

inspect verifica Tower, eventos e apresenta requisitos atuais dos testes preparados.
prepare não entrega nem aplica. O cache de recuperação usa um novo sufixo; caches
anteriores ficam preservados. A CLI não instala conexão em outros chats.

Atlas privado: `#/teia/continuidade`, POST fixo `/api/atlas-private/continuity` com
owner+PIN+same-origin e revalidação depois da leitura. Consulta:
`{scope?,view:overview|board|memory,offset?,limit?,expected_revision?,since?}`.
Offset positivo exige a revisão exata. Fonte completa tem hash conferido; hash de
cada evento é recomputado sem perder floats Python. Falha não retorna contagem zero.
O site conserva seu grant Drive read_only: pode preparar JSON de correção, não
aplicar. Aplicação e readback acontecem no Writer.

O MCP publicado continua declarando somente nexo_capabilities, nexo_search,
nexo_neighbors e nexo_trace sob o grant existente. Não inventar nexo_memory_write,
enxame_register ou acesso automático a informações pessoais. Cada automação deve
provar acesso a Tower/inbox, carregar este bundle e manter os limites do seu runtime.
Configurar ou alterar as cinco automações pertence ao outro chat.

## Benchmark

`scripts/benchmark_continuity_retrieval.py TOWER queries.json report.json --cache DIR`
compara legado/hybrid, lexical, auto, hybrid e rerank. Queries externas com
`{query,relevant:[canonical_id],stratum,role?}` preservam o corpus fora do código.
Relatório mede alvos no top5, MRR, abstenção negativa, hashes/revisões e latências
locais. Não é avaliação cega nem latência de login/Drive; ausência em pesquisa
bibliográfica não demonstra ineditismo. Uma semana real de autonomia ainda precisa
ser observada em operação, com falhas e recuperação.
