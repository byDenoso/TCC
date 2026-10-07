# Continuidade NEXO: correções e integração

Extensão do contrato `gpt/NEXO_CONTINUITY_CONTRACT.md`, sem nova fonte de verdade, transporte, agendador ou permissão. Base inspecionada: TCC `4c4ed3864c04f9690e53539fa0be7d8b3b2fda96` (PR145). O código do Writer instalado foi materializado pelo Drive; os três módulos alterados tiveram seus blobs comparados com essa revisão do GitHub.

## Efeitos desta correção

- `REGISTRO` exige quórum vigente mesmo depois de `FREEZE`. Uma nova objeção ou conflito impede confirmar o registro até sua resolução legítima. O TEST preparado existente permanece preservado.
- Campos vazios, inclusive espaços dentro de listas ou objetos, continuam sendo lacunas. Uma SPEC parcial continua aceita. Valores definidos iguais a zero não são tratados como ausência.
- Retry idêntico de memória ou progresso relê o registro imutável já aplicado, mesmo quando a fonte citada mudou depois. Um evento novo ainda precisa do hash atual; troca de autor ou conteúdo com o mesmo ID permanece conflito.
- A leitura de continuidade deriva do mesmo snapshot que forneceu a revisão. A partir da segunda página, exige revisão fixada; uma mudança de fonte produz erro explícito.
- Endossos de agentes lógicos não são contabilizados como revisão humana independente. O histórico deste protocolo comprova zero revisores humanos, não uma equipe de cinco pessoas.

## Uso pelas tarefas e chats

As quatro operações continuam sendo kinds de envelope do Writer: `ENXAME_EVENT`, `ENXAME_REGISTER_TEST`, `NEXO_MEMORY_ENTRY` e `NEXO_PROJECT_EVENT`. Não são novas ferramentas MCP. Use `{kind, source, intent_id, created_at, payload}` e o esquema integral do contrato principal.

Prepare com `inbox_client.prepare` ou com a CLI. Preserve os bytes e o timestamp em retries. Envie somente pelo ingresso privado autorizado no CONTROL vigente. Releia o arquivo de ingresso e confira os bytes. Confirme a entidade e o recibo canônicos na Tower antes de declarar efeito aplicado. Um upload confirmado ainda não prova aplicação. Não inclua campos `_inbox_*` no envelope: são metadados exclusivos do loader.

O grupo A1–A5 prepara e registra; registro mantém evidência científica vazia e não autoriza execução. Receita, dados, revisão de escopo, reserva e execução continuam nas operações existentes. Nenhuma tarefa ou horário é alterado por esta entrega.

## Leitura paginada

```sh
python gpt/nexo_gpt_writer.py continuity inspect TOWER.json --limit 100
python gpt/nexo_gpt_writer.py continuity inspect TOWER.json --after 100 --limit 100 --expected-revision 'sha256:REVISAO_DA_PRIMEIRA_PAGINA'
```

Use `next_offset` ou `next_cursor`. O cursor inclui revisão, escopo, versão, offset e limite. Preserve esses campos ao continuar. Em `CONTINUITY_REVISION_CHANGED`, recupere uma cópia autorizada atual e recomece a leitura; não misture páginas de revisões distintas. O limite é 1–1000 e o offset é inteiro não negativo. A função Python aplica os mesmos limites da CLI. `source_raw_sha256` identifica o arquivo lido e não substitui o hash canônico da SPEC.

## Validação e instalação

```sh
python -m pytest tests/test_continuity_enxame.py tests/test_continuity_hardening.py -q
python scripts/build_gpt_writer_bundle.py
python gpt/nexo_gpt_writer.py verify TOWER.json
```

Na execução local inicial: 14 testes existentes passaram; os novos casos reproduziram 23 falhas e preservaram quatro controles; após a correção, os 41 casos passaram. São testes de software com fixtures sintéticas, sem inferência astronômica. A suíte completa e o CI remoto devem ser verificados separadamente, sem reutilizar contagens da descrição do PR145 como se fossem execuções desta revisão.

Recompile o bundle antes do uso isolado. O Writer robot existente recompila uma revisão testada do TCC main e verifica os bytes no Drive; criar esta branch não ativa as correções. Não publique o bundle por uma rota alternativa nem substitua o Writer ativo apenas porque um upload é possível. Preserve o bundle anterior para rollback e confirme a revisão efetivamente instalada.

O checkout do Pantheon não comprova a versão publicada do Site Atlas. O endpoint e a sessão privada do Atlas exigem validação no runtime que administra o Site existente. Esta correção não instala conexões em outras conversas nem demonstra uma semana de autonomia.
