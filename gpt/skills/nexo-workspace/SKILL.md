---
name: nexo-workspace
description: Operar a conversa do Dener como interface da Tower e das dez automações NEXO existentes. Usar para status, ideias e testes científicos, resultados antigos, investigação de falhas, comparação com literatura, manutenção e verificação de automações. Reutilizar GitHub, Drive, Writer e projeção; preservar critérios científicos e verificar cada afirmação de conclusão.
---

# Workspace operacional do NEXO

## Inicialização
Ler a raiz e a interface atuais, salvo se já lidas nesta conversa:
- https://raw.githubusercontent.com/byDenoso/TCC/main/gpt/skills/nexo-master-router-0.5.0.md
- https://raw.githubusercontent.com/byDenoso/TCC/main/gpt/skills/nexo-lite-0.5.0.md

Usar a intenção da mensagem; não apresentar menus. Abrir somente as fontes exigidas pelo pedido. Reutilizar leituras quando a revisão não mudou. Consultar `NEXO Lite/pendentes` e o mural para devolver resultados ao Dener, sem interromper assuntos alheios ao NEXO com ruído operacional.

## Autoridade por assunto
- Ciência: Tower, entidades e evidências; projeção como leitura derivada.
- Agenda e tarefas habilitadas: inventário vivo da ferramenta de automações. O workspace atual tem dez tarefas, confirmado por Dener. Campos antigos com quatro bindings ou cinco tarefas não substituem esse inventário. Não inventar que sejam uma camada interna ainda ativa.
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
Ler a projeção em https://bydenoso.github.io/Pantheon/tower-projection/projection.json . Se a ferramenta não abrir, ler o arquivo canônico via Drive; erro de acesso não prova fila vazia. A Tower é o arquivo JSON `1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z`, não uma pasta. Confirmar metadados antes de baixar.

Para análise local, usar a cópia autenticada e o bundle utilizado pelo workflow `byDenoso/Pantheon@main:.github/workflows/nexo-writer-robot.yml`. Inspecionar antes de executar. Rodar somente leituras como `verify`, `status` e `frontier` na cópia local. Conferir stderr e seções esperadas: saída zero com mensagem `skipped` é leitura degradada. Identificar projeção reconstruída como local, sem alegar publicação.

Localizar no Drive as pastas `cosmology-world-model`, `nexo-reporting` e `NEXO Lite`; ler a identidade do SKILL.md antes de usar. Preservar pastas existentes. Pesquisar histórico por referências, não por semelhança de nomes apenas.

## Gravação e acompanhamento
Ler `nexo-operations` e `gpt/PROPOSAL_SCHEMA.md`. Preservar o fluxo atual:
`byDenoso/TCC@nexo/dispatch-runtime:nexo_persist/requests/<stable_id>.json` -> relay -> `nexo-inbox` -> Writer -> Tower -> projeção.

Usar stable_id determinístico em `[a-z0-9-]`, com até 60 caracteres; reutilizar no retry. Conferir fila e recibos antes de repetir. Conteúdo diferente com a mesma identidade é conflito. Releitura do staging prova somente staging; confirmar separadamente relay e aplicação.

Enviar pelo Git público somente propostas sanitizadas permitidas. Manter dados privados, notas pessoais, handoffs privados e transcrições no Drive privado. Não gravar Tower diretamente. Em recusa de autorização, acesso ou política, interromper a ação e relatar; não contornar trocando formato ou serviço. Retentar apenas falhas técnicas pelos caminhos autorizados.

Registrar Diretriz aceita em `NEXO Lite/pendentes`, com ID estável, objetivo, referência da proposta, estado comprovado e próxima verificação. Não prometer data de resultado sem evidência. Memória nativa indisponível não impede a nota operacional autorizada no Drive.

## Dez tarefas: entrada, saída e consumidor
Preservar identidades, papéis, horários, fuso e gatilhos existentes; inventariar antes de alterar. Não criar, pausar ou apagar tarefa para corrigir contagem.
| Tarefa | Gatilho BRT | Entrada -> saída | Próximo consumidor |
|---|---|---|---|
| Cientista | :05, 05h-23h | mapa, quedas, diretrizes -> hipóteses e famílias | Writer e Operadores |
| Pítia | :12, 05h-23h | resultados e roadmaps -> pensamentos com refs | Cientista e Dener |
| Operador A | :20, 05h-23h | início da READY -> bindings/pedidos de receita | Writer e Engenheiro |
| Crítico | :35, 05h-23h | positivos -> contestações independentes | Writer e Operadores |
| Engenheiro | :45, horas pares 06h-22h | circuitos/pedidos -> PR e smoke | Revisor e Dener; depois Operadores |
| Operador B | :50, 05h-23h | fim da READY e staging -> bindings sem duplicar A | Writer e Engenheiro |
| Guardião | :57, 05h-23h | saúde e travas -> integridade e reatribuição | papel responsável e Dener |
| Bom dia | 07h | resultados, mural e pendentes -> resumo | Dener |
| Sentinela | 07h30 | literatura/releases -> contestação, dado ou sinal | Cientista e Operadores |
| Revisor de PR | evento de PR | diff de receita -> revisão e sinal | autor e Dener |

Tratar essa tabela como mapa de integração, não configuração do agendador. Confirmar agenda viva. Cobrança por atraso considera horários ativos. Proteger o Revisor: sem acesso ao conjunto completo de gatilhos, não regravar o prompt nem substituir evento por polling. Não interpretar `next_run_time` ausente como desativação. `last_run_time` não prova aplicação científica.

Ler mural e propostas pendentes para evitar duplicatas. Atraso ou falha de leitura produz diagnóstico; NO-OP somente com leitura válida e ausência de trabalho. Contestações precedem testes novos. Metas de vazão não autorizam inventar testes ou dados.

## Critério de entrega
Distinguir: configurado, proposto, entregue ao inbox, aplicado, executado, revisado e confirmado. Nulo científico exige execução válida. PASS de software permanece operacional. Preservar critérios congelados, multiplicidade, independência da contestação e limites do claim.

Reproduzir falhas, fazer a menor mudança, testar e reler. Informar como desfazer mudanças relevantes. Não criar tickets ou documentos intermediários por padrão. Uma instrução no Git alcança os consumidores que a carregam; não afirmar instalação de plugin, alteração administrativa global ou memória nativa sem confirmação da ferramenta.
