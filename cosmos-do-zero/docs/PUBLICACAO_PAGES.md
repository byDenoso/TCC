> Registro histórico anterior à homologação integrada de13/10/2026. Os resultados e instruções abaixo pertencem à revisão indicada no próprio documento; não aprovam o build atual nem autorizam publicação. Consulte o relatório deQA, código versionado e prévia privada da entrega atual.

# Publicação preparada: Cosmos do Zero

Preparação local em 12/10/2026. Nenhum push, deploy, alteração em Pages ou DNS foi realizado nesta adaptação. O ZIP original foi preservado. Os estados remotos descritos no pacote anterior são históricos e precisam ser reconferidos.

## Dois destinos explícitos

- `github`: origem `https://bydenoso.github.io`, base `/TCC/cosmos-do-zero`; artefato aninhado com redirecionamento na raiz do TCC. URL de fallback: https://bydenoso.github.io/TCC/cosmos-do-zero/
- `custom`: origem `https://cosmos.denerpereira.com.br`, base `/`; site na raiz do artefato. URL final: https://cosmos.denerpereira.com.br/
- `push` só testa e guarda artefato. Publicação exige execução manual com `publish=true` e `domain_ready=true`, na branch `cosmos-do-zero`.
- O workflow confere o domínio configurado em Pages; no modo custom também exige CNAME DNS para `bydenoso.github.io`. Isso não comprova certificado HTTPS nem propagação mundial; a etapa `verify` testa HTTPS e os recursos depois do deploy.
- Pages tem um único destino por repositório. Depois de vincular domínio, a URL github.io pode redirecionar: ela não é preview independente simultâneo. O fallback exige reconfiguração e rebuild `github`.
- `CNAME` no artefato é apenas informativo: GitHub Actions ignora esse arquivo para configuração de domínio. Settings > Pages é obrigatório.

## Acessos e sequência de implantação

1. Conta com escrita na branch `cosmos-do-zero` e administração de Pages em `byDenoso/TCC`, além de acesso ao DNS autoritativo de `denerpereira.com.br`. Conferir se TCC já hospeda outro Pages/workflow antes de publicar; não substituir um site existente sem conciliação. Não alterar `main`, NEXO, registros do domínio raiz, www, MX ou TXT existentes.
2. Registrar a configuração atual de Pages e o registro DNS exato de `cosmos`, se houver, para rollback. Verificar a propriedade do domínio pelo fluxo oficial GitHub (TXT fornecido pelo GitHub; nunca adivinhar valor). Credenciais são inseridas pelo titular, fora do chat.
3. Enviar somente `cosmos-do-zero/` e `.github/workflows/cosmos-do-zero-pages.yml` à branch isolada. `publish-tcc.ps1` agora apenas prepara commit/push nessa branch; não habilita Pages. Ele recusa pasta já existente: reconciliar o diff nesse caso. Nunca executar contra `main`.
4. Executar build/testes `github` sem publicação. Configurar Settings > Pages > Source: GitHub Actions e conferir permissões do environment `cosmos-do-zero-pages` para a branch isolada. O workflow manual precisa estar disponível no seletor Actions; se não aparecer porque não existe na branch padrão, NÃO alterar main só para habilitá-lo. Usar execução autorizada em ambiente com `gh` e verificar suporte de dispatch da branch; caso GitHub recuse, parar e decidir com o titular uma forma de ativação compatível, sem alegar deploy.
5. Opcionalmente publicar e verificar fallback com `target=github`, `publish=true`, `domain_ready=true`, somente com campo Custom domain vazio em Pages.
6. Preparar e testar `custom` com `publish=false`. Em uma janela de migração, associar `cosmos.denerpereira.com.br` em Settings > Pages primeiro, então criar/alterar apenas CNAME `cosmos` -> `bydenoso.github.io` (sem protocolo nem caminho; sem proxy, se houver). Conflitos A/AAAA/CNAME no mesmo nome precisam ser resolvidos conscientemente. Não deixar DNS apontando para um Pages desativado.
7. Aguardar validação DNS/certificado do GitHub; habilitar Enforce HTTPS quando disponível. A mudança de base e do domínio pode ter janela transitória; não é migração de zero downtime. Executar `custom`, `publish=true`, `domain_ready=true`. Exigir build, deploy e verify verdes e abrir home/capítulos/imagens em HTTPS antes de declarar publicado. Não basta o formulário Domain salvo.

## Rollback

Se o domínio já servia outro destino, restaurar seu registro original. Se foi criado agora, remover o CNAME antes de desassociar o domínio para não deixar DNS pendurado. Remover Custom domain de Pages, executar build/deploy `github` com conferência explícita e verificar a URL de fallback. Para um Pages preexistente, restaurar configuração e artefato anteriores registrados no passo 2. A reversão não toca `main`, NEXO ou domínio raiz. Caches/DNS/certificado podem retardar a recuperação.

## Reprodução local

Na pasta `cosmos-do-zero`, com Node >=22.12 (CI: 24):

```sh
npm ci
npm run check
npm test
npm run test:http
SITE_URL=https://bydenoso.github.io SITE_BASE=/TCC/cosmos-do-zero SITE_PUBLIC=true npm run build
SITE_URL=https://bydenoso.github.io SITE_BASE=/TCC/cosmos-do-zero SITE_PUBLIC=true npm run test:pages
SITE_URL=https://bydenoso.github.io SITE_BASE=/TCC/cosmos-do-zero node scripts/package-pages.mjs
SITE_URL=https://cosmos.denerpereira.com.br SITE_BASE=/ SITE_PUBLIC=true npm run build
SITE_URL=https://cosmos.denerpereira.com.br SITE_BASE=/ SITE_PUBLIC=true npm run test:pages
SITE_URL=https://cosmos.denerpereira.com.br SITE_BASE=/ node scripts/package-pages.mjs
```

Para E2E e renders, instalar Chromium pelo Playwright e executar preview com as mesmas variáveis; BASE_URL local é `http://127.0.0.1:4321` para custom e `http://127.0.0.1:4321/TCC/cosmos-do-zero` para github.

Referência oficial: https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site
