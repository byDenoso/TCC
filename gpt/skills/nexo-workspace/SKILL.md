---
name: nexo-workspace
description: Operar a conversa do Dener como interface da Tower e das funções NEXO habilitadas no inventário vivo. Usar para status, ideias e testes científicos, resultados antigos, investigação de falhas, comparação com literatura, manutenção e verificação de automações. Reutilizar GitHub, Drive, Writer e projeção; preservar critérios científicos e verificar cada afirmação de conclusão.
---

# Workspace operacional do NEXO

## Inicialização
Ler a raiz e a interface atuais, salvo se já lidas nesta conversa:
- https://raw.githubusercontent.com/byDenoso/TCC/main/gpt/skills/nexo-master-router-0.5.0.md
- https://raw.githubusercontent.com/byDenoso/TCC/main/gpt/skills/nexo-lite-0.5.0.md

Usar a intenção da mensagem; não apresentar menus. Abrir somente as fontes exigidas pelo pedido. Reutilizar leituras quando a revisão não mudou. Consultar `NEXO Lite/pendentes` e o mural para devolver resultados ao Dener, sem interromper assuntos alheios ao NEXO com ruído operacional.

## Autoridade por assunto
- Ciência: Tower, entidades e evidências; projeção como leitura derivada.
- Agenda e tarefas habilitadas: inventário vivo da ferramenta de automações. A configuração verificada em 03/10/2026 tem Cientista, Engenheiro, Operador, Crítico, Pítia, Guardião e Sentinela. Operadores B/C permanecem pausados com histórico preservado. `Bom dia` pertence ao Guardião. Referências históricas de quantidade, limite do plano e bindings não substituem esse inventário; a integração separada de Revisor de PR por evento só conta como ativa quando comprovada na ferramenta.
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
Carregar `nexo-connectors` antes de operar Google Drive ou GitHub. Busca/snippet e fetch textual degradado nao provam conteudo, ausencia ou versao; usar identidade direta, paginacao, raw fetch/ref pinado e readback conforme o contrato.
Ler a projeção em https://bydenoso.github.io/Pantheon/tower-projection/projection.json . Se a ferramenta não abrir, ler o arquivo canônico via Drive; erro de acesso não prova fila vazia. A Tower é o arquivo JSON `1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z`, não uma pasta. Confirmar metadados antes de baixar.

Para análise local, usar a cópia autenticada e o bundle utilizado pelo workflow `byDenoso/Pantheon@main:.github/workflows/nexo-writer-robot.yml`. Inspecionar antes de executar. Rodar somente leituras como `verify`, `status` e `frontier` na cópia local. Conferir stderr e seções esperadas: saída zero com mensagem `skipped` é leitura degradada. Identificar projeção reconstruída como local, sem alegar publicação.

Localizar no Drive as pastas `cosmology-world-model`, `nexo-reporting` e `NEXO Lite`; ler a identidade do SKILL.md antes de usar. Preservar pastas existentes. Pesquisar histórico por referências, não por semelhança de nomes apenas.

## Gravação e acompanhamento
Antes de escrever, resolva a Tower atual e `CONTROL.json`. Use a superfície de mutação canônica declarada ali, com persistência e readback. Não force `byDenoso/TCC@nexo/dispatch-runtime` quando o CONTROL atual marcar Git state/staging como aposentado ou congelado; referências históricas servem apenas para proveniência.

Para coordenação entre papéis, use BOARD_POST. Para ownership rastreável, HANDOFF somente entre runtime roles suportados conforme a seção seguinte. Na rota privada Drive, prefira upload create-only de **arquivo JSON bruto UTF-8** diretamente no `NEXO_INBOX`, em uma única operação, seguido de readback dos bytes/MIME/parent. Não crie Google Doc vazio e dependa de uma segunda escrita quando upload bruto estiver disponível. Presença no inbox é entrega, não aplicação; releia receipt/Tower antes de retry. Rejeição de segurança/permissão encerra aquela rota; não contorne por serviço alternativo. Staging/proposta, aplicação, execução, resultado e revisão são estados diferentes.

## Funções atuais: pipeline por item

A configuração viva tem sete papéis. Agenda atual verificada:
| Tarefa | Gatilho BRT | Produção mínima por pulso | Próximo consumidor |
|---|---|---|---|
| Pítia | :00, toda hora | 6 TESTs interpretados/priorizados/discriminados | Cientista/Crítico/Operador |
| Cientista | :10, toda hora | 6 TESTs definidos/recuperados + até 24 receitas completas | Engenheiro |
| Engenheiro | :25, toda hora | 6 TESTs com avanço técnico + até 24 receitas certificadas READY_FOR_EXECUTOR | Operador |
| Operador | :40, toda hora | alvo de 6 TESTs executados ou terminais verificáveis | Crítico/Pítia |
| Crítico | :50, toda hora | 6 resultados/TESTs revisados ou contestados | Operador/Pítia/Cientista |
| Guardião | :55, toda hora | 6 cadeias de TEST reparadas/liberadas | todos os papéis |
| Sentinela | :05, a cada 2h | 6 TESTs alimentados com evidência/input material | Cientista/Engenheiro/Crítico |

A meta de 6 mede trabalho material, não volume administrativo. Seeds, retries, shards, downloads, smokes, leituras e duplicatas não são TESTs distintos. Se não houver 6 candidatos válidos, fazer o máximo e provar varredura real das frentes; nunca fabricar ciência para cumprir quota.

A cadência não é barreira global. Cada papel consome entregas já aplicadas, inclusive de rodadas anteriores. Blocker pertence ao item. Se um item trava, registrar/encaminhar e seguir imediatamente para outro.

### Conversa e ownership entre automações
- `BOARD_POST` é o canal de conversa direta entre papéis nomeados: PITIA, LEARNER, EXECUTOR, REFEREE_1, GUARDIAO, ENGINEER, SENTINEL, ADVISOR e demais destinos válidos do schema. Usar refs/reply_to e resolver recados consumidos.
- `HANDOFF` é transferência de ownership e o runtime aceita somente recipient `DAILY|ADVISOR|EXECUTOR|LEARNER|EMERGENT`; sender é um desses ou DIRECTOR. ENGINEER usa ADVISOR no handoff privado.
- PITIA, REFEREE_1, GUARDIAO e SENTINEL não criam handoff com seus nomes. Eles usam BOARD_POST; se ownership precisar mudar, pedem ao runtime role competente para criar/transicionar o HANDOFF.
- Uma entrega com próximo consumidor não termina em prosa: precisa mensagem aplicada e, quando couber, handoff válido.

### Rota operacional atual
Resolver `CONTROL.json` da Tower a cada mudança material. Em 05/10/2026, Drive é armazenamento canônico primário, Git state está aposentado como estado operacional, Actions científico está desabilitado por orçamento e ChatGPT runtime é a execução primária. Não forçar staging/relay Git antigo se o CONTROL vigente não o declarar como rota ativa.

### Invariante READY
`READY` significa executável agora, não “quase pronto”. Exigir definição científica congelada e suficiente, dados/entradas canônicos disponíveis e vinculados, recipe/capability executável, ausência de blocker ou `WAIT_DEPENDENCY`, identidade estável e nenhuma execução equivalente staged/RUNNING/terminal. Se faltar qualquer requisito, corrigir pelo fluxo autorizado para `CHECKPOINTED` ou `WAIT_DEPENDENCY` e criar o binding/reparo; não contar como despacho.

### Consumir recuperação e aceite privado

No início da rodada, carregar o `status` da Tower privada e ler `execution_recovery`, além do
mural. A projeção pública não publica ofertas/aceites. Com o bundle atual, consultar
`python nexo_gpt_writer.py handoff TOWER.json list PAPEL`; use o papel canônico abaixo apenas
para essa caixa privada, mantendo o `source` normal nas demais propostas:

- Engenheiro: `ADVISOR`, triagem e receita/verificação técnica
- Cientista: `LEARNER`, definição congelada e conflitos de linhagem
- Operador: `EXECUTOR`, insumos/proveniência e execução; reler antes de aceitar para não duplicar
- Guardião: verifica oferta pendente, idade, responsável e readback; não aceita em nome de outro papel

A caixa de bootstrap mostra cinco cartões, com `inbox_count` total e `inbox_has_more`; ela não limita a fila operacional. `handoff ... list PAPEL` retorna todas as ofertas abertas válidas do papel. Cruze essa lista com `execution_recovery.items`; ACK antigo não pode esconder oferta pendente. Até o bundle atualizado estar comprovado, use a seção privada completa para identificar os itens omitidos pelo leitor antigo.

Aceite é transferência de ownership; diagnóstico, leitura de fontes, preparação local e reparo de código já autorizado podem avançar antes dele. A operação que depende de assumir a WORK espera o ACK aplicado. Combine preparação e persistência na mesma rodada quando os contratos e o transporte permitirem, sem aguardar o próximo horário de outro papel para uma ação já elegível.

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

### Pipeline de 24 receitas

O Cientista é dono da definição científica da receita. Por pulso, quando houver candidatos válidos, entrega até 24 receitas completas ao Engenheiro. Cada receita deve conter: TEST/roadmap/hipótese, pergunta, inputs e versões/hashes, método, modelo/null/rival, parâmetros e priors, estatística/estimando, critérios de sucesso/kill, implementação/capability alvo, comando/runtime, outputs esperados, schema de artifacts, checkpoint/resume, dependências, custo/runtime esperado, smoke/preflight esperado e proveniência. Receita incompleta não é entregue como pronta.

O Engenheiro é dono da certificação técnica. Para cada receita recebida, implementar ou ligar a capability mínima fiel, conferir inputs, dependências, parâmetros congelados, comando reproduzível, smoke/preflight, artifacts, checkpoint/resume e readback. Só então emitir READY_FOR_EXECUTOR e HANDOFF ADVISOR→EXECUTOR. Se falhar, reparar no mesmo pulso quando possível; se a lacuna for científica, devolver ao LEARNER com causa concreta e seguir para outra receita. A meta é certificar até 24 por pulso, sem fabricar candidatos.

O Operador consome apenas receitas com certificação técnica atual READY_FOR_EXECUTOR. Certificação técnica não substitui revisão científica independente do resultado.

### Autonomia de receitas do roadmap
Dentro da autorização de Dener para resolver receitas NEXO, seguir o ciclo completo:
diagnóstico e WORK com dono → Engenheiro aceita a recuperação → patch mínimo e smoke fiel
ao contrato → Revisor independente verifica os critérios existentes → integração com todos
os checks passando no mesmo SHA → Operador relê a versão integrada, revalida binding/readiness
e reserva a bateria pelo Writer. Reutilizar PR já aberto e dependência existente antes de criar outro.

O autor não aprova o próprio patch. Ausência de receita, smoke ou adapter é reparo de engenharia;
seleção, dataset, likelihood, prior ou critério científico não definidos retornam ao Cientista,
sem substituição conveniente. A autonomia é limitada às receitas dos roadmaps NEXO e às
capacidades já autorizadas; não permite criar credenciais, ampliar acesso, aceitar gates no lugar
do Dener, alterar pré-registro, forçar checks ou publicar mudanças fora desse escopo.

### Preparação do Cientista e prioridade do roadmap

Recuperação acionável dirigida a `LEARNER` vem antes de hipótese nova dentro do orçamento da
rodada. `WAIT_DEPENDENCY` que aguarda outro papel ou dado externo não cria barreira global; registre
dono, dependência e encaminhamento. Trabalho já elegível continua sem esperar uma nova passada do
Cientista. Toda nova `HYPOTHESIS_PROPOSAL` do Cientista usa um roadmap
`ACTIVE` e inclui `preparation_evidence` com `literature_refs` e
`internal_test_search:{checked:true,query,matched_test_ids}`. Se a busca encontrar teste anterior,
somente uma replicação com propósito explícito segue: acrescentar
`replication:{justified:true,purpose,independence_axis,compares_to_test_ids}` cobrindo os IDs
encontrados. Duplicata sem propósito fica registrada como não aplicada. Abrir outra frente exige
carta aprovada pelo Dener e ativação canônica antes da hipótese.

O Executor despacha READY ordinário somente de roadmap `ACTIVE`; contestação pendente pode terminar
a revisão do resultado que atacou. Avançar fase depende de readiness e recibos, não do minuto da
agenda. Sem inventário vivo, não alterar horários nem afirmar mudança nos prompts salvos.

Enquanto houver READY elegível e capacidade na rodada do Operador, NO-OP é inválido. O Operador único cobre toda a fila elegível por prioridade/idade e herda acompanhamento, resíduos e recuperações de EXECUTOR; relê staging/Tower antes de gravar. Guardião trata zero processamento com READY elegível como falha operacional e ausência de aplicação após dois pulsos do Writer como falha de pipeline.

Tratar essa tabela como mapa de integração, não como substituto do inventário vivo. Confirmar agenda viva antes de alterar. A janela silenciosa suspende notificações, nunca a execução. Proteger o Revisor: não substituir evento por polling. `last_run_time` prova execução da tarefa, não aplicação científica.

Ler mural e propostas pendentes para evitar duplicatas. Atraso ou falha de leitura produz diagnóstico; NO-OP somente com leitura válida e ausência de trabalho. Contestações precedem testes novos. Metas de vazão não autorizam inventar testes ou dados.

## Critério de entrega
Preserve stable_id e hash exato; consulte acked e receipts duráveis. Rejeição terminal,
leitura falha, ausência e conflito são distintos. Não reenviar os 14 HANDOFF ACK inválidos
de ADVISOR de 02/10/2026 nem aceitar por outro destinatário. Resultado, encerramento de
tentativa e revisão científica são dimensões separadas. Reconciliação histórica exige
prova compatível, versão e dry-run.

O mandato C01 é exclusivo do cache de readiness em contexto imutável: atribuição de 10%,
100 avaliações candidatas únicas por dia, 7–28 dias e máximo 2800 avaliações.
600 unidades efetivamente avaliadas pela candidata, com independência/estratos justificados,
são necessárias para o gate de qualidade; os 90% de controles não entram no denominador.
Falta de amostra, observabilidade ou readback retorna à baseline sem promoção.
Não amplia autorização a prompt packs, tarefas, ciência, ACL ou CAMB/MCMC.

Distinguir: configurado, proposto, entregue ao inbox, aplicado, executado, revisado e confirmado. Nulo científico exige execução válida. PASS de software permanece operacional. Preservar critérios congelados, multiplicidade, independência da contestação e limites do claim.

Reproduzir falhas, fazer a menor mudança, testar e reler. Informar como desfazer mudanças relevantes. Não criar tickets ou documentos intermediários por padrão. Uma instrução no Git alcança os consumidores que a carregam; não afirmar instalação de plugin, alteração administrativa global ou memória nativa sem confirmação da ferramenta.

## Leitor de status verificável
Para ler a cópia autenticada da Tower, executar `python scripts/status_reader.py TOWER.json nexo_gpt_writer.py`, em processo separado. Obter o script desta skill pelo GitHub conectado se ele não estiver montado. Obter o bundle pelo arquivo Drive usado no workflow do Writer; conferir os bytes antes de executar.

O leitor verifica a integridade e tenta o status nativo. Somente na versão auditada, quando a colisão entre duas funções `_stamp` derruba `review_queue`, isola o formatador original da fila e repete a leitura. Preserva os filtros do Writer, os IDs e o arquivo de entrada. Não altera o bundle implantado nem a Tower. `OK_LOCAL_REVIEW_CLOCK_REPAIR` identifica a correção local; `DEGRADED` e `FAILED` nunca significam fila vazia. Informar qualquer aviso restante e nunca apresentar esta saída como projeção publicada.
