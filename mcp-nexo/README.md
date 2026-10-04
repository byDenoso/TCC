# Servidor MCP do NEXO

MCP remoto por Streamable HTTP em `/api/mcp`, com quatro ferramentas: `status`, `propose`, `bind_recipe` e `board_post`.

`status` devolve a projeção pública inteira. As outras ferramentas criam propostas públicas em `byDenoso/TCC`, branch `nexo/dispatch-runtime`, sob `nexo_persist/requests/`. O relay e o Writer existentes aplicam a proposta. Cada gravação é conferida por leitura de volta e devolve caminho, branch, `stable_id` e SHA do blob.

O ID determinístico usa o conteúdo do envelope ordenado, excluindo `created_at`; repetir o mesmo pedido preserva o primeiro arquivo e sua data. Mudar o payload gera outro ID. O formato segue [PROPOSAL_SCHEMA.md](../gpt/PROPOSAL_SCHEMA.md); BATCH tem no máximo 10 itens. Handoffs privados são recusados: seu destino é o Drive privado. O chamador só envia conteúdo público sanitizado e parâmetros declarativos.

## Deploy na Vercel

1. Após revisar e integrar o PR, importe `byDenoso/TCC` na Vercel, com Root Directory `mcp-nexo` e Framework Preset **Other**. Use Node.js 24. A branch `nexo/dispatch-runtime` já deve existir.
2. Crie as duas variáveis protegidas na Vercel: `GITHUB_TOKEN` (token fine-grained limitado a TCC, Contents: Read and write) e `MCP_SHARED_SECRET` (valor aleatório criado pelo Dener). Nunca cole os valores no GitHub, PR ou código.
3. Faça o deploy. URL do conector: `https://<domínio-do-projeto>.vercel.app/api/mcp`. Use o domínio efetivamente retornado pela Vercel.
4. Configure o header `Authorization: Bearer <MCP_SHARED_SECRET>` no cliente MCP. Por exemplo, o Codex aceita `bearer_token_env_var = "MCP_SHARED_SECRET"` na configuração do servidor remoto.

O servidor implementa a autenticação por header solicitada, utilizável diretamente no Codex. O conector do ChatGPT Business exige um adaptador OAuth antes desse endpoint: a [documentação de autenticação do ChatGPT](https://developers.openai.com/plugins/build/auth) informa que ele não envia API keys personalizadas. Escolher “sem autenticação” não envia o segredo. A URL acima só deve ser cadastrada no ChatGPT depois desse adaptador; não afrouxe a autenticação para conectá-lo.

## Verificação local

```sh
cd mcp-nexo
npm ci
npm test
npm start
```

`npm test` exercita o protocolo MCP real por HTTP local, valida autenticação, formato, identidade, repetição sem nova gravação, rejeição de dado privado e divergência no read-back. O serviço GitHub é uma fixture para esses testes.

Para testar a gravação real, crie uma branch descartável `nexo/mcp-smoke-<sufixo>` e disponibilize as duas variáveis apenas no ambiente. Execute:

```sh
npm run smoke -- nexo/mcp-smoke-<sufixo>
```

Esse teste chama `board_post` duas vezes, verifica caminho/SHA e idempotência, e recusa qualquer branch que não comece com `nexo/mcp-smoke-`. O relay não acompanha essa branch. Apague-a quando terminar. Nenhum workflow existente é alterado.
