---
name: nexo-connectors
description: Contrato de confiabilidade para Google Drive e GitHub no NEXO. Use sempre que uma tarefa ler, localizar, escrever, versionar ou citar conteudo por esses conectores.
version: 0.5.0
---

# NEXO - conectores Drive e GitHub

Objetivo: transformar acesso de conector em evidencia verificavel. Descoberta, leitura, identidade, escrita e readback sao etapas diferentes.

## Regra comum

1. **Identidade antes de conteudo.** Quando houver ID, URL, repo/path/ref ou commit conhecido, use-o diretamente. Busca e descoberta nao provam identidade nem versao.
2. **Leitura valida antes de ausencia.** Resultado vazio, trecho truncado, hidratacao parcial, primeira pagina de busca ou falha de parser nao provam que o dado nao existe.
3. **Versao observavel.** Registre a identidade que realmente foi lida: Drive file ID + modified time/size quando disponiveis; GitHub repo + path + ref/commit. Diferencie blob SHA de commit SHA.
4. **Fonte primaria vence derivado.** Bootstrap, buffer, indice, busca, projecao, snippet e pacote intermediario servem para localizar a fonte; nao substituem o arquivo ou commit que sustenta o claim.
5. **Escrita so fecha com readback.** Criar, atualizar, renomear ou mover continua nao verificado ate reler o alvo e conferir identidade, conteudo relevante e metadados esperados.
6. **Falha localizada.** Uma capability quebrada bloqueia somente a acao dependente. Continue partes independentes e registre o erro exato.
7. **Sem bypass de seguranca.** 403, recusa de politica, ACL ou autenticacao nao autorizam trocar silenciosamente de servico, conta ou rota.

## Google Drive

### Descoberta

- Se arquivo ou pasta ja tem ID/URL exato, leia metadados pelo ID e siga. Nao faca busca so para confirmar nome.
- Busca serve para nomes/termos desconhecidos. A busca usa topn; listagem direta de pasta usa top_k. Nao misture contratos.
- Busca paginada so terminou quando next_page_token for nulo. Reutilize o token opaco sem reinterpretar.
- item_type em busca e metadado; best_effort_fetch nao prova leitura integral.
- Nome semelhante em busca nao substitui confirmacao por ID, MIME, parent e URL observados.

### Leitura

- Leia metadados antes de exportar ou baixar: MIME, tamanho, URL, parents e modificacao.
- Fetch textual e leitura conveniente e limitada. Se vier content vazio com is_empty=false, conteudo truncado ou ilegivel, considere DEGRADED_READ.
- Para arquivos armazenados nao nativos, como PDF, JSON grande, ZIP, Office, imagem ou CSV bruto, use fetch bruto autenticado com download_raw_file=true e include_base64=false; trabalhe sobre file_uri/arquivo materializado.
- Para Google Docs, Sheets e Slides nativos, use as APIs especificas para leitura/edicao estruturada; exporte apenas quando o formato de saida exigir.
- PDF cientifico: raw fetch -> materializacao -> inspecao/renderizacao por pagina. Texto extraido e auxiliar.
- JSON grande: raw fetch -> conferir tamanho/bytes -> parsear a copia materializada. content vazio de fetch textual nao autoriza declarar Tower vazia.
- list_folder prova somente os filhos diretos retornados. Nao inferir recursao ou completude alem do limite solicitado.

### Escrita


### Ponte privada de celulas para automacoes sem arquivo exportavel

**Autorizacao restrita, ja implementada no Writer existente (sem segundo Writer):**
quando o runtime agendado NAO consegue vincular/exportar os bytes para o upload bruto
por `container_session_unavailable`, `file_uri` indisponivel ou ausencia da capacidade
de arquivo, um **BOARD_POST, INTEGRITY_REPORT ou LEARNING_SIGNAL** privado, sem
anexo, segredo, dados brutos da Tower ou instrucoes privilegiadas pode usar
exclusivamente o `NEXO_SCHEDULED_SPOOL` privado que o Writer ja consome:
Google Sheets ID `1M2maKkuEjxumZRa145dzei7dEPFi2yKsKlUf7_scC-E`,
aba `Sheet1`, ID numerico `1417054989`, colunas
`stable_id | created_at | role | envelope_b64url`. O proprietario e o Writer
sao os unicos destinatarios conhecidos da ACL observada em 12/10/2026.
Confirme metadados e ACL atuais antes de escrever; sem prova, preserve LOCAL_ONLY.

1. Classifique a falha original. `403`, escopo/ACL insuficiente, politica de seguranca,
   erro de autenticacao, rejeicao do Writer, schema invalido e conflito de identidade
   **NAO** habilitam essa ponte. Ela so evita a passagem de bytes pela sessao local.
2. Prepare exatamente um envelope JSON UTF-8 privado permitido, com `kind`,
   `source`, `created_at` UTC, `intent_id` estavel e `payload` conforme
   `gpt/PROPOSAL_SCHEMA.md`. Codifique os **mesmos bytes** em Base64URL
   sem quebra de linha e sem padding, limite total codificado a 24 KiB.
   Gere um `stable_id` imutavel em `[a-z0-9-]`, 1-60 caracteres,
   prefixado por `sched-v1-`; nunca use a timestamp do pulso como nova
   identidade para repeticoes da mesma proposta.
3. Confira pelo `stable_id` a coluna A da planilha e
   `byDenoso/Pantheon@main:nexo-one/scheduled-spool-ack.json` (key `acked`);
   confira tambem recibo/efeito canonico quando disponivel. Se ja existe
   mesmo ID, nao crie segunda linha; diferenca de bytes e CONFLITO,
   nao substituicao. Se busca/leitura for degradada, pare em UNKNOWN.
4. Se a API nativa `batch_update_spreadsheet` estiver **realmente**
   disponivel nesse runtime, use um unico `appendCells` de quatro campos
   `stringValue` na aba verificada; nao use `create_file`, Google Doc,
   scripts de terceiros, Git publico, outra conta ou permissao nova.
5. Releia a linha e compare quatro celulas, identidade, data e Base64URL
   byte a byte. Somente com match declare `DELIVERED_PENDING_WRITER`.
   A prova `acked[stable_id]` nao substitui a leitura do efeito e receipt
   na Tower para `APPLIED`. Se o runtime agendado nao expuser o Sheets
   write, preserve `PENDING_WRITE_LOCAL_ONLY` e a proposta original.

**Proibido nesta ponte:** `HANDOFF`, `HANDOFF_TRANSITION`, `OPERATOR_INTENT`,
aprovar mandato, substituir CONTROL, criacao de TEST/RESULT, gravacao direta
da Tower, publicacao, revisao cientifica, credencial/segredo e payload PEER
destinado ao Atlas. Handoffs continuam exclusivamente no `NEXO_INBOX`
create-only com proveniencia `DRIVE`. O Writer valida todos os envelopes
e continua unico aplicador. Registro no spool nao e efeito canonico.

### Ponte de arquivo exportado (ChatGPT -> Drive)
- Para JSON bruto gerado no ChatGPT, **prefira o snapshot de arquivo exportado**, não um caminho do contêiner. Na superfície Files, depois de obter o `file_id` real do artefato exportado (formato `file_...`), faça **uma** operação `files.manage_library` com `{"operations":[{"operation":"upload","source_file_ref":{"file_id":"<file_id observado>"},"destination_path":"<pasta privada NEXO_INBOX>/<nome imutável>.json"}]}`. A pasta deve ser descoberta e conferida no Drive/Library; nunca invente file_id.
- Na superfície nativa Google Drive `upload_file`, use somente o `file_uri` retornado de uma exportação/ação de arquivo compatível, com `parent_folder_id` confirmado. Não passe `/mnt/data/...`, caminhos Windows, URL textual ou base64 no lugar de `file_uri`.
- `container_path` no `files.manage_library` só é elegível quando a sessão desse contêiner estiver de fato vinculada à ferramenta Files. `container_session_unavailable` ("No active container session was found for container_path") é **falha da ponte local**, não negação Drive/ACL nem problema do Writer: não repita o mesmo argumento. Se existir snapshot exportado **do mesmo arquivo**, recupere pela referência exata; sem referência verificável, mantenha `PENDING_WRITE_LOCAL_ONLY`.
- **Antes de enviar:** valide UTF-8/JSON, tamanho e SHA-256; procure identidade/nome em `NEXO_INBOX`, `processed` e recibos; presença, resultado parcial ou busca degradada exigem reconciliação, nunca nova identidade. A operação é create-only, com mesmo nome e bytes; não sobrescreva nem crie Google Doc de duas etapas. **Depois:** leia metadados e bytes brutos pelo ID de retorno, compare SHA-256, tamanho, MIME `application/json` e parent canônico. Só então marque `DELIVERED/PENDING_WRITE`; `APPLIED` exige recibos **e efeito real** na Tower.
- Este procedimento reutiliza a **mesma** pasta/conta/permissão Drive autorizada; não é fallback de ACL. Não use Git público, serviço externo, Writer alternativo ou upload do snapshot inteiro da Tower como transporte.


- Resolva alvo e parents atuais antes de mover ou renomear.
- Arquivo nativo Google e editado pela API nativa; arquivo bruto usa operacao de arquivo. Nao converter tipo por acidente.
- Create/update/move/share so contam apos readback pelo ID retornado e verificacao de conteudo/metadados.
- No NEXO privado, presenca no inbox e entrega; aplicacao continua exigindo receipt/Tower.

### Diagnostico minimo

Classifique antes de concluir:
- NOT_FOUND: ID/URL resolvido como inexistente ou inacessivel;
- PERMISSION: 403/ACL/escopo;
- DISCOVERY_EMPTY: busca sem resultado, ainda sem prova de ausencia;
- DEGRADED_READ: metadados existem, mas leitura textual/parse ficou parcial ou vazia;
- RAW_FETCH_FAILED: falhou tambem a rota bruta valida;
- WRITE_UNVERIFIED: mutacao respondeu, mas readback nao confirmou.

## GitHub

### Descoberta e leitura

- Use repository_full_name + path + ref quando conhecidos. Para arquivo textual, fetch_file e a leitura canonica naquele ref.
- Busca de codigo retorna excertos e serve para localizar caminhos. Depois faca fetch_file do caminho completo.
- Busca cobre o branch padrao e e uma superficie de indice. Nunca use snippet de busca como prova da versao atual.
- Para evidencia reproduzivel, fixe o ref em commit SHA. main, tag movel ou URL sem ref servem para estado atual, nao para prova imutavel.
- Diferencie blob SHA, identidade do conteudo de um arquivo, de commit SHA, identidade do snapshot do repositorio.
- get_pr_info da metadados do PR, nao o diff. Para mudancas use fetch_pr_patch ou patch por arquivo.
- Logs e artifacts de Actions usam operacoes dedicadas. Ausencia em metadados nao prova ausencia do log/artifact.
- Pesquisas e listagens paginadas devem seguir page/cursor/token quando a tarefa exige completude.

### Escrita

- Antes de atualizar arquivo existente: fetch_file -> obter blob SHA atual -> update_file com esse SHA.
- Nao faca writes concorrentes no mesmo path. Atualizacoes sequenciais usam o SHA observado mais recente.
- Depois do write: releia o arquivo no branch alvo e, quando a identidade do snapshot importar, leia tambem o commit retornado.
- Conflito de SHA/lease significa concorrencia; refresque o estado antes de tentar novamente. Nao use force para esconder conflito.
- Commit, branch, PR, issue e workflow sao objetos diferentes. Nao inferir merge, deploy ou execucao a partir de commit criado.

### Diagnostico minimo

Classifique antes de concluir:
- REPO_NOT_RESOLVED;
- PATH_OR_REF_NOT_FOUND;
- PERMISSION;
- SEARCH_EMPTY;
- INDEX_DISCOVERY_ONLY;
- CONTENT_READ_FAILED;
- WRITE_CONFLICT;
- WRITE_UNVERIFIED;
- CI_NOT_CHECKED.

## Prova minima por tarefa

| Campo | Drive | GitHub |
|---|---|---|
| alvo | file/folder ID | repo + path |
| versao | modified time/size ou revisao | ref + commit SHA |
| leitura | MIME + texto valido ou raw fetch/materializacao | fetch_file/fetch_commit |
| mutacao | operacao + ID retornado | commit SHA retornado |
| confirmacao | readback do mesmo ID | fetch_file no branch/ref + commit quando necessario |
| limite | paginacao, truncamento, ACL, parser | indice, paginacao, permissoes, CI |

## Smoke de capacidade read-only

Quando houver suspeita de falha geral do conector, rode antes de declarar indisponibilidade:

**Drive**
1. get_file_metadata na Tower canonica 1m97cFmEkw19yiqD_6FWPG4j1lDCAYM4z.
2. fetch textual do mesmo ID. Se content vier vazio com is_empty=false, registrar DEGRADED_READ.
3. repetir por raw fetch com download_raw_file=true e include_base64=false.
4. confirmar tamanho do arquivo materializado e parse JSON. Se isso passar, o conector Drive esta funcional e a falha era da superficie textual/arquivo alvo.

**GitHub**
1. get_profile para confirmar identidade da conexao.
2. fetch_file de byDenoso/TCC:gpt/skills/nexo-master-router-0.5.0.md em main.
3. usar search apenas como teste de indice. Resultado zero nao invalida o fetch_file.
4. quando uma versao exata importar, repetir fetch_file com commit SHA conhecido e/ou fetch_commit.

Nao executar writes de smoke por padrao. Validar escrita apenas quando a tarefa ja exige uma mutacao real, usando o proprio write e readback como teste.

## Criterio de conclusao

- **LIDO:** conteudo primario efetivamente acessado na versao identificada.
- **LOCALIZADO:** somente metadado/busca foi resolvido.
- **APLICADO:** write confirmado por readback.
- **NAO ENCONTRADO:** somente apos esgotar a rota valida de identidade/descoberta pertinente; busca vazia isolada nao basta.
- **BLOQUEADO:** erro real de permissao/capability apos tentativa pela rota correta, com partes independentes concluidas.
