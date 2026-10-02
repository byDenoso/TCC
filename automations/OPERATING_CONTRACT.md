# NEXO — contrato operacional das automações

As regras científicas, de privacidade e de readback valem para todos os papéis.
Os comandos locais de escrita deste documento pertencem ao adapter Claude Code/PC
com Writer autorizado. As dez ChatGPT Tasks usam a rota descrita em
**Limite do runtime ChatGPT Tasks**, conforme `nexo-master-router-0.5.0` e
`gpt/skills/nexo-workspace/SKILL.md`; não recebem autorização para escrever a Tower
ou trocar essa rota por um inbox direto.

## Verdade e escrita

- Truth Owner: `NEXO_TOWER_LIVE.json` no Drive (file id `1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z`).
- No adapter local Claude Code/PC, o caminho de escrita autorizado é
  `python scripts/nexo_tower.py apply <request.json>` neste repositório.
  Ele faz lock → leitura → mutação → releitura do head → escrita no mesmo file id → readback, e avisa o ATLAS.
- Nas ChatGPT Tasks, gravar o envelope pelo transporte aprovado e deixar a aplicação
  canônica para o Writer existente. Os comandos locais abaixo não ampliam esse escopo.
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

## Resolução de especificação científica por ancestralidade

Antes de declarar `SCIENTIFIC_DEFINITION_MISSING`, resolva primeiro a especificação já congelada na linhagem canônica: TEST → HYPOTHESIS/WORK originário → roadmap/campanha → refs/parent/predecessor → TESTs ancestrais → RESULT/CHECKPOINT/DATA_BINDING → prior_art/artefatos. Reutilize somente definições já congeladas cuja ligação ao TEST atual seja inequívoca, incluindo estimand/observable, null/rival, seleção, dados/versão, janela/domínio, método/estatística, parâmetros/priors, prediction e success/kill/decision rule.

Se a ancestralidade resolver univocamente a definição, registre as refs de proveniência, valide que o contrato científico não mudou e prossiga com o MESMO TEST_ID. Se houver definições ancestrais materialmente incompatíveis sem desambiguação canônica, não escolha a mais conveniente: aí sim `SCIENTIFIC_DEFINITION_MISSING` é legítimo e deve voltar ao Learner. Nunca use o resultado observado para escolher retrospectivamente qual definição aplicar.

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

### Recuperação executável e responsabilidade

O Writer mantém `EXECUTION_RECOVERY_V1` sobre os TESTs públicos em preparação: revalida a
elegibilidade, preserva o desenho científico e cria uma única WORK de recuperação por identidade
congelada. O estado `BLOCKED_INPUT` informa que a execução ainda não está liberada; a WORK contém
o que precisa ser recuperado, as fontes candidatas e a próxima ação, para não transformar a fila
em um conjunto de avisos sem continuidade.

- Consulte `status.execution_recovery` e a caixa privada de handoffs no início da rodada
- Preserve o responsável já registrado no TEST ou WORK associada. Sem responsável inequívoco,
  ADVISOR recebe a triagem; isso não representa aceite nem atribuição a Dener
- A triagem encaminha definição congelada ausente/conflitante a LEARNER, receita/verificação
  técnica a ADVISOR e recuperação de insumos a EXECUTOR. A engenharia nunca escolhe um novo
  dataset, estimand, prior ou critério científico para liberar um teste
- O handoff privado `BLOCKER_RECOVERY` é uma oferta. Até o destinatário enviar ACK, o responsável
  anterior continua responsável. ACK muda ownership por CAS e registra a origem do aceite
- Uma mudança de etapa pode abrir nova oferta, mas nunca troca silenciosamente o dono. FAILED
  deixa o dono registrado e exige uma decisão material antes de repetir a mesma rota
- DONE requer condições executáveis novamente verificadas. Se o Writer recuperar essas condições
  antes do aceite, ele encerra a oferta como SUPERSEDED, sem fabricar ACK ou resultado científico
- Um artifact histórico BOUND não basta. Reuso automático exige inputs com versão/hash, vínculo
  inequívoco à pré-inscrição congelada e ausência de candidatos incompatíveis; demais fontes são
  preservadas como candidatas para resolução pelo responsável

Na fila de baterias, a direção explícita de Dener prevalece; depois vêm roadmap ativo, prioridade
do roadmap e do teste e valor informativo. O nome alfabético da receita não define prioridade.
Contestações de resultados anteriores podem concluir revisão após o fechamento do roadmap sem
reabrir a campanha nem criar novas famílias automaticamente.

## Conclusão de um teste

Só conta com cômputo real + persistência pela Tower + readback. Preflight, download e reparo não são resultado.
PASS de software nunca promove claim científico. Identidade científica congelada é preservada; ciência
materialmente diferente exige nova identidade TEST.

## Relato

Termine cada execução com um relatório curto em português: o que rodou, o que mudou na Tower
(fingerprint antes/depois), estado do ATLAS (`status`), e o próximo passo que a próxima execução vai pegar.

## Limite do runtime ChatGPT Tasks

As dez Tasks carregam `gpt/skills/nexo-master-router-0.5.0.md` e
`gpt/skills/nexo-workspace/SKILL.md`. Para propostas públicas sanitizadas, a rota vigente é:

`byDenoso/TCC@nexo/dispatch-runtime:nexo_persist/requests/<stable_id>.json`
→ relay → `byDenoso/TCC@nexo-inbox:inbox/` → Writer → Tower privada → projeção.

- O arquivo de staging contém `{"stable_id": "...", "envelope": {...}}`.
  Usar stable_id determinístico em `[a-z0-9-]`, até 60 caracteres, e reutilizar
  identidade e bytes exatos no retry. Aplicam-se `gpt/PROPOSAL_SCHEMA.md` e os recibos
  do Writer; payload diferente com a mesma identidade é conflito.
- Releitura exata de `nexo_persist/requests` confirma apenas STAGED. Confirmar
  separadamente entrega pelo relay e aplicação pelo Writer: esta exige recibo
  `OPERATION_RECEIPT_V1` com hash correspondente e outcome `APPLIED` ou
  `ALREADY_APPLIED`; ack do relay comprova apenas entrega. STAGED_PENDING_RELAY é diagnóstico válido quando staging
  foi confirmado e a entrega ainda não tem prova; não chamar isso de aplicação.
- `nexo-inbox/inbox` é destino do relay nesta rota, não uma alternativa de gravação
  direta para as Tasks. Uma recusa de autorização/acesso/política não autoriza trocar
  branch, formato, serviço ou abrir issue para contorná-la. Registrar bloqueio e
  manter a operação pendente; só falhas técnicas podem ser retentadas pelo caminho
  já autorizado, depois de consultar acked e receipts com hash exato.
- Handoffs e outras mensagens privadas explicitamente autorizadas usam
  `NEXO_INBOX` da Drive com releitura exata. Uma proposta pública que não possa ser
  sanitizada sem perder significado permanece pendente; não criar um fallback
  privado genérico sem autorização específica do router para essa operação.
  Nunca publicar conteúdo confidencial no GitHub. Persistência no inbox nunca
  significa aplicação na Tower.
- **Proposal científica e handoff têm semânticas diferentes.** Nas Tasks, os
  envelopes `HANDOFF` e `HANDOFF_TRANSITION` (aliases `HANDOFF_ACK`, `HANDOFF_DONE`,
  `HANDOFF_FAILED`) são documentos JSON privados no Drive `NEXO_INBOX`, conforme
  `gpt/PROPOSAL_SCHEMA.md`. O converter validado e o Writer persistem o evento
  dirigido na Tower com controle de versão e readback; gravar o documento não
  comprova ACK/DONE. Nunca colocar esses envelopes no staging público.
- A Task pode ler sua caixa privada com o bundle:
  `python nexo_gpt_writer.py handoff TOWER.json list PAPEL`. Sem canal privado
  autorizado ou readback, declarar o canal privado indisponível, manter owner
  e oferta anteriores e não simular ACK nem aceitar em nome de outro destinatário.
- A aplicação canônica continua no Writer existente. Não usar `scripts/nexo_tower.py
  apply/handoff`, upload direto da Tower, sediment/TXT bridge, `inbox done` ou edição
  manual de `tower-head.json` para promover uma simulação local a estado canônico.

## Inboxes consumidos por adapters locais e pelo Writer

O leitor local `python scripts/nexo_tower.py inbox list` também conhece o inbox
GitHub `nexo-inbox/inbox/`, a pasta Drive `NEXO_INBOX` e issues legadas
`[NEXO_INBOX]`/`nexo-proposal`. Essa capacidade de leitura não cria uma ordem de
fallback para as dez Tasks. Os adapters que já têm autorização específica para
esses canais continuam sujeitos a privacidade, versão, CAS e readback; nenhuma
Task recebe nova autorização por carregar este documento.

O Writer aplica as operações admitidas e reconhece sua aplicação. Leitura de
staging, receipt de transporte, fingerprint projetado localmente e coincidência
de fingerprints de dados não comprovam escrita na Tower nem publicação de uma
nova revisão de código. Não existe upload bridge ativo para as ChatGPT Tasks.
