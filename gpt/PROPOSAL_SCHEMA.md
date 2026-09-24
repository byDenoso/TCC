# NEXO · Formato das propostas do GPT (fonte única)

Todas as tarefas do GPT (Executor, Gaps, Learner) escrevem neste formato. O **NEXO · Writer**
aplica na Tower com `gpt/nexo_gpt_writer.py`, que completa o que faltar, mas quanto mais
completo, melhor fica o site (ATLAS: cards, grafos, aba Aprendizado).

Envelope (um arquivo por proposta; Google Doc em NEXO_INBOX com o JSON no corpo, ou
`inbox/<nome>.json` no GitHub byDenoso/TCC branch `nexo-inbox`):

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
