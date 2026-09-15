# Scientific execution launch markers

Os workflows pesados não devem ser disparados por commits comuns de código ou documentação.

Para iniciar a campanha ACT otimizada, crie uma branch de execução contendo somente o marcador:

`.github/launch/peer-act20-optimized.txt`

Abra um PR de execução para `main` e **não mesclar** esse PR. O marcador existe apenas para registrar e disparar a campanha. A execução manual pelo painel também permanece disponível.

Para continuar uma campanha interrompida, execute o workflow manualmente e informe `resume_run_id` com o ID exato do run otimizado anterior. Se o artefato solicitado não existir, o workflow deve falhar em vez de começar do zero silenciosamente.
