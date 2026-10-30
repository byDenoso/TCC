# NEXO MCP remoto

Mantém o servidor MCP do PR #184 na rota /api/mcp; separa leitura e escrita com OAuth 2.1 de um provedor externo, sem criar outro servidor de identidade.

## OAuth e privacidade

- /.well-known/oauth-protected-resource anuncia o recurso exato e o issuer OAuth (RFC 9728).
- O servidor valida JWT de acesso **RS256** contra JWKS HTTPS, issuer, audience, expiração, subject fixo do proprietário e os escopos realmente concedidos.
- nexo:read permite initialize, tools/list e status. nexo:write **também exige nexo:read** e autoriza propose, bind_recipe e board_post. Tokens inválidos recebem 401; tokens de leitura tentando escrever recebem 403.
- O issuer externo deve implementar OAuth 2.1 com autorização PKCE e suporte ao cadastro do cliente ChatGPT por CIMD/DCR ou configuração compatível. Para uso contínuo pelo ChatGPT, configure emissão de refresh token e offline_access conforme a documentação da OpenAI.
- O servidor recusa todas as credenciais se o OAuth não estiver configurado. Não há fallback para MCP_SHARED_SECRET nem login por PIN.
- O TCC é público. BOARD_POST exige texto iniciado por PUBLIC:, que deve ser sanitizado pelo operador antes do envio. Tower, handoffs e mural privado permanecem no Drive e no Writer canônico. Staging Git não equivale a aplicação à Tower.

## Variáveis na Vercel

- OAUTH_ISSUER: issuer HTTPS **exato** do provedor, preservando barra final se houver, idêntico à claim iss.
- OAUTH_AUDIENCE: URL HTTPS exata do recurso MCP, por exemplo https://SEU_HOST/api/mcp; precisa corresponder à claim aud.
- OAUTH_JWKS_URI: endpoint HTTPS de chaves públicas do emissor OAuth.
- OAUTH_OWNER_SUB: identificador subject (claim sub) do proprietário autorizado, obtido por canal administrativo privado.
- GITHUB_TOKEN: token com permissão Contents read/write **somente** em byDenoso/TCC.
- NEXO_BRANCH: opcional. Sem configuração, usa nexo/dispatch-runtime. Apenas no teste isolado, defina nexo/mcp-smoke-disposable.

Não registre valores, tokens, emails ou identidade privada no GitHub; configure tudo diretamente no painel do provedor/Vercel. MCP_SHARED_SECRET da versão anterior não é mais utilizado.

## Preparar deploy

1. Revise este PR, sua dependência externa OAuth e o provedor escolhido. Não faça merge automaticamente.
2. Na equipe Vercel correta, crie um projeto ligado a byDenoso/TCC e Root Directory mcp-nexo, com Node >=20. Configure as variáveis acima somente no ambiente necessário.
3. Valide inicialmente uma prévia isolada; publique apenas quando autorizado, com OAuth configurado, testes verdes e ramo NEXO_BRANCH seguro.
4. Cadastre https://SEU_HOST/api/mcp como MCP personalizado na interface web compatível do ChatGPT. A descoberta OAuth será https://SEU_HOST/.well-known/oauth-protected-resource.
5. Uma conexão OAuth válida não concede ferramentas de escrita em todos os planos: ChatGPT Pro tem atualmente escopo limitado a leitura/recuperação para servidores MCP personalizados; operações de escrita dependem de suporte do espaço de trabalho.

## Testes

Na pasta mcp-nexo:

    npm ci (se package-lock existir) ou npm install
    node --test test/oauth.test.js
    npm test
    node --check api/mcp.js

A suíte OAuth usa chaves RSA temporárias. O teste HTTP usa servidor Node real, SDK MCP da dependência, JWT de teste e upstreams simulados em memória; nunca aciona GitHub real, e o único ramo aceito para BOARD_POST é nexo/mcp-smoke-disposable. Ela cobre initialize, tools/list, status, 401 sem bearer, 403 com escopo de leitura e readback de BOARD_POST. A integração externa com provedor OAuth, Vercel e ChatGPT ainda exige execução pós-deploy.

A projeção pública usada por status permanece em https://bydenoso.github.io/Pantheon/tower-projection/projection.json; uma resposta inválida ou indisponível causa erro explícito. Nenhum workflow, solver, critério científico ou destino privado foi alterado.
