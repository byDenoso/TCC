# NEXO MCP remoto (staging público)

Servidor MCP stateless HTTP na Vercel, com quatro ferramentas: status, propose, bind_recipe e board_post. Usa mcp-handler 2 e não cria banco nem armazena credenciais.

## Escrita e privacidade

propose(envelope) aceita RECIPE_BIND e BOARD_POST públicos, segundo gpt/PROPOSAL_SCHEMA.md. Calcula stable_id determinístico com SHA-256 de JSON canônico, cria o arquivo nexo_persist/requests/<stable_id>.json no ramo nexo/dispatch-runtime de byDenoso/TCC, lê de volta e devolve caminho, sha256 e SHA do blob. Uma repetição exata não sobrescreve bytes.

TCC é público. BOARD_POST exige text iniciado por PUBLIC: para sinalizar a intenção de publicar; o operador ainda é responsável por sanear o conteúdo. Recados privados, handoffs e Tower seguem exclusivamente o NEXO_INBOX do Drive. O staging Git não aplica propostas à Tower, não confirma Writer e não equivale a recibo.

## Testes locais

Na pasta mcp-nexo, execute npm install, npm test e node --check api/mcp.js. O teste usa GitHub simulado em memória com NEXO_BRANCH=nexo/mcp-smoke-disposable; exercita BOARD_POST, readback, SHA-256, rejeição de recado privado, idempotência e RECIPE_BIND. Não escreve no ramo de produção nem no GitHub externo.

Antes de implantar, valide também o protocolo HTTP com o MCP Inspector (initialize, tools/list, status, autenticação e leitura/escrita contra ramo descartável). A suíte local testa a lógica de staging, não substitui esse teste de integração.

## Implantação na Vercel

1. Conecte o repositório byDenoso/TCC a um novo projeto Vercel, com Root Directory mcp-nexo e Node.js 20 ou superior. A função HTTP ficará em /api/mcp.
2. Crie GITHUB_TOKEN como variável de ambiente secreta, com Contents: read/write restrito a byDenoso/TCC, e MCP_SHARED_SECRET como segunda variável secreta longa e aleatória. Nunca imprima os valores em arquivos, logs ou URLs.
3. Em produção, deixe NEXO_BRANCH ausente para usar nexo/dispatch-runtime. Use NEXO_BRANCH=nexo/mcp-smoke-disposable somente no teste isolado.
4. Depois de publicar, a URL para clientes MCP que aceitem bearer será https://<dominio-real-da-vercel>/api/mcp. Envie Authorization: Bearer <MCP_SHARED_SECRET>, sem segredo no endereço.
5. Confirme bloqueio sem bearer, lista das quatro ferramentas, status e leitura de volta. Só reconfigure o ramo de produção após o teste de integração isolado.

## Limite de compatibilidade

O ChatGPT não aceita chave estática arbitrária como autenticação de MCP customizado. A conexão direta pela interface ChatGPT requer integração OAuth 2.1 ou um proxy compatível. O servidor atende clientes MCP com cabeçalho Authorization próprio; não declare conector ChatGPT instalado apenas informando a URL.

status depende do endpoint público da projeção NEXO. Ausência ou formato inválido resulta em erro explícito. Nenhum workflow existente foi alterado.
