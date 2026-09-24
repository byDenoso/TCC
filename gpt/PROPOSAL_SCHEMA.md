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

## Olympus (pessoas reais)
Nunca escreva o nome de uma pessoa em ids, títulos ou textos públicos. Cada pessoa tem um `subject_code`
de 3 letras (ex.: `MIQ`, `JOS`) em todo teste/campanha Olympus. O site mostra só o código; a projeção
reescreve ids de campanha que contenham nomes (`CAMP-OLY-<código>-<hash>`). Novas campanhas: `CAMP-OLY-<código>-<tema>-<data>`.
