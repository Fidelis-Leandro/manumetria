# ManuMetria — desenvolvimento

ManuMetria: avaliação cinemática da mão por visão computacional (webcam comum +
MediaPipe, sem marcadores). Este arquivo é para quem for mexer no código; o uso
e a instalação estão no README.md.

## Como rodar

- Dois cliques em **Abrir sistema.bat**, ou no terminal:

```
.venv\Scripts\python.exe sistema.py            (webcam)
.venv\Scripts\python.exe sistema.py --sim      (mão simulada, sem câmera)
.venv\Scripts\python.exe sistema.py --help     (outras opções)
```

- Pacientes fictícios de demonstração (EX-001, João e Maria): `.venv\Scripts\python.exe tools\criar_demonstracao.py`
- Todos os testes automáticos: `.venv\Scripts\python.exe tests\testar.py`
- Uma gravação com outro filtro: `.venv\Scripts\python.exe tools\analisar_gravacao.py ARQUIVO.npz --filtro kalman --nas-medidas`

## Onde ficam os dados

| Pasta | O que tem |
|---|---|
| `dados_locais/avaliacoes.sqlite` | pacientes e avaliações (SQLite) |
| `dados_locais/config.json` | Configurações (instituição, logotipo, tema, tamanho) |
| `dados_locais/pontos/` | pontos da mão de cada avaliação salva (.npz, sem vídeo) |
| `dados_locais/copias_de_seguranca/` | cópia do banco feita antes de cada migração do esquema |
| `relatorios/` | PDFs, CSVs, planilhas e datasets de pesquisa |
| `assets/logo_relatorio.png` | logotipo do PDF |

## Como o código está organizado

O caminho de um quadro da câmera até a tela:

```
câmera ─► nucleo/capture.py ─► app/avaliador.py ───────► app/telas/avaliacao.py (mostra)
                                (fases, calibração,        │
                                 estabilizador, filtros,    │
                                 medidas)                   ▼ ao encerrar
                                usa: nucleo/kinematics.py  resultados (dicionário)
                                     nucleo/stabilizer.py    ├─► app/dados/banco.py (salva)
                                     nucleo/filtros.py       │
                                     nucleo/medidas.py       ├─► app/dados/documento.py (PDF)
                                                             └─► app/dados/interpretacao.py (ficha)
```

As dependências vão num sentido só: `app/` usa `nucleo/`, e `nucleo/` nunca importa de `app/`.

**Cálculo (sem interface, numpy puro)** — pasta `nucleo/`:

| Arquivo | Faz |
|---|---|
| `kinematics.py` | ângulos das articulações, TAM, repetições, velocidade, suavidade, calibração |
| `medidas.py` | arco funcional, Strickland, polpa-palma, abertura dos dedos, tremor, confiabilidade |
| `stabilizer.py` | segura falhas curtas do MediaPipe e fixa o lado da mão |
| `filtros.py` | suavização dos ângulos: EMA, Kalman e EMA + Kalman, com os parâmetros do artigo EMA × Kalman |
| `geometria.py` | pontos da mão, mão sintética (simulação/testes), conversão para o 3D |
| `capture.py` | webcam + MediaPipe, arquivos de pontos (gravar, ler, reproduzir) |
| `caminhos.py` | todas as pastas e arquivos do projeto (dados locais, relatórios, assets, modelos) |

**Aplicação** — pasta `app/`:

| Arquivo | Faz |
|---|---|
| `avaliador.py` | **motor da avaliação**: recebe cada quadro e decide tudo (sem interface) |
| `janela.py` | janela principal e a navegação entre as telas |
| `tema.py` / `formato.py` | cores, botões, rótulos / números e datas em português |
| `icones.py` | ícones desenhados em SVG |
| `simulacao.py` | mão simulada (`--sim`) |
| `telas/` | uma tela por arquivo: pacientes, ficha, avaliação, relatório, configurações, ajuda |
| `componentes/` | partes das telas: palco 3D, mão 3D procedural (`mao3d.py`: cilindros, esferas e palma gerados a partir dos 21 pontos), painel do dedo (`painel.py`), peças pequenas como réguas, barras e abas (`pecas.py`), mapa da evolução (`mapa.py`), gráfico, barra do topo, dicas, diálogos |
| `dados/` | banco (`banco.py`, com a migração), configurações, resultados, interpretação, PDF, planilha para o Excel (`exportacao.py`), dataset para pesquisa (`dataset.py`), recálculo |
| `versao.py` | versão do ManuMetria e identificação do método dos ângulos, gravadas em cada avaliação |

**Testes** — pasta `tests/`: `testar.py` (roda todos os testes), `test_*.py` e
`dados/gravacao_referencia.npz` (pontos de uma mão saudável real, usados pelos testes).
`test_banco.py` cobre a migração, o código fixo das avaliações e a gravação dos pontos;
`test_dataset.py`, o dataset para pesquisa (com `--copia-do-banco` também exporta uma CÓPIA de
`dados_locais`). O `test_dataset.py` relê os arquivos com o pandas, que é só de desenvolvimento:
`.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` (sem ele, usa o módulo csv). Nenhum
teste toca em `dados_locais`: tudo roda em pastas temporárias (inclusive o caminho usado para apagar
pontos, `caminhos.ROOT`).

**Ferramentas** — pasta `tools/`: `criar_demonstracao.py` (3 pacientes fictícios com avaliações
simuladas pelo mesmo motor da câmera), `analisar_gravacao.py` (passa um arquivo de pontos pelo motor e
mostra a linha do tempo) e `gerar_hash_registro.py` (pacote e hash SHA-512 para o registro de software,
chamado pelo `gerar_hash_registro.bat`).

## Como acrescentar uma medida nova

1. Calcule em `nucleo/kinematics.py` (por dedo) ou `nucleo/medidas.py` (mão inteira), sem interface.
2. Guarde no resultado em `app/dados/resultados.py` (o banco salva o dicionário inteiro).
3. Mostre no painel (`app/componentes/painel.py`), na ficha ou no CSV, se quiser. Para o dataset de
   pesquisa, acrescente a coluna em `app/dados/dataset.py` com a descrição, a unidade e o tipo (o teste
   falha se o dicionário não cobrir todas as colunas).
4. Explique a medida em `app/glossario.py` (vale para a dica ao passar o mouse e para a Ajuda) e use `explain(widget, "chave")` onde ela aparece.
5. Escreva um teste em `tests/test_auditoria.py` (ou `tests/test_medidas.py`) com um caso de resposta
   conhecida.
6. Rode `tests\testar.py`. Se a conta de uma medida mudou, suba `VERSAO` em `app/versao.py` (e
   `GONIOMETRIA`, se mudou o método dos ângulos): cada avaliação guarda a versão que a calculou.
7. Para as avaliações já salvas ganharem a medida: Configurações > **Recalcular avaliações**
   (`app/dados/recalculo.py`). Ele passa os pontos gravados pelo cálculo atual, mostra o que
   muda antes de gravar e guarda o resultado anterior dentro da avaliação (`"original"`).
   Avaliações sem pontos gravados (antes de 15/10/2026) ficam como estão.

O motor usa o horário de cada quadro (`raw["t"]`), não o relógio do computador: por isso
recalcular a partir dos pontos dá exatamente o mesmo resultado da avaliação ao vivo
(há um teste para isso em `tests/test_medidas.py`).

## Banco de dados

O esquema tem versão (`PRAGMA user_version`, `SCHEMA_VERSION` em `app/dados/banco.py`). Ao abrir,
`Banco.__init__` copia o arquivo para `copias_de_seguranca/` (API de backup do SQLite) e `_migrate` leva o
banco até a versão atual numa transação só. Regras: a migração só acrescenta (nenhum valor salvo muda), é
idempotente (confere cada coluna antes de criar) e é testada em `tests/test_banco.py` num banco no
formato antigo. Para acrescentar um campo do paciente: `FIELDS`, `SCHEMA` e um passo novo em `_migrate`
com `SCHEMA_VERSION + 1`.

- **v1 (1.3.0)**: `pacientes.sexo`; `pacientes.id_pesquisa` (pseudônimo aleatório, único);
  `sessoes.codigo` (código fixo da avaliação no paciente, A01, A02..., preenchido uma vez na ordem das
  avaliações existentes) e `pacientes.ultimo_codigo` (o número nunca é reaproveitado, nem depois de apagar
  a última avaliação); índices.
- **Salvar uma avaliação** (`salvar_sessao(..., gravar_pontos=...)`): grava os pontos primeiro (arquivo
  temporário + `os.replace`), depois a linha e o código na mesma transação; se o banco falhar, apaga o
  arquivo novo. **Apagar**: banco primeiro, arquivos depois.
- O caminho dos pontos é salvo relativo à pasta do projeto, com `/` (`caminhos.relativo`); a leitura
  (`caminhos.absoluto`) aceita também a `\` das avaliações salvas até a 1.2.0.
- Cada resultado guarda `versao_app`, `goniometria` e `fuso_utc` (formato 3 de `resultados.py`); sem eles
  = salvo antes da 1.3.0.
- O dataset para pesquisa (`app/dados/dataset.py`) repassa os pontos pelo motor com
  `analisar(..., por_quadro=...)`, que lê o registro de cada quadro em `Avaliador.quadro` (ângulos brutos
  e suavizados, estado, descarte, vista, fase); esse registro não muda nenhuma conta.

## Combinados do projeto

- As **medidas usam os dados brutos**. Suavização (desde a 1.1.0, `nucleo/filtros.py`,
  padrão EMA + Kalman com os parâmetros do artigo EMA × Kalman): por padrão vale SÓ
  PARA A EXIBIÇÃO AO VIVO. O `Avaliador` aplica o filtro logo depois do cálculo e do
  descarte e, no mesmo quadro (`_update_session`), entrega à `Session` os dados brutos
  e guarda os suavizados em `av.display` (valor "Agora", dica da mão 3D) e
  `av.display_history` (gráfico do TAM). Com "Aplicar a suavização também nas medidas"
  (`suavizacao_medidas` em Configurações; `nas_medidas` no registro), a `Session`
  recebe os suavizados, como no pipeline do artigo. Motivo do padrão: o filtro achata
  os picos (na gravação de referência, -10 pp no TAM ativo do indicador e até -66% na
  velocidade de pico; tabela no README). Com o padrão, os resultados
  são idênticos aos do modo "Desligada" (há um teste para isso). Calibração, tremor
  e as medidas por pontos (abertura, polpa-palma) usam sempre os dados brutos. O filtro
  só usa a ordem dos quadros (nada de relógio): o recálculo tem de dar o mesmo resultado
  do ao vivo. Cada avaliação guarda `resultados["filtro"]` (modo, parâmetros e
  `nas_medidas`); o recálculo usa esse registro (sem registro: "Desligada"; sem
  `nas_medidas`: dados brutos). Os parâmetros do artigo não devem ser mudados sem um
  motivo documentado. A média de 8 quadros só decide QUANDO há repetição (e os instantes
  de início e fim, pelo critério da meia sensibilidade); amplitude, classificação, TAM no
  pico, excursão e velocidades saem dos dados brutos. A derivada de Savitzky–Golay (5
  pontos) entra na velocidade de pico (derivada do TAM) e no SPARC (norma das velocidades
  articulares).
- **Goniometria** (v1.2.0): `kin.joint_angles` é um porte fiel do `gonio` da versão web
  (`C:\sistema-mao-web\core\goniometro.js`, igual ao Hand Filter Lab): decomposição por
  osso, recomendação ISB (Wu et al., 2005). Ao mudar essa conta, refaça a prova contra o
  JavaScript (docs/AUDITORIA_CALCULOS.md, seção 3) e o autoteste em `tests/test_auditoria.py`.
- **Auditoria dos cálculos** (v1.2.0): `docs/AUDITORIA_CALCULOS.md` e
  `tests/test_auditoria.py`. Todo número afirmado num texto (README, Ajuda, PDF, dicionário
  de dados, comentário) precisa de evidência no repositório (teste, gravação de referência)
  ou de fonte conferida; o teste confere os números citados e falha se um texto sem fonte
  voltar. Ao mudar uma conta, atualize o relatório e o teste.
- Interpretação por regras explícitas, com "sugestivo de": apoio à decisão, não diagnóstico.
- Textos da interface em português, sem emojis.
- A mão 3D é gerada pelo próprio código (sem modelo de terceiros). A cor de cada
  articulação segue a mesma regra dos cartões dos dedos (`kin.grade`).
- Bibliotecas de terceiros e licenças: `AVISOS_TERCEIROS.md`.
