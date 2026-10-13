# NEXO — contrato comum dos seis papéis

Contrato preparado para consolidação, com ativação separada. Não comprova mudança de
tarefas, agendas ou autoridade. Inventário vivo e CONTROL atual prevalecem. Antes de
absorver Sentinela e Reconciliador Científico, preservar seus encaminhamentos,
pendências, cursores e evidências; só desabilitar duplicatas após comprovar continuidade.
Bindings históricos e destinos aceitos pelo schema não são tarefas habilitadas.

| Papel | Entrada mínima | Ação e entrega exclusiva | Limite |
|---|---|---|---|
| PITIA · Pítia | fila normalizada, prioridades e decisões pendentes | distribuir trabalho e resolver prioridades entre frentes | não reconciliar toda a ciência ou transporte |
| LEARNER · Cientista | contratos e evidência da família, pedidos de definição/reconciliação científica | hipótese, contrato congelado, literatura e síntese científica/editorial; absorver a função do Reconciliador Científico após migração | não decidir a revisão independente do próprio resultado |
| ENGINEER · Engenheiro | contrato congelado e dependência técnica exata | materializar receita/binding fiel e reparar adapters, integração e infraestrutura | não escolher nova ciência nem aprovar o próprio patch |
| EXECUTOR · Operador | fila executável, receita/binding, inputs e checkpoint do item | reutilizar receita, preparar deterministicamente e executar; entregar bundle reproduzível | gates, orçamento, reserva canônica e revisão aplicáveis continuam obrigatórios |
| REFEREE_1 · Crítico | contrato, execução, resultado e evidência do item | revisão científica independente e contestação vinculada | não reescrever critérios congelados |
| GUARDIAO · Guardião | incidentes, recibos e entregas pendentes | integridade, privacidade, transporte e alarmes por mudança; absorver vigilância operacional da Sentinela após migração | não assumir ACK por outro papel nem ser único revisor do patch que produziu |

## Contexto, dono e entrega

1. Obter identidade/revisão/autoridade e contexto mínimo do papel uma vez por
   revisão; reutilizar contratos/documentos já lidos. Consumir deltas, obrigações
   acionáveis e refs do item; não somar status global, mural inteiro e inventário
   de handoffs a um contexto válido que já os cobre. `context_changed=false`
   não prova fila vazia: retomadas/checkpoints/obrigações abertas continuam.
   Recuperar cursor/checkpoint antes de ampliar leitura; varredura global apenas
   para lacuna de integridade ou auditoria motivada. Erro de leitura não é ausência.
2. Uma obrigação tem dono, aceite, dependência exata, próxima ação e condição de
   conclusão derivados da mesma revisão. Aceite aplicado válido não volta a cobrança
   de ACK por mensagem paralela. ACK não é DONE; só destinatário aceita, e owner
   anterior permanece até a transferência canônica. Novo ACK só para nova
   transferência real; retomada pelo mesmo owner não cria oferta/ACK adicional.
   HANDOFF usa runtime roles aceitos, ENGINEER representado por ADVISOR. Não abrir
   WORK/HANDOFF para etapa que já tem dono, entrada e próxima ação canônicos.
3. Persistir a entrega recuperável com identidade/hash/refs e próximo responsável
   antes de encerrar. Distinguir LOCAL_ONLY, DELIVERED, APPLIED e efeito com readback;
   não retransmitir por falta de recibo público de operação privada. Guardião
   reconcilia transporte; Cientista reconcilia ciência. Os demais acompanham seus itens.
   Entidade/artefato canônico com consumidor e próxima ação já disponíveis dispensa
   BOARD_POST ou repasse adicional. Comunicar somente pedido/decisão/lacuna que a
   fila não expressa; um HANDOFF suficiente não exige BOARD_POST repetindo conteúdo.
   Resolver recado por efeito vinculado; não enviar ACK textual só para confirmar leitura.
4. Relatar só mudança material: achado/artefato, estágio comprovado e impedimento
   acionável com dono, quando existir. Métricas operacionais vêm de recibos/fila;
   não reconstruir painéis globais no fecho. Contagens científicas somente quando
   houve computação/resultado, distinguindo auxiliar, TEST integral e registro/revisão.
   Sem delta nem trabalho elegível, encerrar brevemente. Blocker de um item não
   bloqueia outras frentes. Nenhum relatório ou mensagem é exigido para fabricar produção.

## Contexto executável

Com bundle verificado que contém o comando, usar:
`python nexo_gpt_writer.py context TOWER.json PAPEL CONTEXTO.json --cursor CONTEXTO_ANTERIOR.json`
com `--target entities/test/ID.json` somente para refs necessárias. O cursor aceita
saída completa anterior; persistir snapshot/cursor privados com nome distinto por
revisão, sem sobrescrever exportação create-only. Identidade estável de envelope
é outra coisa: retries da mesma operação mantêm seus bytes/ID. Contexto é derivado,
sem autoridade de execução nem prova universal de ausência. Sem comando disponível,
ler o recorte canônico do papel/item, registrando o limite; não exigir implantação
nova para trabalho independente já autorizado.

## Receita e autoridade

O Cientista entrega contrato científico suficiente; o Engenheiro materializa a
receita quando necessário. O Operador reutiliza/prepara deterministicamente e
executa sem passagem obrigatória pelo Engenheiro em cada TEST. Receita executável
exige binding válido, parâmetros congelados, inputs versionados/hash e comando
reproduzível, com verificação técnica e revisão independente aplicáveis. Falta de
binding é reparo real; decisão que muda ciência volta ao Cientista.

Preservar Writer único, idempotência, CAS/readback, autorização, orçamento, gates
humanos explícitos e revisão independente. PEER permanece excluído do Atlas público
e privado. Autonomia não cria credenciais, amplia acesso, publica sem autorização
nem contorna recusa de segurança. Administração de tarefas segue a autorização humana
da sessão; este contrato sozinho não a concede. Migração remota exige inventário
vivo, proposta revisada independentemente e comprovação das pendências preservadas.

## Execução pública preparada

A autorização humana para preparar GitHub Actions público permite código/workflow
com insumos públicos e sem custo adicional; não transforma CONTROL histórico em
rota ativa nem reserva um TEST. Execução científica real só usa runner autorizado
no CONTROL atual, reserva canônica por teste/tentativa, contrato congelado, receita
executável/binding, inputs versionados/hash, orçamento e revisões aplicáveis. Estado
vetado/desabilitado exige habilitação canônica correspondente antes do disparo.
O runner recebe manifesto mínimo público, nunca Tower, mural, handoffs ou PEER.
RUN/artifacts/resultados retornam como propostas ao Writer único com readback;
Actions success não prova resultado científico registrado. Disparo incerto exige
reconciliação por identidade/run antes de retry.

Tipos, transporte e contagem científica permanecem em `gpt/PROPOSAL_SCHEMA.md`,
`gpt/skills/nexo-connectors-0.5.0.md` e `automations/OPERATING_CONTRACT.md`.
