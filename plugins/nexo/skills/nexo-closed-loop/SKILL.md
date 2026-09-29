---
name: nexo-closed-loop
description: Carregue em toda tarefa agendada do NEXO e sempre que a conversa tocar carta de roadmap, campanha central, contestação e revisão de resultado, receita, critério de parada, genoma, aptidão, diário da Pítia, iscas, mural ou pressão de emergência. Define os tipos exatos de proposta e como hipótese e roadmap terminam. O fluxo e os donos estão no `nexo-master-router`; aqui ficam os detalhes de execução.
version: 0.4.0
---

# NEXO — ciclo fechado (detalhes)

O fluxo, os cinco papéis, a carga por fila, a cobertura cruzada e os donos de cada trava estão no `nexo-master-router` (0.4.0). Esta skill traz o que o router não repete: tipos de proposta, escada de revisão, parada de hipótese e roadmap, genoma, aptidão, iscas, mural e receitas.

## 1. Estado de partida
Comece toda rodada pelo estado atual da Tower (`status` quando o bundle do escritor está local; senão a projeção pública): portão do Dener, filas de referee, progresso das cartas (`stop_reached`, `review_due`), genoma (`canonical`/`canary` por gene), iscas, `arm_for_this_run` (`canary` em hora UTC ímpar), `emergence` (laços atrasados), `watchdog` (papéis quietos), `board` (recados, §9) e `recipe_health` (circuitos abertos). Use o valor do gene do seu braço.

**Propriedade da escrita.** Papéis agendados produzem propostas; só o robô escritor grava a Tower. Grave como o router descreve (staging → relay → inbox) e leia de volta. Proposta em staging com o relay na fila conta como durável (`STAGED_PENDING_RELAY`). O robô nunca julga ciência.

**O que o robô faz sozinho a cada rodada (não duplique):** fecha roadmap por SUCCESS/KILL/BUDGET; arquiva cadeias de contestação com mais de 1 nível; mantém testes aposentados fora da fronteira; classifica falha de bateria (transitória e receita quebrada não gastam as 2 chances do teste), abre e fecha o circuito da receita; expande famílias e despacha baterias (até 20 por bateria; com 20 ou menos prontos envia 75%, mínimo 5); despacha qualquer teste READY que tenha `recipe` e `recipe_params`, com os `DENER_DIRECTED` na frente; arquiva rascunho parado há 21 dias; audita se o desenho foi congelado antes do resultado; anota sobrevivência Benjamini–Hochberg (q=0,1); registra papel quieto (`watchdog`).

## 2. Pressão de emergência
`status.emergence.stale` lista laços que passaram do limite (pensamento 6h, sonho 24h, mutação de genoma 48h, aptidão 12h, hipótese nova 6h, resultado 3h, contestação 12h, isca 168h) com o papel dono. Se o laço é seu e há alvo válido, produza um item dele. Sem alvo válido, NO-OP e nomeie o laço; item fabricado polui a Tower mais que laço quieto.

## 3. Campanha central
`RM-DENER-CORE-CAMPAIGN-V1` é semipermanente (`renewable`): prioridade máxima, nunca fecha por orçamento. Toda hipótese diz qual objetivo da campanha serve. Com `review_due`, o Guardião escreve um relatório de rumo (progresso por objetivo, o que travou, o que mudaria) e pergunta ao Dener.

## 4. Tipos de proposta
Envelope `{kind, source, payload, created_at}`. Vários de uma vez: `kind: "BATCH"`, `payload.items: [envelopes]`, até 10 itens, aplicados em ordem.
| Tipo | Quem | Payload |
|---|---|---|
| ROADMAP_CHARTER | Pítia (Learner, para engenharia) | roadmap_id?, title, question, objectives[], scope, data, budget{max_tests,max_days}, stop{success_confirmed,kill_consecutive_refuted}, renewable?, review_every_days?, priority?, rationale, refs[], rival_of? |
| OPERATOR_INTENT `APPROVE_CHARTER`/`REJECT_CHARTER`/`CANONIZE`/`REJECT_CANARY` | **só conversa com o Dener, nas palavras explícitas dele**, `source: "DENER"` | roadmap_id ou gene |
| ROADMAP_CLOSE | Guardião (SATURATION / BLOCKED, §6); o robô fecha SUCCESS/KILL/BUDGET | roadmap_id, reason, final_report (português simples: o que aprendemos, o que segue aberto) |
| HYPOTHESIS_PROPOSAL | Learner; Dener via Lite (`origin_kind: DENER_DIRECTED`, `priority: P0`) | display_name, pergunta, nula, rival, método, dados, previsão, critérios, `hypothesis_id`, `stop{success_criteria, kill_criteria, max_discriminants, independence_requirement}` (§5); com teste pronto: `recipe`, `recipe_params` |
| FAMILY_CHARTER | Learner | family_id, roadmap_id (ACTIVE), recipe existente, template, instances[{label, params}], stop{kill_rejected:2, success_promoted:2}; até 40 instâncias, grade declarada antes; incompleta é descartada em silêncio, releia |
| RECIPE_BIND | qualquer papel que tenha o teste na mão | test_id, recipe, params: liga a receita a um teste existente (DRAFT, READY ou BLOCKED_INPUT); o robô despacha na rodada seguinte |
| DATA_BINDING | Learner, Operador | test_id, inputs[{name, url, format, load, license}], status BOUND/PARTIAL/UNAVAILABLE, note; sem `sha256` (o filtro do ChatGPT recusa hash longo; a receita confere na primeira execução) |
| CONTEST | Refutador (`REFEREE_1`), Pítia sentinela (`SENTINEL`) | test_id, reason, refs, contest_test{question, null, rival, method, data, success_criteria, kill_criteria} |
| VERDICT_REVIEW | Refutador, depois de o teste de contestação rodar | test_id, outcome SURVIVED/REFUTED, evidence, contest_test_id |
| LEARNING_SIGNAL `RECIPE_REQUEST` / `RECIPE_REVIEW` | Operador escreve a especificação; Guardião revisa (§8) | spec{name, inputs, data_sources, statistic, criterion, outputs, tests_served[]} / review{spec_ref, verdict APPROVED/CHANGES, reasons[]} |
| GENOME_MUTATION | Learner (resultado de engenharia CONFIRMED), Pítia | gene, value, current_value, rationale, refs, metric |
| GENOME_ROLLBACK | Guardião | gene, reason, fitness |
| FITNESS_REPORT | Guardião | measurements[{gene?, arm, value, components}] |
| NEXO_THOUGHT | Pítia (grave com `source: PITIA`, também o NOOP) | entries[{kind SURPRISE/QUESTION/DREAM/SELF_PREDICTION/CRISIS/SENTINEL, text, refs[]}], retire[ids]? |
| DECOY_PLANT / DECOY_CALL / DECOY_REVEAL | Guardião planta e revela; qualquer papel chama | commitment / test_id, reason / test_id, secret |
| BOARD_POST | qualquer papel | entries[{to, text, refs[]?, reply_to?, ttl_h?}], resolve[ids]? (§9) |
O robô nunca rejeita em silêncio: duplicata, roadmap fechado e gene da espinha ficam registrados.

## 5. Escada de revisão e parada de hipótese
PROMOTED/SUPPORTED → PENDING_REVIEW → uma contestação independente → **CONFIRMED** se o teste de ataque passa no próprio critério congelado, **REFUTED** se falha (o robô decide sozinho, `FROZEN_ATTACK_CRITERION_V1`). Só CONFIRMED conta para parada e aptidão. Uma contestação por resultado. Resultado positivo de família o próprio robô contesta, com replicação em outra coleção de supernovas. Contestação é um teste NOVO com critérios congelados (nunca uma opinião). Teste de contestação não é contestado (profundidade 1). No mesmo roadmap, contestação pendente roda antes de teste novo. Menu de ataque: teste adversarial (dado embaralhado ou nulo, outra janela ou catálogo), replicação independente e a anotação FDR do robô (`fdr.survives=false` é motivo forte para contestar).
**Toda hipótese termina.** `stop` congelado ao nascer: `success_criteria`, `kill_criteria` (padrão: **2 discriminantes independentes REFUTED**), `max_discriminants` (padrão 4), `independence_requirement`. Uma hipótese sobrevive provisoriamente com 1 positivo e só é *sustentada* depois da escada. Nunca teste variante após variante da mesma ideia até uma parecer boa; a família pré-declara a grade.

## 6. Todo roadmap termina (o Guardião fecha na mesma rodada)
`HIPÓTESE → TESTES → RESULTADOS → CONTESTAÇÕES → DECISÃO → FECHA → PRÓXIMA`. SUCCESS (`success_confirmed` CONFIRMED), KILL (`kill_consecutive_refuted` refutações independentes seguidas) e BUDGET (`max_tests` ou `max_days`) o robô fecha. **SATURATION** (Guardião): nenhum teste restante ou propositável mudaria a decisão. **BLOCKED** (Guardião): todo próximo discriminante válido precisa de recurso genuinamente indisponível; estaciona só esse roadmap. BUDGET e SATURATION não significam que a hipótese é falsa: o valor marginal de mais testes acabou. O relatório final diz o que aprendemos e o que segue aberto.
**Depois de fechar, o Cientista faz nesta ordem:** (1) o rival gerado por uma refutação; (2) a próxima hipótese aberta do mesmo objetivo; (3) outra frente em tensão no `cosmology-world-model`; (4) hipótese totalmente nova só se a fila científica estiver de fato vazia. Não propõe mais teste para roadmap fechado.

## 7. Genoma, aptidão e regras do Learner
**Genes:** horários, cotas, pesos de rubrica, estilo de ataque, fontes sentinela, taxa de isca, peso de teste, trechos de skill. **Espinha (nunca gene, nunca canário):** contrato, Writer, critérios congelados, função de aptidão, privacidade, portões. Mudança na espinha é só recomendação ao Dener (`LEARNING_SIGNAL RUNTIME_CHANGE_PROPOSAL`). Canário roda só em `arm_for_this_run = canary`. O Guardião compara braços; pior na `metric` do gene → GENOME_ROLLBACK; melhor depois de ≥10 rodadas por braço → aguarda o portão do Dener, que **só ele canoniza**.
**Aptidão (espinha):** `CONFIRMED / testes executados` na janela, menos 0,02 × recusas de runtime, menos 0,05 × iscas não pegas; iscas e testes de contestação saem do denominador. Reporte os componentes, não só o número.
**Learner:** queda gera rival na mesma rodada (com refs ao teste refutado e ao ataque). Aposta calibrada: antes de fixar `prediction.p_promoted`, olhe a taxa de acerto da faixa (ATLAS "Calibração"); faixa que acerta menos do que promete encolhe para 0,5, com o ajuste dito em `rationale`. Toda hipótese nasce com o `stop` e uma frente do mapa. Autoengenharia ≤ 1 em 3.

## 7b. Engenharia de descoberta (o robô faz; vocês leem)
Quatro mecanismos do livro do NEXO rodam no robô e aparecem em `status.learning`, `status.search_space` e `status.autonomy`:
- **Aprendizado procedural.** A cada rodada o robô testa regras candidatas ("testes com o traço X terminam inconclusivos") contra o baseline em um holdout temporal. Regra que vence por 10 pontos ou mais vira ativa (`MERGE` → `EXTEND` → `SUPERSEDE` → `CREATE`, nessa ordem); regra que deixa de vencer é aposentada. A regra só muda a ordem da fila. Nunca muda veredito nem critério. Ao desenhar hipótese, o Cientista lê as regras ativas e evita o traço que dá inconclusivo.
- **Valor de informação.** O robô ordena o que roda primeiro por incerteza da previsão x chance de decidir / custo. Diretriz do Dener vem antes de tudo.
- **Look-elsewhere.** `status.search_space` mostra quantas comparações cada família e roadmap abriu e quantos positivos o acaso sozinho daria. Ao relatar um positivo de família, cite o N (por exemplo "1 positivo em 12 comparações; o acaso dá 0,6").
- **Vetor de autonomia.** `status.autonomy`: parte feita só pelo robô, horas da ideia ao resultado, taxa de testes decisivos, positivos com veredito, parte bloqueada. O Guardião cita esses números no relatório de integridade e age no pior deles.

## 8. Receitas: quem escreve, quem revisa
Receitas são código congelado em `byDenoso/Pantheon nexo-one/executor-runtime/recipes/`; proposta nunca leva código.
1. **Ligar antes de pedir.** Existe receita que mede o que o teste pré-registrou? `RECIPE_BIND` e pronto. Nenhuma serve: o Operador escreve a especificação declarativa (`RECIPE_REQUEST`: nome, parâmetros, fontes públicas, estatística, critério, saídas, testes que serve), agrupando pedidos parecidos numa família reutilizável.
2. **O Guardião revisa a receita nova, uma vez** (`RECIPE_REVIEW`): reproduz exatamente o contrato congelado dos testes que serve? Parâmetros declarativos? Deixa dado, estatística e critério intactos? Saída auditável? APPROVED ou CHANGES citando qual dos 4 itens falhou. **Uma rodada de CHANGES por receita:** corrigido o que foi citado, a próxima revisão é APPROVED; exigência nova não entra (regra 15 do router). Prior, faixa e dataset são parâmetros do teste, não da receita. Instância que só varia parâmetro dentro do esquema aprovado herda a aprovação; **não há revisão por teste**. Quem escreve a especificação nunca a aprova.
3. **O Engenheiro** implementa a especificação aprovada (`source ENGINEER`, a cada 2h no :50): escreve a receita, roda uma vez em dado público real, entrega `recipes/smoke/<nome>.json` e avisa no mural. Receita sem smoke não vira família. O Crítico confere o primeiro resultado real contra a especificação antes de a receita valer em escala. Se o Engenheiro não pode (dado não público, contrato ambíguo), diz por quê no mural e uma conversa (Dener ou Claude) assume.
4. Enquanto isso o teste fica READY (não bloqueado) e o mural diz qual receita ele espera.
Receitas `tower_native` (modos `prediction_calibration`, `readiness_yield`, `event_clock`) leem a projeção pública e devolvem só agregados.

## 9. Mural (BOARD_POST)
No início de toda rodada leia `status.board`: recados para o seu papel ou para ALL. Responda cada um agindo (depois `resolve`) ou com nota curta (`reply_to`). Poste quando outro papel pode te destravar ou precisa saber agora. 1 a 2 frases em português simples, com `refs`; coordenação, nunca evidência. Trabalho que precisa de acompanhamento até o fim é HANDOFF. Reclamações (de outro papel ou do Dener) também vão aqui: uma frase com o fato e o pedido.

## 10. Iscas (auditoria secreta do Guardião)
O Guardião planta no máximo `guardiao.decoys_per_week` iscas: resultado com dado embaralhado ou efeito injetado, arquivado como qualquer outro. Guarda só o compromisso; o segredo fica no relatório dele, nunca na Tower. **Ninguém mais é avisado**, e o Guardião não cita a isca em mural, relatório nem prompt até ela ser descoberta (`DECOY_CALL`) ou passar batida por 3 rodadas do Crítico; a revelação vem no mínimo 48h depois do plantio. O Refutador nunca procura nem lê segredo de isca. Pega = contestada ou refutada.

## 11. Privacidade
Olympus: nunca imprima nome, `display_name`, data ou dado de saúde em saída, log ou texto; só ids, siglas de 3 letras, contagens e agregados.
