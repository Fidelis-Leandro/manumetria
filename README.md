# ManuMetria

**Avaliação cinemática da mão por visão computacional**

O ManuMetria mede os movimentos da mão com uma **webcam comum**, sem marcadores, para profissionais de
reabilitação. A câmera encontra 21 pontos da mão (MediaPipe) e o sistema calcula, ao vivo, os ângulos de
cada articulação dos dedos (MCP, PIP, DIP e IP do polegar), o TAM (*total active motion*), as repetições e a
qualidade do movimento. Uma mão 3D desenhada pelo próprio sistema mostra, por cores, a situação de cada
articulação. As avaliações ficam numa ficha por paciente, com a evolução ao longo do tempo, relatório em
PDF e exportação em CSV.

> Software de pesquisa. Não é dispositivo médico registrado na ANVISA.

---

## Requisitos

- Windows 10 ou 11 (64 bits);
- **Python 3.11** (64 bits);
- internet durante a instalação e cerca de 1 GB de espaço livre;
- uma webcam, para medir de verdade (sem câmera, dá para usar a mão simulada);
- placa de vídeo com OpenGL 2.0 ou superior (qualquer computador recente).

## Instalação passo a passo

1. **Baixe o projeto**: no GitHub, **Code → Download ZIP** (e descompacte), ou `git clone` do repositório.
2. **Instale o Python 3.11**, se ainda não tiver: no PowerShell, rode
   `winget install -e --id Python.Python.3.11`
   (ou baixe em <https://www.python.org/downloads/release/python-3119/>, marcando *Add python.exe to PATH*).
3. **Dê dois cliques em `Instalar sistema.bat`.** Ele:
   - cria o ambiente Python só deste projeto (`.venv`);
   - instala os pacotes do `requirements.txt`;
   - baixa o modelo de detecção da mão do MediaPipe (`hand_landmarker.task`);
   - roda os testes automáticos;
   - cria 3 pacientes fictícios de demonstração.

   Leva de 2 a 10 minutos na primeira vez e termina com `=== Instalacao concluida ===`.
4. **Abra o ManuMetria:**
   - **`Abrir sistema.bat`**: com a webcam;
   - **`Abrir simulacao.bat`**: com uma mão simulada (não precisa de câmera).

O passo a passo manual (e a solução dos problemas mais comuns) está em [INSTALACAO.md](INSTALACAO.md).

## Como usar

1. **Pacientes** (tela inicial): cadastre um paciente ou abra a ficha de um paciente existente (dois cliques).
2. Na **ficha**, clique em **Nova avaliação**.
3. Peça ao paciente para mostrar a mão com a **palma voltada para a câmera**, a cerca de 50 cm, com boa luz.
4. **Calibração**: o sistema pede a mão aberta e parada por 2 segundos.
5. Peça o movimento (por exemplo, abrir e fechar a mão o máximo possível, algumas vezes). Os cartões dos
   dedos contam os movimentos ao vivo; clique num dedo para ver os detalhes.
6. A tela de avaliação abre com a **câmera** em destaque e a **mão 3D** na miniatura do canto (clique na
   miniatura, ou nos botões *Câmera* / *Modelo 3D*, para trocar). Na mão 3D, cada esfera de articulação tem a cor do seu dedo, conforme o % do normal do TAM ativo na
   sessão: vermelho abaixo de 50%, amarelo de 50% até abaixo de 75% e verde a partir de 75% (cinza enquanto não há
   medidas). Arraste para girar e passe o mouse sobre uma articulação para ver o nome e os valores dela.
7. Clique em **Encerrar sessão**. No relatório, escreva as observações, faça o **reteste** quando indicado e
   **salve na ficha**. Depois, gere o **PDF** ou o **CSV**.
8. A **ficha** mostra a evolução (gráfico, mapa, comparação entre avaliações). A tela **Ajuda** explica cada
   medida; passar o mouse sobre um número também mostra a explicação.

Para conhecer o sistema com os pacientes fictícios: abra a ficha do **João Pereira (fictício)** (tendões
flexores, zona II) ou da **Maria Souza (fictícia)** (fratura do rádio distal, com alta e platô).

### O que o sistema faz

| Tela | Funções |
|---|---|
| **Pacientes** | cadastro, busca, filtro por situação, % do normal, tendência, destaque de quem está sem avaliação há mais de 3 semanas, exportação para pesquisa |
| **Ficha** | dados do paciente, resumo por regras, lista de avaliações, gráfico de evolução (datas ou semanas desde a lesão), mapa da evolução, comparação entre avaliações, exclusão de avaliação |
| **Avaliação** | câmera + mão 3D com as articulações coloridas, contagem de movimentos por dedo, medidas ao vivo, aviso de mão de lado / longe / perto, qualidade da captura, contador de repetições fortes, conferência ao encerrar |
| **Relatório** | resultado por dedo, observações do profissional, reteste, PDF e CSV |
| **Configurações** | instituição e logotipo do PDF, tema claro/escuro, tamanho da interface, suavização do sinal (Desligada / EMA / Kalman / EMA + Kalman; só na exibição ou também nas medidas), recálculo de avaliações antigas |
| **Ajuda** | como avaliar, como medir bem, glossário de todas as medidas, limites do sistema |

**Medidas** (detalhes na tela Ajuda): flexão de cada articulação, TAM e TAM ativo (% do normal), déficit de
extensão, arco de movimento e arco funcional (Bain et al., 2015), escore de Strickland, distância
polpa–palma, repetições (movimento / parcial / completa), velocidades de flexão, extensão e pico, suavidade
(SPARC), ciclo, cadência e regularidade, indicadores de fadiga, consistência do esforço, independência dos
dedos e contribuição de cada articulação, abertura dos dedos e do polegar, tremor, confiabilidade da
avaliação, erro de medida por teste–reteste (MDC), mudança real, tendência e platô.

### Mudança de método na versão 1.2.0

A versão 1.2.0 (auditoria dos cálculos, [docs/AUDITORIA_CALCULOS.md](docs/AUDITORIA_CALCULOS.md)) mudou a
forma de calcular algumas medidas:

- ângulos por decomposição por osso, recomendação ISB (Wu et al., 2005), a mesma conta da versão web e do
  Hand Filter Lab: a abdução não entra mais na flexão;
- amplitude, classificação, velocidades e excursão de cada repetição pelos dados brutos, com início e fim
  pelo critério da meia sensibilidade (pausas não entram no tempo);
- déficit de extensão sem a tolerância de 3°;
- independência com o mesmo sinal no numerador e no denominador;
- SPARC sobre a norma das velocidades articulares;
- na ficha, a mudança da extensão é classificada pelo déficit (aumentar a hiperextensão não conta como
  melhora).

Por isso, as avaliações salvas antes da 1.2.0 **não são comparáveis** às novas até serem atualizadas: abra
**Configurações > Recalcular avaliações**. O recálculo passa os pontos gravados pelo cálculo novo, mostra o que
muda antes de gravar e guarda o resultado anterior na própria avaliação. As avaliações feitas antes de
15/10/2026 não têm pontos gravados e **ficam no método antigo**.

### Tratamento do sinal

Os ângulos são calculados quadro a quadro a partir dos pontos do MediaPipe. O que o código faz, nesta ordem:

- **descarta** quadros com ângulos fisicamente impossíveis (fora de −60° a 130°) e quadros com a mão de
  lado (palma a mais de 60° da frente), como se fossem falhas de detecção;
- em falhas curtas de detecção (até 0,4 s), **mantém a última pose** e não atualiza as medidas; o lado da
  mão (direita/esquerda) é fixado na calibração;
- **suaviza a exibição ao vivo**: os ângulos de cada articulação (um filtro independente por articulação)
  passam pelos mesmos filtros e parâmetros do artigo EMA × Kalman (Fidelis, ERAMIA-RS 2026; implementação
  de referência no repositório `computer-vision-based-hand-kinematic-assessment`), escolhidos em
  Configurações:

  | Modo | Equações | Parâmetros | Atraso médio |
  |---|---|---|---|
  | Desligada | dados brutos | — | 0 |
  | EMA | y = α·z + (1 − α)·y anterior | α = 0,30 | ≈ 2,3 quadros |
  | Kalman | posição constante: P⁻ = P + Q; K = P⁻/(P⁻ + R); x = x + K·(z − x); P = (1 − K)·P⁻ | Q = 0,01; R = 0,10; P₀ = 1; x₀ = 1º valor | ≈ 2,7 quadros (K estável ≈ 0,27) |
  | **EMA + Kalman** (padrão, como no aplicativo do artigo) | EMA e depois Kalman | os dois acima | ≈ 5,0 quadros (≈ 0,17 s a 30 quadros/s) |

  **Por padrão, o filtro vale só para a exibição ao vivo** (valor "Agora" das articulações, dica da mão
  3D e gráfico "TAM nos últimos 20 s"). **Todas as medidas da sessão usam os dados brutos** (máximos,
  mínimos, déficits, TAM ativo, % do normal, repetições, velocidades, SPARC, independência, PDF e CSV),
  iguais às do modo Desligada. Motivo: a suavização **achata os picos**. Na gravação de referência
  (mão saudável, cálculo da versão 1.2.0), aplicando EMA + Kalman também nas medidas:

  | Dedo | Repetições | TAM ativo (% do normal) | Velocidade de pico (°/s) |
  |---|---|---|---|
  | Polegar | 32 → 21 | 65 → 61 | 332 → 111 (−66%) |
  | Indicador | 23 → 19 | 98 → 88 | 246 → 182 (−26%) |
  | Médio | 31 → 22 | 104 → 94 | 237 → 165 (−30%) |
  | Anelar | 27 → 21 | 107 → 98 | 278 → 172 (−38%) |
  | Mínimo | 25 → 16 | 108 → 99 | 372 → 266 (−29%) |

  (dados brutos → suavizado nas medidas). A flexão máxima da MCP do indicador cai de 81,5° para 71,1°,
  no limite do arco funcional (71°) ([comparação](docs/filtros_comparacao.png)).

  Para reproduzir o pipeline do artigo, marque em Configurações **"Aplicar a suavização também nas
  medidas"**: o filtro entra antes do contador de repetições e de todas as medidas. O filtro só usa a
  sequência de quadros (não o relógio), então recalcular a partir dos pontos gravados dá o mesmo resultado
  da avaliação ao vivo. Quadros descartados ou "segurando" não entram no filtro; perda longa da mão, mão de
  lado, pausa, recalibração e nova avaliação o zeram. Calibração, tremor, abertura dos dedos e
  polpa–palma usam sempre os dados brutos. Cada avaliação registra o filtro e se ele entrou nas medidas
  (PDF, CSV e dicionário de dados), e "Recalcular avaliações" usa sempre esse registro (sem registro:
  Desligada; sem a indicação de medidas: dados brutos);
- os **ângulos** são medidos por decomposição por osso, recomendação ISB (Wu et al., 2005): cada osso tem
  eixos próprios, e a abdução (dedo desviado para o lado) fica separada da flexão;
- o **contador de repetições** decide QUANDO há uma repetição sobre a média dos últimos 8 quadros do TAM,
  com histerese igual à sensibilidade medida na calibração (3 × o tremor parado, medido nos dados brutos).
  A amplitude (pico menos vale), a classificação movimento / parcial / completa, o TAM no pico, a excursão
  de cada articulação e as velocidades médias saem dos **dados brutos**. O início e o fim de cada subida e
  descida seguem um critério do sistema (sem fonte na literatura): último instante a até meia sensibilidade
  do vale, primeiro instante a até meia sensibilidade do pico. Assim, pausas não entram no tempo;
- **déficit de extensão** = maior valor entre 0 e a menor flexão, como na fórmula do TAM da ASSH (a
  hiperextensão conta 0);
- a **velocidade de pico** usa uma derivada por mínimos quadrados em 5 pontos (Savitzky–Golay de 1ª ordem)
  do TAM de cada repetição, e a **suavidade** (SPARC, Balasubramanian et al., 2015) a norma das velocidades
  das articulações do dedo, em grade uniforme de 30 Hz (dados brutos; suavizados só com a opção "também nas
  medidas").

### Limites

- As medidas são **estimativas por câmera comum**, sem marcadores: não substituem a goniometria. O sistema
  ainda não foi comparado com o goniômetro manual; o erro em graus não é conhecido (o reteste estima quanto a
  medida varia ao repetir).
- O erro aumenta com a mão de lado; por isso só entram na medida os quadros com a palma até 60° da frente.
- A rotação de cada dedo em torno do próprio eixo não aparece nos 21 pontos da câmera, e a base do
  metacarpo não é marcada: na MCP, a linha do punho até a base do dedo faz o papel do metacarpo.
- Com uma câmera só, dedos escondidos atrás de outros não são medidos.
- A interpretação (resumo, mudança real, platô) é feita por regras explícitas: apoio à decisão, não
  diagnóstico.

### Verificação dos cálculos

Cada medida tem um teste automático de **resposta conhecida** (`tests\test_auditoria.py`, rodado pelo
`tests\testar.py`); o relatório completo da auditoria da versão 1.2.0 está em
[docs/AUDITORIA_CALCULOS.md](docs/AUDITORIA_CALCULOS.md).

| Medida | Como é testada |
|---|---|
| Ângulos (MCP, PIP, DIP, IP) com sinal | autoteste do Hand Filter Lab e 300 poses do modelo de mão do lab com abdução (erro ~0), mão girada no espaço, hiperextensão, mão esquerda = espelho da direita; prova contra o JavaScript original na gravação (diferença ≤ 0,005°) |
| TAM, TAM ativo, déficit, arco, % do normal, classificação | sequências de ângulos com máximos e mínimos conhecidos, déficit = max(0, menor flexão), dedo sem dados, TAM negativo |
| Repetições, classificação, velocidades, ciclo, cadência, regularidade, tendências, esforço | sinais em cosseno com amplitude e período conhecidos (amplitude 200°, velocidade de pico = A·π/T), instantes de início e fim refeitos à parte, pausa antes e no topo, queda linear de amplitude, uma repetição só, nenhuma repetição |
| Derivada e SPARC | seno com derivada exata (resposta do filtro de Savitzky–Golay), movimento em sino, velocidade nula, articulações em sentidos opostos (norma das velocidades) |
| Independência, acoplamento, contribuição | um dedo sozinho (100%) e todos juntos (acoplamento = (A − sensibilidade)/A); divisão conhecida entre as articulações |
| Sensibilidade e calibração | ruído de desvio padrão conhecido (3 × desvio), calibração sem dados (5°) |
| Arco funcional, Strickland | contas feitas à mão com as faixas de Bain et al. (2015) e as classes de Strickland e Glogovac (1980) |
| Abertura dos dedos e do polegar, polpa–palma | mão plana com direções e distâncias definidas |
| Tremor | oscilação senoidal de frequência e amplitude conhecidas (frequência e RMS = A/√2) |
| Erro de medida (MDC), mudança real, tendência, platô | pares teste–reteste com o MDC calculado à mão (1,96 × desvio das diferenças), +5 pp por semana |
| Tela, banco, CSV e recálculo | na gravação de referência: o salvo é o que a tela mostra, o CSV converte as unidades certas, o dicionário cobre todas as colunas e "Recalcular avaliações" num banco temporário reproduz o resultado |
| Números citados nos textos | conferidos na gravação de referência (quadros descartados, tremor parado, tamanho da mão na imagem, tabela dos filtros) |
| Checagem clínica | a mão saudável da gravação de referência não recebe nenhuma limitação |

### Dados e privacidade

- Pacientes, avaliações e pontos da mão ficam **só neste computador**, em `dados_locais/` (SQLite +
  arquivos `.npz`, sem vídeo). Nada é enviado para a internet. Essa pasta não vai para o GitHub
  (`.gitignore`).
- Dado de saúde é dado pessoal sensível (LGPD, art. 11): no uso com pacientes reais, proteja o computador
  (senha, criptografia do disco) e obtenha o consentimento dos participantes.
- Para recriar os pacientes fictícios: `.venv\Scripts\python.exe tools\criar_demonstracao.py`.

## Estrutura de pastas

```
sistema.py               ponto de entrada (python sistema.py --help mostra as opções)
nucleo/                  cálculo, sem interface (numpy): câmera, cinemática, medidas, estabilizador, filtros
app/                     interface (PyQt5): janela, telas, componentes, mão 3D, banco e relatórios
  telas/                 uma tela por arquivo (pacientes, ficha, avaliação, relatório, configurações, ajuda)
  componentes/           partes das telas (palco 3D, mão 3D procedural em mao3d.py, painéis, gráficos)
  dados/                 banco SQLite, configurações, resultados, interpretação, PDF, exportação
assets/                  logotipo padrão do relatório
tests/                   testes automáticos (tests\testar.py roda todos)
tools/                   pacientes de demonstração e análise de gravações
docs/                    imagens da documentação
Instalar sistema.bat     instalação completa no Windows
Abrir sistema.bat        abre com a webcam
Abrir simulacao.bat      abre com a mão simulada
gerar_hash_registro.bat  pacote e hash SHA-512 para o registro de software (ver abaixo)
```

Detalhes para quem for mexer no código: [DESENVOLVIMENTO.md](DESENVOLVIMENTO.md). Bibliotecas de terceiros e
licenças: [AVISOS_TERCEIROS.md](AVISOS_TERCEIROS.md).

Linha de comando: `.venv\Scripts\python.exe sistema.py --help` (`--sim` mão simulada, `--cam 1` outra
câmera, `--resolucao 1280x720`, `--banco outro.sqlite`, `--replay ARQUIVO` toca uma gravação de pontos).

## Pacote para o registro de software (INPI)

O `gerar_hash_registro.bat` (que chama `tools\gerar_hash_registro.py`) gera um ZIP só com o código-fonte e
a documentação (sem `.git`, `.venv`, `__pycache__`, `dados_locais/`, relatórios, gravações nem o modelo
baixado do MediaPipe), calcula o **SHA-512** do ZIP e salva o ZIP e um `.txt` com o hash, a data e a lista
de arquivos na pasta **`REGISTRO_INPI`**, ao lado da pasta do projeto (fora do repositório).

- Rode esse script **somente depois da aprovação final do orientador**, com a versão definitiva.
- O ZIP gerado **nunca mais pode ser alterado**: qualquer mudança, mesmo de um caractere, muda o hash.
  Não descompacte e recompacte; não renomeie arquivos dentro dele.
- Guarde o ZIP e o `.txt` **em mais de um lugar** (por exemplo: HD externo, nuvem institucional e uma cópia
  com o NIT).

## Autor

**Leandro Fidelis**, Universidade Federal de Ciências da Saúde de Porto Alegre (UFCSPA), laboratório NERV.
