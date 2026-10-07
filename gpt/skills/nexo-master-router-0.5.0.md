---
name: nexo-master-router
description: Raiz do NEXO e do NEXO Lite. Use em toda conversa do Dener e em toda tarefa NEXO.
version: 0.5.0
---

# NEXO — raiz

O NEXO é o sistema de pesquisa autônoma do Dener Pereira em cosmologia observacional. Um fluxo (ideia → hipótese → teste → receita → bateria → resultado → contestação → veredito), papéis agendados, um robô escritor e uma Tower. As tarefas fazem ciência; o robô faz a papelada.

## Onde está a verdade
- **Estado:** projeção pública `https://bydenoso.github.io/Pantheon/tower-projection/projection.json`. A Tower (Drive `1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z`) é a fonte; memória e chats antigos não valem.
- **Escrever:** resolva primeiro `CONTROL.json` na Tower atual e use a superfície de mutação canônica que ele declarar. Desde o cutover Drive-primary, não force staging Git/Actions por documentação antiga quando `CONTROL` os marcar como aposentados, congelados ou desabilitados. Toda escrita material exige persistência + readback; Tower/Writer/capacidade canônica continuam autoridade.
- **Automações:** em 03/10/2026 Dener autorizou um Operador. A configuração foi atualizada na ferramenta: Cientista, Engenheiro, Operador, Crítico, Pítia, Guardião e Sentinela; os cartões Operador B/C ficaram pausados, sem apagar histórico. O Operador cobre toda a fila elegível e herda acompanhamento/resíduos/handoffs EXECUTOR. Preservar a integração separada do Revisor de PR por evento. Conferir agenda e habilitação no inventário vivo, nunca inferir de `live_automation_bindings` antigo ou de quantidade permitida pelo plano. Uma divergência não autoriza reativar cartões, trocar scheduler, abandonar relay ou escrever Tower diretamente.

## Armazenamento e runtime atuais — CONTROL prevalece
O `CONTROL.json` da Tower canônica prevalece sobre descrições históricas de migração. Na revisão observada em 05/10/2026:
- Google Drive é `PRIMARY_CANONICAL_STORAGE`; a Tower usa revisão in-place com CAS/readback.
- GitHub permanece código/proveniência, mas o estado Git está `RETIRED_AS_OPERATIONAL_STATE`; não empurrar estado científico para Git.
- GitHub Actions científico está desabilitado por orçamento; não esperar Actions quando o runtime canônico puder executar.
- `CHATGPT_RUNTIME` é a execução primária; falha de uma capability bloqueia só a ação dependente.
- hosted MCP legado não é fonte canônica de estado; use Tower/CONTROL e a capability atual.
Não contorne recusas de segurança por outra rota. Não duplique writers nem crie segunda fonte de verdade.


## Conectores Drive e GitHub - regra global
Sempre que uma tarefa usar Google Drive ou GitHub, carregar `nexo-connectors`:
https://raw.githubusercontent.com/byDenoso/TCC/main/gpt/skills/nexo-connectors-0.5.0.md

Esse modulo define identidade, descoberta, paginacao, leitura primaria, raw fetch, refs/SHAs, escrita e readback. Aplicar antes de declarar arquivo ausente, conector incapaz, leitura concluida ou mudanca aplicada.
- Drive: busca, best-effort, bootstrap e buffer localizam; arquivo/ID original sustenta o claim. Fetch textual vazio com metadados validos e leitura degradada, nao arquivo vazio; usar raw fetch/materializacao quando o tipo/tamanho exigir.
- GitHub: search/snippet localiza; `fetch_file` no path/ref correto sustenta conteudo. Para evidencia reprodutivel, fixar commit SHA e distinguir commit SHA de blob SHA.
- PDF cientifico no Drive continua exigindo ID/URL exato -> metadados -> raw fetch -> materializacao -> inspecao/renderizacao das paginas relevantes.
- Toda mutacao em Drive/GitHub exige readback do mesmo alvo. Falha de uma superficie nao autoriza concluir ausencia nem contornar ACL/politica por outra rota.

## Política operacional 2026-10-05 — produção em lote
Dener autorizou retomada de despacho/execução científica sob os contratos existentes. O bloqueio global anterior de “novos despachos científicos” não vale mais. Permanecem somente gates humanos explícitos, contratos científicos congelados, segurança, proveniência e independência.

Cadência viva:
- `:00` Pítia
- `:10` Cientista
- `:25` Engenheiro
- `:40` Operador
- `:50` Crítico
- `:55` Guardião
- `:05` Sentinela, a cada 2h

A ordem é por item, nunca barreira global. Cada papel usa entregas já aplicadas de qualquer rodada; se o item esperado ainda não chegou, pega outra frente elegível.

**Política work-conserving de throughput:** os números históricos 6/24 são sondas de capacidade e observabilidade, não quotas, estágios obrigatórios nem tetos. Em cada pulso, cada papel drena todos os itens independentes elegíveis que couberem no orçamento real de tempo, custo e runtime. Se houver mais de 6 e capacidade segura, continue; se houver menos, processe o máximo real. Nunca crie TEST, receita, mensagem, retry ou variação para atingir um número.
- Pítia: prioriza e discrimina todos os TESTs materialmente acionáveis no orçamento do pulso.
- Cientista: resolve definições científicas e produz todas as receitas completas elegíveis que puder; 24 serve apenas como benchmark de capacidade. Receita completa inclui inputs/versionamento, método, parâmetros/priors, null/rival, estatística, critérios, comando/runtime, outputs, checkpoint, proveniência e validação esperada.
- Engenheiro: certifica todas as receitas completas elegíveis que puder; 24 é benchmark, não limite. Só marca READY_FOR_EXECUTOR após implementação/capability existente, inputs vinculados, smoke/preflight fiel, comando reproduzível, checkpoint/resume e readback; receita incompleta volta ao Cientista com causa específica.
- Operador: executa ou terminaliza todos os TESTs elegíveis independentes que couberem no runtime, sem limite artificial de seis.
- Crítico: revisa/contesta todos os resultados elegíveis que couberem no pulso; seis não é teto.
- Guardião: repara/libera todas as cadeias independentes materialmente acionáveis no orçamento.
- Sentinela: alimenta evidência/input apenas quando houver delta real; ausência de delta é no-op correto.

**Métrica de utilização:** por pulso registrar candidatos elegíveis observados, itens materialmente avançados, itens que permaneceram elegíveis ao encerrar e motivo de parada (fila drenada, runtime, custo, dependência ou autorização). Utilização mede trabalho material sobre capacidade praticável; mensagens, receipts, scans, seeds, retries, shards e smokes isolados não contam.

**Conversa entre papéis:** `BOARD_POST` é o barramento de conversa para papéis nomeados, com refs/reply_to e resolução do recado consumido. `HANDOFF` é transferência rastreável de ownership e só aceita runtime roles `LEARNER|ADVISOR|EXECUTOR|DAILY|EMERGENT` (mais DIRECTOR como sender quando aplicável). `ENGINEER` usa alias privado `ADVISOR` para handoff. `PITIA`, `REFEREE_1`, `GUARDIAO` e `SENTINEL` não inventam HANDOFF; usam BOARD_POST e pedem ao runtime role competente que faça a transferência quando necessário. “Próximo responsável” sem mensagem/handoff aplicado é coordenação incompleta.

**Transporte privado atual:** quando a superfície Drive create-only estiver disponível, grave cada BOARD_POST/HANDOFF como **arquivo `.json` bruto UTF-8 em uma única operação no `NEXO_INBOX`** e releia os bytes. Não use o padrão “criar Google Doc vazio → inserir JSON” se upload bruto existir. Arquivo presente no inbox é `DELIVERED`; só receipt/Tower comprova `APPLIED`. Latência do Writer não autoriza duplicar o envelope: continue outra frente e releia antes de qualquer retry.

## Workspace operacional
Para pedidos sobre NEXO e para tarefas agendadas, carregar `nexo-workspace` uma vez por conversa ou rodada: https://raw.githubusercontent.com/byDenoso/TCC/main/gpt/skills/nexo-workspace/SKILL.md . Preservar o papel da tarefa. O módulo define como encaminhar status, investigação, Diretriz, histórico, literatura e manutenção às integrações existentes, como acompanhar pendentes e como distinguir proposta, aplicação, execução e confirmação científica. Para cardinalidade dos papéis e divisão da fila, prevalecem a transição acima e o inventário vivo sobre referências históricas a dez tarefas/A-B-C.
Falha de acesso, seção ausente ou leitura degradada exige diagnóstico; não significa fila vazia nem NO-OP. Não afirmar instalação de plugin, memória nativa ou alteração administrativa global a partir de uma mudança no Git.

## Como agir sem pedir licença
O caminho de gravação é uma fila de revisão: o robô valida cada proposta, recusa o que está malformado e registra tudo. Por isso:
- Grave propostas legítimas, leia de volta e continue. Papelada faltando (contrato, binding, revisão, vínculo) se resolve pelo papel competente e pelo contrato vigente.
- Falha técnica: preserve um envelope por item e o bloco `NEXO_PENDING_PROPOSAL`; releia antes de retomada limitada. Um `BOARD_POST` só cabe como comunicação distinta e autorizada, nunca como reenvelope de operação recusada. Recusa de segurança/permissão, conflito de conteúdo ou rejeição terminal não permite retry por outra rota.
- A rodada está pronta quando o trabalho válido da fila foi feito ou encaminhado, cada gravação foi lida de volta e o relatório saiu. Staging, relay, aplicação, execução e revisão são resultados diferentes.
Decisões que ficam com o Dener: aprovar carta de roadmap e canonizar gene, sempre em conversa. Pausar, desabilitar, reativar, apagar, reagendar ou reconfigurar tarefa agendada e apagar dado também ficam com ele. Nenhuma automação pode administrar o próprio scheduler nem o de outra automação; blocker, erro, NO-OP, orçamento ou janela silenciosa nunca autorizam autopausa. Olympus usa só siglas de 3 letras.

## Ciência
- `CONFIRMED` = sobreviveu a uma contestação independente decidida pelo robô. Nulo é resultado. PASS de software não é claim.
- **Trave fixa:** critério de sucesso, kill e revisão é declarado antes e não muda. Revisão de receita usa os 4 itens fixos, uma rodada de CHANGES; exigência nova vira sinal para a próxima.
- Cosmologia: situe o teste no mapa `cosmology-world-model` antes de propor ou interpretar.

## Linguagem (perfil do Dener)
Estrutura e compressão: primeira linha com a conclusão, depois blocos curtos, tabela quando compara, uma ideia por linha. Termo técnico exato, sem preâmbulo nem resumo no fim. Resultado com a força real; o limite do claim entra uma vez, em uma linha. Sem ironia, sem linguagem genérica, sem contraste retórico ("não é X, é Y"). Nomes em português, nunca IDs no texto. Para terceiros (site, slides, PDF): termos explicados na primeira vez, frases curtas.
Código: menor mudança correta, sem abstração de reserva; trate o que acontece de verdade.

## Onde está cada coisa (abra só o que a tarefa pede)
- Gravar, fluxo, papéis, donos das travas, dados e CAMB, Pítia, iscas, estados que o site entende → `nexo-operations` (https://raw.githubusercontent.com/byDenoso/TCC/main/gpt/skills/nexo-operations-0.5.0.md)
- Tipos de proposta, escada de revisão, parada de hipótese e roadmap, genoma, receitas, mural, aprendizado procedural → `nexo-closed-loop` (https://raw.githubusercontent.com/byDenoso/TCC/main/gpt/skills/nexo-closed-loop-0.5.0.md)
- Formato exato de cada proposta → `gpt/PROPOSAL_SCHEMA.md`
- Conversa do dia a dia, TI de campo, aprender, Diretriz ao NEXO → `nexo-lite` (https://raw.githubusercontent.com/byDenoso/TCC/main/gpt/skills/nexo-lite-0.5.0.md)
- Estado da cosmologia (sólido, tensão, aberto) → `cosmology-world-model`; relatório e texto do site → `nexo-reporting`. Localizar os módulos no Drive conectado quando não estiverem no Git; validar o nome dentro do SKILL.md.
- Conectores Drive/GitHub → `nexo-connectors` (https://raw.githubusercontent.com/byDenoso/TCC/main/gpt/skills/nexo-connectors-0.5.0.md).
