# NEXO minimalista — compatibilidade e contexto por papel

Esta entrega amplia a etapa de GC da PR #165. Implementa compatibilidade do CONTROL, bootstraps sem cópia monolítica, deltas privados e correção do efeito de BOARD_POST. Nenhuma retirada física, deploy ou alteração de scheduler é ativada pela presença do código.

## CONTROL por responsabilidades

`control_compat.read_control_compat` lê o CONTROL legado enquanto ele existir. No ensaio de migração, a identidade vem do cabeçalho da Tower, onze campos operacionais consumidos podem ir a `runtime/executor_policy.json`, e mandato/revogações ficam em `evolution/autonomy_authority.json`. Esses documentos não recriam o CONTROL de 182 campos. A autoridade fica protegida pelo mesmo token humano e controle de revisão do Writer; pedidos genéricos e gravação simultânea no documento legado são recusados.

`prepare_migration(raw)` gera **somente candidato de ensaio**. Conserva integralmente a entrada antiga em histórico privado endereçado por hash, preserva todos os outros arquivos e verifica a paridade dos campos consumidos. COMPONENTE faltando, schema inválido ou autoridade dupla falham explicitamente. A materialização reutilizada só remove o CONTROL anterior se ele vier do snapshot anterior verificado e estiver sem edição local; arquivo desconhecido/editado é protegido.

A presença de chaves históricas não prova que estejam inativas. `inventory_consumers` gera pistas estáticas com SHA de cada fonte; ausência de ocorrência não autoriza remoção. Consumidores dinâmicos, bundles implantados, prompts e clientes externos ainda exigem reconciliação. A coleta/retirada física permanece separada do ensaio.

## Bootstraps e deltas

O bootstrap preserva sua estrutura e recebe apenas os campos operacionais de `bootstrap_control`, com referência à autoridade canônica. Filas, estado de autonomia, fragmentos e caixa de handoff mantêm suas decisões e limites atuais. Os valores completos continuam no arquivo canônico legado ou na visão de compatibilidade; caches nunca passam a ser autoridade.

```sh
python gpt/nexo_gpt_writer.py context PRIVATE_TOWER.json ADVISOR PRIVATE_CONTEXT.json
python gpt/nexo_gpt_writer.py context PRIVATE_TOWER.json ADVISOR PRIVATE_NEXT_CONTEXT.json --cursor PRIVATE_CONTEXT.json
python gpt/nexo_gpt_writer.py context PRIVATE_TOWER.json EXECUTOR PRIVATE_TARGET_CONTEXT.json --target entities/test/TEST_ID.json
```

O cursor pertence à mesma fonte, papel e seleção de alvos. Hashes de conteúdo detectam alterações de resolução, ACK/DONE/FAILED, versões e revogações; identidade/autoridade/seleção incompatível reinicia o contexto. Handoffs são resolvidos pelos eventos canônicos ordenados, além dos formatos de entidade de compatibilidade. Work e handoff saem como metadados/hash/ref, com conteúdo completo carregado quando solicitado pelo alvo. O mural conserva seu texto; não vira evidência científica.

O cursor é derivado e reconstruível. `context_changed=false` **não prova fila vazia nem autoriza NO_OP científico**; materializar/reservar/executar continua dependendo da entidade/receita/entrada e autorização atuais. Não há escrita canônica, serviço ou automação nova. Saídas locais são privadas, create-only e não comprovam implantação.

## Handoffs e recibos por transação

O índice transacional existente da PR #165 também reaproveita eventos de handoff. Um único scan alimenta consultas repetidas; novos eventos atualizam o índice imediatamente. Savepoints O(1) abrangem ambos os journals, e rollback desfaz o estado em memória junto com o disco. Transações aninhadas sobre o mesmo candidato reutilizam o contexto. Outra transação não herda o cache. Materialização de múltiplas views deixa de reler o histórico inteiro por papel.

## Efeito real do mural

Texto igual com refs, reply ou privacidade diferentes representa mensagem distinta. A deduplicação agora compara o conteúdo semântico completo. Um recibo aceito de documento não basta: o Writer confere IDs/campos efetivamente gravados no mural antes de produzir APPLIED. Falha desfaz o envelope pelas rotas de rollback existentes. A mudança não reescreve recibos históricos nem infere que um post antigo ausente nunca existiu.

## MCP opcional

O caminho nativo do Writer já executa sem cliente MCP; regressão bloqueia rede e confirma aplicação local real de BOARD_POST. A mudança correspondente no repositório privado `NEXO-Obsidian-Vault` remove fallback canônico Git, congela escrita Git em código, verifica identidade/fingerprint do Drive, consulta eventos pelo Drive e reduz o catálogo remoto padrão a seis consultas. O catálogo read-only de compatibilidade é opt-in; mutações científicas/saúde nunca são registradas. Autenticação permanece.

O Railway existente não é desligado sem inventário de consumidores. Configurar outro leitor, credencial ou ACL não é parte desta entrega. Nenhuma automação científica deve depender da disponibilidade desse MCP para executar pelo runtime autorizado e Writer existente.

## Lanes e ciência

A PR #156 continua como entrega independente da seleção de lanes; seus dez testes são executados no SHA original. O patch de bootstrap é em região diferente de `continue_campaign`; integração conjunta é ensaiada sem duplicar a PR de lanes.

A validação científica usa apenas um TEST existente, receita/parametrização original e cinco inputs públicos com hash congelado. Execução isolada pode produzir cálculos parciais; não equivale a reserva, RUN/RESULT canônico ou aprovação independente. Uma falha de holdout não é nulo científico. Não corrigir faixa/mínimo/dataset post hoc para forçar fechamento.

## Promoção e reversão

Integrar após revisão independente no SHA testado, mantendo a PR #165 e #156 rastreáveis. Depois, conferir o bundle efetivo e testar os consumidores vivos antes de aposentar CONTROL ou MCP. Enquanto isso, CONTROL e serviço atuais permanecem.

Reverter o bundle para a base é suficiente antes de qualquer migração canônica. Se houver cutover futuro, restaurar a representação compatível sobre a última revisão pelo Writer, com CAS/readback e reconciliação de deltas; não sobrescrever com backup antigo. Falhas bloqueiam o componente/lote dependente, preservando ciência independente.
