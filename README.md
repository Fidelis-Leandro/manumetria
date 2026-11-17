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
   sessão: vermelho abaixo de 50%, amarelo de 50 a 75% e verde acima de 75% (cinza enquanto não há
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
| **Configurações** | instituição e logotipo do PDF, tema claro/escuro, tamanho da interface, recálculo de avaliações antigas |
| **Ajuda** | como avaliar, como medir bem, glossário de todas as medidas, limites do sistema |

**Medidas** (detalhes na tela Ajuda): flexão de cada articulação, TAM e TAM ativo (% do normal), déficit de
extensão, arco de movimento e arco funcional (Bain et al., 2015), escore de Strickland, distância
polpa–palma, repetições (movimento / parcial / completa), velocidades de flexão, extensão e pico, suavidade
(SPARC), ciclo, cadência e regularidade, indicadores de fadiga, consistência do esforço, independência dos
dedos e contribuição de cada articulação, abertura dos dedos e do polegar, tremor, confiabilidade da
avaliação, erro de medida por teste–reteste (MDC), mudança real, tendência e platô.

### Tratamento do sinal

Os ângulos exibidos são calculados quadro a quadro a partir dos pontos do MediaPipe, **sem filtro de
suavização** (não há filtro de média móvel exponencial nem de Kalman). O que o código faz:

- **descarta** quadros com ângulos fisicamente impossíveis (fora de −60° a 130°) e quadros com a mão de
  lado (palma a mais de 60° da frente), como se fossem falhas de detecção;
- em falhas curtas de detecção (até 0,4 s), **mantém a última pose** e não atualiza as medidas; o lado da
  mão (direita/esquerda) é fixado na calibração;
- o **contador de repetições** decide sobre a média dos últimos 8 quadros do TAM, com histerese igual à
  sensibilidade medida na calibração (3 × o tremor parado); os valores mostrados continuam crus;
- a **velocidade de pico** e a **suavidade** (SPARC) usam uma derivada por mínimos quadrados em 5 pontos
  (Savitzky–Golay de 1ª ordem) sobre o TAM cru de cada repetição, reamostrado em grade uniforme de 30 Hz.

### Limites

- As medidas são **estimativas por câmera comum**, sem marcadores: não substituem a goniometria.
- O erro aumenta com a mão de lado; por isso só entram na medida os quadros com a palma até 60° da frente.
- Com uma câmera só, dedos escondidos atrás de outros não são medidos.
- A interpretação (resumo, mudança real, platô) é feita por regras explícitas: apoio à decisão, não
  diagnóstico.

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
nucleo/                  cálculo, sem interface (numpy): câmera, cinemática, medidas, estabilizador
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
