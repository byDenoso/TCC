# Automação C — Learner do Dener

Objetivo: perceber, pelo jeito que o Dener conversa, onde falta base de conhecimento, e ensinar de forma
intuitiva — ligado ao mesmo grafo semântico dos testes, para que cada lição apareça no ATLAS (aba Learning)
perto dos testes que a motivaram.

Leia primeiro `automations/OPERATING_CONTRACT.md`.

## Fontes de sinal (só estas)

1. `python scripts/nexo_tower.py inbox list` → itens `LEARNING_SIGNAL` criados pelo ChatGPT:
   `{topic_id, evidence, evidence_kind: QUOTE|PARAPHRASE, gap_type: CONCEPT|MATH|METHOD|TOOL|INTUITION, confidence, source_ref?}`.
2. Transcrições locais do Claude Code do último dia: `%USERPROFILE%/.claude/projects/*/*.jsonl`
   (apenas mensagens do usuário). Extraia sinais você mesmo no mesmo formato.

`confidence` = confiança de que a lacuna existe, não nota do Dener. Uma pergunta isolada não é lacuna;
agregue por `topic_id` e só gere lição com ≥2 sinais ou 1 sinal de confiança ≥ 0.8. Ausência de evidência nunca é lacuna.
Nunca copie trechos pessoais/sensíveis para a Tower: parafraseie.

## Lição

Para cada tópico elegível, crie ou atualize `entity_kind: lesson`, id `LESSON::<topic_id>`:

```json
{
  "title": "...",
  "status": "ACTIVE",
  "semantic": {"domain_id": "...", "subdomain_id": "...", "topic_id": "..."},
  "gap_type": "CONCEPT",
  "intuition": "1 parágrafo: a ideia com uma imagem mental/analogia física",
  "explanation": "o mínimo formal necessário, com 1 equação se ajudar",
  "exercise": "1 pergunta curta que o Dener consegue responder em 2 min, com a resposta escondida no fim",
  "source_signal_count": 3,
  "linked_test_ids": ["testes da Tower no mesmo topic_id"],
  "updated_at": "<utc>"
}
```

Tom: professor bom e direto, português, sem condescendência. Priorize o que destrava os testes ativos do roadmap.
Depois de consumir sinais do inbox: `inbox done <ids>`.

## Relatório

Contrato + tópicos com lição nova/atualizada e por quê.
