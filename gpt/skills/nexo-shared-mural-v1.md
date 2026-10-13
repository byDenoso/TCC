# NEXO · Mural compartilhado e confirmação entre pulsos (proposta de política v1)

Documento operacional para agentes agendados. **O CONTROL.json vivo e os contratos de domínio prevalecem.** Esta proposta não altera CONTROL, mandatos, timers, limite de paralelismo, Writer ou autoridade científica.

## 1. Fonte e responsabilidade
- Tower privada e CONTROL vigentes são canônicos; Writer único, BOARD_POST, HANDOFF/WORK e fila permanecem. PEDIDO é projeção operacional de itens já governados pelo Writer, não ledger novo.
- Sete papéis: Maestro/Pítia (continuidade e prioridades), Cientista (HIPOTESE/CONTRATO/RECEITA/LITERATURA), Engenheiro (BINDING/INTEGRIDADE técnica), Executor (EXECUCAO), Crítico (REVISAO independente), Sintetizador (propostas entre ciência/literatura), Editor (REDACAO e projeção aprovada). Uma vaga livre. Aliases de apresentação não concedem autoridade Writer.
- Pedido mínimo: `{tipo:"PEDIDO",id,precisa:CAPACIDADE,sobre:referencia,porque:frase,de:papel,depende_de:[ids],estado:"ABERTO"}`, capacidades PRIORIDADE,HIPOTESE,CONTRATO,RECEITA,BINDING,EXECUCAO,REVISAO,LITERATURA,INTEGRIDADE,REDACAO,DECISAO_DENER. Persistir por schema existente; não presumir conversor implantado.
- Em cada pulso confirmar conexão autorizada, identidade/revisão de Tower/CONTROL, recibos associados e pedidos liberados, de preferência com delta/cursor. Ordenar primeiro por prioridade explícita do roadmap/Maestro, depois abertura mais antiga. Dedupe capacidade + referência + finalidade. Não gerar ideias extras enquanto pedidos elegíveis destravadores esperam.

## 2. Reserva, dependências e encerramento
- BOARD_POST comunica e recebe resposta apenas quando necessária; nunca prova ownership, execução ou entrega. HANDOFF/WORK canônico é solicitação rastreável.
- `PEGO` somente com reserva **atômica** do Writer/lease existente, vinculando pedido, papel, revisão e prazo de duas cadências. ACK sem CAS/readback não concede exclusividade; se faltar mecanismo, registrar demanda técnica, não assumir trabalho exclusivo.
- `FEITO` requer efeito concreto persistido, recibo e readback de mesma identidade; preparação local ou `DELIVERED` não é aplicação. `AGUARDA`: reutilizar/criar PEDIDO para capacidade faltante, ligar `depende_de`, detectar ciclos e registrar causa nova. Dependência validada libera elegibilidade derivada automaticamente pelo Writer.
- Vencimento exige reconciliação: se job ativo, acompanhar o **mesmo** job/checkpoint; sem job ativo, liberar via Writer. Nunca duplicar por horário. Três devoluções distintas acionam decisão do Maestro. Após um pulso sem resposta admite uma cobrança; após dois, diagnosticar antes de nova cobrança. Maestro não aprova ciência nem é intermediário obrigatório de tudo.

## 3. Persistência, falhas e controle de agendas
- Um pulso reconcilia receipts `PENDING_WRITE` pertinentes e IDs de job; reenvio somente após verificação de não aplicação, com identidade e bytes iguais. Use o inbox privado autenticado declarado pelo CONTROL; jamais GitHub público para recados privados. `DELIVERED` não equivale a `APPLIED`.
- Se a escrita falhar, mantenha `PENDING_WRITE` em armazenamento durável autorizado. Se não houver durabilidade, indique `PENDING_WRITE_LOCAL_ONLY`; nunca inventar recibo. Registrar `FALHA` com ferramenta, código e trabalho afetado, seguir com itens independentes. MCP indisponível não equivale a fila vazia; não contornar 401/403, ACL nem política.
- Todo pulso produz `BATIMENTO={papel,em:UTC,fez:resumo,proximo:acao}`, persistido somente quando Writer/canal autorizado permitir. Resposta curta: PAPEL/UTC, Feito, Pedidos, Falhas/decisões novas, Próximo, Persistência.
- **NUNCA PAUSAR:** agentes não criam, pausam, ativam, desativam, excluem ou alteram quaisquer agendas. Apenas Dener administra. Remover ferramentas de administração dos agentes quando possível. Ação que precise de autorização ainda ausente vira DECISAO_DENER com pergunta e recomendação; não insistir a cada pulso.

## 4. Cadências, capacidade e fronteira científica
- Cadência inicial: Maestro/Pítia 30 minutos; Cientista, Engenheiro e Executor 1 hora; Crítico, Sintetizador e Editor 2 horas, fuso America/Sao_Paulo. Ajustar pela capacidade real e inventário vivo. Sem metas artificiais ou quotas de novos testes; cada job longo mantém seu ID.
- Respeitar contrato congelado, null/rival, inputs, autorização, budget, validade e readback. Cientista pode implementar receita simples; Engenheiro cuida de binding/adapters; Executor executa e retoma; Crítico revisa independentemente; Sintetizador propõe teste de sistemática, discriminante ou reparo reutilizável; Editor somente projeta conteúdo aprovado.
- Ninguém faz revisão independente do próprio resultado. Resultado nulo válido é entrega, sucesso técnico não é confirmação científica. Não mover critérios após olhar dados; claims incluem limite em uma linha e explicação em português.
- Rótulos operacionais propostos: `estado_proposto:NOME_EM_MAIUSCULAS`, `definicao:frase`, mantendo estado base. Maestro só incorpora após 3 eventos distintos de >=2 papéis em 48 horas (retries não contam); 7 dias sem uso e sem pedido ativo permite arquivar o rótulo, sem apagar histórico ou alterar schema, transições, critérios ou autoridade.

## 5. Novas campanhas do Cientista
- LEARNER pode criar `ROADMAP_CHARTER` com `status=PROPOSED`, questão nova, null/rival, literatura, dedupe, fontes públicas, budget/stop, segurança, escopo e impacto. Sem `mandate_id` que promova automaticamente; não enviar `APPROVE_CHARTER` em nome de Dener.
- Atlas privado exibe cartão da Tower `roadmaps/<id>.json` com `charter.status=PROPOSED`. Dener aprova/rejeita pela superfície humana autenticada já existente (`OPERATOR_INTENT APPROVE_CHARTER/REJECT_CHARTER`) e o Writer persiste/relê. Até então nenhuma admissão de TEST prospectivo sob essa carta.
- PEER continua **excluído de todas as projeções do Atlas**, tanto privada quanto pública. Não exponha conteúdo de handoffs PEER no mural privado.

## 6. GitHub Actions público
- Resolver primeiro no CONTROL a identidade **exata** do repositório público de execução autorizado, permissões e política do custo. Lista de repositórios verificados não define, por si só, um destino para testes.
- Capacidade `Actions disponível` exige provas de job real em runner padrão, quota e custo gratuitos e workflow técnico compatível com o TEST; um job de publicação ou Writer bem-sucedido não comprova a likelihood científica.
- CONTROL observado em 11/10/2026: `github_actions_science_role=DISABLED_BUDGET_EXHAUSTED` e `github_actions_reenable_policy=EXPLICIT_OPERATOR_ONLY_AFTER_BUDGET_RESET_OR_PLAN_CHANGE`. Portanto, nenhuma execução científica é despachada em Actions até reconciliação canônica explícita pelo Writer e autorização adequada; preserve execução local.
- Nunca compartilhe Tower privada, PEER privado, secrets, auth/paths internos, ou dados não-publicados nos logs e artifacts de repositório público. Preserve id/commit/inputs e verifique run original antes do retry.

## 7. Aceite e evidência
- Antes de migrar agendas: inventário **vivo** com identidade das tasks, roles/cadência atuais, CONTROL e Tower atuais, Writer único com CAS/lease e readback comprovados; nunca criar duplicatas para contornar falta de acesso.
- Testar em runtime real e pelo Writer o ciclo PEDIDO -> PEGO -> FEITO, falta de RECEITA -> AGUARDA -> liberação, replay duplicado, lease vencido com job ativo, pedido sem resposta e indisponibilidade MCP. Cada teste deve demonstrar que nenhum agente alterou agendas e que trabalho independente continuou.
- PEER fica fora dos Atlas público e privado; Olympus e dados pessoais permanecem privados. Publicação usa só projeção aprovada e autorização vigente.
- Sem prova operacional, marcar apenas PREPARADO/EM_REVISAO. Não anunciar recuperação, integração, atualização de prompt salvo ou execução científica sem recibo/teste verificável.

