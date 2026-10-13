# NEXO — contrato de continuidade privada validada

Base reconciliada: `byDenoso/TCC@4c4ed3864c04f9690e53539fa0be7d8b3b2fda96`.
Este adendo descreve o delta validado de continuidade e recuperação. O contrato
`gpt/NEXO_CONTINUITY_CONTRACT.md` e o `CONTROL.json` vigente continuam governando
autoridade, ingresso, persistência e exposição.

## Operações

`ENXAME_EVENT`, `ENXAME_REGISTER_TEST`, `NEXO_MEMORY_ENTRY` e
`NEXO_PROJECT_EVENT` continuam sendo kinds de envelopes do Writer existente,
não novas ferramentas MCP.

Formato comum:

```json
{"kind":"...","source":"...","intent_id":"...","created_at":"...","payload":{}}
```

Preservar `intent_id`, timestamp e bytes em retries. O caminho material continua
conexão autorizada -> inbox privado -> Writer serializado -> Tower -> receipt/readback
-> projeções. Entrega no inbox não significa aplicação.

## Contexto owner-private

Novo comando:

```sh
python nexo_gpt_writer.py continuity context TOWER.json --scope WORK
python nexo_gpt_writer.py continuity context TOWER.json --scope SCIENCE --query "calibrador"
python nexo_gpt_writer.py continuity context TOWER.json --scope PERSONAL --include-history
python nexo_gpt_writer.py continuity context TOWER.json --scope CLIENT:ID --at 2026-10-07T12:00:00Z
```

Escopo é obrigatório: `WORK`, `PERSONAL`, `SCIENCE` ou `CLIENT:<id>`.
Não existe `ALL`, inferência de cliente ou fallback entre escopos.

Argumentos adicionais:
- `--limit 1..100`
- `--expected-revision sha256:...`
- `--include-history`
- `--at <ISO-8601>`

O resultado usa `NEXO_OWNER_CONTEXT_V1` e retorna origem, revisão, estado,
fontes, referências e score lexical. Correções futuras não substituem
prematuramente a versão atual; expiração não ressuscita uma versão substituída.
Consulta livre usa memória vigente. Identidade exata pode recuperar histórico,
explicitando seu estado.

`--at` aplica validade declarada dentro do snapshot fornecido. Não reconstrói
automaticamente o que o sistema sabia em uma data passada.

## Integridade

Cada citação identifica o objeto canônico efetivamente hasheado por
`json_pointer`. `excerpt_json_pointer` aponta apenas o trecho exibido.
Fonte alterada ou ausente gera revalidação; síntese nunca ganha autoridade
científica independente.

Projetos `REOPENED` exigem predecessor `COMPLETED` e evidência. Campos de
validade/substituição de memória não são aceitos em eventos de projeto.

## Paginação

Primeira página:

```sh
python nexo_gpt_writer.py continuity inspect TOWER.json --after 0 --limit 100
```

Continuação:

```sh
python nexo_gpt_writer.py continuity inspect TOWER.json --after 100 --limit 100 \
  --expected-revision sha256:REVISAO_DA_PRIMEIRA_PAGINA
```

Offset positivo sem revisão falha. Mudança de revisão entre páginas também falha.
A materialização usa os bytes do snapshot já verificado, evitando misturar
proveniência antiga com conteúdo relido depois.

## Recuperação exata

Consultas no formato `NAMESPACE::ID` são tratadas como identidade canônica.
Se o ID não existe, está oculto ou está inativo na visão autorizada, o modo
automático se abstém em vez de devolver um item semanticamente parecido.
Histórico autorizado continua exigindo `include_inactive=True`.

Caches derivados usam o namespace
`.retrieval-1.1-continuity-validated-20261007`; caches anteriores permanecem
intactos e reconstruíveis.

## Limites de acesso

Esta função pressupõe um snapshot obtido por conexão já autorizada. Ela não é
autenticação HTTP. Atlas e outros consumidores precisam manter sessão,
proprietário, PIN e escopo vigentes. Registros owner-private continuam
`private=true`, `allowed_roles=[]`; papéis científicos não recebem acesso
automático a dados pessoais ou de clientes.

## Consumidores

Chats, Atlas e automações podem usar `continuity context` somente depois de
confirmar que o bundle/runtime implantado contém esta revisão. Cada runtime
prova suas próprias conexões e readback. Este contrato não cria, pausa,
reagenda ou altera automações, e o registro ENXAME não dispara ciência.

## Rollback

Rollback de código restaura a revisão anterior pelo mesmo fluxo de publicação.
Não apagar eventos, receipts, memórias ou estado canônico para reverter uma
interface. Índices e caches podem ser reconstruídos.
