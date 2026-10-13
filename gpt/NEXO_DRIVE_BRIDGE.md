# Ponte privada de chats e automações

Confira as ferramentas realmente expostas no runtime. Leia a Tower privada e o
CONTROL atual. Use o papel da execução; autorização de outro runtime não se herda.

Antes de enviar, procure o mesmo intent_id nos recibos e o arquivo na raiz da
NEXO_INBOX e em processed. Preserve identidade, data e bytes. Grave um JSON UTF-8
bruto na raiz da INBOX por upload create-only; artefatos binários ficam em _runtime
com referências e SHA256. Releia bytes, MIME e parent. Registre DELIVERED.

Leia o recibo do Writer e a entidade resultante na Tower. Registre APPLIED somente
com recibo correspondente e readback. Mensagem ou binding aplicado não prova receita
pronta nem execução científica. Timeout significa resultado desconhecido: reconciliar
sem criar outro arquivo. Recusa de permissão exige reautorização, sem trocar de rota.
Recusa definitiva de criação (400/404/409/422) fica CREATE_REJECTED e exige
correção explícita pelo operador; não é timeout nem autoriza reenvio automático.

Se faltar uma ferramenta, informe exatamente a operação pendente e diferencie
ferramenta ausente, autenticação ausente, permissão negada e erro do Writer. Uma URL
ou skill não estabelece conexão. Preserve prompts, horários e ativação das tarefas.

## Cliente Python reutilizável

`runtime.nexo_agent_api.inbox_client.prepare` valida envelope, papel, tipos de
operação explicitamente autorizados e identidade estável. `deliver` aceita a
Tower já lida e um journal persistente; exige checkpoint antes da criação remota.
`DriveInboxClientTransport` recebe uma sessão Drive já autenticada, usa upload
multipart e busca a raiz e processed com paginação pelo transporte existente.
Não descobre credenciais nem escreve na Tower. `receipt_status` usa o mesmo hash
e identidade de recibos do Writer existente.
Sessão Drive ausente é recusada antes de qualquer procura de credenciais. A
reconciliação lê `operations/receipts/`, `mutations/receipts/operations/` e o
layout antigo direto `mutations/receipts/`, com os defaults e a validação de
recibos do Writer. Um ledger inválido é erro, não ausência de recibo.

A lista de tipos autorizados é definida pelo chamador confiável, nunca pelo JSON.
O cliente aceita somente um envelope por arquivo: `kind`, `source`, `created_at`,
`intent_id`, `payload` e, em correções, `supersedes`. Campos de request bruto não
podem ser acrescentados no topo. `BATCH` é recusado: entregue cada filho aprovado
separadamente, com identidade, papel autorizado, journal e recibo próprios.
Tipos desconhecidos também são recusados; o cliente não autoriza inferência de
outra operação pelo conteúdo do payload. Replays ALREADY_APPLIED continuam
exigindo conferência da entidade.
`created_at` precisa ser um timestamp UTC válido, com `Z` ou `+00:00`; o cliente
rejeita valores inválidos sem normalizar os bytes aprovados. Em CONTEST/REFUTATION,
os campos opcionais `source` e `referee` do payload devem corresponder ao papel
confiável, preservando os controles de admissão e autoria do Writer.
Papéis diferentes do padrão REFEREE_1 precisam explicitar essa autoria no payload.
Em HANDOFF, `from_role` deve corresponder ao `runtime_role` confiável; nas
transições, a mesma regra vale para `writer_role`, inclusive nos wrappers e aliases.
Uma origem genérica CHATGPT não autoriza assumir outro papel no payload. O
chamador precisa resolver o papel autorizado antes de preparar essas operações.
O Writer continua validando schema, papéis das mutações, dependências e revisões.
O lock do cliente serializa apenas threads do mesmo processo. Runtimes distintos
podem criar duplicatas físicas concorrentes; o intent_id mantém o efeito idempotente
no Writer único. O Drive não oferece CAS atômico em files.update: preservar um
único aplicador continua obrigatório.

No chat, use diretamente o conector Drive autorizado para o upload bruto. No Site,
a concessão Drive permanece read_only. Não amplie acesso para instalar este cliente.
