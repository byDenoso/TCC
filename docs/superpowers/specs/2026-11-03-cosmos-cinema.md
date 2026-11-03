# Cosmos — escola azul e audiovisual

## Resultado
Evoluir o Cosmos inteiro mantendo as seis aulas e 36 experiências. Azul profundo substitui o roxo da interface; linguagem natural aproxima cada pergunta de uma cena. Seis aberturas narrativas em SVG têm etapas, pausa, régua temporal e um vídeo curto equivalente. As capas passam a usar modelos vetoriais vivos.

## Contrato
- Escopo: Cosmos do Zero, branch isolada `cosmos-do-zero` do TCC. NEXO Research e dados científicos privados ficam fora deste trabalho.
- Preservar IDs, URLs, conteúdo científico, progresso local, quizzes, fontes, suporte sem WebGL e movimento reduzido.
- Reutilizar Astro, SVG, GSAP/ScrollTrigger e Three.js/glTF existentes. Novas dependências só diante de necessidade demonstrada.
- Azul-base `#031226`, superfícies `#08233d`, ciano `#74dceb`, azul de destaque `#83b6ff`; cores que representam grandezas físicas permanecem semanticamente distintas.
- Narrativa: situação inicial, transformação, conclusão. Um relógio por cena; interação manual pausa; cenas fora da janela e abas ocultas param.
- Filmes de 20 s, H.264 720p, sem reprodução de áudio automática, com texto português, legenda VTT opcional e transcrição. Vídeo e SVG compartilham a descrição matemática.
- Galáxias: saltos de escala explicitamente ilustrativos. Expansão: lambda/lambda_emitido = a/a_emitido; exemplo 400→800 nm. Rotação: curvas de modelo, sem atribuir medições fictícias. Estrelas: caminhos simplificados por massa. Órbitas: períodos proporcionais a a^(3/2), dimensões ilustrativas. Atmosfera: altura 0–120 km e limites aproximados das camadas.
- Modo cinema: cena, legenda e controles juntos; perguntas e leitura retornam ao fechar. Escape restaura foco e posição.
- Entregar também um prompt reutilizável e publicar a versão verificada nos mesmos destinos existentes.
