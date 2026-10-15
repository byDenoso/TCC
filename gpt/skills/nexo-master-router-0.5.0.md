---
name: nexo-master-router
description: Raiz operacional do NEXO; usar em pesquisa, estado e manutencao NEXO, nao em toda conversa comum.
version: 0.5.0
---

# NEXO: raiz

Para postura geral, aplicar `AGENTS.md` da raiz. Para operação, aplicar `automations/ROLE_CONTRACT_V1.md`. Esse contrato comum resolve referências históricas a seis papéis, receita obrigatória e leitura global por pulso nos módulos antigos; o schema continua definindo os envelopes aceitos. Documentação não altera Tower, deploy ou agenda por si. O corte das sete Tasks foi aplicado em seus prompts, com validação do inventário vivo.

## Autoridade
**Política:** pseudo-MCP privado no Drive, `MCP_RUNTIME_CONTRACT_V1.json`, ID `1XO_V7Cmb75l8zSWCIsaoQGFRssLwLqMB`, sobretudo `control_retirement_transition.current_verified_rules` e `policy_import`. **Estado e evidência:** Tower LIVE privada no Drive, arquivo `1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z`. `CONTROL.json` interno é histórico/compatibilidade técnica, nunca gate de execução científica. Writer técnico único e serializado aplica mutações do JSON canônico, com readback; HEAD-PATCH-readback de JSON bruto não é CAS atômico entre máquinas. GitHub é código/proveniência; inventário vivo é agenda/habilitação. Atlas, MCP hospedado e índices públicos são derivados e não substituem a Tower. A projeção pública `tower-projection/projection.json` foi retirada: não usar nem reativar. PEER excluído dos Atlas público e privado.

MCP é auxiliar pela conexão instalada. Falha de binding não prova Tower ausente nem suspende Drive já autorizado. Não contornar 401/403 ou ampliar acesso. Não colocar credenciais em prompts, arquivos ou logs. Compute/orçamento seguem a capacidade real e autorização do runtime/runner; um campo histórico do CONTROL não prova bloqueio de toda a plataforma Actions.

## Operar
Resolver identidade/revisão uma vez por revisão e ler contexto/cursor do papel. Sem delta, verificar obrigações abertas; contexto válido dispensa mural/status/handoffs globais redundantes. Falha de leitura não é NO-OP. Blocker pertence ao item; preparo independente autorizado continua.

Novos artefatos científicos são CREATE-ONLY na pasta privada CAMP_ID, com conteúdo não vazio e readback verificado; sua produção não exige Writer/inbox antes da evidência. Receita formal é opcional na rota direta autorizada. Faltas administrativas não dispensam dados, implementação fiel, critério prospectivo, capacidade real e autorização. Preserve contratos congelados, proveniência, reservas compartilhadas, idempotência e revisão científica independente. Runner legado de receitas continua exigindo o que realmente executa; não envie TEST direto a esse runner.

Pacotes pequenos em Docs nativos usam `NEXO_ARTIFACT_PACKAGE_V1` quando suportado pelo bundle implantado: preparar/preencher/reler fora do inbox, mover evidência completa para a campanha e entregar proposta individual com referências/hashes ao Writer. Ver `gpt/PROPOSAL_SCHEMA.md`; até 128 KiB de bytes originais por pacote. Chat interativo não prova capacidade agendada; instalação, acesso de leitura do Writer e canário de cada Task são verificações distintas. Não confundir `producer_role` do pacote com role autorizado.

Reutilizar entidades científicas e evitar duplicação de TEST/event_id; não multiplicar WORK/HANDOFF/BOARD_POST. ACK não é DONE. Distinguir LOCAL_ONLY, ARTIFACT_PERSISTED, PENDING_TOWER_APPLICATION, TOWER_APPLIED_READBACK, REVIEWED e ATLAS_PUBLISHED. Recibo público ausente não autoriza reoferta privada. Relatar efeito material, erro acionável ou NO-OP verdadeiro; não fabricar produção.

## Módulos sob demanda
- Estado, investigação e histórico: `nexo-workspace/SKILL.md`.
- Conectores/transporte: `nexo-connectors-0.5.0.md` e `gpt/PROPOSAL_SCHEMA.md` na raiz do repositório.
- Operações: `nexo-operations-0.5.0.md`, `nexo-closed-loop-0.5.0.md` e `automations/OPERATING_CONTRACT.md`, somente a seção necessária.
- Autonomia: `nexo-autonomy-1.0.0.md`; pacote preparado não ativa mandato nem amplia permissão.
- Literatura e papers: skills vigentes pertinentes no Drive; confirmar identidade e ler antes de alegar conformidade.

Agentes não administram suas agendas. Push, merge/deploy, publicação/submissão, gastos, exclusão e permissões seguem autorização humana explícita. Nenhuma mudança neste arquivo comprova implantação, atualização da Tower ou teste científico.
