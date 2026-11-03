# Prompt para evoluir o Cosmos do Zero

Refaça o Cosmos do Zero como uma escola interativa de cosmologia em português brasileiro. A experiência deve convidar a observar, experimentar e entender uma ideia por vez. Use perguntas reais, frases curtas e linguagem natural. Explique termos técnicos perto de onde aparecem.

## Direção visual

Use azul profundo `#031226` como fundo, superfícies `#08233d`, ciano `#74dceb` nos controles e azul claro `#83b6ff` nas comparações. Combine o céu escuro com textos claros, bom contraste e espaços confortáveis. Preserve cores científicas quando elas comunicarem temperatura, comprimento de onda ou categorias. Mantenha a opção de tema claro.

## Escola e navegação

Mostre uma demonstração logo após a abertura. Apresente as seis aulas com capas vetoriais que antecipem o assunto. Cada aula deve começar com uma pergunta, uma explicação visual curta e um caminho claro para entrar nos seis assuntos. Evite instruções repetidas. Diferencie “Avançar cena” de “Próximo assunto”. Preserve URLs, histórico de leitura, progresso, desafios, referências e dicionário.

## SVG, motion graphics e vídeos

Crie uma história visual de 20 segundos para cada aula: endereço cósmico; alongamento da luz; giro de galáxias; vida das estrelas; períodos orbitais; atmosfera. Organize cada história em três momentos nomeados, com uma frase explicando a mudança. Os SVG devem ser nítidos, determinísticos e ter títulos e descrições acessíveis. Gere os vídeos MP4 e suas legendas a partir da mesma geometria e dos mesmos estados usados nas cenas.

Reproduza as cenas automaticamente quando estiverem visíveis. Pause ao sair da tela ou ocultar a página. Uma pausa manual, a escolha de uma etapa ou a mudança da régua deve prevalecer. Ofereça reproduzir, pausar, recomeçar e escolher o momento. Carregue vídeos apenas quando solicitados. Faça uma capa se mover por vez e ofereça um botão para pausar as capas.

Use o Three.js existente quando a profundidade ajudar a compreender; use SVG para diagramas, curvas, comparações e alternativas ao WebGL. Use GSAP nas transições que orientam a leitura. Adicione bibliotecas apenas quando resolverem uma necessidade concreta. Preserve uma explicação estática útil quando JavaScript, WebGL ou movimento não estiverem disponíveis.

## Modo ampliado e acessibilidade

No modo cinema, mantenha a cena, os controles e o botão de fechar acessíveis inclusive em celulares baixos. Escape deve fechar e devolver o foco ao botão original. Respeite a preferência de movimento reduzido, mostre uma conclusão estática legível e permita explorar as etapas manualmente. Não inicie áudio automaticamente. Disponibilize a transcrição e as legendas em português.

## Rigor e entrega

Identifique ilustrações, modelos e dados observados. Declare simplificações de escala, tempo e geometria. Confira relações como comprimento de onda proporcional ao fator de escala e períodos orbitais compatíveis com Kepler. Não apresente curvas inventadas como medições. Preserve as fontes de cada explicação.

Implemente, confira as seis aulas, navegação por teclado, celular, modo ampliado, vídeos, pausa manual, movimento reduzido e retorno à cena. Execute as verificações do projeto e publique pelos destinos já configurados. Entregue a URL funcionando e uma imagem real do resultado.

## Implementação desta versão

As cenas estão em `cosmos-do-zero/src/lib/story-scenes.ts`; o controle está em `src/scripts/story.ts`; a interface está em `src/components/StoryLesson.astro`. Os seis filmes, capas, legendas e a procedência estão em `public/media/stories/`.

Para regenerar os vídeos, use Node.js 24, as dependências do projeto e FFmpeg: `node scripts/render-story-films.mjs`, dentro de `cosmos-do-zero`. Depois execute `npm run check`, `npm test`, o build público e os testes de navegador do workflow existente.
