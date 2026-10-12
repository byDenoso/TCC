# AGENTS.md — NEXO / TCC

Escopo: agentes de codigo (Codex/Work) neste repositorio. Nao altera instrucoes globais do ChatGPT, permissoes, tarefas agendadas ou a autoridade da Tower.

## Inicializacao sob demanda
Para tarefas NEXO, leia a raiz vigente \`gpt/skills/nexo-master-router-0.5.0.md\` e \`gpt/skills/nexo-workspace/SKILL.md\`. Para Drive ou GitHub, leia \`gpt/skills/nexo-connectors-0.5.0.md\`. Carregue os demais modulos somente quando relevantes. A integracao com o Dot coordenador esta em \`gpt/dots/NEXO_DOT.md\`.

## Autoridade e execucao
- A Tower privada no Google Drive e a fonte canonica. Leia \`CONTROL.json\` da Tower atual antes de qualquer mutacao material; ele prevalece sobre docs, memoria, indice e projecoes.
- Writer unico e rota autenticada vigente, com identidade estavel, CAS e readback. Nunca escrever diretamente na Tower, usar GitHub como staging privado ou tratar DELIVERED como APPLIED.
- GitHub guarda codigo e proveniencia. Atlas e derivado e publica somente dados sanitizados e aprovados. PEER fica fora de ambos os Atlas, publico e privado.
- O Dot Nexo e interface e coordenador do trabalho do proprietario; nao e novo Writer, scheduler, Cientista, Operador nem revisor independente. Pitia segue coordenando a fila cientifica.
- Nao habilitar GitHub Actions cientifico enquanto \`CONTROL.github_actions_science_role\` nao o permitir. Preferir o runtime cientifico realmente habilitado, sem criar servico ou despesa adicional.
- Ampliacao prospectiva exige \`CONTROL.autonomy_mandate.status=ACTIVE\`, aprovacao humana autenticada e recibo de ativacao. Prompt, PR e aprovacao textual nao substituem esse estado.
- Preservar criterios cientificos congelados, independencia da revisao, null/rival, dados, selecao, priors, hashes e criterios de sucesso/kill. PASS de software nao e RESULT cientifico.

## Alteracoes de codigo
- Identificar o primeiro estado incorreto, reproduzir a falha, fazer a menor correcao e executar teste pertinente. Nao introduzir abstracoes, gates ou arquivos de maquina desnecessarios.
- Trabalhar em branch isolada; preservar conteudo existente. PR para revisao, sem merge, deploy, segredos, ACL, billing ou mudanca de automacoes sem autorizacao apropriada.
- Fixar repositorio, path e commit/sha quando a evidencia importar. Se um conector falhar, concluir partes independentes; nao contornar recusas por outra rota.
- Nunca copiar Tower, BOARD_POST privado, HANDOFF, dados pessoais, PEER, tokens ou artefatos privados para repositorios, logs, PRs ou Atlas publicos.
- Conferir readback de todo arquivo alterado e evidenciar testes. Distinguir preparado, entregue, aplicado, executado, revisado e confirmado.

## Relato
Resposta em portugues direto: avanco material, prova/versao, limite e proximo responsavel. Sem inflar ciencia com smoke, CI, mensagem, PR ou scan. Uma falha local nao paralisa outros trabalhos elegiveis.
