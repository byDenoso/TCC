---
name: nexo-workspace
description: Operar a conversa do Dener como interface da Tower e das funções NEXO habilitadas no inventário vivo. Usar para status, ideias e testes científicos, resultados antigos, investigação de falhas, comparação com literatura, manutenção e verificação de automações. Reutilizar GitHub, Drive, Writer e projeção; preservar critérios científicos e verificar cada afirmação de conclusão.
---

# Workspace operacional do NEXO

## Inicialização

Aplicar raiz e `automations/ROLE_CONTRACT_V1.md` na revisão conhecida; reutilizar
leituras válidas da mesma revisão. Usar intenção da mensagem e abrir somente fontes
do pedido. Para automações, usar contexto/fila do próprio papel, cursores duráveis e
refs necessárias ao item. O comando executável e o fallback restrito estão no
contrato comum; não ler o bundle inteiro nem status global por rotina.
Consultar `NEXO Lite/pendentes` e recados a DENER somente ao atender assunto NEXO
ou delta material destinado a ele; não inserir ruído operacional em outra conversa.

## Autoridade por assunto
- Ciência: Tower, entidades e evidências; projeção como leitura derivada.
- Agenda e tarefas habilitadas: inventário vivo da ferramenta de automações. Sete Tasks NEXO ativas: MAESTRO, CIENTISTA, ENGENHEIRO, EXECUTOR, CRITICO, SINTETIZADOR, EDITOR. Demais Tasks visíveis estão desativadas/concluídas em 15/10/2026. Papéis históricos não são agenda e não autorizam criar/reativar tarefas.
- Caminho operacional: política do pseudo-MCP privado Drive `1XO_V7Cmb75l8zSWCIsaoQGFRssLwLqMB` (`control_retirement_transition`), Tower LIVE para estado/evidência, prompts/agenda vivos, código implantado e recibos de execução. `CONTROL` é histórico/compatibilidade técnica; divergência é defeito de migração, não veto de ciência.
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
Ler a Tower privada pela rota autorizada e usar apenas derivados atualmente aprovados. A projeção pública retirada não é rota de leitura; erro de acesso não prova fila vazia. A Tower é o arquivo JSON `1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z`, não uma pasta. Confirmar metadados antes de baixar.

Para análise local, usar a cópia autenticada e o bundle utilizado pelo workflow `byDenoso/Pantheon@main:.github/workflows/nexo-writer-robot.yml`. Inspecionar antes de executar. Rodar somente leituras como `verify`, `status` e `frontier` na cópia local. Conferir stderr e seções esperadas: saída zero com mensagem `skipped` é leitura degradada. Identificar projeção reconstruída como local, sem alegar publicação.

Localizar no Drive as pastas `cosmology-world-model`, `nexo-reporting` e `NEXO Lite`; ler a identidade do SKILL.md antes de usar. Preservar pastas existentes. Pesquisar histórico por referências, não por semelhança de nomes apenas.

## Gravação e acompanhamento
Para novo artefato científico, resolva a CAMP_ID privada e crie um item imutável CREATE-ONLY com ID/event_id, fonte, conteúdo não vazio, MIME, parent e hash/readback. Para consolidar estado na Tower, use somente o Writer técnico exclusivo autorizado, com recibos e readback; a Task não sobrescreve o JSON LIVE. Leia o pseudo-MCP Drive como política e Tower LIVE como estado; não usar `CONTROL.json` histórico para liberar/bloquear ciência. Git de staging só é ingress técnico se comprovadamente autorizado e sanitizado.

Coordenação direta entre agentes é opcional e não bloqueia teste independente. `BOARD_POST` e `HANDOFF` são envelopes legados quando um consumidor realmente os exigir, nunca pré-requisito universal. JSON/binários de campanha usam upload create-only autorizado; Google Doc OAuth só conta após criar, inserir texto com controle de revisão, mover e reler conteúdo não vazio na pasta correta. Inbox privado é transporte técnico de propostas da Tower, não repositório obrigatório dos artefatos científicos. Trate 401/403/SECURITY_BLOCK como limites reais. Diferencie ARTIFACT_PERSISTED, PENDING_TOWER_APPLICATION e TOWER_APPLIED_READBACK.

## Compatibilidade do pipeline legado por item (não cria gates novos)

Esses seis papéis (PITIA, LEARNER, ENGINEER, EXECUTOR, REFEREE_1, GUARDIAO) são aliases de envelopes do Writer, não as sete Tasks científicas vigentes nem exigência de handoff. A agenda, permissões e a execução científica vêm do inventário vivo e do pseudo-MCP no Drive. Manter compatibilidade de mensagens apenas quando consumidor efetivo comprovado.

Os antigos números 6/24 são probes de capacidade para medir utilização, nunca quotas nem limites. Continue enquanto houver trabalho independente elegível e orçamento seguro. Seeds, retries, shards, downloads, smokes, leituras, receipts e duplicatas não contam como produção científica. Se a fila elegível drenar, o no-op é correto; se restarem itens elegíveis, a rodada deve registrar por que parou.

A cadência não é barreira global. Cada papel consome entregas já aplicadas, inclusive de rodadas anteriores. Blocker pertence ao item. Se um item trava, registrar/encaminhar e seguir imediatamente para outro.

### Conversa e ownership entre automações
- `BOARD_POST` é o canal de conversa direta entre papéis nomeados: PITIA, LEARNER, EXECUTOR, REFEREE_1, GUARDIAO, ENGINEER, SENTINEL, ADVISOR e demais destinos válidos do schema. Usar refs/reply_to e resolver recados consumidos.
- `HANDOFF` é transferência de ownership e o runtime aceita somente recipient `DAILY|ADVISOR|EXECUTOR|LEARNER|EMERGENT`; sender é um desses ou DIRECTOR. ENGINEER usa ADVISOR no handoff privado.
- PITIA, REFEREE_1, GUARDIAO e SENTINEL não criam handoff com seus nomes. Eles usam BOARD_POST; se ownership precisar mudar, pedem ao runtime role competente para criar/transicionar o HANDOFF.
- Uma entrega com próximo consumidor precisa efeito/artefato canônico ou pendência recuperável com refs e ação. Se a fila já apresenta o efeito e o consumidor, não repetir em BOARD_POST. HANDOFF somente para nova transferência real; não acrescentar recado duplicando o handoff suficiente.

### Rota operacional atual
Resolver política no pseudo-MCP privado do Drive e estado na Tower LIVE, cada um na menor revisão adequada. A capacidade de compute deve ser observada em cada runtime; `DISABLED_BUDGET_EXHAUSTED` do CONTROL antigo não é veto global a Actions. Staging/relay Git é só transporte técnico comprovado, nunca fonte de estado nem canal para dados privados.

### Invariante READY
`READY` significa cientificamente e operacionalmente executável na superfície autorizada. Exigir definição congelada suficiente, dados e inputs autenticados, avaliador fiel realmente executável, capacidade disponível, identidade estável e ausência de execução equivalente. Um catálogo de recipes ou binding administrativo só é obrigatório para o runner específico que o consome, não para todo chat ou Task. Se faltar qualquer requisito, corrigir pelo fluxo autorizado para `CHECKPOINTED` ou `WAIT_DEPENDENCY` e criar o binding/reparo; não contar como despacho.

### Consumir recuperação e aceite privado

Obter obrigações, ofertas e recuperações pertinentes do contexto privado do próprio
papel. Como fallback, consultar `status.execution_recovery` somente para os itens
do papel/refs em questão; não varrer a seção inteira por rotina. Quando o comando context verificado já cobre a fila, não executar status,
mural e handoff list globais para reconfirmar a mesma revisão. Carregar entidade
completa apenas quando o recorte não basta à ação. Se faltar essa capacidade,
`python nexo_gpt_writer.py handoff TOWER.json list PAPEL` lê a caixa privada:
Engenheiro usa ADVISOR; Cientista LEARNER; Operador EXECUTOR. Guardião não aceita
por outro papel. A caixa de bootstrap de cinco cartões não limita a fila; paginar
ou consultar ofertas pertinentes quando indicar `inbox_has_more`, sem inventário
global em toda rodada. Fonte inacessível não comprova continuidade/ausência.

Aceite é transferência de ownership; diagnóstico, leitura de fontes, preparação local e reparo de código já autorizado podem avançar antes dele. A operação que depende de assumir a WORK espera o ACK aplicado. Combine preparação e persistência na mesma rodada quando os contratos e o transporte permitirem, sem aguardar o próximo horário de outro papel para uma ação já elegível.

Ao aceitar nova transferência real de uma WORK, enviar `HANDOFF_ACK` com `writer_role` igual ao destinatário canônico pelo
Drive privado NEXO_INBOX conforme PROPOSAL_SCHEMA. Reler a aplicação: só o aceite aplicado muda
ownership. Retomada pelo mesmo owner e ACK válido da mesma obrigação dispensam nova oferta/ACK. Proposta gravada, comentário no mural e atribuição ADVISOR não são aceite. Se faltarem
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

### Pipeline de receitas work-conserving

O Cientista define a pergunta e o contrato científico: TEST/roadmap/hipótese, literatura, antecedentes internos, modelo/null/rival, método, seleção, parâmetros/priors, estatística/estimando, sucesso/kill e independência. Entrega o contrato ao Engenheiro quando precisar de materialização e ao Operador para reutilização/preparação e execução. Lacuna de definição volta ao Cientista sem alterar contratos congelados; não precisa de uma passagem obrigatória pelo Engenheiro.

O Engenheiro materializa receita e binding a partir do contrato congelado quando necessário, e mantém infraestrutura, transporte e dependências compartilhadas. O Operador reutiliza receita fiel e prepara deterministicamente a execução: inputs/versionamento/hashes, dependências, parâmetros, comando reproduzível, outputs, artifacts, preflight/smoke, checkpoint/resume, custo e proveniência. Falta de implementação vai ao Engenheiro; mudança científica volta ao Cientista. Só solicita READY após os gates técnicos e a revisão independente aplicáveis. Não há barreira administrativa do Engenheiro por teste.

O Operador executa apenas receitas tecnicamente válidas e readiness atual, com reserva canônica por teste/tentativa. Não aprova a própria receita. Certificação técnica não substitui revisão científica independente do resultado.

### Autonomia de receitas do roadmap
Dentro da autorização de Dener para resolver receitas NEXO, seguir o ciclo completo:
diagnóstico e WORK com dono → Engenheiro materializa receita quando necessário; Operador reutiliza/prepara deterministicamente → patch mínimo e smoke fiel
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
carta aprovada pelo Dener ou pelo Writer dentro do novo mandato ativo verificável, e ativação canônica antes da hipótese. O pacote preparado não ativa essa delegação.

O Executor despacha READY ordinário somente de roadmap `ACTIVE`; contestação pendente pode terminar
a revisão do resultado que atacou. Avançar fase depende de readiness e recibos, não do minuto da
agenda. Sem inventário vivo, não alterar horários nem afirmar mudança nos prompts salvos.

Enquanto houver READY elegível e capacidade na rodada do Operador, NO-OP é inválido. O Operador único cobre toda a fila elegível por prioridade/idade e herda acompanhamento, resíduos e recuperações de EXECUTOR; relê Tower/inbox/recibos privados antes de gravar. Guardião investiga falta de avanço com trabalho realmente acionável e capacidade comprovada; tempo decorrido ou dois pulsos sem recibo, isoladamente, não provam falha. Atualizar um incidente por transição material, sem alarmes repetidos.

Tratar esse contrato como mapa de integração, não como substituto do inventário vivo. Confirmar agenda viva antes de alterar. A janela silenciosa suspende notificações, nunca a execução. Proteger o Revisor: não substituir evento por polling. `last_run_time` prova execução da tarefa, não aplicação científica.

Usar refs/recibos/fila pertinentes para evitar duplicatas, reutilizando a revisão já lida. Atraso ou falha de leitura produz diagnóstico; NO-OP somente com leitura válida e ausência de trabalho. Contestações precedem testes novos. Metas de vazão não autorizam inventar testes ou dados.

## Critério de entrega
Preserve stable_id e hash exato; consulte acked e receipts duráveis. Rejeição terminal,
leitura falha, ausência e conflito são distintos. Não reenviar ACK inválido nem aceitar por outro destinatário. Resultado, encerramento de
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
