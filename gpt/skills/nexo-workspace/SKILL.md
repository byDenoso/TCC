---
name: nexo-workspace
description: Operar a conversa do Dener como interface da Tower e das dez automações NEXO ativas. Usar para status, ideias e testes científicos, resultados antigos, investigação de falhas, comparação com literatura, manutenção e verificação de automações. Reutilizar GitHub, Drive, Writer e projeção; preservar critérios científicos e verificar cada afirmação de conclusão.
---

# Workspace operacional do NEXO

## Inicialização
Ler a raiz e a interface atuais, salvo se já lidas nesta conversa:
- https://raw.githubusercontent.com/byDenoso/TCC/main/gpt/skills/nexo-master-router-0.5.0.md
- https://raw.githubusercontent.com/byDenoso/TCC/main/gpt/skills/nexo-lite-0.5.0.md

Usar a intenção da mensagem; não apresentar menus. Abrir somente as fontes exigidas pelo pedido. Reutilizar leituras quando a revisão não mudou. Consultar `NEXO Lite/pendentes` e o mural para devolver resultados ao Dener, sem interromper assuntos alheios ao NEXO com ruído operacional.

## Autoridade por assunto
- Ciência: Tower, entidades e evidências; projeção como leitura derivada.
- Agenda e tarefas habilitadas: inventário vivo da ferramenta de automações. O workspace mantém dez automações ativas por limite do plano; `Bom dia` foi incorporado ao Guardião e pausado para abrir o slot do Operador C. Campos antigos com quatro bindings ou cinco tarefas não substituem esse inventário.
- Caminho operacional: raiz atual, prompts salvos, código implantado e recibos de execução. Divergência com CONTROL histórico deve ser explicitada, sem trocar de arquitetura por conta própria.
- Literatura: `cosmology-world-model` no Drive, com data da referência; confirmar valores atuais em fontes primárias antes de congelar critérios. O mapa orienta e não produz vereditos.
- Memória: contexto operacional em `NEXO Lite/notas`, nunca fonte de resultado científico.

## Roteamento da conversa
| Pedido | Ler e executar | Entregar |
|---|---|---|
| status; o que saiu; o que importa | projeção, revisão/data, mural e pendentes | novidades verificadas, bloqueio e decisão humana |
| investiga; por que falhou; por que deu nulo | teste, hipótese, contrato, receita, dados, execução, resultado e revisão | cadeia de evidência e lacunas; separar falha técnica de nulo científico |
| testa esta ideia | mapa, busca de duplicatas, receitas e schema | Diretriz DENER_DIRECTED P0 com pergunta testável, nula, rival e critérios congelados |
| acha o resultado antigo | referências históricas da Tower e origem do resultado | resultado datado, alcance e relação com o atual, sem reabrir teste cancelado |
| compara com literatura; modelo do Universo | mapa datado, artigos primários, terminais auditáveis e campanhas abertas | síntese separando literatura, resultado NEXO e hipótese |
| confere automação; arruma | prompt/agenda, execução, entrada, saída, recibo e consumidor | correção mínima autorizada, teste e estado real |

## Leitura das fontes
Ler a projeção em https://bydenoso.github.io/Pantheon/tower-projection/projection.json . Se a ferramenta não abrir, ler o arquivo canônico via Drive; erro de acesso não prova fila vazia. A Tower é o arquivo JSON `1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z`, não uma pasta. Confirmar metadados antes de baixar.

Para análise local, usar a cópia autenticada e o bundle utilizado pelo workflow `byDenoso/Pantheon@main:.github/workflows/nexo-writer-robot.yml`. Inspecionar antes de executar. Rodar somente leituras como `verify`, `status` e `frontier` na cópia local. Conferir stderr e seções esperadas: saída zero com mensagem `skipped` é leitura degradada. Identificar projeção reconstruída como local, sem alegar publicação.

Localizar no Drive as pastas `cosmology-world-model`, `nexo-reporting` e `NEXO Lite`; ler a identidade do SKILL.md antes de usar. Preservar pastas existentes. Pesquisar histórico por referências, não por semelhança de nomes apenas.

## Gravação e acompanhamento
Ler `nexo-operations` e `gpt/PROPOSAL_SCHEMA.md`. Preservar o fluxo atual:
`byDenoso/TCC@nexo/dispatch-runtime:nexo_persist/requests/<stable_id>.json` -> relay -> `nexo-inbox` -> Writer -> Tower -> projeção.

Usar stable_id determinístico em `[a-z0-9-]`, com até 60 caracteres; reutilizar no retry. Conferir fila e recibos antes de repetir. Conteúdo diferente com a mesma identidade é conflito. Releitura do staging prova somente staging; confirmar separadamente relay e aplicação.

Enviar pelo Git público somente propostas sanitizadas permitidas. Manter dados privados, notas pessoais, handoffs privados e transcrições no Drive privado. Não gravar Tower diretamente. Em recusa de autorização, acesso ou política, interromper a ação e relatar; não contornar trocando formato ou serviço. Retentar apenas falhas técnicas pelos caminhos autorizados.

Registrar Diretriz aceita em `NEXO Lite/pendentes`, com ID estável, objetivo, referência da proposta, estado comprovado e próxima verificação. Não prometer data de resultado sem evidência. Memória nativa indisponível não impede a nota operacional autorizada no Drive.

## Dez automações ativas: pipeline horário
O plano permite dez automações ativas. Preservar função antes de preservar cartões separados: o resumo `Bom dia` foi incorporado ao Guardião na rodada das 07:07, e o cartão antigo permanece pausado. O slot liberado pertence ao Operador C.

O Writer externo pulsa a cada 15 minutos em BRT: `:04`, `:19`, `:34`, `:49`. Posicionar produtores e consumidores ao redor desses pulsos para reduzir latência.

| Tarefa | Gatilho BRT | Entrada -> saída | Próximo consumidor |
|---|---|---|---|
| Operador C | :00, toda hora | READY residual após A/B -> despacho/bindings | Writer :04 |
| Engenheiro | :05, toda hora | RECIPE_REQUEST/circuitos -> PR e smoke | Revisor e Operadores |
| Guardião | :07, toda hora | saúde, SLA A/B/C, Writer e travas -> integridade/reatribuição | papéis; às 07:07 também resumo diário ao Dener |
| Crítico | :09, toda hora | positivos novos -> até 20 contestações independentes | Writer :19 e Operadores |
| Cientista | :12, toda hora | quedas, diretrizes e lacunas -> READY realmente executável | Writer :19 |
| Pítia | :15, toda hora | resultados e roadmaps -> pensamentos com refs | Writer :19, Cientista e Dener |
| Operador A | :30, toda hora | primeiro segmento READY elegível -> até 12 despachos | Writer :34 |
| Operador B | :45, toda hora | segmento restante READY elegível -> até 12 despachos | Writer :49 |
| Sentinela | 06:40 diário | literatura/releases -> contestação, dado ou sinal | Writer :49; Cientista/Operadores |
| Revisor de PR | evento de PR | diff de receita -> revisão e sinal | autor e Dener |

### Invariante READY
`READY` significa executável agora, não “quase pronto”. Exigir definição científica congelada e suficiente, dados/entradas canônicos disponíveis e vinculados, recipe/capability executável, ausência de blocker ou `WAIT_DEPENDENCY`, identidade estável e nenhuma execução equivalente staged/RUNNING/terminal. Se faltar qualquer requisito, corrigir pelo fluxo autorizado para `CHECKPOINTED` ou `WAIT_DEPENDENCY` e criar o binding/reparo; não contar como despacho.

### Consumir recuperação e aceite privado

No início da rodada, carregar o `status` da Tower privada e ler `execution_recovery`, além do
mural. A projeção pública não publica ofertas/aceites. Com o bundle atual, consultar
`python nexo_gpt_writer.py handoff TOWER.json list PAPEL`; use o papel canônico abaixo apenas
para essa caixa privada, mantendo o `source` normal nas demais propostas:

- Engenheiro: `ADVISOR`, triagem e receita/verificação técnica
- Cientista: `LEARNER`, definição congelada e conflitos de linhagem
- Operadores A/B/C: `EXECUTOR`, insumos/proveniência e execução; reler antes de aceitar para não duplicar
- Guardião: verifica oferta pendente, idade, responsável e readback; não aceita em nome de outro papel

Ao assumir uma WORK, enviar `HANDOFF_ACK` com `writer_role` igual ao destinatário canônico pelo
Drive privado NEXO_INBOX conforme PROPOSAL_SCHEMA. Reler a aplicação: só o aceite aplicado muda
ownership. Proposta gravada, comentário no mural e atribuição ADVISOR não são aceite. Se faltarem
ferramentas para ler ou escrever o canal privado, registrar a capacidade ausente sem publicar o
handoff no GitHub, simular ACK ou retirar a responsabilidade anterior.

Tratar primeiro recuperações e revisões que destravam o roadmap ativo, respeitando direção
explícita de Dener. Não criar novos testes para contornar dependência existente. A WORK termina
quando o Writer revalida elegibilidade; sucesso de software não altera resultado científico.
Antes de despachar, confirmar que receita e runner consomem os inputs versionados/hash do binding
e implementam os parâmetros congelados. URL mutável ou parâmetro ignorado exige reparo, mesmo
quando o manifesto formal foi aceito.

### Motivo de inatividade e continuidade
`*_NOOP` é uma resposta de proposta específica, não prova de que a automação inteira não trabalhou.
O Writer grava `_noop_reason`: mensagem já registrada, pensamento sem entrada fundamentada,
família já registrada ou contestação existente que precisa terminar. Contrato inválido vira
`UNAPPLIED` com `_not_applied_reason`; não tratar erro de leitura/transporte como fila vazia.
`review_queue.waiting_on_existing_contest` aponta originais cuja contestação já ocupa o slot;
destrave o ataque existente pelo dono, sem reenviar CONTEST que será recusado.
Sem ferramentas para o canal privado, use `PRIVATE_CHANNEL_UNAVAILABLE` e preserve a oferta
pendente. NO-OP da rodada exige leitura válida e ausência de ação executável ou recuperação que
o papel possa realizar; não gere recado, hipótese ou resultado só para eliminar o rótulo.

Enquanto houver READY elegível no segmento de um Operador e capacidade na rodada, NO-OP é inválido. A processa o início/mais antigo, B o fim/mais novo restante e C faz sweep residual após A/B; todos relêem staging/Tower antes de gravar. Guardião trata zero processamento com READY elegível como falha operacional e ausência de aplicação após dois pulsos do Writer como falha de pipeline.

Tratar essa tabela como mapa de integração, não como substituto do inventário vivo. Confirmar agenda viva antes de alterar. A janela silenciosa suspende notificações, nunca a execução. Proteger o Revisor: não substituir evento por polling. `last_run_time` prova execução da tarefa, não aplicação científica.

Ler mural e propostas pendentes para evitar duplicatas. Atraso ou falha de leitura produz diagnóstico; NO-OP somente com leitura válida e ausência de trabalho. Contestações precedem testes novos. Metas de vazão não autorizam inventar testes ou dados.

## Critério de entrega
Distinguir: configurado, proposto, entregue ao inbox, aplicado, executado, revisado e confirmado. Nulo científico exige execução válida. PASS de software permanece operacional. Preservar critérios congelados, multiplicidade, independência da contestação e limites do claim.

Reproduzir falhas, fazer a menor mudança, testar e reler. Informar como desfazer mudanças relevantes. Não criar tickets ou documentos intermediários por padrão. Uma instrução no Git alcança os consumidores que a carregam; não afirmar instalação de plugin, alteração administrativa global ou memória nativa sem confirmação da ferramenta.

## Leitor de status verificável
Para ler a cópia autenticada da Tower, executar `python scripts/status_reader.py TOWER.json nexo_gpt_writer.py`, em processo separado. Obter o script desta skill pelo GitHub conectado se ele não estiver montado. Obter o bundle pelo arquivo Drive usado no workflow do Writer; conferir os bytes antes de executar.

O leitor verifica a integridade e tenta o status nativo. Somente na versão auditada, quando a colisão entre duas funções `_stamp` derruba `review_queue`, isola o formatador original da fila e repete a leitura. Preserva os filtros do Writer, os IDs e o arquivo de entrada. Não altera o bundle implantado nem a Tower. `OK_LOCAL_REVIEW_CLOCK_REPAIR` identifica a correção local; `DEGRADED` e `FAILED` nunca significam fila vazia. Informar qualquer aviso restante e nunca apresentar esta saída como projeção publicada.
