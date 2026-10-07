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

## Criterio de conclusao

- **LIDO:** conteudo primario efetivamente acessado na versao identificada.
- **LOCALIZADO:** somente metadado/busca foi resolvido.
- **APLICADO:** write confirmado por readback.
- **NAO ENCONTRADO:** somente apos esgotar a rota valida de identidade/descoberta pertinente; busca vazia isolada nao basta.
- **BLOQUEADO:** erro real de permissao/capability apos tentativa pela rota correta, com partes independentes concluidas.
