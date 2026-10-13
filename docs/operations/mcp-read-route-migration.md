# Migração restrita de leitura MCP

`SET_MCP_ROUTE` registra na Tower somente as rotas de `nexo_capabilities`,
`nexo_search`, `nexo_neighbors` e `nexo_trace`, para leitura privada `LEARNER`.
O Writer continua único aplicador. A operação não troca
`hosted_mcp_current_endpoint`, o backend legado, gates de cutover global,
mandato, ciência, ACL, credenciais ou sessões operacionais de execução.

Campos governados de CONTROL:

- `mcp_tool_routes`: associa os quatro nomes ao endpoint verificado, preservando
  qualquer outra rota existente.
- `hosted_mcp_scientific_read_endpoint`: endpoint dessa leitura restrita.
- `hosted_mcp_scientific_read_route`: prova privada da mudança, source read,
  catálogo, canário conectado, autorização e rotas anteriores.

Esses campos também sobrevivem ao ensaio de compatibilidade do CONTROL em
`runtime/executor_policy.json`. Não existe documento paralelo de roteamento.
Clientes externos precisam consumir as rotas; gravar CONTROL não instala um
plugin nem redireciona ferramentas já registradas na plataforma.

## Preparação privada

```sh
python gpt/nexo_gpt_writer.py mcp-route prepare TOWER.json https://HOST/mcp PENDING_ROUTE.json --approval-ref REFERENCIA
```

Sem catálogo ou canário, a saída é `PENDING_CONNECTION`, `endpoint_observed:false`,
`human_authenticated:false` e `envelope:null`. O candidato não é uma proposta
aplicável e não deve ser enviado ao inbox como `OPERATOR_INTENT`.
Cada saída é privada e create-only. Não copia a Tower para o arquivo de proposta.

Depois de observar o endpoint real e conectar o MCP no ChatGPT:

```sh
python gpt/nexo_gpt_writer.py mcp-route prepare TOWER.json https://HOST/mcp PREPARED_ROUTE.json --catalog CATALOG.json --canary CONNECTED_CANARY.json --approval-ref REFERENCIA
```

`CATALOG.json` contém exatamente `endpoint`, `source_file_id`, `role:"LEARNER"`,
`tools`, `sha256` e `observed_at`. `tools` é a lista efetivamente observada dos
quatro tools, com `inputSchema.type:"object"` e annotations
`readOnlyHint:true`, `destructiveHint:false`. `sha256` é o hash JSON canônico da
lista, sem prefixo. Não substituir o catálogo remoto por uma lista inventada.

`CONNECTED_CANARY.json` contém exatamente `runtime:"CHATGPT_CONNECTED_MCP"`,
`endpoint`, `source_file_id`, `role:"LEARNER"`, `tool:"nexo_capabilities"`,
`catalog_sha256`, `observed_at`, `receipt_ref`, `readback:"PASS"`, `capabilities`
e `capabilities_sha256`. `capabilities` é a resposta JSON privada completa
da chamada conectada; o hash é calculado sobre essa resposta canônica.
`receipt_ref` identifica o registro privado real da chamada, jamais um exemplo.

A resposta deve indicar `status:AUTHENTICATED`, fonte/revisão/hash da mesma
Tower, `roles:[LEARNER]`, `read_only:true`, `writes_enabled:false`, os quatro
tools e a janela de validade ainda ativa. `INDEX_REFRESHING`, discovery,
erro de binding ou resposta de outra Tower são recusados independentemente de
labels `PASS`. HTTP smoke e Site publicado não comprovam chamada pelo conector
ChatGPT. O canário deve ocorrer depois da leitura do catálogo e antes do envelope.

## Autenticação e aplicação

A saída completa ainda é `PREPARED_PENDING_HUMAN_AUTHENTICATION`. O envelope usa
`OPERATOR_INTENT`, `source:DENER` e `payload.action:SET_MCP_ROUTE`; esse texto
nunca autentica o usuário. O verificador humano existente precisa aceitar a
ação e assinar/verificar o hash exato por sessão humana autenticada + HMAC/OIDC.
`autonomy.ACTIONS` continua restrito a aprovação/revogação de mandato.

O Writer recebe hashes verificados por seu contexto protegido
`NEXO_VERIFIED_HUMAN_INTENTS`, produzido pelo verificador. Metadata de um arquivo,
`source:DENER`, `DRIVE` ou presença no inbox não substituem essa prova.
Não enviar o candidato por rota alternativa após 403 ou recusa de política.

O conversor compara `source_read.file_id`, revisão/hash dos bytes canônicos e
fingerprint dos campos relevantes de CONTROL antes de produzir merge limitado.
`source_read.tower_updated_at` é a data do snapshot, não uma leitura inventada.
Mudança concorrente de rota exige nova leitura e nova autorização do envelope.
Repetição da mesma proposta é idempotente pelo recibo durável do Writer.

A aplicação segue singleton Writer, verificação do head, PATCH e readback;
Drive não oferece CAS atômico nesse transporte. Confirmar recibo privado e
os quatro campos efetivamente registrados antes de afirmar redirecionamento.
Reversão usa nova proposta autorizada com a última revisão, sem restaurar
uma cópia antiga da Tower inteira.
