# NEXO · Formato das propostas do GPT

> Este arquivo define só o **formato** de cada proposta. Fluxo, papéis, horários e regras estão no `nexo-master-router` e no `nexo-closed-loop` (`gpt/skills/`); em conflito, eles vencem.

Todos os agentes do GPT escrevem neste formato. O **NEXO · Writer** aplica as propostas na Tower
privada e atualiza o ATLAS público apenas com a projeção permitida. O conteúdo deve explicar em
português simples o que aconteceu, por que importa e qual é o próximo passo.

Envelope (um arquivo ou documento por proposta):

```json
{"kind": "...", "source": "CHATGPT", "created_at": "2026-09-24T12:00:00Z", "payload": {...}}
```
Nome: `<utc>-<kind>-<slug>`.

**Privacidade e destino:** GitHub `byDenoso/TCC@nexo-inbox` é público e aceita somente propostas
sanitizadas, sem dados privados da Tower, conteúdo de conversas, nomes ou referências internas de
handoff. Handoffs entre agentes e outras mensagens privadas devem ser um Google Doc com JSON no corpo,
criado em `NEXO_INBOX` no Drive privado. Depois de criar, releia o documento e confirme que o JSON está
inteiro. Se essa rota falhar, mantenha a proposta como pendente; não copie conteúdo privado para o
GitHub público. O Writer existente lê o Drive e aplica a mensagem à Tower com controle de versão e
readback.

## BOARD_POST — mural compartilhado entre os agentes
Recado curto de um papel para outro (ou para todos). É coordenação, nunca evidência: não muda teste nem veredito.
`payload`: `{to: PITIA|LEARNER|EXECUTOR|REFUTADOR|REFEREE_1|GUARDIAO|ENGINEER|SENTINEL|ADVISOR|CONVERSA|DENER|ALL, text, refs[]?, reply_to?, ttl_h? (48 padrão, máx 336)}` ou `{entries:[…]}`; `resolve:[ids]` fecha recados. Destinatário desconhecido é recusado, nunca ampliado silenciosamente para ALL.
Todo papel lê os recados para ele no início da rodada (`status.board`) e responde com ação ou com outro recado (`reply_to`). Para trabalho que precisa ser feito e acompanhado, use HANDOFF.

## HANDOFF — passar trabalho ou conversa a outro agente

Use um handoff quando houver uma próxima ação concreta que pertence a outro papel. O evento mantém
um resumo compreensível, a relação com o objetivo, as evidências e o identificador da conversa; não
grave a transcrição inteira. Campos em linguagem natural devem explicar o sentido, sem códigos de
campo ou instruções técnicas para o destinatário. Valores estruturados, como `entity_ref`, ficam nos
campos de referência.

**Sempre salve handoffs e transições no Drive privado `NEXO_INBOX`. Nunca os publique no inbox do GitHub.**

Criar um handoff:
```json
{
  "kind": "HANDOFF",
  "source": "CHATGPT",
  "created_at": "2026-09-27T12:00:00Z",
  "payload": {
    "request_id": "REQ-UTC-UNICO",
    "from_role": "ADVISOR",
    "to_role": "EXECUTOR",
    "handoff_type": "RESEARCH_READY",
    "entity_ref": "WORK::ID-DA-ENTIDADE",
    "thread_id": "ID-DA-CONVERSA",
    "summary_plain": "O que foi descoberto, em uma frase simples.",
    "why_it_matters": "Como isso ajuda o objetivo atual.",
    "next_action": "Uma ação específica para o papel que vai receber o trabalho.",
    "objective_ref": "ID-DO-OBJETIVO",
    "confidence_plain": "Confiança moderada porque a fonte sustenta a comparação, mas não decide qual explicação está correta.",
    "evidence_refs": [{"ref": "TEST::ID", "kind": "TEST"}],
    "source_links": [{"label": "Artigo", "url": "https://example.org/paper", "access_date": "2026-09-27"}]
  }
}
```

O destinatário consulta sua fila de mensagens no Tower usando o bundle existente:
`python nexo_gpt_writer.py handoff <TOWER.json> list <PAPEL>`. A fila contém apenas mensagens
direcionadas a esse papel que ainda estão abertas.

Ao assumir o trabalho, envie `HANDOFF_ACK`; ao concluir, envie `HANDOFF_DONE`; quando não puder
prosseguir, envie `HANDOFF_FAILED`. As transições também são documentos JSON no Drive privado:
```json
{
  "kind": "HANDOFF_TRANSITION",
  "source": "CHATGPT",
  "created_at": "2026-09-27T12:15:00Z",
  "payload": {"handoff_id": "HO-ID-DO-HANDOFF", "state": "ACK", "writer_role": "EXECUTOR"}
}
```

O Writer valida se o papel que responde é o destinatário original. `ACK` mantém a mensagem ativa;
`DONE` e `FAILED` encerram essa etapa e preservam o histórico privado. Não marque como concluído até
que a ação descrita esteja registrada ou tenha um motivo claro para parar.

Para `handoff_type: BLOCKER_RECOVERY`, a WORK deve ter `kind: DEPENDENCY_RECOVERY` e
`recovery.policy: EXECUTION_RECOVERY_V1`. O emissor é o dono atual; criar o evento não transfere
responsabilidade. ACK do destinatário faz a transferência por CAS e guarda `acceptance_source`.
DONE exige aceite prévio, WORK concluída e elegibilidade do TEST verificada novamente. FAILED
preserva o dono e o histórico. Esses eventos continuam privados e não podem passar pelo GitHub.

## Semântica (obrigatória em tudo que vira teste ou lição)
IDs de `SEMANTIC_TAXONOMY_V1` (runtime/nexo_agent_api/contracts/SEMANTIC_TAXONOMY_V1.json):
```json
"semantic": {
  "domain_id": "science",
  "subdomain_id": "science.cosmology.dark_matter",
  "topic_id": "science.cosmology.dark_matter.nature",
  "display_name": "Nome curto em português, 3–7 palavras (contestação: \"Ataque N · <nome do atacado>\")",
  "question_plain": "A pergunta em português simples, 1 frase",
  "why_it_matters": "Por que isso importa, 1 frase",
  "result_meaning": "Só em resultados: 2–3 frases simples — o que deu e o que significa",
  "verdict_plain": "Só em resultados: ex. 'Inconclusivo'",
  "confidence_plain": "alta | média | baixa"
}
```

## MUTATION_PROPOSAL — resultado de teste existente
```json
{"tests": [{
  "test_id": "DMN26-002-S8-SUPPRESSION",
  "result": {"verdict": "PROMOTED|INCONCLUSIVE|REJECTED", "decision": "CODIGO_CURTO", "summary": "1–3 frases com os números-chave", "statistics": {...}},
  "semantic": {...},
  "limitations": ["..."],
  "reproducibility": {"code": "resumo", "data_sources": ["url"]}
}]}
```
Nunca promova além do que o teste sustenta. Resultado nulo é resultado.

## HYPOTHESIS_PROPOSAL — teste novo congelado
```json
{
  "test_id": "DMN26-005-XXXX",
  "roadmap_id": "RM-DARK-MATTER-NATURE-20260923-V1",
  "question": "pergunta científica (inglês ok)",
  "null": "...", "rival": "...", "method": "...", "data": "...",
  "success_criteria": "...", "kill_criteria": "...",
  "claim_boundary": "...", "depends_on": ["..."], "priority": "P0|P1|P2",
  "preparation_evidence": {
    "literature_refs": ["fonte primária"],
    "internal_test_search": {"checked": true, "query": "...", "matched_test_ids": []}
  },
  "semantic": {...}
}
```
Com `roadmap_id`, o writer herda campanha/hipótese do roadmap e põe o teste na fronteira.
Para propostas do Cientista (`source: LEARNER`), o roadmap deve estar `ACTIVE` e
`preparation_evidence` é obrigatório. Havendo `matched_test_ids`, acrescentar
`replication:{justified:true,purpose,independence_axis,compares_to_test_ids}` dentro de
`preparation_evidence`; todos os IDs encontrados entram em `compares_to_test_ids`.
Recuperação acionável dirigida a LEARNER é priorizada; espera externa/por outro papel não bloqueia
toda a preparação. Este gate vale para TEST novo do Cientista, não para replay ou enriquecimento de
TEST existente.
Opcional (recomendado quando é uma hipótese nova), aparece em Ciência > Hipóteses:
```json
"hypothesis": {"id": "HYP-...", "statement": "enunciado", "model": "modelo rival",
               "baseline": "modelo nulo", "falsification_criterion": "o que derruba a hipótese"}
```
Sem esse bloco o writer deriva a hipótese do próprio teste (rival, null, kill).

## "Quero testar X" (qualquer conversa)
1. Monte na hora a HYPOTHESIS_PROPOSAL completa (com bloco `hypothesis`, semantic, critérios congelados, método e dados); escolha o `roadmap_id` mais próximo.
2. Se dá para executar agora com dados públicos: rode no Python e gere a MUTATION_PROPOSAL do resultado.
3. Rode o NEXO_WRITER_PROCEDURE (contrato MCP) na mesma conversa → aparece no ATLAS em minutos.
4. Se não dá para executar agora: grave só a hipótese; o Executor pega na fronteira.

## LEARNING_SIGNAL — lacuna de conhecimento do Dener (tarefa Gaps)
```json
{"signals": [{"topic_id": "science.cosmology.lss_growth", "evidence": "paráfrase, sem dado pessoal",
  "evidence_kind": "PARAPHRASE", "gap_type": "CONCEPT|MATH|METHOD|TOOL|INTUITION", "confidence": 0.8}]}
```
Fica salvo na Tower como `artifact LEARNING_SIGNAL::*` para o Learner ler.

## LESSON_PROPOSAL — lição (tarefa Learner)
```json
{"topic_id": "science.cosmology.lss_growth", "title": "...", "gap_type": "METHOD",
 "intuition": "imagem mental", "explanation": "mínimo formal, 1 equação se ajudar",
 "exercise": "pergunta de 2 min + resposta no fim", "linked_test_ids": ["..."],
 "semantic": {"domain_id": "...", "subdomain_id": "...", "topic_id": "..."}}
```
Vira `lesson LESSON::<topic_id>` e aparece no ATLAS (lente Aprendizado), perto dos testes do mesmo tópico.

## Tipos novos (router 0.4.0)
- `RECIPE_BIND` `{test_id, recipe, params}`: liga receita congelada a teste existente (DRAFT, READY ou BLOCKED_INPUT); o robô despacha na rodada seguinte.
- `FAMILY_CHARTER`: grade pré-registrada de instâncias de uma receita (formato no router, "O fluxo único").
- `LEARNING_SIGNAL` `gap_type: METHOD_TRANSFER` `{origin, destination, analog, breaks_if}`: método de um campo testado em outro.
- `HYPOTHESIS_PROPOSAL` com `origin_kind: DENER_DIRECTED`, `priority: P0`: Diretriz do Dener (vinda do NEXO Lite).

Consumo: hipóteses e lições citam em `linked_signal_ids` os ids `LEARNING_SIGNAL::*` que consumiram; sinal citado não é reprocessado.
Testes com id `META-*` (domain_id `engineering`) são hipóteses sobre o próprio sistema; recebem `origin: META`.

## INTEGRITY_REPORT (Guardião)
```json
{"date": "2026-09-25", "status": "GREEN|YELLOW|RED",
 "checks": [{"area": "tower|site|inbox|tasks|science|cycle|contract", "ok": true, "detail": "..."}],
 "semantic": {"domain_id": "engineering", "topic_id": "engineering.nexo_runtime"}}
```
Vira `artifact INTEGRITY_REPORT::*`. O Guardião nunca corrige nada.

## SEMANTIC_BACKFILL — completar leitura simples de entidades existentes
Preenche só o que está vazio (use `"overwrite": true` para corrigir). Serve para testes, hipóteses, lições e campanhas públicas. Para campanhas, use `entity_kind: "campaign"` mais o `roadmap_id`; o Writer atualiza o documento da campanha sem substituir a pergunta científica original. `title` recebe o nome curto em português mostrado ao público.
```json
{"items": [
  {"id": "DDEUDS26-001-EFFECTIVE-WZ",
   "semantic": {"question_plain": "A energia escura muda com o tempo?", "why_it_matters": "...",
                "result_meaning": "2–3 frases simples", "verdict_plain": "Inconclusivo", "confidence_plain": "média",
                "topic_id": "science.cosmology.dark_energy.equation_of_state"}},
  {"id": "CAMP-DARK-ENERGY-NATURE-20260923", "entity_kind": "campaign", "roadmap_id": "RM-DARK-ENERGY-NATURE-20260923-V1",
   "title": "Natureza da energia escura", "overwrite": true,
   "semantic": {"question_plain": "A expansão acelerada recente é compatível com uma constante cosmológica?", "why_it_matters": "..."}},
  {"id": "T-OLYCAUSE-016A", "subject_code": "MIQ", "semantic": {"question_plain": "..."}}
]}
```
Toda campanha pública precisa de `title`, `question_plain` e `why_it_matters`. Todo teste precisa de `question_plain` e `why_it_matters`; todo teste concluído precisa de `result_meaning` e `verdict_plain`.
Enquanto faltar, o site mostra uma leitura automática marcada como provisória.

Para saneamento de privacidade, cada item de `SEMANTIC_BACKFILL` também pode usar `{id, entity_kind, subject_code, redact_names:[...]}`. O Writer substitui cada nome listado pelo `subject_code` em campos de texto livre da entidade (incluindo `title`, `display_name`, `source_ref/source_refs` e justificativas), preservando `id`, campos `*_id`/`*_ids`, `entity_version` e o próprio `subject_code`.

## Olympus (pessoas reais)
Nunca escreva o nome de uma pessoa em ids, títulos ou textos públicos. Cada pessoa tem um `subject_code`
de 3 letras (ex.: `MIQ`, `JOS`) em todo teste/campanha Olympus. O site mostra só o código; a projeção
reescreve ids de campanha que contenham nomes (`CAMP-OLY-<código>-<hash>`). Novas campanhas: `CAMP-OLY-<código>-<tema>-<data>`.

## Nenhum teste flutuando
Todo teste pertence a um roadmap. `HYPOTHESIS_PROPOSAL` sem `roadmap_id` é ligada automaticamente ao roadmap ACTIVE
da mesma subárea (senão, do mesmo domínio). Para ligar testes que já existem: `ROADMAP_ATTACH`
`{"items": [{"test_id": "...", "roadmap_id": "opcional"}]}`.

## CHECKPOINTED (em espera)
A cada pulso o Executor revisa até 3 testes CHECKPOINTED (os mais antigos primeiro):
1. o input que faltava agora existe → retome e grave o resultado (MUTATION_PROPOSAL);
2. o resultado já existe em `runtime/results`/artifacts → grave-o (MUTATION_PROPOSAL);
3. o input é inalcançável com dados públicos → MUTATION_PROPOSAL com `result.verdict: "BLOCKED_INPUT"` e o motivo
   em `semantic.result_meaning`; o teste sai da fila de retomada (status BLOCKED_INPUT) e continua visível.
Nunca marque CHECKPOINTED como READY nem invente o input.

## DATA_BINDING — dado ligado para destravar teste (skill nexo-data-hydration)
```json
{"test_id": "T-...", "inputs": [{"name": "...", "url": "https://...", "version": "release ou commit imutável", "sha256": "...", "format": "...",
  "load": "como carregar", "checked": "valor conferido contra o paper", "license": "public"}],
 "status": "BOUND|PARTIAL|UNAVAILABLE", "note": "português simples"}
```
O Writer materializa a ligação no próprio TEST, revalida readiness e mantém a identidade científica.
BOUND exige nome, URL HTTPS, versão e SHA256; input gerado exige generator, seed e SHA256.
Artifacts históricos são fontes candidatas, não substituem a ligação atual. A receita/runner deve
validar os bytes que realmente consome: manifesto válido sozinho não demonstra fidelidade da execução.

Propostas sem mudança recebem artifact `*_NOOP` com `_noop_reason` explícito. Duplicata legítima e
ausência de pensamento fundamentado são distintos de contrato inválido (`UNAPPLIED_*`). Uma
contestação já existente bloqueada deve ser recuperada, sem reenviar ataque para o mesmo slot.

## Escrita barrada pelo runtime
Se GitHub e Doc forem recusados, imprima o envelope no relatório entre `NEXO_PENDING_PROPOSAL` e
`END_NEXO_PENDING_PROPOSAL`. A próxima execução da mesma tarefa reenvia antes do trabalho novo.

## Closed loop (writer ≥ 2026-09-25; skill `nexo-closed-loop`)

Run `python nexo_gpt_writer.py status <tower>` first: Dener's gate, referee queues, charter progress with
`stop_reached`, genome (canonical/canary), decoys and `arm_for_this_run`.

| Kind | Payload | Effect |
|---|---|---|
| `BATCH` | `items: [envelopes]` | each envelope applied on its own |
| `ROADMAP_CHARTER` | roadmap_id?, `title` (curto, em português), question, `semantic{question_plain,why_it_matters}`, scope, data, budget{max_tests,max_days}, stop{success_confirmed,kill_consecutive_refuted}, rationale, refs, rival_of? | `roadmaps/<id>.json` charter PROPOSED (new roadmap if absent), com leitura pública em português |
| `OPERATOR_INTENT` `action: APPROVE_CHARTER\|REJECT_CHARTER\|CANONIZE\|REJECT_CANARY`, `source: "DENER"` | roadmap_id / gene | the two gates; any other source is only recorded |
| `ROADMAP_CLOSE` | roadmap_id, reason SUCCESS\|KILL\|BUDGET, final_report | charter CLOSED, index state CLOSED |
| `CONTEST` | test_id, reason, refs, source REFEREE_1\|SENTINEL, contest_test{frozen hypothesis} | somente teste original pode ser atacado; profundidade máxima 1; resultado do ataque fecha o original mecanicamente |
| `VERDICT_REVIEW` | legado; não é necessário para fechar contestação nova | o Writer usa o critério congelado do ataque e fecha CONFIRMED / REFUTED mecanicamente |
| `GENOME_MUTATION` | gene, value, current_value, rationale, refs, metric (`seed:true` = generation 0) | gene CANARY; spine genes are no-ops |
| `GENOME_ROLLBACK` | gene, reason, fitness | canary dropped |
| `FITNESS_REPORT` | measurements[{gene?, arm, value, components}] | `evolution/genome.json` fitness |
| `NEXO_THOUGHT` | entries[{kind, text, refs[]}] | Pítia's diary (entries without refs dropped) |
| `DECOY_PLANT` / `DECOY_REVEAL` | commitment sha256("test_id:secret") / test_id, secret | decoy audit |

New TESTs require `display_name` (até 8 palavras, português, sem sigla) and `domain`; proposals missing either are rejected before TEST creation. Optional fields: `rank_score`, `rank_rubric`, `origin_kind`, `prior_art`, `prediction`, `contests_test_id`.
READY hypotheses get `prereg_hash` automatically. Positive results start at `review_state: PENDING_REVIEW`.

### Recibo prospectivo da previsão
Ao receber `prediction` em uma mutação de TEST, o Writer cria `prediction_receipt` sob o contrato
`NEXO_PREDICTION_RECEIPT_V1`: hash de TEST + previsão exata, horário real de recebimento e classe
prospectiva ou posterior à reserva/resultado. Esse namespace é independente de `prereg_hash`;
não muda a identidade científica. O remetente não pode fornecer ou corrigir o recibo.

O primeiro recibo e a previsão vinculada são imutáveis; replay idêntico preserva o horário.
Previsão que chega com um resultado importado ou depois da reserva não é prospectiva. Nenhuma
rotina preenche datas dos registros antigos. O resultado público só recebe
`prereg.prediction.recorded_at`, `receipt_contract` e `prediction_hash` quando o hash confere
e, havendo execução datada, o recebimento a antecede. Ausência permanece ausência.
O recibo prova observação canônica pelo Writer, não independência científica nem pré-registro externo.

Charters may be semi-permanent: `renewable: true, review_every_days: N, objectives: [...], priority: "P0"` — never closed by budget; `status` reports `review_due` for a course review by Dener.

## Test batteries (GitHub Actions, public and free)
`TEST_BATTERY {battery_id?, tests:[{test_id, recipe, params, timeout_min<=340, prediction}]}`. Código inline (`script`, `script_b64`) é proibido e rejeitado. `recipe` aponta para receita congelada em `byDenoso/Pantheon nexo-one/executor-runtime/recipes/`; se nenhuma receita reproduzir fielmente o contrato do TEST, emitir `LEARNING_SIGNAL` com `gap_type: RECIPE_REQUEST` e dizer exatamente o que a receita deve fazer. Nenhum READY pode ficar >24 h sem bateria ou RECIPE_REQUEST. Até 20 testes públicos e não-Olympus por bateria.
A recipe escreve `{verdict, decision, summary, statistics, semantic}` em `os.environ["RESULT_PATH"]`. Receita CAMB deve usar o `runtime/portable_camb` versionado do TCC, com commit/proveniência congelados.
The Writer robot marks them RUNNING, dispatches `NEXO test battery` (byDenoso/Pantheon, isolated runners, no secrets),
collects results as `BATTERY_STATUS DONE` and records them like any result; a crash follows the bounded runtime-failure policy.

### Preflight de parâmetros e indisponibilidade operacional
O catálogo pode publicar `recipes/preflight/<recipe>.json` e `recipe_param_preflight.py` sob
`RECIPE_PARAM_PREFLIGHT_V1`. O mesmo validador puro é executado pela admissão e pelo runner;
os hashes exatos do manifesto e do validador entram na reserva e no fingerprint de execução.
A primeira migração obrigatória é `w0wa_bao_sn_multi`; outras receitas mantêm o escopo explícito
de sintaxe/smoke até aderirem com um manifesto validado. O preflight verifica semântica dos
parâmetros e fontes declaradas, não comprova download, ajuste numérico nem resultado científico.

Falha de parâmetros, insumo ou ajuste deve retornar `ok: false`, `result: null`,
`operational_status: INPUT_UNAVAILABLE`, `operational_reason` estruturado e os mesmos
`attempt_id`/`recipe_sha256` da reserva. O Writer registra `BLOCKED_INPUT` com causa persistente;
não cria `executed_at`, estatística ou veredito. O responsável repara a ligação/implementação
e revalida pelo Writer. Seleção incompatível com o release congelado exige revisão científica;
nunca trocar release ou redshifts automaticamente. Reservas históricas não recebem preflight retroativo.
