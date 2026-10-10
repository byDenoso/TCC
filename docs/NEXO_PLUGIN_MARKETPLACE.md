# Marketplace NEXO

O marketplace publica um plugin `nexo` com três skills: `nexo-master-router`, `nexo-closed-loop` e `nexo-lite`. A fonte continua em `gpt/skills/*-0.4.0.md`; os três `SKILL.md` do plugin são cópias byte a byte. Não há skill, dado ou ferramenta Olympus no pacote. As referências textuais de privacidade/exclusão de Olympus já presentes nas fontes são preservadas.

## Importar no ChatGPT Business

Depois do merge, abra **Workspace settings > Plugins > Add > Import marketplace**:

| Campo | Valor |
|---|---|
| Source | `https://github.com/byDenoso/TCC` |
| Path | Deixar vazio: o marketplace está na raiz do repositório. |
| Branch, tag, or commit | `main` |

Para testar antes do merge, use o nome do ramo deste PR no terceiro campo. O manifesto é `.agents/plugins/marketplace.json`; **não informe esse nome de arquivo em Path**. O catálogo aponta para `./plugins/nexo`, relativo à raiz do repositório. O plugin usa o manifesto portátil `plugins/nexo/plugin.json` e descobre as skills em `skills/`.

Revise a política de instalação do plugin no workspace após importar. A importação distribui as skills; o acesso ao Google Drive e demais serviços usados por elas depende dos conectores de cada membro.

## Atualizar e conferir

Edite as fontes `gpt/skills/nexo-master-router-0.4.0.md`, `gpt/skills/nexo-closed-loop-0.4.0.md` e `gpt/skills/nexo-lite-0.4.0.md`; depois rode:

```sh
python3 scripts/build_plugin_marketplace.py
python3 scripts/build_plugin_marketplace.py --check
python3 -m unittest discover -s tests -p test_plugin_marketplace.py -v
```

Inclua as fontes e arquivos gerados no mesmo PR. O teste falha por arquivo divergente, ausente ou skill extra. Após o merge, use **Sync now** no marketplace ou aguarde a sincronização diária. Nenhum workflow é alterado.

Formato conferido na documentação oficial:

- [Package your plugin](https://developers.openai.com/plugins/build/plugins)
- [Importing and syncing plugin marketplaces from GitHub](https://help.openai.com/en/articles/20001504-importing-and-syncing-plugin-marketplaces-from-github)
