# Cosmos

Escola de Física, Astronomia e Cosmologia. O domínio público é https://cosmos.denerpereira.com.br. A versão com API e sessões fica em https://cosmos-do-zero.vercel.app. As duas distribuições usam a mesma fonte Next.js. Os visitantes podem estudar e guardar um histórico neste navegador. Uma conta permite retomar o estudo em outros dispositivos.

## Executar

Use Node.js 24 e execute na pasta desta escola.

    npm ci
    npm run dev

O currículo fica em content/*.mdx. O cabeçalho JSON contém disciplina, nível, sequência, gráfico, exercício, gabarito, tolerância e fonte. O compilador MDX aplica remark-math e KaTeX durante a construção. Contribuições editoriais feitas no painel ficam versionadas em PostgreSQL. A aplicação renderiza esse texto como conteúdo, sem executá-lo como MDX.

O motor físico está em src/lib/model.ts. A projeção SVG, o gráfico D3 e a cena Three.js recebem a mesma simulação. A imagem no início usa vista ilustrativa de Saturno com shader progressivo. O explorador inclui fontes e escalas por destino.

## Contas e edição

Configure DATABASE_URL (ou POSTGRES_URL) no ambiente de servidor para um PostgreSQL persistente com TLS conforme o provedor. A aplicação cria apenas tabelas com prefixo cosmos_school_ e serializa a inicialização em uma transação. O usuário escolhe um pseudônimo e uma senha. As sessões usam cookies HttpOnly e Secure em HTTPS. A atividade de visitante pode ser importada explicitamente no ambiente de contas da mesma origem. O histórico do visitante no domínio Pages fica associado ao navegador e àquela origem.

Contas novas recebem o papel student. O papel editor é atribuído pelo operador a uma conta existente quando autorizado. A rota /gestao/ permite salvar rascunhos, submeter uma revisão científica e publicar seu conteúdo com fonte HTTPS. Conflitos de versão retornam 409. A página /trilhas/ inclui as publicações e cada atualização mantém o histórico.

COSMOS_CERTIFICATES=1 habilita a emissão. O servidor verifica todos os exercícios do nível e pelo menos 70% na avaliação, emite um identificador estável e permite a consulta pública pelo identificador. As questões do currículo também estão disponíveis para estudo individual.

## Validação e publicação

    npm run check
    npm test
    COSMOS_TEST_DATABASE_URL=postgresql://... npm run test:database
    npm run build:pages
    npm run build

Use uma base isolada para os testes PostgreSQL. O teste cria duas contas temporárias com identificadores aleatórios e remove seus dados ao terminar. A exportação Pages produz out/. O build de servidor produz .next/. Para os testes de navegador, instale o Chromium do Playwright, sirva uma dessas distribuições e execute os comandos abaixo.

    BASE_URL=http://127.0.0.1:4173 npm run test:browser
    BASE_URL=http://127.0.0.1:4173 node tests/explorer.mjs

O workflow de Pages constrói e testa a escola antes da implantação no domínio configurado no repositório. O projeto cosmos-do-zero na Vercel usa esta subpasta como raiz e o preset Next.js. O commit anterior e seu histórico preservam a implementação Astro e os dados originais das imagens.
