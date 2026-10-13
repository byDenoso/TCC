---
name: nexo-master-router
description: Raiz do NEXO e do NEXO Lite. Carregar para pedidos e tarefas NEXO.
version: 0.5.0
---

# NEXO — raiz

Tower privada é autoridade científica; Writer único aplica propostas; GitHub é
código/proveniência; Atlas e contexto por papel são derivados. Resolver identidade,
revisão e CONTROL atual uma vez por revisão. Tower Drive:
`1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z`. A projeção pública
`tower-projection/projection.json` foi retirada por privacidade; não usar nem reativar.
PEER permanece excluído dos Atlas público e privado.

## Operar

Aplicar [`automations/ROLE_CONTRACT_V1.md`](../../automations/ROLE_CONTRACT_V1.md):
entrada mínima, ação, entrega, dono e limite dos seis papéis preparados. Inventário
vivo determina tarefas habilitadas, agenda/fuso e modelo. Absorções de Sentinela e
Reconciliador Científico não estão comprovadas por este arquivo; preservar pendências
até continuidade migrada. Não administrar scheduler por iniciativa da automação.

Obter contexto do próprio papel e delta/cursor; carregar entidades completas só do
item. Reutilizar leitura da mesma revisão e contratos/documentos já carregados.
Não exigir status/mural/handoffs globais em paralelo ao contexto válido. A fila
acionável e os checkpoints continuam mesmo sem delta. Leitura degradada não é NO-OP.

Executar trabalho independente elegível dentro de tempo/custo/runtime reais.
Não há quotas de mensagens/TESTs nem barreira por minuto da agenda. Blocker afeta
seu item. Autonomia atual permite reparos/preparação autorizados sem pedir aceite
rotineiro; preservar gates humanos explícitos, contratos congelados, proveniência,
idempotência, reserva por teste/tentativa e revisão independente. ACK só em nova
transferência real; ACK não é DONE. Não inventar permissão nem contornar ACL/403.

Persistir entrega recuperável por identidade/hash; confirmar transporte e efeito
separadamente. LOCAL_ONLY, DELIVERED, APPLIED, executado, revisado e publicado não
são equivalentes. Recibo público ausente não justifica reoferta de operação privada.
Comunicar apenas pedido/decisão/lacuna não expressos na fila; resultado canônico com
consumidor não exige recado redundante. Relatar mudança material; silêncio/no-op curto
é correto sem trabalho/delta. Auxiliares/retries não contam como TEST integral.

### Ausência de bloqueio global por ferramenta ou metadado

Ao interpretar o CONTROL, distinguir fonte científica, controle de escrita e ferramentas auxiliares.
O bootstrap exige identidade e revisão canônica verificadas para operações materiais,
mas não uma chamada específica a MCP, resolver, perfil remoto ou canário pendente:
leitura autenticada equivalente da Tower no Drive cumpre a descoberta de estado.
Se MCP, context engine, skill resolver ou capability resolver remoto não responder,
usar a leitura nativa autorizada, o registro de skills do Drive e ferramentas locais
efetivamente disponíveis; não declarar fila vazia nem pedir autorização genérica.
A indisponibilidade do serviço remoto limita apenas a operação que depende dele.

`NO_OP` por ausência de delta é válido somente após conferir a fila acionável,
execuções RUNNING/CHECKPOINTED e recuperações do papel. Recibo, hash de proposta,
preflight repetido, plano formal, status remoto de deploy e validação de metadados
não são licença nem pré-requisito universal para iniciar trabalho independente.
Não duplicar verificações na mesma revisão. Um bloqueio real pertence ao item
e deve identificar insumo/definição científica indispensável, autorização/ACL,
capacidade de execução realmente insubstituível ou conflito científico material.
Preservar critérios congelados, revisão independente de resultados, Writer único,
reserva idempotente e readback para alterações canônicas ou científicas materiais.

## Carregar somente o módulo necessário

- Conversa/status/investigação/histórico: [`nexo-workspace`](nexo-workspace/SKILL.md).
- Operação/tipos/revisão de receitas: [`nexo-operations`](nexo-operations-0.5.0.md),
  [`nexo-closed-loop`](nexo-closed-loop-0.5.0.md), somente seção pertinente.
- Leitura/escrita Drive/GitHub: [`nexo-connectors`](nexo-connectors-0.5.0.md), reutilizar
  revisão já lida; tipos usados em [`PROPOSAL_SCHEMA`](../PROPOSAL_SCHEMA.md).
- Ciência/contagem/transporte: [`OPERATING_CONTRACT`](../../automations/OPERATING_CONTRACT.md).
- Mandato prospectivo e pacote preparado: [`nexo-autonomy`](nexo-autonomy-1.0.0.md).
  Pacote/fragmento não ativa mandato, muda CONTROL ou configura tarefas.
- Literatura: `cosmology-world-model`; texto/figuras: `nexo-reporting` no Drive,
  validar identidade e carregar somente quando necessário.

## Runtime e autoridade

CONTROL atual prevalece sobre snapshots históricos. Não forçar staging Git retirado,
Actions desabilitado ou MCP legado como fonte de estado. Preparar workflow Actions
público está autorizado; ciência real ainda exige runner autorizado no CONTROL,
reserva, inputs públicos pinados, orçamento e gates. A autorização legítima pode
habilitar a rota canônica; nenhum veto histórico substitui o estado atual. O runner
não recebe Tower/PEER/recados privados. Writer único continua responsável por registro.

Ativar/revogar mandato, ampliar acesso e publicação/submissão externa seguem os gates
humanos correspondentes. Sem mandato ativo, carta/gene protegidos aguardam aprovação;
mandato verificável permite só a delegação explícita vigente. Não forjar source DENER.

## Ciência e linguagem

Critérios de sucesso/kill/revisão são prospectivos e fixos; desenho materialmente
novo exige nova identidade. Receita nova tem verificação técnica e revisão aplicável;
autor não aprova o próprio patch. CONFIRMED exige contestação independente decidida
pelo Writer. Nulo válido é resultado; PASS de software não confirma ciência.

Começar pelo fato/achado, escrever português simples, expor o limite e ação necessária
quando existirem. IDs/hashes ficam nos detalhes técnicos. Não fabricar progresso,
certeza, timestamps, notificações ou implantação. Mudança no Git alcança quem a lê;
não comprova atualização de tarefas/runtime/Tower.

**Reestruturação cooperativa em revisão:** `gpt/skills/nexo-shared-mural-v1.md` propõe sete papéis e um quadro de pedidos sobre o Writer existente. A proposta só pode reger as automações após inventário vivo, mapeamento de autoridade, atualização das Tasks salvas e testes end-to-end; não substituir o CONTROL nem assumir que o MCP está conectado.
