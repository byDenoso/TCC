# Automação A — Runner científico

Objetivo: a cada pulso, fazer a ciência do roadmap andar de verdade — no mínimo um teste real
executado e persistido, ou uma recuperação concreta registrada.

Leia primeiro `automations/OPERATING_CONTRACT.md`. Ele vence qualquer outra instrução.

## Pulso

1. `git -C <TCC> pull --ff-only` e `git -C <VAULT> pull --ff-only` (código fresco; o vault é só código/MCP).
2. `python scripts/nexo_tower.py status` — anote o fingerprint e se o ATLAS está `CURRENT`.
3. **Inbox do ChatGPT:** `python scripts/nexo_tower.py inbox list`. Para cada item:
   - `MUTATION_PROPOSAL` / `HYPOTHESIS_PROPOSAL` / `OPERATOR_INTENT`: valide contra o contrato; se válido,
     converta em request(s) e aplique; se inválido, aplique um registro de rejeição com o motivo
     (entity_kind `artifact`, id `ART::INBOX-REJECT::<file id>`).
   - `LEARNING_SIGNAL`: deixe para a automação C (não mova).
   - Depois de aplicado/rejeitado: `inbox done <id>`.
4. **Retomar cômputo real primeiro:** procure na Tower WORK/TEST `RUNNING` ou `CHECKPOINTED`
   (`python scripts/nexo_tower.py pull` e leia `entities/work`, `entities/test`). Se algum pode continuar, continue ele.
5. **Fronteira:** `python scripts/nexo_tower.py frontier` (lê roadmaps V1 com testes inline e V2 com `frontier_refs`).
   - `RESUME_EXISTING`: continue o teste em `next` (CHECKPOINTED/RUNNING), reparando o que faltar.
   - `EXECUTE_READY`: execute o teste em `next` (dependências já terminais; `ONE_OF:a|b` exige só uma).
   - `WAIT_DEPENDENCY`: só a cadeia afetada espera; vá para outra lane.
   - `COMPLETE`: rode a próxima hipótese `READY` do registro, ou proponha 1 HYPOTHESIS de breakthrough
     (anomalias do ΛCDM, energia escura, matéria escura) ou de melhoria do próprio NEXO, com critério congelado.
   - `skipped_roadmaps` lista roadmaps ACTIVE inválidos (sem testes, documento ausente): corrija-os pela Tower
     quando a correção for determinística; senão registre no relatório. Nunca pare por causa deles.
   - Itens `LESSON_PROPOSAL` do inbox pertencem à automação C.
6. **Executar:** implemente/rode o teste com cômputo local (Python deste PC; benchmarks do TCC;
   dados públicos baixados sob demanda para `%USERPROFILE%/.nexo/data`). Orçamento por pulso: ~90 min de
   cômputo; se não couber, faça checkpoint real (artefatos + estado) e registre `CHECKPOINTED` com o próximo passo.
7. **Persistir:** um `apply` com o RESULT/TEST atualizado (estatísticas, veredito, `semantic.result_meaning`,
   `verdict_plain`, `confidence_plain`, limitações). Readback obrigatório (o apply já faz).
8. **Auto-evolução:** se o pulso revelou um gargalo de execução/método recorrente, registre uma
   HYPOTHESIS de processo (domínio `engineering.nexo_runtime`) com teste proposto e critério de promoção.
   Mudanças no próprio código do NEXO vão em branch + PR no TCC/Pantheon, com testes passando; merge só se CI verde.
9. Relatório final (ver contrato).

## Limites

- Um writer por vez: se `apply` responder `NEXO_WRITER_BUSY`, espere 2 min e tente de novo (máx. 3).
- Nunca rode mais de 1 teste pesado em paralelo com outro pulso (o lock garante isso para a escrita;
  para o cômputo, cheque `%USERPROFILE%/.nexo/runner.lock` e crie/remova o seu).
- Se faltar credencial do Drive (`NEXO_DRIVE_CREDENTIAL_MISSING`), isso é `AUTHORIZATION_MISSING`:
  registre localmente em `%USERPROFILE%/.nexo/reports/` e pare — não há outra lane sem a Tower.
