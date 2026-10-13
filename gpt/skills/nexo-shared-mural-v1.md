---
name: nexo-shared-mural
version: 1.0.0
description: Contrato operacional de atendimento entre automações NEXO, vinculado aos registros privados da Tower e ao Writer único.
---

# NEXO — atendimento entre papéis (Mural v1)

**Âmbito:** todas as automações de coordenação do NEXO. Aplica-se em cada pulso, sem alterar agenda, modelo, habilitação, orçamento, mandato humano, contratos científicos, ownership ou controles de privacidade. O contrato efetivo do `CONTROL.json` da Tower prevalece.

## Invariantes

- Fonte: Tower privada canônica no Drive, `CONTROL.json`, bootstrap, `evolution/board.json`, `execution_recovery`, índices e eventos de handoff, Inbox/processed e recibos. Projeções e memória são derivadas. Confirmar ID, revisão, leitura bruta quando necessário. `DEGRADED_READ` não é fila vazia.
- Somente o Writer aplica mutações, com CAS/readback. Entrada autorizada é JSON UTF-8 bruto em `NEXO_INBOX`, usando `file_id` de snapshot exportado com `source_file_ref` ou `file_uri` legítimo no Drive. Nunca contornar ACL, usar Git público/Google Doc como caixa postal ou simular entrega a partir de arquivo local.
- PEER fica excluído do Atlas público e privado. Sem divulgação privada/pública por recado. Actions científico continua vedado se `github_actions_science_role=DISABLED_BUDGET_EXHAUSTED`. PR/CI de outro workflow não remove a trava.
- BOARD_POST é conversa privada; HANDOFF é transferência de ownership entre `LEARNER|ADVISOR|EXECUTOR|DAILY|EMERGENT` (remetente `DIRECTOR` quando previsto). `ENGINEER` usa alias `ADVISOR` apenas para HANDOFF. `PITIA`, `REFEREE_1`, `GUARDIAO`, `SENTINEL` não emitem ACK/DONE de outra role. O schema vigente define destinatários válidos de BOARD_POST, sem inventar papel.

## Algoritmo por pulso

1. **Reconciliar a escrita antes do trabalho novo.** Para todos `PENDING_WRITE` conhecidos, inclusive de outros papéis, conferir identidade e bytes no Inbox, processed, `OPERATION_RECEIPT_V1` e efeito real na Tower. Estados distintos: `LOCAL_ONLY` (sem transporte), `DELIVERED` (arquivo e hash relidos), `APPLIED` (receipt + efeito material revisado), `REJECTED_TERMINAL`, `DEFERRED_DEPENDENCY`, `RETRYABLE_TRANSPORT`. Um receipt de envelope não prova cada item do lote. Nunca reenviar com nova identidade só por latência.
2. **Ler tudo que é endereçado ao papel.** Consultar o `evolution/board.json` completo, mensagens `to=PAPEL|ALL`, respostas por `reply_to`, refs e revisões. A visão reduzida do bootstrap ou `_board_view` não constitui fila completa. Conferir ofertas e eventos do handoff para a runtime role. Quando o snapshot contém 300 posts ou há suspeita de poda, marcar a completude como *não demonstrada*; buscar evidência histórica na Tower/receipts/processed antes de afirmar ausência. Não tratar posts expirados/resolvidos como demandas novas; também não apagar um trabalho ainda ativo só porque seu lembrete expirou.
3. **Classificar antes de repetir.** Por pedido: `post_id`, thread/ref, autor, destinatário, objeto, revisão, ação solicitada, condição real de conclusão, estado e proprietário atual. Conferir resultados e artefatos já existentes para evitar resposta duplicada. `ACK` sem execução ou `DONE` sem artefatos/readback é inconsistência, não sucesso.
4. **Atender ou escalar com efeito.** O destinatário faz a ação autorizada que couber na rodada; se bloquear, registra a *primeira dependência real*, owner e menor passo legitimamente executável, e continua outros itens independentes. Para todo pedido válido recebido, emitir `BOARD_POST` privado com `reply_to` do post de origem e `refs` que comprovem o efeito ou a causa. Resposta genérica de cortesia ou relatório sem envio privado não fecha o pedido. Reencaminhamento usa mesmo thread/ref e dono correto, sem forjar ACK/DONE, sem ping repetido na mesma revisão.
5. **Fechar apenas após verificação.** O destinatário pode enviar `BOARD_POST` com `payload.resolve:[post_id]` só depois de resposta/evidência aplicada ou item materialmente resolvido. Não fechar um pedido ainda pendente de execução apenas por triagem ou envio de aviso. `HANDOFF_TRANSITION ACK` somente pelo papel destinatário após readback; `DONE` somente após resultado/artefato e aplicação canônica. Writer retém ownership até o ACK efetivo.
6. **Entregar e continuar.** Exportar JSON UTF-8 e confirmar nome/ID/parent/MIME/tamanho/SHA-256 do download bruto. Se houver `file_id` válido, usar `files.manage_library` com `source_file_ref` para a pasta privada autorizada; se houver `file_uri` legítimo, `upload_file` do Drive. `container_session_unavailable` impede essa ponte local, não prova falha do Drive. Sem exportação válida, manter `LOCAL_ONLY` e a dependência, sem fallback inseguro. Não esperar a aplicação pelo Writer no mesmo pulso; o próximo papel reconcilia por ID. Não criar tráfego para simular progresso.
7. **Saída verificável.** Informar demandas reais recebidas, atendidas, respondidas e bloqueadas, artefatos/recibos efetivamente lidos, próximas ações e donos, itens independentes restantes e motivo da parada. Não confundir comunicação, execução científica, revisão e publicação.

## Prioridade sem burocracia

Atender primeiro pedidos materialmente acionáveis que destravam execução/revisão existente, depois novos trabalhos autorizados. Nunca impor teto artificial à leitura/triagem do mural; capacidade real de runtime e orçamento regula quanto trabalho cabe no pulso. Uma nova carta permanece `ROADMAP_CHARTER PROPOSED` até aprovação autenticada do Dener ou mandato vigente comprovado. Uma síntese editorial privada exige TEST→RUN→RESULT→REVIEW→claim, proveniência/hash, nulos/contrários/limites e independência: variantes correlacionadas do mesmo dataset não são replicações. Autor não revisa o próprio RESULT; Guardião não substitui Crítico; ninguém publica por simples recado.

## Ponto de atenção da implementação

Na revisão pública do Writer de 12/10/2026, `compose_board_snapshots` ainda trunca snapshots a 300 mensagens e `_board_view` mostra no máximo 40; isso **não autoriza** concluir que todos os pedidos históricos foram vistos. O isolamento fail-closed de mensagens privadas na projeção é tratado separadamente na PR #154 e só conta como corrigido após revisão independente, integração e readback implantado. Antes disso, manter contenção e não transformar recados internos em fonte pública.
