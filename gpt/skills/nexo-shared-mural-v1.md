# NEXO · Mural compartilhado e confirmação entre pulsos (proposta de política v1)

Documento operacional para agentes agendados. **O CONTROL.json vivo e os contratos de domínio prevalecem.** Esta proposta não altera CONTROL, mandatos, timers, limite de paralelismo, Writer ou autoridade científica.

## 1. Fonte e responsabilidade
- A fonte única é a Tower privada `NEXO_TOWER_LIVE.json` (Drive ID `1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z`); o Atlas privado apenas a apresenta. Não crie banco/mural alternativo.
- `BOARD_POST` = diálogo privado `from/to/text/refs/reply_to`, nunca transição de ownership nem prova de compute.
- `HANDOFF` = solicitação rastreável com `handoff_id`, `thread_id`, destinatário canônico, `entity_ref` e próxima ação concreta. Só os runtime roles autorizados pelo Writer podem criar/aceitar handoffs; ENGINEER tem alias ADVISOR quando o contrato permitir. Pítia, Crítico, Guardião e Sentinela conversam via BOARD_POST, não assumem outro papel.
- No início **de todo pulso de cada papel**, leia CONTROL, recibos/envelopes pendentes do próprio pulso anterior, `evolution/board.json` e **todas** as ofertas abertas dirigidas ao papel, não somente os cinco cards de bootstrap. Para os runtime roles válidos, use `AgentService.inbox_for(role)` ou `python nexo_gpt_writer.py handoff <TOWER.json> list <PAPEL>` em cópia local verificada; `inbox_has_more` sinaliza paginação, não inexistência.
- Priorize handoffs antigos já autorizados, tarefas encaminhadas por outros agentes e roadmaps ACTIVE antes de emitir ideias extras. Trate solicitações como parte do orçamento do papel, nunca como fila infinita paralela.

## 2. Fechamento obrigatório da conversa
- Uma mensagem relevante deve gerar resposta `BOARD_POST` com `reply_to` e evidência ou limitação real; recado sem referência e sem destinatário não prova ação.
- Para `HANDOFF` recebido: se compatível com controle/ownership, `HANDOFF_TRANSITION(state=ACK,writer_role=<papel>)` antes de assumir; em seguida **executar a próxima ação concreta**; somente após artefato/efeito realmente produzido e persistido emitir `DONE`. Falha material comprovada `FAILED` com diagnóstico e próximo responsável. Não converter leitura/ACK/patch em RESULT científico.
- A transição de HANDOFF, recibo e WORK devem ser correlacionados pelo mesmo `handoff_id`, `request_id`, `thread_id`, `entity_ref` e revisão; nunca recriar identidade em retry.
- Operador (EXECUTOR) responde ao Cientista (LEARNER) com resultado/artefato concreto ou bloqueio demonstrado. Engenheiro remove dependência e passa referências verificáveis. Crítico revisa independentemente depois do RUN quando o contrato pedir. Pítia coordena pendências sem executar ciência; Sentinela verifica atrasos e Guardião investiga falhas de entrega.

## 3. Writer e readback atrasado
1. Início do pulso N: primeiro reconcile `PENDING_WRITE` deixado por **qualquer papel** no pulso anterior, conferindo identidade + receipt de envelope/efeito + entidade efetiva na geração atual da Tower. Um recibo `APPLIED` sem efeito correspondente exige investigação; STAGED ou DELIVERED não equivalem a APPLIED.
2. Execute trabalhos autorizados. Ao fim do pulso N, envie envelopes idempotentes para a **entrada privada autenticada** declarada no CONTROL, uma vez por identidade, preferindo arquivo JSON UTF-8 create-only no Drive `NEXO_INBOX` e readback de bytes/MIME/parent. Ausência de transporte = PENDING/DELIVERY_UNAVAILABLE, nunca aplicado. **Não aguarde Writer para finalizar a rodada**.
3. Pulso N+1: a próxima automação cronologicamente disponível, de qualquer papel, lê recebimentos anteriores. Confirma somente com readback efetivo; caso ainda pendente, não duplica, continua trabalho independente. Após persistência real ou rejeição terminal, atualiza estado derivado. Reenvio só se comprovado permitido pelo protocolo idempotente e após busca no inbox/processed/ledger.
4. Intermediário `PENDING_WRITE` não conta como RUN/RESULT canônico, nem como DONE. Confirmação eventual pelo próximo pulso é **reconciliação operacional**, não dispensa os requisitos de persistência e readback terminal do CONTROL para ações materiais.
5. Se nenhum runtime tiver acesso à rota Writer, anote `WRITE_DELIVERY_UNAVAILABLE` e continue tarefas somente leitura/compute cuja segurança permita; não contorne ACL com Git público ou overwrite direto da Tower.

## 4. Tetos por pulso e segurança científica
- `EXECUTOR`: **até 10 TESTs científicos materialmente executados por pulso**, observando tempo e capacidade efetivos. Teste conta somente com computação real; RUN/RESULT passa a confirmado apenas com Writer e readback em pulso seguinte (ou quando possível); entrada na fila, smoke, patch e retry não contam.
- `LEARNER`: **até 5 unidades materiais de definição/triagem científica por pulso**, incluindo pedidos recebidos e propostas de campanhas; não executar ciência fora do papel.
- `ENGINEER/ADVISOR`: **até 5 reparos/entregas técnicas por pulso**, incluindo pedidos de outros papéis; não executar RESULT científico em lugar do EXECUTOR.
- Tetos **não são metas mínimas**, não aumentam paralelismo, nem exigem cinco novos testes se houver trabalho já definido. `CONTROL.role_queue_limit=5` continua apenas um limite de **projeção**, não confunda com esses novos tetos. Qualquer conflito com CONTROL atual deve ir ao Writer/autoridade humana, não ser sobreposto por prompt.

## 5. Novas campanhas do Cientista
- LEARNER pode criar `ROADMAP_CHARTER` com `status=PROPOSED`, questão nova, null/rival, literatura, dedupe, fontes públicas, budget/stop, segurança, escopo e impacto. Sem `mandate_id` que promova automaticamente; não enviar `APPROVE_CHARTER` em nome de Dener.
- Atlas privado exibe cartão da Tower `roadmaps/<id>.json` com `charter.status=PROPOSED`. Dener aprova/rejeita pela superfície humana autenticada já existente (`OPERATOR_INTENT APPROVE_CHARTER/REJECT_CHARTER`) e o Writer persiste/relê. Até então nenhuma admissão de TEST prospectivo sob essa carta.
- PEER continua **excluído de todas as projeções do Atlas**, tanto privada quanto pública. Não exponha conteúdo de handoffs PEER no mural privado.

## 6. GitHub Actions público
- Resolver primeiro no CONTROL a identidade **exata** do repositório público de execução autorizado, permissões e política do custo. Lista de repositórios verificados não define, por si só, um destino para testes.
- Capacidade `Actions disponível` exige provas de job real em runner padrão, quota e custo gratuitos e workflow técnico compatível com o TEST; um job de publicação ou Writer bem-sucedido não comprova a likelihood científica.
- CONTROL observado em 11/10/2026: `github_actions_science_role=DISABLED_BUDGET_EXHAUSTED` e `github_actions_reenable_policy=EXPLICIT_OPERATOR_ONLY_AFTER_BUDGET_RESET_OR_PLAN_CHANGE`. Portanto, nenhuma execução científica é despachada em Actions até reconciliação canônica explícita pelo Writer e autorização adequada; preserve execução local.
- Nunca compartilhe Tower privada, PEER privado, secrets, auth/paths internos, ou dados não-publicados nos logs e artifacts de repositório público. Preserve id/commit/inputs e verifique run original antes do retry.

## 7. Critérios de aceitação
- Uma solicitação LEARNER -> EXECUTOR aparece no mural privado (quando não PEER), tem `ACK` do destinatário e depois `DONE` com evidência concreta ou `FAILED` com motivo, **após o Writer aplicar cada transição**.
- Pulso N entrega proposta; pulso N+1 confirma somente se Tower/recibo refletir efeito. O mesmo request não é aplicado duas vezes.
- Proposta de campanha tem carta privada e continua inativa até ação humana autenticada; publicações não são inferidas.
- Tetos e isolamento entre papéis preservados; GitHub indisponível mantém a rota local, não paralisa frentes independentes.
