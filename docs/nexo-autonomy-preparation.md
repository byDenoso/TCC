# NEXO — preparação, ativação e reversão

O pacote prepara autonomia contínua em cosmologia observacional, campanhas por pergunta e acompanhamento público. Preparar ou implantar o código não ativa o mandato e não altera as tarefas do ChatGPT.

## Estado e responsabilidades

Tower no Drive continua canônica; o Writer existente é o único aplicador. A entrada autenticada recebe propostas, o Writer admite/reserva e runners padrão gratuitos do GitHub Actions executam receitas congeladas. Vercel serve entrada e consultas. Neon e Railway permanecem com suas funções existentes; o pacote não exige serviços pagos novos.

O Cientista define perguntas, hipóteses e contratos. O Operador prepara receitas e executa. O Engenheiro mantém infraestrutura e dependências. O Crítico revisa independentemente. O Guardião observa mandato, custo, integridade, continuidade e publicação. O código novo permanece com ampliação desativada quando não existe `CONTROL.autonomy_mandate` válido e ativo.

O aumento 1→2→4 usa a política fixa `NEXO_CAPACITY_STABILITY_V1` do Writer, que exerce a verificação independente do Guardião. Cada estágio exige pelo menos duas baterias reais concluídas, sem falhas, duplicações, pendências ou revisões ausentes na população completa desde o início do estágio. No estágio dois, ambas as amostras precisam provar duas execuções sobrepostas por observações dos respectivos passos científicos. O Writer emite e aplica o recibo protegido de capacidade no mesmo round/CAS, somente com quota gratuita atual. Um relatório que declara o papel Guardião não autoriza aumento. Vinte continua teto técnico.

Os prompts preparados estão em `gpt/automations/nexo-automation-prompt-pack-v1.1.0.json`. A versão 1.0.0 é histórico datado. O pacote novo tem somente cinco funções; não contém agendas, modelos ou habilitação. IDs observados são pistas, não autoridade para localizar ou alterar tarefa.

Genes operacionais elegíveis usam plano prospectivo com `metric`, mínimo de dez unidades em cada braço, `minimum_gain` positivo, `higher_is_better` e todos os `units[{test_id,arm}]`. O Writer congela esse plano antes das execuções e recalcula o ganho dos recibos reais. A revisão de cada unidade é produzida pelo reconciliador a partir de um ataque independente executado, com autoria vinculada ao contest; atribuir o papel de Crítico no relatório não produz prova. O `rollback_ref` deve ser exatamente `sha256:<digest do canonical anterior>`. Falta de qualquer evidência mantém a candidata sem promoção e conserva a baseline.

## Conferência antes de ativar

1. Identificar a revisão implantada e os checks dessa mesma revisão. Conferir integração das propostas de transporte, terminalização, dependências e descoberta completa; bundles do Writer e leitores precisam de geração determinística e readback por hash.
2. Ler metadados e bytes da Tower canônica, materializar/validar o CONTROL e conferir revisão/fingerprint. Leitura textual vazia ou degradada não basta. Não alterar o armazenamento, o Writer, as ACLs ou contratos para contornar falha.
3. Exercitar ingresso autenticado, idempotência, recibo e leitura canônica em uma fixture operacional aprovada. Verificar a reserva por teste/tentativa e a reconciliação de disparo incerto. Confirmar que runners não recebem credenciais da Tower.
4. Verificar capacidade gratuita no contexto atual: repositório público, runner padrão, cotas e orçamento disponíveis. Nenhuma prova antiga autoriza custo novo. Começar com uma execução simultânea; medição registrada precede etapas de duas e quatro.
5. Conferir o publicador: projeção sanitizada, perguntas/identidades, testes em progresso, resultados revisados/aprovados, fechamento explícito, ausência de dados privados, versão/data e leitura pública. Falha mantém a versão anterior verificada.
6. No ChatGPT com as cinco tarefas existentes, reler inventário, prompts e configurações atuais. Reconciliar pelos papéis e confirmar IDs. Guardar snapshot dos cinco prompts e configurações para reversão, sem segredos. Atualizar somente os prompts para os bootstraps da revisão verificada e reler cada um; preservar mudanças concorrentes e todos os outros campos.
7. Registrar a decisão humana na superfície protegida e validar o atestado no coletor. Somente depois dos cinco readbacks, da quota e demais provas, gerar o recibo de ativação com revisão, fingerprint e horários reais e aplicar `APPROVE_AUTONOMY_MANDATE`. Reler CONTROL e recibo. Prompt, `source: DENER` ou `verified: true` no payload não autenticam aprovação.

Em `activation_receipt.source_revision`, registrar o commit implantado do **Pantheon**, cujo workflow e smoke do executor passaram; não usar o commit do pacote de prompts TCC nesse campo. Registrar a versão TCC e os hashes dos cinco prompts junto às evidências de ativação. A capacidade exige também observar o job real atual do Writer em runner público padrão, com a implementação aprovada e início recente. CI histórico sozinho não demonstra disponibilidade atual. Somente avanços de `main` restritos aos três marcadores existentes do próprio Writer (`tower-head`, recibos da inbox pública e do spool) conservam a equivalência da implementação; mudança de código, história divergente, listagem incompleta, job ainda invisível na API ou cota indisponível bloqueiam novas admissões.

Antes do disparo, comparar o HEAD de `main` com a revisão reservada. Divergência mantém a reserva pendente e exige reconciliação; não criar outra execução para reparar. Uma mudança entre essa conferência e a aceitação pelo GitHub também será recusada pelo vínculo exato do run. O Engenheiro deve conferir o histórico completo, registrar a causa e apresentar a correção prospectiva de versão ao Guardião antes de qualquer nova tentativa. Nenhum caminho redefine o contrato ou interpreta timeout como ausência de execução.

Nested Watch, Pítia, Sentinela, Revisor por evento, cartões antigos, agendas, modelos, habilitação e execuções protegidas permanecem como encontrados. Não executar esta conferência como administração automática de tarefas. O prompt de ativação é uma instrução humana para uma conversa posterior e não deve ser enviado durante a preparação.

A consulta e revogação humanas ficam no painel Autonomia da sessão privada existente. O endpoint `/api/autonomy-status` fornece estado canônico sanitizado e proposta exata de revogação; não inventa provas de ativação. Depois das conferências acima, a conversa de ativação deve preparar o JSON `{envelope,proposal_sha256}` do recibo completo. Dener revisa esse recibo no painel e confirma os bytes exatos pela sessão humana. `DELIVERED` significa envio autenticado à fila: somente nova leitura do CONTROL prova aplicação. Uma resposta incerta exige leitura/reconciliação, sem reenvio automático.

## Campanhas e acompanhamento

Cada pergunta científica explícita mantém uma identidade estável e uma campanha/roadmap; os IDs existentes são reutilizados. Mudança de título não cria outra pergunta. Questão diferente abre outra campanha e pode vincular antecedentes. A reconciliação dos agrupamentos editoriais com a Tower exige vínculo explícito; sem prova, não juntar títulos parecidos ou inventar histórico.

O site apresenta andamento e encerramento verificado, testes em progresso, pergunta, motivação, método, próximo passo, limites e atualização. Pausada/bloqueada permanece em andamento com causa. Encerrada pode ter resultado negativo ou inconclusivo. Resultados aguardam revisão independente e política pública; o publicador nunca recebe a Tower bruta. Acompanhamento no site é automático dentro da política; artigos e submissões externas permanecem humanos.

O pacote desta preparação gera e valida a projeção depois do readback do Writer. O adaptador de publicação da hospedagem atual ainda precisa ser conectado e confirmado; a conta Namecheap informada por Dener estava sem sessão autenticada durante a conferência. Até identificar a fonte ativa, não substituir o site e não tratar staging em `/tmp` como publicação. O registro canônico permanece `PENDING_PUBLICATION` e conserva o último readback/data verificados. A variável de liberação, sozinha, não conecta um publicador.

## Piloto e avaliação inicial

O candidato H0 depende da revisão científica da receita, do estimador, covariância, inputs congelados e independência dos recortes. CI ou smoke aprovado não libera esse gate. Sem independência demonstrável, registrar a limitação e não fabricar holdout. Preservar as execuções MCMC/checkpoints protegidas.

Um ciclo completo com execução válida, evidência e revisão independente precede a avaliação inicial de 168 horas. Medir continuidade, duplicação, tempo de recuperação, custo/cota, resultados revisados e leitura pública. A avaliação não expira o mandato, que continua até revogação. Evidência local ou simulada deve ser identificada como tal; não prova execução cloud ou publicação.

## Revogação e reversão

- **Mandato:** Dener revoga pela mesma superfície humana com `REVOKE_AUTONOMY_MANDATE`, ID ativo, revisão esperada e referência da decisão. Reler o estado `REVOKED`. Novas admissões e promoções param; histórico permanece. Reaprovação exige nova identidade; uma mensagem atrasada não ressuscita ID revogado.
- **Tentativas já iniciadas:** acompanhar/coletar conforme o contrato; não cancelar, redespachar ou apagar por efeito colateral da revogação. Execuções protegidas permanecem intocadas.
- **Fragmento operacional:** candidata reprovada não é promovida e conserva a baseline. Reversão de fragmento já canonizado exige procedimento autorizado com evidência e nova versão; o pacote não acrescenta monitor geral de rollback pós-canonização. Revogação do mandato faz o bootstrap usar seu fallback seguro. Os limites e o monitor próprios de C01 permanecem intactos; não há autoedição de scheduler.
- **Prompts instalados posteriormente:** somente ação humana autorizada restaura os cinco snapshots, após comparar o inventário atual e preservar mudanças concorrentes. Reler cada prompt; não restaurar agendas, modelos ou habilitação por acidente.
- **Código/publicação:** selecionar a revisão anteriormente implantada e os bundles correspondentes pelo processo existente, verificar build e readback. O publicador conserva a última projeção aprovada até confirmar a nova. Não restaurar a Tower inteira para desfazer código, nem descartar resultados recebidos depois do snapshot.

Encerrar a entrega com revisão preparada/implantada, testes executados, limitações de acesso e capacidade, mandato ativo/inativo e próxima prova necessária. Configurado, preparado, aplicado, executado, revisado e confirmado são resultados distintos.
