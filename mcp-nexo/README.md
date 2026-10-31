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


## Descoberta privada integrada (sem novo serviço)

A mesma rota `/api/mcp` oferece três ferramentas adicionais, todas exigindo `nexo:read`:

- `catalog_status`: fontes lidas, bloqueadas ou não configuradas, versão, data, SHA-256 e quantidade de registros.
- `catalog_search`: busca por texto e categoria, páginas de 1–100 registros, cursor vinculado ao filtro e ao hash da fonte. Um cursor fica inválido quando a fonte muda.
- `catalog_get`: um ID retornado pela busca, contrato original e proveniência. Não lê um arquivo arbitrário nem executa código indicado pelo catálogo.

Categorias: runtime, solver, adapter, likelihood, dataset, recipe, skill, contract, tower, writer, resource e capability. Os códigos de classificação documentados do LOOKUP são mapeados conservadoramente; nomes sem tipo explícito permanecem `resource` e podem ser encontrados por texto. Não inferimos validação científica de nome, pasta, categoria ou estado histórico. Entradas de adaptadores agregam seus vínculos e limitações documentados, sem promover todos os datasets à condição validada.

A implementação não transforma os recursos em ferramentas individuais e não duplica o banco, Tower ou Writer. O catálogo continua no Drive; o processo mantém somente cache privado volátil de 30 segundos. `remoteExecution: false` é explícito em todas as respostas de descoberta: catálogo disponível não significa solver instalado, backend conectado, concessão de execução ou aprovação científica.

### Configuração privada pendente

Configure fora do Git, somente após autorização operacional:

- `NEXO_CATALOG_SOURCES`: JSON de até 32 fontes previamente autorizadas, por exemplo:
  `[{"id":"runtime","fileId":"ID_PRIVADO_CONFIGURADO_NO_SERVIDOR","format":"runtime"}]`.
- `GOOGLE_DRIVE_ACCESS_TOKEN`: credencial de leitura do servidor, independente do token OAuth recebido do cliente MCP. O servidor não cria, renova nem amplia credenciais. Um token expirado gera fonte `UNAVAILABLE`; use a infraestrutura de credenciais autorizada para renová-lo. Acesso ao Drive/Sheets precisa ser concedido explicitamente fora desta implementação.

Formatos suportados:

| Formato | Fonte e contrato |
| --- | --- |
| `runtime` | `MCP_RUNTIME_CONTRACT_V1`, capabilities, referências e versão; preserva estados e limites originais |
| `datasets_csv` | Inventário CSV com `resource_id`; preserva contratos, hashes declarados, loaders e limitações |
| `lookup_sheet` | Planilha canônica, aba `LOOKUP`, colunas `drive_file_id,name_category_aliases,canonical_path,resource_json` |
| `index_json` | Array ou campo `resources`, `entries` ou `items`; IDs explícitos e categorias reconhecidas |

IDs privados não são embutidos no repositório. Não configure espelhos públicos para contornar autorização. Não colocar catálogos reais, checkpoints, nomes privados ou tokens em fixtures, logs, issues ou commits. Fixtures do teste são sintéticas. A revisão concreta do catálogo é lida da fonte, não congelada no código.

O loader usa apenas GET em origens Google fixas, recusa redirects, limita cada fonte a 64 MiB e 50.000 registros, e verifica versão/metadados antes e depois da leitura. A planilha pede as colunas completas `LOOKUP!A:D`, sob o limite de bytes; mais de 50.000 linhas de dados bloqueia a fonte, sem truncar caudas esparsas silenciosamente. `sha256` opcional na configuração fixa os bytes da representação lida; para Sheets é a resposta JSON da API, não o hash de um XLSX exportado. SHA-256 do catálogo **não** certifica os bytes dos arquivos nele referenciados. Formatos não implementados, corrupção, divergência de hash ou mudança durante a leitura permanecem bloqueados. Fontes parcialmente disponíveis geram estado `PARTIAL`, nunca catálogo silenciosamente completo.

Esta versão não hidrata payloads científicos, não executa solvers, não dispara campanhas, não escreve na Tower e não substitui o Writer. `status` público e as três operações públicas de staging preexistentes permanecem separados. Para ligar execução futura, é necessário implementar e homologar um backend no contrato canônico, com autorização específica; esta descoberta não o fornece.

### Verificação local e homologação

`npm ci && npm test` executa testes de parser, paginação, hash, limites, isolamento de origem, readback de versão, OAuth e HTTP MCP local com upstreams simulados. `package-lock.json` registra versões resolvidas. Isso não é homologação contra Google, Vercel ou provedor OAuth reais. Antes de conectar produção: configurar fontes/grants privados, executar readback autorizado do servidor e confirmar `initialize`, `tools/list`, busca/detalhe, 401/403 e ausência de escrita. Não fazer merge/deploy automaticamente.
