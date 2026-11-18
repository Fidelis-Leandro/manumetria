# Auditoria dos cálculos — ManuMetria 1.2.0

Data: 17/11/2026. Ponto de partida: `main` na tag v1.1.0 (commit dd08986). Objetivo: conferir que todo número
que o sistema mostra, salva, exporta ou afirma é calculado corretamente e tem evidência.

Como foi feito:

- testes de **resposta conhecida** para cada grandeza (`tests/test_auditoria.py`, 105 verificações): mão sintética
  com ângulos definidos, sinais analíticos com amplitude, período e frequência conhecidos, pares teste–reteste
  com o MDC calculado à mão, mão esquerda × direita, hiperextensão e casos-limite (sem dados, uma repetição só,
  divisão por zero);
- a **gravação de referência** (`tests/dados/gravacao_referencia.npz`: mão direita saudável, 60 s, 1.623 quadros,
  1.550 com mão, ~31 quadros/s) passou pelo motor completo para conferir tela = banco = CSV = recálculo e os
  números citados nos textos;
- a goniometria foi comparada com a da versão web (`C:\sistema-mao-web\core\goniometro.js`), idêntica à do Hand
  Filter Lab publicado (seção 3).

A auditoria teve duas etapas:

1. **Conferência da v1.1.0** (seções 1 a 3): o estado do código auditado, as correções de texto e a comparação da
   goniometria. As tabelas dessas seções descrevem a **v1.1.0**.
2. **Decisões do autor D1–D9, aplicadas na 1.2.0** (seções 4, 6 e 7): goniometria ISB, repetições nos dados
   brutos, novo critério de início e fim, déficit sem tolerância, acoplamento no mesmo sinal, SPARC pela norma
   das velocidades articulares e classificação da extensão pelo déficit. A seção 6 mostra o antes × depois.

Termo usado: **dados brutos** = ângulos quadro a quadro, sem filtro de suavização.

Legenda do resultado: **OK** confere; **ERRO** conta, sinal, unidade, índice ou caso-limite errado; **PROMESSA
FALSA** texto afirma o que o código não faz; **SEM FONTE** número afirmado sem evidência no repositório nem fonte
conferida; **DECISÃO** depende de escolha do autor (seção 4).

## 1. Resultado por grandeza

Estado da **v1.1.0** auditada, com as linhas da primeira etapa. "Impacto" = mudança nos resultados da gravação de
referência causada pela correção desta etapa (todas de texto). O que mudou depois, com as decisões D1–D9, está nas
seções 4 e 6.

| Grandeza | Arquivo:linha | Verificação feita | Resultado | Correção | Impacto |
|---|---|---|---|---|---|
| Flexão MCP/PIP/DIP/IP com sinal | `nucleo/kinematics.py:165` | mão sintética 0/30/90/−20° (erro ≤ 0,6°); espelho esquerda = direita (idêntico); hiperextensão negativa; lado trocado inverte o sinal | OK no modelo do próprio sistema | — | — |
| Idem, com abdução | `nucleo/kinematics.py:165` | modelo ISB do Hand Filter Lab: MCP 60° + 20° de abdução → 72,2°; PIP 70° + 15° → 61,7° | PROMESSA FALSA ("no plano do movimento", "o desvio lateral não entra como flexão") + DECISÃO | texto corrigido (docstring, Ajuda, PDF, glossário, README); método: D1 | 0 (texto) |
| Vista da palma | `nucleo/kinematics.py:146` | mão girada 30/60/90/150° → mesmo ângulo (erro < 0,01°); esquerda espelhada = 0° | OK | — | — |
| Descarte de ângulo impossível | `nucleo/kinematics.py:130` | limites −60°/130° | OK; comentário dizia "8 de 1.550", são 7 | comentário corrigido | 0 |
| TAM, TAM ativo, % do normal | `nucleo/kinematics.py:431-443` | 80+100+60 = 240 → 92,3%; com déficits 210−90 = 120; polegar /140; sem dados → None; TAM negativo → 0% | OK | docstring do TAM ativo corrigida ("desconta o viés do MediaPipe") | 0 |
| Déficit de extensão (tolerância 3°) | `nucleo/kinematics.py:98, 419` | 3° → 0, 3,0001° → conta; hiperextensão → 0 | OK; tolerância SEM FONTE | comentário corrigido (o "±5° do goniômetro" e "1–2° de tremor" não tinham evidência); valor: D5 | 0 (tolerância 0 também dá 0 na gravação) |
| Arco | `nucleo/kinematics.py:427` | máx − mín | OK | — | — |
| Classificação do % do normal | `nucleo/kinematics.py:55-56, 522` | 49% ruim, 50% regular, 74,9% regular, 75% bom | OK; textos diziam "acima de 75%" | textos: "75% ou mais"; fonte: D4 | 0 |
| Normais 85/105/70 e 60/80 | `nucleo/kinematics.py:43` | literatura | SEM FONTE (totais 260/140 só em fonte secundária; divisão por articulação sem fonte primária) | textos dizem isso; valores: D4 | 0 |
| Repetições e classificação | `nucleo/kinematics.py:375` | cosseno 40/120/230° → movimento/parcial/completa | OK na regra; a amplitude é a do TAM médio de 8 quadros | PROMESSA FALSA corrigida: README, DESENVOLVIMENTO, comentário e glossário diziam que a média "não muda os valores mostrados" | 0 (texto); método: D2 |
| Amplitude de cada repetição | `nucleo/kinematics.py:375` | cosseno de 200° em 2 s → 194°; em 4 s → 198,5°; na gravação, 10–23% abaixo do pico-vale dos dados brutos | DECISÃO | documentado (Ajuda, PDF, dicionário de dados) | — |
| Sensibilidade e calibração | `nucleo/kinematics.py:63-67, 570` | ruído de DP conhecido → 3 × DP (exato); sem calibração → 5° | OK; comentário do teto de 30° ("7–8° a 14 fps") SEM FONTE | comentário reescrito | 0 |
| Velocidade de pico | `nucleo/kinematics.py:221, 375` | A·π/T: 314°/s esperado, 312°/s medido (−0,6%, resposta conhecida da derivada de 5 pontos) | OK | — | — |
| Derivada (Savitzky–Golay) | `nucleo/kinematics.py:221` | seno de 1 Hz: igual à resposta teórica do filtro (erro < 1e−9) | OK; "~40°/s" virou a conta σ·√2·fs | comentário | 0 |
| Velocidade média de flexão/extensão | `nucleo/kinematics.py:285-296` | cosseno: 200°/s ± 6% | OK com movimento contínuo; **ERRO** em caso-limite: uma pausa com a mão aberta antes de fechar entra no tempo de subida (na gravação, a 1ª subida do indicador "dura" 7,06 s) | documentado; correção: D3 | — |
| SPARC | `nucleo/kinematics.py:233` | sino −1,55 (esperado ~−1,4 a −1,6); fórmula, limiar 0,05 e corte 10 Hz iguais a Balasubramanian 2015 | OK; "abaixo de −3, aos trancos" SEM FONTE | frase retirada | 0 |
| Ciclo, cadência, regularidade | `nucleo/kinematics.py:455` | período 2 s → 2,00 s e 30/min; CV ~0 → Regular; uma repetição → None | OK (ciclo herda o caso-limite do D3) | textos: "abaixo de 15%" (era "até") | 0 |
| Tendências (amplitude, velocidade) | `nucleo/kinematics.py:253` | queda linear 200→140 → −30%; < 6 valores ou início ≤ 0 → None | OK | — | — |
| Amplitude fim × início | `nucleo/kinematics.py:455` | média das 3 últimas / 3 primeiras − 1 (exato) | OK | — | — |
| Consistência do esforço, repetições fortes | `nucleo/kinematics.py:455, 491` | picos iguais → Consistente; 8 de 8 fortes | OK | — | — |
| Independência | `nucleo/kinematics.py:605` | só o indicador se move → 100%; todos juntos → 0% | OK nos extremos | — | — |
| Acoplamento | `nucleo/kinematics.py:605` | mesmo movimento nos dois dedos → 1,01 (esperado 0,975): numerador nos dados brutos, denominador no TAM médio de 8 quadros | DECISÃO | D6 | — |
| Contribuição, articulação limitante | `nucleo/kinematics.py:445, 516` | 0,6/1/0,7 → 26/43/30% | OK | — | — |
| Arco funcional (Bain 2015) | `nucleo/medidas.py:26, 33` | cobertura 100%, 50%, 0%; polegar None; faixas 19–71, 23–87, 10–64 conferidas no resumo do artigo | OK | DOI acrescentado | 0 |
| Strickland | `nucleo/medidas.py:47-60` | (100+75−10−5)/175; classes 85/70/50 (conferidas em Strickland e Glogovac 1980) | OK | — | — |
| Polpa–palma | `nucleo/medidas.py:72, 81` | ponta a 5 cm da linha 5–17 → 5 cm − zero do dedo; zeros = 1,4–2,3 cm na gravação (como o comentário diz) | OK | — | — |
| Abertura dos dedos | `nucleo/medidas.py:100` | mão plana com dedos a −10/0/8/20° → 10/8/12° | OK | dicionário: regra "MCP até 30°" vale para os 3 pares | 0 |
| Abertura do polegar | `nucleo/medidas.py:122` | igual ao ângulo 3D metacarpo do polegar × punho–base do indicador | OK | dicionário mais preciso | 0 |
| Tremor (frequência, RMS, pico) | `nucleo/medidas.py:162-236` | seno de 6 Hz/2 mm → 6,0 Hz e 1,41 mm (= A/√2); 9 Hz/1 mm → 9,0 Hz e 0,71 mm; sem dados → None | OK; "~1 mm de ruído" sem evidência → na gravação, 1,19 mm com a mão saudável parada; faixas 4–6 e 8–12 Hz sem fonte primária conferida | textos reescritos com o valor medido; faixas marcadas como "valores típicos, fonte não conferida"; resolução de 0,5 Hz informada | 0 |
| Distância da câmera | `nucleo/medidas.py:248` | "0,27–0,29": mediana 0,27, P10–P90 0,23–0,29 | OK | comentário com os valores medidos; "meio segundo" = 15 quadros a 30 quadros/s | 0 |
| Confiabilidade | `nucleo/medidas.py:281` | sem quadros → baixa; limiares | OK; limiares escolhidos | — | — |
| Erro de medida (MDC) | `app/dados/interpretacao.py:33` | 3 pares × 5 dedos: MDC = 7,8283 pp feito à mão = sistema; viés; par "baixa" fora; < 10 pares → None | OK (MDC95 = 1,96 × DP das diferenças = 1,96 × √2 × EPM, com EPM = DP/√2) | — | — |
| Mudança real | `app/dados/interpretacao.py:78` | igual ao MDC = estável; acima = melhora/piora | OK | — | — |
| Tendência, platô, resumo | `app/dados/interpretacao.py:114-266` | +5 pp/semana exato; platô com amplitude ≤ MDC | OK | — | — |
| Resultado salvo × tela × recálculo | `app/dados/resultados.py:23`, `app/dados/recalculo.py:54` | gravação: dicionário = métodos do mesmo FingerTracker que o painel usa; recálculo num banco temporário = resultado original (maior diferença 0°) | OK | — | — |
| CSV e dicionário de dados | `app/dados/resultados.py:178`, `app/dados/exportacao.py` | % × 100, contribuição em %, decimais; uma descrição com unidade por coluna | OK; descrições incompletas (amplitude e velocidades no TAM médio, sensibilidade, tremor) | descrições corrigidas | 0 |
| PDF (Método e limitações) | `app/dados/documento.py:36` | texto × código | PROMESSA FALSA ("no plano do movimento"); SEM FONTE ("erro típico entre 5° e 15°") | reescrito | 0 |
| Ajuda | `app/telas/ajuda.py` | texto × código | SEM FONTE ("mão renderizada, erro médio de 6° a 36°") | retirado; limitações reais acrescentadas | 0 |
| Filtros (EMA, Kalman, cascata) | `nucleo/filtros.py:69-195` | equações, K estável 0,270 e atraso 2,33 + 2,70 = 5,03 quadros conferidos; tabela do README reproduzida na gravação (33→21, 66→62, 343→134 etc.) | OK | — | — |

Nenhuma conta aritmética do código estava errada. Todas as correções da primeira etapa foram de texto: **nenhum
resultado mudou** nessa etapa. A gravação de referência continua idêntica à v1.0.0 (teste em `tests/test_filtros.py`).

Números afirmados que foram conferidos e agora têm teste (`tests/test_auditoria.py`, seção 7): 7 de 1.550 quadros
impossíveis, até 155° e −142°, com a mão a 75–128° da palma; desvio do TAM parado de 0,6–0,9° por dedo; TAM
mediano ~31° com a mão aberta e parada; PIP até 44° e MCP até −38° com os dedos abertos; tremor de 1,2 mm na mão
parada; amplitude 10–23% abaixo do pico-vale; tamanho da mão na imagem.

Afirmações sem evidência no repositório que foram retiradas ou reescritas: "erro típico entre 5° e 15°" (PDF),
"erro médio de 6° a 36° com mão renderizada" (Ajuda e comentário), "~1 mm de ruído do MediaPipe" (glossário,
dicionário, comentário: trocado pelo valor medido), "tremor parado de 0,5–1,1° numa gravação de 20 s" (a
gravação não está no repositório: trocado pelo valor da gravação de referência), "7–8° a 14 fps" (teto da
sensibilidade), "TAM ~61° com a mão aberta" (são ~31° na gravação), "8 de 1.550 quadros" (são 7), "74–92°" (são
75–128°), "48° na PIP" (são 44°), "3 × 2 min de mão parada" (o teste no repositório é de 60 s), "SPARC abaixo
de −3 = aos trancos".

## 2. Referências conferidas

| Referência | Uso | Situação |
|---|---|---|
| Bain et al., J Hand Surg Eur 2015;40(4):406-411, doi:10.1177/1753193414533754 | arco funcional MCP 19–71°, PIP 23–87°, DIP 10–64° | conferida no resumo |
| Strickland e Glogovac, J Hand Surg Am 1980 | fórmula /175° e classes 85/70/50% | conferida no texto (revisão em `C:\sistema-mao-web\docs\REVISAO_MEDIDAS.md`) |
| Balasubramanian et al., J NeuroEng Rehabil 2015 | SPARC, V̄ = 0,05, ωc = 20π rad/s (10 Hz) | conferida no texto (mesma revisão) |
| MDC95 = 1,96 × √2 × EPM | erro de medida | fórmula padrão conferida; com EPM = DP das diferenças/√2, dá 1,96 × DP das diferenças (conta) |
| ASSH: TAM bom > 75%, regular 50–75%, ruim < 50% | classificação | só em fonte secundária; o sistema junta "excelente" com "bom" |
| Normais 260° / 140° | % do normal | só em fonte secundária |
| Normais 85/105/70° e 60/80° | divisão por articulação | sem fonte primária encontrada |
| Tremor: repouso parkinsoniano ~4–6 Hz, fisiológico ~8–12 Hz | texto da Ajuda | não conferido na fonte primária (Deuschl et al. 1998 sem acesso ao texto) |

## 3. Goniometria: ManuMetria × referência (sistema-mao-web / Hand Filter Lab)

Esta seção compara a goniometria da **v1.1.0** com a referência. A 1.2.0 **adotou** a da referência (D1). Prova de
que o porte é fiel: o JavaScript original (`core/goniometro.js` e `core/alinhamento.js` da versão web, pelo caminho
`gonio(toModelFrame(worldToLab(pontos, mão direita)))`) rodado no Node sobre todos os 1.550 quadros com mão da
gravação de referência, tratados como mão direita e como mão esquerda (3.100 quadros, 43.400 ângulos), difere do
novo `kin.joint_angles` em no máximo **0,0050°**: o arredondamento do JavaScript a 2 casas. O `gonioSelfTest` do
JavaScript passa 12 de 12, e o autoteste portado para `tests/test_auditoria.py` dá erro de 1e−13°.

**Referências.** O goniômetro de `C:\sistema-mao-web\core\goniometro.js` é idêntico, linha a linha, ao do Hand
Filter Lab publicado (https://fidelis-leandro.github.io/hand-filter-lab/, baixado em 17/11/2026) e à cópia em
`tests/referencia/hand-filter-lab-original.html`: funções `gonio`, `flexAbd`, `fk`, `tamSession`,
`worldToLab`, `toModelFrame` e `palmBasis` iguais. **Não há divergência entre as duas referências.** O porte
para Python usado na comparação (fora do repositório) deu a mesma saída que o JS original rodado no Node (maior
diferença 0,005°, o arredondamento a 2 casas do JS) e passou no autoteste do laboratório (erro < 1e−13°).

**Diferenças de método.**

| | ManuMetria (`kin.joint_angles`) | Referência (`gonio`) |
|---|---|---|
| Plano de projeção, dedos longos | UM plano para todas as articulações: perpendicular ao eixo fixo P5→P17 | um plano por osso (decomposição ISB, Wu et al. 2005): eixo lateral do metacarpo do próprio dedo (P5→P17 tirada a parte ao longo do osso), levado ao longo da cadeia (falange proximal, depois média) |
| MCP | ângulo entre punho→MCP e MCP→PIP, ambos projetados nesse plano | flexão no plano sagital do metacarpo (punho→MCP do próprio dedo), separada da abdução (`asin`) |
| Polegar (MCP e IP) | segmentos projetados no plano da palma (eixo = normal da palma) | eixo = normal da palma tirada a parte ao longo do metacarpo do polegar (perpendicular a ele) |
| Sinal | `atan2((u×v)·eixo, u·v)`: flexão +, hiperextensão − | `atan2(d·volar, d·y)`: flexão +, hiperextensão − |
| Mão esquerda | rótulo da mão real (imagem espelhada antes da detecção); o eixo P5→P17 é invertido na esquerda; a normal da palma se inverte sozinha | espelha o x da geometria de mão direita para a quiralidade de mão esquerda do modelo (`worldToLab`) |
| Abdução por dedo | não mede (abertura entre falanges vizinhas em `medidas.py`) | mede (`ABD`) |
| TAM da sessão | Σ máximos − Σ déficits, com déficit < 3° = 0 | Σ máximos − Σ déficits, sem tolerância |

Nas duas, mão esquerda e mão direita espelhada dão exatamente os mesmos ângulos (conferido).

**Mãos sintéticas de ângulo conhecido** (erro em graus; verdade entre parênteses):

| Caso | ManuMetria | Referência |
|---|---|---|
| Modelo do lab (ISB): flexão pura MCP/PIP/DIP (60/45/20) | 62,8 / 40,6 / 18,5 | 60,0 / 45,0 / 20,0 |
| MCP 60 + abdução 20 | 72,2 | 60,0 |
| 40/70/30 + abdução 15 | 49,0 / 61,7 / 24,7 | 40,0 / 70,0 / 30,0 |
| Hiperextensão MCP −20 | −22,3 | −20,0 |
| −20 / 90 / 60 | −22,3 / 94,3 / 54,6 | −20,0 / 90,0 / 60,0 |
| Mínimo 50/30 + abdução 25 | 54,3 / 32,3 | 50,0 / 30,0 |
| Médio 85/105/70 | 85,2 / 105,2 / 70,0 | 85,0 / 105,0 / 70,0 |
| Polegar MCP 30 / IP 40 | 30,8 / 39,8 | 30,0 / 40,0 |
| 400 poses aleatórias do modelo do lab, erro máximo | 1,1 (anelar MCP) a 20,3° (polegar IP); erro médio absoluto 0,3–4,3° | < 1e−13° |
| Mão sintética do ManuMetria (flexão em torno do eixo x global), erro máximo dedos / polegar | 0,6 / 0,0 | 3,4 / 0,0 |

Cada método acerta o modelo construído com a sua convenção. O critério que não depende de convenção é a
PIP e a DIP, que são dobradiças: num dedo plano, a flexão é o ângulo entre as falanges. No modelo do lab com
abdução, a referência acerta e o ManuMetria erra até 19,5° (PIP) e 20,1° (DIP). Na mão sintética do ManuMetria,
sem abdução, o ManuMetria erra até 0,6° na PIP e a referência até 2,0° (o eixo lateral dela segue a linha
punho–base do dedo, oblíqua nesse modelo). Para a MCP com abdução, a convenção ISB é a recomendação
publicada; o método do ManuMetria deixa parte da abdução entrar como flexão.

**Gravação de referência** (1.435 quadros válidos; diferença ManuMetria − referência, em graus):

| Articulação | Média | Média absoluta | P95 | Máxima |
|---|---|---|---|---|
| Polegar MCP | +1,78 | 1,78 | 3,70 | 4,96 |
| Polegar IP | −2,13 | 2,14 | 6,85 | 9,55 |
| Indicador MCP / PIP / DIP | −0,55 / +0,84 / −0,53 | 0,70 / 1,03 / 1,87 | 3,23 / 2,31 / 4,73 | 7,96 / 8,84 / 7,08 |
| Médio MCP / PIP / DIP | +0,10 / +0,84 / −0,19 | 0,22 / 0,89 / 0,46 | 0,93 / 2,51 / 1,59 | 2,67 / 4,46 / 3,15 |
| Anelar MCP / PIP / DIP | +0,05 / +0,68 / +0,19 | 0,11 / 0,72 / 0,56 | 0,51 / 2,16 / 1,49 | 1,87 / 4,43 / 3,97 |
| Mínimo MCP / PIP / DIP | −0,54 / −0,09 / −0,22 | 0,59 / 1,29 / 1,04 | 1,57 / 4,30 / 3,46 | 4,10 / 8,49 / 5,74 |

**Impacto nas medidas da sessão** (motor completo, trocando só o goniômetro):

| Dedo | % do normal | TAM ativo (°) | Repetições | Maior mudança por articulação |
|---|---|---|---|---|
| Polegar | 65,8 → 64,6 | 92,2 → 90,5 | 33 → 32 | MCP máx 42 → 38 |
| Indicador | 99,2 → 98,4 | 258,0 → 255,7 | 24 → 23 | MCP máx 75 → 82; MCP mín −41 → −36; DIP mín 4 → 11 (déficit) |
| Médio | 103,7 → 104,0 | 269,6 → 270,4 | 27 → 31 | MCP máx 74 → 77 |
| Anelar | 106,5 → 107,1 | 277,0 → 278,4 | 25 → 27 | — (≤ 1°) |
| Mínimo | 104,8 → 107,7 | 272,5 → 280,1 | 24 → 25 | DIP máx 93 → 97; MCP máx 89 → 92 |

Quadros descartados: 7 → 3. A troca passa dos limites de 2° por articulação e de 2 pp (mínimo +2,9 pp): é o item D1.

## 4. Decisões do autor (aplicadas na 1.2.0)

| | Decisão | O que foi feito | Teste de resposta conhecida (`tests/test_auditoria.py`) |
|---|---|---|---|
| D1 | Adotar a goniometria ISB da referência | `kin.joint_angles` com lado: porte fiel do `gonio` (decomposição por osso, eixo lateral levado ao longo da cadeia; polegar: normal da palma ortogonalizada ao metacarpo) e do `worldToLab`; sem lado: ângulo 3D sem sinal, como antes | autoteste do lab (10 casos, duas mãos); MCP 60 + abdução 20 → 60,0; 40/70/30 + abdução 15 → 40/70/30; mão girada 70°; 300 poses aleatórias (erro ~0); prova contra o JavaScript (seção 3) |
| D2 | Amplitude de cada repetição nos dados brutos | pico − vale do TAM dos dados brutos nas janelas de 0,4 s antes a 0,1 s depois dos instantes do detector; daí saem classificação, TAM no pico, excursão e velocidades médias. A média de 8 quadros só decide quando há repetição | cosseno de 200° em 2 s → 200°, completa, pico 210°, excursão 0,6/1/0,7 |
| D3 | Início e fim pelo critério da meia sensibilidade | início = último instante em que o TAM médio esteve a até meia sensibilidade do vale; fim = primeiro a até meia sensibilidade do pico; o mesmo na extensão. Critério do sistema, sem fonte | instantes refeitos à parte; 3 s parado antes da 1ª repetição: velocidade a ≤ 5% das outras; pausa de 1,5 s no topo não entra na flexão nem na extensão |
| D4 | Manter os normais e as faixas | sem mudança | normais 260/140 e faixas 50/75% conferidos |
| D5 | Tirar a tolerância de 3° do déficit | déficit = max(0, menor flexão) | 2/0/1 com mínimos 2/−5/1; 0,5° já conta |
| D6 | Acoplamento no mesmo sinal | numerador e denominador no TAM dos dados brutos, na janela do vale ao pico desta repetição | mesmo movimento → (A − sensibilidade)/A = 0,975; independência 2,5% |
| D7 | SPARC pela norma das velocidades articulares | `kin.joint_speed`; limiar 0,05, corte 10 Hz e regra dos 15° mantidos; velocidade de pico continua na derivada do TAM | uma articulação flete e outra estende: a derivada do TAM é 0, o SPARC da norma é calculado |
| D8 | Manter os limiares | tabela da seção 7 | — |
| D9 | Extensão classificada pelo déficit (ficha e comparação) | `interp.extension_change`: menos déficit = melhora; sem déficit nas duas, sem classificação | 20 → 5° melhora; 0 → −15° sem classificação; 10 → −10° melhora |

Comportamentos reconferidos na gravação de referência depois da D1 (limiares sem mudança): `good_view` não
depende dos ângulos (mesmos 115 quadros fora da vista); quadros com ângulo impossível (`PLAUSIBLE_RANGE`): 7 → 3,
os 3 com a mão a 75–128° da palma (o maior valor fora da faixa é −102°); a calibração completou nas duas versões,
com sensibilidades de 3,2 a 4,6° (antes, 3,2 a 5,0°).

## 5. O que não foi possível verificar

- Erro em graus contra o goniômetro manual: não há gravação com goniometria de referência no repositório.
- Texto completo de Bain 2015, da ASSH e de Deuschl 1998: os valores foram conferidos só no resumo ou em fonte
  secundária (tabela da seção 2).
- O acerto da goniometria na mão real: a gravação de referência não tem ângulos verdadeiros; a comparação
  mostra só a diferença entre os métodos. A ISB acerta os modelos de mão com abdução, mas a mão real tem rotação
  axial dos dedos, que os 21 pontos não mostram.
- O critério da meia sensibilidade (D3) é do sistema, sem fonte: num cosseno, a velocidade média sai maior que
  amplitude/(meio período), e num movimento rápido os instantes vêm da média de 8 quadros.
- PDF gerado: conferido o texto (`METHOD_NOTE`) e a montagem com a gravação; a aparência impressa não.

## 6. Mudanças da 1.2.0 (gravação de referência, v1.1.0 → 1.2.0)

Motor completo, sem suavização nas medidas (padrão). v1.1.0 rodada num worktree temporário da tag.

| Dedo | % do normal | TAM ativo (°) | Repetições (parciais / completas) | Vel. média flexão (°/s) | Vel. média extensão (°/s) | Vel. de pico (°/s) | SPARC | Independência |
|---|---|---|---|---|---|---|---|---|
| Polegar | 65,8 → 64,6 | 92,2 → 90,5 | 33 (15/0) → 32 (18/0) | 49 → 176 | 48 → 114 | 343 → 332 | −1,98 → −1,93 | 11% → 24% |
| Indicador | 99,2 → 98,4 | 258,0 → 255,7 | 24 (7/0) → 23 (9/0) | 69 → 141 | 58 → 128 | 319 → 246 | −2,07 → −1,98 | 14% → 26% |
| Médio | 103,7 → 104,0 | 269,6 → 270,4 | 27 (7/1) → 31 (8/2) | 91 → 119 | 80 → 119 | 276 → 237 | −2,19 → −2,22 | 10% → 38% |
| Anelar | 106,5 → 107,1 | 277,0 → 278,4 | 25 (8/1) → 27 (9/1) | 70 → 145 | 70 → 158 | 281 → 278 | −1,98 → −2,20 | 12% → 41% |
| Mínimo | 104,8 → 107,7 | 272,5 → 280,1 | 24 (11/1) → 25 (12/1) | 52 → 115 | 84 → 159 | 340 → 372 | −2,01 → −2,00 | 30% → 46% |

| Dedo | Articulação | Flexão máx. (°) | Flexão mín. (°) | Déficit (°) |
|---|---|---|---|---|
| Polegar | MCP | 42 → 38 | −7 → −7 | 0 → 0 |
|  | IP | 50 → 53 | −28 → −29 | 0 → 0 |
| Indicador | MCP | 75 → 82 | −41 → −36 | 0 → 0 |
|  | PIP | 103 → 100 | −9 → −7 | 0 → 0 |
|  | DIP | 85 → 85 | 4 → 11 | 4 → 11 |
| Médio | MCP | 74 → 77 | −25 → −25 | 0 → 0 |
|  | PIP | 101 → 99 | 9 → 9 | 9 → 9 |
|  | DIP | 103 → 103 | −15 → −15 | 0 → 0 |
| Anelar | MCP | 91 → 92 | −22 → −22 | 0 → 0 |
|  | PIP | 97 → 98 | 4 → 4 | 4 → 4 |
|  | DIP | 93 → 93 | −8 → −8 | 0 → 0 |
| Mínimo | MCP | 89 → 92 | −38 → −38 | 0 → 0 |
|  | PIP | 90 → 91 | −1 → −1 | 0 → 0 |
|  | DIP | 93 → 97 | −16 → −16 | 0 → 0 |

Limitações apontadas: antes nenhuma; depois nenhuma. Quadros descartados por ângulo impossível: 7 → 3. Sensibilidade (°): polegar 3,2 → 3,2, indicador 4,4 → 4,6, médio 5,0 → 4,1, anelar 4,8 → 4,1, mínimo 4,5 → 4,0.


Por que mudou:

- **% do normal, TAM ativo, máximos e mínimos**: goniometria ISB (D1). As diferenças ficam até 2,9 pp e 7° (MCP do
  indicador). O déficit da DIP do indicador passa de 4° para 11° porque a nova conta mede a DIP mais fletida na
  mão aberta. Nenhum déficit mudou por causa da D5 nesta gravação (nenhum mínimo entre 0 e 3°).
- **Repetições**: os ângulos novos mudam o TAM e, com ele, o detector (médio 27 → 31). As parciais aumentam
  porque a amplitude agora vem dos dados brutos (D2), sem a atenuação da média de 8 quadros.
- **Velocidades médias** (o dobro, em alguns dedos): D3 tira as pausas do tempo de subida e de descida (na
  v1.1.0, a 1ª subida do indicador "durava" 7,06 s), e D2 usa a amplitude dos dados brutos.
- **Velocidade de pico** (cai no indicador e no médio): com a amplitude nos dados brutos, mais repetições
  pequenas passam do limiar de 15° e entram na média (indicador: 10 das últimas 10, antes 6), e elas têm pico
  menor.
- **Independência** (sobe de 10–30% para 24–46%): D6 e a janela nova, do vale ao pico desta repetição nos dados
  brutos (antes, de 0,2 s antes do início do detector até o fechamento, o que incluía parte da volta dos outros
  dedos).
- **SPARC**: D7 (norma das velocidades articulares) e os trechos novos; diferença ≤ 0,22.

**Checagem clínica**: a mão saudável da gravação de referência não recebe nenhuma limitação, antes nem depois
(teste em `tests/test_auditoria.py`).

**Recálculo de avaliações da v1.1.0**: ver o [CHANGELOG](../CHANGELOG.md), versão 1.2.0.

## 7. Parâmetros escolhidos sem fonte (validar com goniômetro)

Mantidos na 1.2.0 (D8). Linhas da versão 1.2.0.

| Parâmetro | Valor | Arquivo:linha | Motivo |
|---|---|---|---|
| Faixa plausível dos ângulos | −60° a 130° | `nucleo/kinematics.py:122` | descartar erros do MediaPipe (pontos trocados ao girar a mão) |
| Vista máxima da palma | 60° | `nucleo/kinematics.py:135` | com a mão de lado o MediaPipe erra mais os ângulos |
| Sensibilidade | 3 × desvio padrão parado, entre 2° e 30°; 5° sem calibração | `nucleo/kinematics.py:63, 67` | separar movimento de ruído; teto para câmeras lentas |
| Média do detector | 8 quadros | `nucleo/kinematics.py:75` | zero repetições falsas em 60 s de mão parada simulada |
| Faixa de início e fim (D3) | meia sensibilidade | `nucleo/kinematics.py:415` | o ruído do TAM médio fica bem abaixo dela |
| Calibração | 60 quadros; janela de 15; mão parada < 4°; mão aberta: TAM mediano < 90°; tempo limite 10 s; espera da mão aberta 5 s | `nucleo/kinematics.py:77-89`, `app/avaliador.py:32` | ~2 s de mão aberta e parada; aceitar quem não abre a mão |
| Classificação da repetição | parcial ≥ 25%, completa ≥ 75% do TAM normal | `nucleo/kinematics.py:59-60` | mesmas faixas da classificação do TAM |
| Velocidade de pico e SPARC | só em repetições ≥ 15° | `nucleo/kinematics.py:110` | abaixo disso o tremor domina a derivada |
| Qualidade do movimento | últimas 10 repetições; tendência com ≥ 6; regularidade 15/30%; esforço 5 mais fortes, ≥ 3, 10/20%; repetições fortes até 10% abaixo do melhor | `nucleo/kinematics.py:93-103` | — |
| Acoplamento | teto de 1,5 | `nucleo/kinematics.py:731` | o outro dedo pode se mover mais que este |
| Abertura dos dedos | só com a MCP até 30° | `nucleo/medidas.py:98` | com o dedo fletido a projeção encolhe |
| Polpa–palma | zero por dedo 0,24/0,14/0,15/0,24 do comprimento da palma | `nucleo/medidas.py:73` | os pontos ficam no centro da articulação, não na pele |
| Tremor | janelas de 2 s; faixa 3–12 Hz; pico ≥ 4× a mediana | `nucleo/medidas.py:162-165` | separar oscilação rítmica do ruído |
| Distância da câmera | mão < 0,13 ou > 0,50 da altura da imagem, por 15 quadros | `nucleo/medidas.py:249-250` | aviso de longe/perto sem piscar |
| Confiabilidade | quadros válidos 60/85%; 15/20 quadros/s; brilho 50/80; vista 40/50°; < 3 repetições ou < 15 s | `nucleo/medidas.py:289-308` | — |
| Estabilizador | falha curta até 0,4 s; voto do lado em 15 quadros | `nucleo/stabilizer.py:24-25` | não perder repetições por uma falha de detecção |
| Erro de medida | ≥ 10 pares; tendência com ≥ 4 avaliações; platô nas 3 últimas | `app/dados/interpretacao.py:23-25` | — |
| Regras do resumo | arco funcional < 90%; DIP < 40% da participação normal com PIP ≥ 30°; independência ≥ 60% / < 30% | `app/dados/interpretacao.py:166-168, 183` | só regras que não marcaram limitação na mão saudável |
