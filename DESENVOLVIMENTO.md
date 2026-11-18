# ManuMetria — desenvolvimento

ManuMetria: avaliação cinemática da mão por visão computacional (webcam comum +
MediaPipe, sem marcadores). Este arquivo é para quem for mexer no código. O uso
está no [README.md](README.md), a instalação em [INSTALACAO.md](INSTALACAO.md), o
método de cálculo em [docs/METODOLOGIA.md](docs/METODOLOGIA.md), o histórico de
versões em [CHANGELOG.md](CHANGELOG.md) e a arquitetura (camadas, responsabilidades e
o caminho de um quadro) em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## Como rodar

- Dois cliques em **Abrir sistema.bat**, ou no terminal:

```
.venv\Scripts\python.exe sistema.py            (webcam)
.venv\Scripts\python.exe sistema.py --sim      (mão simulada, sem câmera)
.venv\Scripts\python.exe sistema.py --help     (outras opções)
```

  Opções: `--sim` mão simulada, `--cam 1` outra câmera, `--resolucao 1280x720`,
  `--confianca 0.5` limiar do MediaPipe, `--banco outro.sqlite` outro banco,
  `--replay ARQUIVO` toca uma gravação de pontos (.npz).

- Pacientes fictícios de demonstração (EX-001, João e Maria): `.venv\Scripts\python.exe tools\criar_demonstracao.py`
- Todos os testes automáticos: `.venv\Scripts\python.exe tests\testar.py`
- Uma gravação com outro filtro: `.venv\Scripts\python.exe tools\analisar_gravacao.py ARQUIVO.npz --filtro kalman --nas-medidas`

## Onde ficam os dados

| Pasta | O que tem |
|---|---|
| `dados_locais/avaliacoes.sqlite` | pacientes e avaliações (SQLite) |
| `dados_locais/config.json` | Configurações (instituição, logotipo, tema, tamanho) |
| `dados_locais/pontos/` | pontos da mão de cada avaliação salva (.npz, sem vídeo) |
| `dados_locais/logo_relatorio.*` | logotipo escolhido em Configurações (se houver) |
| `dados_locais/copias_de_seguranca/` | cópia do banco feita antes de cada migração do esquema |
| `relatorios/` | PDFs, CSVs, planilhas e datasets de pesquisa |
| `manumetria/recursos/logo_relatorio.png` | logotipo padrão do PDF (versionado; nunca é sobrescrito) |
| `manumetria/recursos/hand_landmarker.task` | modelo do MediaPipe, baixado na instalação (fora do Git) |

Com outro banco (`sistema.py --banco D:\pasta\outro.sqlite` ou
`tools\criar_demonstracao.py D:\pasta\outro.sqlite`), os pontos vão para `pontos/` ao lado desse banco e o
caminho salvo é relativo à pasta dele (`caminhos.pastas_do_banco`). Todas as pastas são definidas em
`manumetria/caminhos.py`.

## Como o código está organizado

Na raiz do projeto:

```
sistema.py               ponto de entrada (python sistema.py --help mostra as opções)
manumetria/              o sistema, em camadas (docs/ARQUITETURA.md)
tests/                   testes automáticos (tests	estar.py roda todos)
tools/                   pacientes de demonstração, análise de gravações e pacote para o registro
docs/                    metodologia, arquitetura, auditorias e imagens da documentação
requirements.txt         pacotes do sistema
requirements-dev.txt     só para os testes (pandas); não é preciso para usar o sistema
Instalar sistema.bat     instalação completa no Windows
Abrir sistema.bat        abre com a webcam
Abrir simulacao.bat      abre com a mão simulada
gerar_hash_registro.bat  pacote e hash SHA-512 para o registro de software (seção abaixo)
```

Dentro de `manumetria/`:

```
manumetria/
  caminhos.py versao.py formato.py      utilitários (não importam nenhuma camada)
  calculo/      goniometria, sinal, repeticoes, sessao, medidas, filtros, estabilizador, geometria
  captura/      camera, gravacao, simulacao, qualidade
  avaliacao/    motor, resultados, interpretacao
  dados/        banco, configuracoes, recalculo, planilha, dataset
  relatorios/   pdf
  interface/    janela, tema, icones, glossario, telas/, componentes/
  recursos/     logotipo padrão e o modelo do MediaPipe
```

As camadas vão num sentido só: **calculo → captura → avaliacao → dados → relatorios → interface**.
Cada uma só importa as anteriores e os utilitários; só `relatorios` e `interface` usam o PyQt5. O
`tests/test_arquitetura.py` confere isso pelos imports e falha se alguém importar uma camada posterior.
Os nomes de classes e funções ficam em inglês (`FingerTracker`, `Session`, `joint_angles`); arquivos,
pastas, docstrings e comentários, em português.

| Arquivo | Faz |
|---|---|
| `calculo/goniometria.py` | dedos e articulações, valores normais, ângulos ISB com sinal, plausibilidade, vista da mão, classificação do % do normal |
| `calculo/sinal.py` | reamostragem, derivada (Savitzky–Golay), SPARC, norma das velocidades, tendência |
| `calculo/repeticoes.py` | `Rep` e `FingerTracker`: repetições e todas as métricas por dedo |
| `calculo/sessao.py` | `Calibration` (sensibilidade) e `Session` (um tracker por dedo, independência) |
| `calculo/medidas.py` | arco funcional, Strickland, polpa-palma, abertura dos dedos, tremor, confiabilidade, distância |
| `calculo/filtros.py` | suavização: EMA, Kalman e EMA + Kalman (parâmetros em docs/METODOLOGIA.md) |
| `calculo/estabilizador.py` | segura falhas curtas do MediaPipe e fixa o lado da mão |
| `calculo/geometria.py` | pontos da mão, mão sintética (simulação e testes), conversão para o 3D |
| `captura/camera.py` | webcam + MediaPipe (thread), download do modelo, desenho do esqueleto |
| `captura/gravacao.py` | arquivos de pontos: gravar (atômico), ler, reproduzir |
| `captura/simulacao.py` | mão simulada (`--sim`) |
| `captura/qualidade.py` | qualidade da captura (luz, fps, detecção) para o aviso no topo |
| `avaliacao/motor.py` | **motor da avaliação** (`Avaliador`, `analisar`): recebe cada quadro e decide tudo |
| `avaliacao/resultados.py` | o resultado de uma avaliação como dicionário (formato gravado no banco) |
| `avaliacao/interpretacao.py` | erro de medida, mudança real, tendência, platô, frases do resumo |
| `dados/banco.py` | banco SQLite com migração automática e cópia de segurança |
| `dados/configuracoes.py` | Configurações (`config.json`) e o logotipo |
| `dados/recalculo.py` | "Recalcular avaliações" a partir dos pontos gravados |
| `dados/planilha.py` | CSV de uma avaliação e a planilha identificada para o Excel |
| `dados/dataset.py` | dataset pseudonimizado para pesquisa |
| `relatorios/pdf.py` | documento do relatório (prévia na tela e PDF) |
| `interface/janela.py` | janela principal e a navegação entre as telas |
| `interface/tema.py` / `manumetria/formato.py` | cores, botões, rótulos / números e datas em português |
| `interface/icones.py` | ícones desenhados em SVG |
| `interface/glossario.py` | explicação de cada medida (dica ao passar o mouse e Ajuda) |
| `interface/telas/` | uma tela por arquivo: pacientes, ficha, avaliação, relatório, configurações, ajuda |
| `interface/componentes/` | partes das telas: palco, mão 3D procedural (`mao3d.py`: cilindros, esferas e palma gerados a partir dos 21 pontos), painel do dedo (`painel.py`), peças pequenas (`pecas.py`), mapa da evolução (`mapa.py`), gráfico, barra do topo, dicas, diálogos |
| `versao.py` | versão do ManuMetria e identificação do método dos ângulos, gravadas em cada avaliação |

**Testes** — pasta `tests/`: `testar.py` (roda todos os testes), `test_*.py` e `dados/`
(`gravacao_referencia.npz`, pontos de uma mão saudável real, e `referencia_resultados.json`, o resultado
completo dela). `test_arquitetura.py` confere as camadas; `test_reorganizacao.py`, que todos os números da
gravação de referência continuam idênticos; `test_banco.py`, a migração, o código fixo das avaliações e a
gravação dos pontos; `test_pastas.py`, as pastas do banco e o logotipo; `test_dataset.py`, o dataset para
pesquisa (com `--copia-do-banco` também exporta uma CÓPIA de `dados_locais`). O `test_dataset.py` relê os
arquivos com o pandas, que é só de desenvolvimento:
`.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` (sem ele, usa o módulo csv). Nenhum
teste toca em `dados_locais`: tudo roda em pastas temporárias, e os pontos de um banco temporário ficam
ao lado dele (`Banco.root`); o `test_pastas.py` confere no fim que `dados_locais` tem o mesmo SHA-256.

**Ferramentas** — pasta `tools/`: `criar_demonstracao.py` (3 pacientes fictícios com avaliações
simuladas pelo mesmo motor da câmera), `analisar_gravacao.py` (passa um arquivo de pontos pelo motor e
mostra a linha do tempo) e `gerar_hash_registro.py` (pacote e hash SHA-512 para o registro de software,
chamado pelo `gerar_hash_registro.bat`).

## Como acrescentar uma medida

1. Calcule em `manumetria/calculo/repeticoes.py` (por dedo) ou `manumetria/calculo/medidas.py` (mão
   inteira), sem interface.
2. Guarde no resultado em `manumetria/avaliacao/resultados.py` (o banco salva o dicionário inteiro).
3. Mostre no painel (`manumetria/interface/componentes/painel.py`), na ficha ou no CSV
   (`manumetria/dados/planilha.py`), se quiser. Para o dataset de pesquisa, acrescente a coluna em
   `manumetria/dados/dataset.py` com a descrição, a unidade e o tipo (o teste falha se o dicionário não
   cobrir todas as colunas).
4. Explique a medida em `manumetria/interface/glossario.py` (vale para a dica ao passar o mouse e para a
   Ajuda) e use `explain(widget, "chave")` onde ela aparece.
5. Escreva um teste em `tests/test_auditoria.py` (ou `tests/test_medidas.py`) com um caso de resposta
   conhecida.
6. Rode `tests\testar.py`. Se a conta de uma medida mudou, o `test_reorganizacao.py` falha de propósito:
   gere de novo `tests/dados/referencia_resultados.json`, documente a mudança em
   `docs/AUDITORIA_CALCULOS.md`, em `docs/METODOLOGIA.md` e no `CHANGELOG.md` e suba `VERSAO` em `manumetria/versao.py` (e `GONIOMETRIA`, se mudou o
   método dos ângulos): cada avaliação guarda a versão que a calculou.
7. Para as avaliações já salvas ganharem a medida: Configurações > **Recalcular avaliações**
   (`manumetria/dados/recalculo.py`). Ele passa os pontos gravados pelo cálculo em uso, mostra o que
   muda antes de gravar e guarda o resultado anterior dentro da avaliação (`"original"`).
   Avaliações sem pontos gravados ficam como estão.

O motor usa o horário de cada quadro (`raw["t"]`), não o relógio do computador: por isso
recalcular a partir dos pontos dá exatamente o mesmo resultado da avaliação ao vivo
(há um teste para isso em `tests/test_medidas.py`). O horário `inicio` de cada avaliação é o
começo da sessão (preparação, antes da calibração); a duração (`duracao_s`) conta só a medição.

## Banco de dados

O esquema tem versão (`PRAGMA user_version`, `SCHEMA_VERSION` em `manumetria/dados/banco.py`). Ao abrir,
`Banco.__init__` copia o arquivo para `copias_de_seguranca/` (API de backup do SQLite) e `_migrate` leva o
banco até a versão atual numa transação só. Regras: a migração só acrescenta (nenhum valor salvo muda), é
idempotente (confere cada coluna antes de criar) e é testada em `tests/test_banco.py` num banco no
esquema 0. Para acrescentar um campo do paciente: `FIELDS`, `SCHEMA` e um passo em `_migrate`
com `SCHEMA_VERSION + 1`.

- **Esquema 1**: `pacientes.sexo`; `pacientes.id_pesquisa` (pseudônimo aleatório, único);
  `sessoes.codigo` (código fixo da avaliação no paciente, A01, A02..., preenchido uma vez na ordem das
  avaliações existentes) e `pacientes.ultimo_codigo` (o número nunca é reaproveitado, nem depois de apagar
  a última avaliação); índices.
- **Salvar uma avaliação** (`salvar_sessao(..., gravar_pontos=...)`): grava os pontos primeiro (arquivo
  temporário + `os.replace`), depois a linha e o código na mesma transação; se o banco falhar, apaga o
  arquivo recém-gravado. **Apagar**: banco primeiro, arquivos depois.
- O caminho dos pontos é salvo relativo à pasta base do banco (`Banco.root`: a do projeto no banco padrão,
  a do próprio banco em outro), com `/` (`caminhos.relativo`); a leitura (`caminhos.absoluto`) aceita
  também a `\`.
- Formatos do resultado (`VERSION` em `avaliacao/resultados.py`): o formato 3 guarda `versao_app`,
  `goniometria` e `fuso_utc`; nos formatos 1 e 2 o método do cálculo não está registrado.
- O dataset para pesquisa (`manumetria/dados/dataset.py`) repassa os pontos pelo motor com
  `analisar(..., por_quadro=...)`, que lê o registro de cada quadro em `Avaliador.quadro` (ângulos brutos
  e suavizados, estado, descarte, vista, fase); esse registro não muda nenhuma conta.

## Combinados do projeto

- As **medidas usam os dados brutos**. Suavização (`manumetria/calculo/filtros.py`,
  padrão EMA + Kalman; método e origem em [docs/METODOLOGIA.md](docs/METODOLOGIA.md)): por padrão vale SÓ
  PARA A EXIBIÇÃO AO VIVO. O `Avaliador` aplica o filtro logo depois do cálculo e do
  descarte e, no mesmo quadro (`_update_session`), entrega à `Session` os dados brutos
  e guarda os suavizados em `av.display` (valor "Agora", dica da mão 3D) e
  `av.display_history` (gráfico do TAM). Com "Aplicar a suavização também nas medidas"
  (`suavizacao_medidas` em Configurações; `nas_medidas` no registro), a `Session`
  recebe os suavizados. Motivo do padrão: o filtro achata os picos (tabela em
  docs/METODOLOGIA.md, conferida pelo `tests/test_auditoria.py`). Com o padrão, os resultados
  são idênticos aos do modo "Desligada" (há um teste para isso). Calibração, tremor
  e as medidas por pontos (abertura, polpa-palma) usam sempre os dados brutos. O filtro
  só usa a ordem dos quadros (nada de relógio): o recálculo tem de dar o mesmo resultado
  do ao vivo. Cada avaliação guarda `resultados["filtro"]` (modo, parâmetros e
  `nas_medidas`); o recálculo usa esse registro (sem registro: "Desligada"; sem
  `nas_medidas`: dados brutos). Os parâmetros dos filtros não devem ser mudados sem um
  motivo documentado. A média de 8 quadros só decide QUANDO há repetição (e os instantes
  de início e fim, pelo critério da meia sensibilidade); amplitude, classificação, TAM no
  pico, excursão e velocidades saem dos dados brutos. A derivada de Savitzky–Golay (5
  pontos) entra na velocidade de pico (derivada do TAM) e no SPARC (norma das velocidades
  articulares).
- **Goniometria**: `goniometria.joint_angles` é um porte fiel do `gonio` da versão web
  (`C:\sistema-mao-web\core\goniometro.js`, igual ao Hand Filter Lab): decomposição por
  osso, recomendação ISB (Wu et al., 2005). Ao mudar essa conta, refaça a prova contra o
  JavaScript (docs/AUDITORIA_CALCULOS.md, seção 3) e o autoteste em `tests/test_auditoria.py`.
- **Auditoria dos cálculos**: `docs/AUDITORIA_CALCULOS.md` e `tests/test_auditoria.py`. Todo
  número afirmado num texto (README, METODOLOGIA, Ajuda, PDF, dicionário de dados, comentário) precisa de
  evidência no repositório (teste, gravação de referência) ou de fonte conferida; o teste confere
  os números citados e falha se um texto sem fonte voltar. Ao mudar uma conta, atualize o
  relatório e o teste. A auditoria da organização do código está em `docs/AUDITORIA_ORGANIZACAO.md`.
- Comentários e docstrings em português, atemporais (sem histórico de mudanças nem número de
  versão do app; os formatos gravados são "formato N" e "esquema N").
- Interpretação por regras explícitas, com "sugestivo de": apoio à decisão, não diagnóstico.
- Textos da interface em português, sem emojis.
- A mão 3D é gerada pelo próprio código (sem modelo de terceiros). A cor de cada
  articulação segue a mesma regra dos cartões dos dedos (`goniometria.grade`).
- Bibliotecas de terceiros e licenças: `AVISOS_TERCEIROS.md`.

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
