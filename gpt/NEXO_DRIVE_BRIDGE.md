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

A lista de tipos autorizados é definida pelo chamador confiável, nunca pelo JSON.
O Writer continua validando schema, papéis das mutações, dependências e revisões.
O lock do cliente serializa apenas threads do mesmo processo. Runtimes distintos
podem criar duplicatas físicas concorrentes; o intent_id mantém o efeito idempotente
no Writer único. O Drive não oferece CAS atômico em files.update: preservar um
único aplicador continua obrigatório.

No chat, use diretamente o conector Drive autorizado para o upload bruto. No Site,
a concessão Drive permanece read_only. Não amplie acesso para instalar este cliente.
