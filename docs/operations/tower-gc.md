# GC seguro da Tower — primeira etapa

O Writer mantém um índice de recibos por candidato transacional. O GC inicial é somente `dry-run`; não existe comando de coleta destrutiva ou ativação automática nesta entrega. Não há dependência, serviço, automação ou Writer novo.

## Comandos no Writer existente

```sh
python gpt/nexo_gpt_writer.py gc dry-run TOWER.json PRIVATE_REPORT.json
python gpt/nexo_gpt_writer.py gc backup TOWER.json PRIVATE_BACKUP.json.gz PRIVATE_BACKUP_MANIFEST.json
python gpt/nexo_gpt_writer.py gc archive TOWER.json PRIVATE_PATHS.json PRIVATE_ARCHIVE.zip PRIVATE_MANIFEST.json
python gpt/nexo_gpt_writer.py gc restore CURRENT.json PRIVATE_ARCHIVE.zip PRIVATE_MANIFEST.json EXPECTED_REVISION PRIVATE_CANDIDATE.json
```

`PRIVATE_PATHS.json` contém uma lista explícita de caminhos lógicos, não um critério de exclusão. Os arquivos de saída devem ser novos e são criados com modo 0600. Esses comandos geram artefatos privados locais e candidatos de ensaio; não fazem upload, sobrescrita canônica, exclusão ou alteração de agenda. Preserve-os no armazenamento privado já autorizado quando forem usados operacionalmente. Um artefato local não é prova de backup durável em produção.

O backup conserva os bytes exatos do snapshot bruto. O arquivo de itens conserva a representação canônica exata de cada entrada da Tower, seus caminhos e identidades; não promete restaurar a formatação externa do snapshot inteiro. Itens diferentes com bytes iguais compartilham um blob; identidades e triplas de recibos nunca são colapsadas. Hashes, manifesto, tamanho e membros são verificados antes de restaurar; ausência/corrupção é erro explícito.

`restore` prepara o inverso sobre a revisão atual fornecida: conserva entradas novas e recusa colisões de caminhos ou revisão obsoleta. Nunca sobrescreve a Tower com um backup antigo. O candidato depende de aplicação serial pelo Writer único, conferência do head e readback no mesmo ID. O transporte Drive existente usa head-check/PATCH/readback, que **não é CAS atômico**; esta entrega não altera nem amplia sua capacidade de concorrência.

## Inventário e limites de segurança

`plan_gc` inventaria caminhos, IDs, referências, ciclos, tamanhos e hashes; calcula alcance a partir de raízes protegidas. Ciência, autoridade/revogações, eventos auditáveis e idempotência são retidos. Referências externas ou desconhecidas e consumidores não cobertos não autorizam remoção. A busca detecta identidades exatas e caminhos; referências construídas dinamicamente ou embutidas em texto exigem cobertura adicional dos consumidores. Não confundir o inventário automático com prova completa de ausência.

Todas as entradas têm `eligible_for_removal=false` nesta etapa. O inventário não aceita um booleano de “cobertura completa” enviado por um produtor para liberar exclusões. A promoção posterior exige evidência de cobertura dos leitores, resolução histórica, autorização vigente e revisão técnica independente. Evidências científicas e autoridade permanecem intactas no piloto. PEER e todos os artefatos/índices privados permanecem fora das projeções públicas e privadas.

`build_live_tower_payload(..., excluded_paths=...)` permite ensaiar exclusões explícitas tanto no scan quanto no carryover de `base`. É argumento interno de candidato, não campo consumido de proposta/CONTROL; sozinho não autoriza arquivamento nem prova cobertura dos leitores.

## Continuidade no ciclo existente

O robô existente inclui uma chamada opcional depois do trabalho ordinário. Ela vem desativada e só gera `dry-run`, mediante `NEXO_TOWER_GC_DRY_RUN=1` e orçamento explícito `NEXO_TOWER_GC_MAX_BYTES`. O valor deve ser escolhido pela medição de tempo/memória no runtime vigente. Não foram alterados ambiente, scheduler ou configuração de produção nesta entrega.

O único relatório fica no cache privado existente, com identidade de política e hash dos bytes da Tower; repetição idêntica reutiliza o relatório e não registra revisão/recibo canônico. Orçamento insuficiente ou falha de GC não impede o fluxo normal. Não ativar a manutenção em ciclos sem capacidade livre. Esse opt-in não habilita compactação da Tower ativa.

## Índice de recibos

O índice em memória pertence a uma materialização/candidato, com no máximo uma carga completa. Consultas por tripla, intenção e rejeição terminal preservam ordenação/desempate e dual-read legado. Persistência atualiza o índice imediatamente; replays/no-ops não criam recibos redundantes. Checkpoints de rollback são O(1) e desfazem entradas novas em memória junto com o snapshot em disco, sem rescan. Outra transação/CAS rejeitado não reutiliza o índice. Não há cache de autorização.

## Validação

As regressões cobrem igualdade de decisões, legado, corrupção, invalidação, rollback interno, referências/ciclos, colisão de hash simulada, aliases, arquivo truncado/membro ausente, backup bruto exato, restauração com deltas posteriores, revisão obsoleta, caminho conflitante, repack com `base`, saída privada e orçamento/cache do modo oportunista. Também se executam as regressões existentes de ciência, privacidade, Writer, bundle e transporte.

```sh
python scripts/build_gpt_writer_bundle.py
python -m pytest tests/test_tower_gc.py tests/test_receipt_transaction.py tests/test_operation_receipts.py tests/test_runner_battery_identity.py tests/test_robot_persistence.py tests/test_writer_bundle.py tests/test_execution_recovery.py tests/test_execution_phase_reconciliation.py tests/test_scientific_integrity.py tests/test_public_campaign_writer.py tests/test_robot_battery_admission.py tests/test_robot_contest_generation.py runtime/nexo_agent_api/test_drive_transport.py runtime/nexo_agent_api/test_drive_inbox.py runtime/nexo_agent_api/test_live_tower.py -q
python scripts/benchmark_tower_gc.py PRIVATE_TOWER.json PRIVATE_METRICS.json
```

O benchmark mede consultas de recibos pareadas, custo de dry-run e restauração. Não mede a vazão integral de `apply_to_tower`, avanço de TEST por pulso ou ganho em produção. Compressão de backup não é economia líquida nem redução ativa da Tower. A implantação depende da revisão independente; após integrar, reler bundle efetivo e executar novamente o dry-run na revisão atual antes de preparar coleta piloto.

## Reversão

Nesta etapa basta restaurar o bundle anterior; nenhuma entrada canônica foi arquivada ou excluída. Após eventual coleta futura, primeiro restaurar pelo Writer atual a representação entendida pelo bundle anterior, sobre a última revisão, com reconciliação e readback. Suspender apenas GC diante de falha, mantendo trabalho científico independente.
