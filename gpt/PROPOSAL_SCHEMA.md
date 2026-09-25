# NEXO · Formato das propostas do GPT (fonte única)

Todas as tarefas do GPT (Executor, Gaps, Learner) escrevem neste formato. O **NEXO · Writer**
aplica na Tower com `gpt/nexo_gpt_writer.py`, que completa o que faltar, mas quanto mais
completo, melhor fica o site (ATLAS: cards, grafos, aba Aprendizado).

Envelope (um arquivo por proposta). **Caminho principal: `inbox/<nome>.json` no GitHub
byDenoso/TCC branch `nexo-inbox`** (JSON puro, sem o passo "criar Doc e depois colar", que às vezes
deixa o Doc vazio). Reserva: Google Doc em NEXO_INBOX com o JSON no corpo — depois de criar, releia o
Doc; se vier vazio ou com JSON inválido, grave a mesma proposta no GitHub e registre isso no relatório.
O Writer move Docs vazios/inválidos para `NEXO_INBOX/processed/_invalid` (nunca apaga) para não travar a fila.

```json
{"kind": "...", "source": "CHATGPT", "created_at": "2026-09-24T12:00:00Z", "payload": {...}}
```
Nome: `<utc>-<kind>-<slug>`.

## Semântica (obrigatória em tudo que vira teste ou lição)
IDs de `SEMANTIC_TAXONOMY_V1` (runtime/nexo_agent_api/contracts/SEMANTIC_TAXONOMY_V1.json):
```json
"semantic": {
  "domain_id": "science",
  "subdomain_id": "science.cosmology.dark_matter",
  "topic_id": "science.cosmology.dark_matter.nature",
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
  "semantic": {...}
}
```
Com `roadmap_id`, o writer herda campanha/hipótese do roadmap e põe o teste na fronteira.
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

## Sistema de aprendizado (ciclo)
1. **Gaps** (GPT) detecta lacunas nas conversas → LEARNING_SIGNAL.
2. **Writer** grava os sinais na Tower.
3. **Learner** (GPT, diário) lê os sinais na Tower (artifacts `LEARNING_SIGNAL::*` e o que já existe em `lesson`),
   agrega por `topic_id` (≥2 sinais ou 1 com confiança ≥0,8), prioriza o que destrava testes ativos e emite
   LESSON_PROPOSAL (e a mini-aula no chat).
4. **Writer** grava a lição → ATLAS atualiza sozinho.

## Linha de montagem (papel único por tarefa)
| Tarefa | Grava só | Lê |
|---|---|---|
| Gaps (diária) | LEARNING_SIGNAL `evidence_kind: PARAPHRASE` | conversas |
| Learner autônomo (diária) | HYPOTHESIS_PROPOSAL (+ teste META-*), MUTATION_PROPOSAL das próprias hipóteses, LESSON_PROPOSAL, LEARNING_SIGNAL `RUNTIME_CHANGE_PROPOSAL` | resultados, sinais, INTEGRITY_REPORT |
| Executor (horária) | MUTATION_PROPOSAL, LEARNING_SIGNAL `RUNTIME_FAILURE` | `frontier` |
| Writer (horária) | a Tower (dono único) | inbox |
| Guardião (diária 06:00) | INTEGRITY_REPORT, LEARNING_SIGNAL `INTEGRITY` | tudo (só audita) |

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
Preenche só o que está vazio (use `"overwrite": true` para corrigir). Serve para testes, hipóteses e lições.
```json
{"items": [
  {"id": "DDEUDS26-001-EFFECTIVE-WZ",
   "semantic": {"question_plain": "A energia escura muda com o tempo?", "why_it_matters": "...",
                "result_meaning": "2–3 frases simples", "verdict_plain": "Inconclusivo", "confidence_plain": "média",
                "topic_id": "science.cosmology.dark_energy.equation_of_state"}},
  {"id": "T-OLYCAUSE-016A", "subject_code": "MIQ", "semantic": {"question_plain": "..."}}
]}
```
Todo teste precisa de `question_plain` e `why_it_matters`; todo teste concluído precisa de `result_meaning` e `verdict_plain`.
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
{"test_id": "T-...", "inputs": [{"name": "...", "url": "https://...", "sha256": "...", "format": "...",
  "load": "como carregar", "checked": "valor conferido contra o paper", "license": "public"}],
 "status": "BOUND|PARTIAL|UNAVAILABLE", "note": "português simples"}
```
Vira `artifact DATA_BINDING::*`. O Executor lê antes de retomar um CHECKPOINTED.

## Escrita barrada pelo runtime
Se GitHub e Doc forem recusados, imprima o envelope no relatório entre `NEXO_PENDING_PROPOSAL` e
`END_NEXO_PENDING_PROPOSAL`. A próxima execução da mesma tarefa reenvia antes do trabalho novo.

## Closed loop (writer ≥ 2026-09-25; skill `nexo-closed-loop`)

Run `python nexo_gpt_writer.py status <tower>` first: Dener's gate, referee queues, charter progress with
`stop_reached`, genome (canonical/canary), decoys and `arm_for_this_run`.

| Kind | Payload | Effect |
|---|---|---|
| `BATCH` | `items: [envelopes]` | each envelope applied on its own |
| `ROADMAP_CHARTER` | roadmap_id?, title, question, scope, data, budget{max_tests,max_days}, stop{success_confirmed,kill_consecutive_refuted}, rationale, refs, rival_of? | `roadmaps/<id>.json` charter PROPOSED (new roadmap if absent) |
| `OPERATOR_INTENT` `action: APPROVE_CHARTER\|REJECT_CHARTER\|CANONIZE\|REJECT_CANARY`, `source: "DENER"` | roadmap_id / gene | the two gates; any other source is only recorded |
| `ROADMAP_CLOSE` | roadmap_id, reason SUCCESS\|KILL\|BUDGET, final_report | charter CLOSED, index state CLOSED |
| `CONTEST` | test_id, reason, refs, source REFEREE_1\|SENTINEL, contest_test{frozen hypothesis} | test `review_state: CONTESTED` (max 2) + contest test P0 |
| `VERDICT_REVIEW` | test_id, referee 1\|2, outcome SURVIVED\|REFUTED, evidence | ladder → REFEREE1_PASSED → CONFIRMED / REFUTED |
| `GENOME_MUTATION` | gene, value, current_value, rationale, refs, metric (`seed:true` = generation 0) | gene CANARY; spine genes are no-ops |
| `GENOME_ROLLBACK` | gene, reason, fitness | canary dropped |
| `FITNESS_REPORT` | measurements[{gene?, arm, value, components}] | `evolution/genome.json` fitness |
| `NEXO_THOUGHT` | entries[{kind, text, refs[]}] | Pítia's diary (entries without refs dropped) |
| `DECOY_PLANT` / `DECOY_REVEAL` | commitment sha256("test_id:secret") / test_id, secret | decoy audit |

New optional test fields: `rank_score`, `rank_rubric`, `origin_kind`, `prior_art`, `prediction`, `contests_test_id`.
READY hypotheses get `prereg_hash` automatically. Positive results start at `review_state: PENDING_REVIEW`.

Charters may be semi-permanent: `renewable: true, review_every_days: N, objectives: [...], priority: "P0"` — never closed by budget; `status` reports `review_due` for a course review by Dener.

## Test batteries (GitHub Actions, public and free)
`TEST_BATTERY {battery_id?, tests:[{test_id, script, requirements[], timeout_min<=340, prediction}]}` — up to 20 registered, non-Olympus tests.
Each script is self-contained and writes `{verdict, decision, summary, statistics, semantic}` to `os.environ["RESULT_PATH"]`.
The Writer robot marks them RUNNING, dispatches `NEXO test battery` (byDenoso/Pantheon, isolated runners, no secrets),
collects results as `BATTERY_STATUS DONE` and records them like any result; a crash sends the test back to READY.
