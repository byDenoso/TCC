# PEER pNGB deformado: verificação de integração

Esta etapa executa somente verificações numéricas finitas. Não inicia MCMC e não compara modelos por avaliações em pontos arbitrários.

O modelo físico é V=A[1-cos((phi-phi0)/F)]^3 {1+eta[1-cos((phi-phi0)/F)]}, com eta=0.1, theta_i=2.89155, log10(z_c)=3.81 e decaimento zero. A hipótese adicional F120 não está presente. O ramo nulo é o mesmo CLASS sem campo escalar.

A comparação principal autorizada usa Planck 2018 low-ell TT, Sroll2 EE, Planck 2018 lensing nativo, DESI DR2 BAO, SH0ES H0=73.04 +/- 1.04 e SPT-3G D1 TT/TE/EE multifrequência. SPT isolado é diagnóstico complementar. Planck high-ell, ACT e SPT KK não entram.

Os priors cosmológicos simétricos mantêm os intervalos da campanha anterior, com a mudança explícita para 100 theta_s exato CLASS uniforme [1.030,1.050]; isto não é identidade com a aproximação theta_MC de CAMB. Ambos usam CLASS/HyRec, uma espécie de neutrino com 0.06 eV, N_eff=3.046 e A_L=1. A deformação amostra f_EDE uniforme [0,0.18]; eta, theta_i e z_c permanecem fixos. A,F,H0 são recalibrados para cada cosmologia. Não se transporta uma trajetória previamente ajustada.

O template SPT oficial e seus 43 nuisances/26 priors externos são usados uma única vez. A análise principal usa tau uniforme [0,0.10] com Sroll2; o diagnóstico SPT isolado usa o prior tau gaussiano oficial 0.051 +/- 0.006. Kappa permanece nuisance de TnE; não representa ativação da likelihood KK.

O patch é aplicado ao commit oficial CLASS e85808324f51fc694d12e3ed7439552a3c3f9540. Ele preserva a base histórica exact-KG, incluindo suporte de transferência desativado por gamma=0, e acrescenta somente a deformação ao potencial. Não se publica o pacote privado de origem, dados privados ou resultados antigos. Os dados da análise são obtidos dos distribuidores oficiais.

Produção MCMC permanece bloqueada até terminar a integração real, a verificação de precisão/priors/unidades, a revisão independente e o teste de recursos. PASS desta etapa é validação técnica; não é evidência cosmológica.
