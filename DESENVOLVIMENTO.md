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

## Onde ficam os dados

| Pasta | O que tem |
|---|---|
| `dados_locais/avaliacoes.sqlite` | pacientes e avaliações (SQLite) |
| `dados_locais/config.json` | Configurações (instituição, logotipo, tema, tamanho) |
| `dados_locais/pontos/` | pontos da mão de cada avaliação salva (.npz, sem vídeo) |
| `relatorios/` | PDFs, CSVs e exportações para pesquisa |
| `assets/logo_relatorio.png` | logotipo do PDF |

## Como o código está organizado

O caminho de um quadro da câmera até a tela:

```
câmera ─► nucleo/capture.py ─► app/avaliador.py ───────► app/telas/avaliacao.py (mostra)
                                (fases, calibração,        │
                                 estabilizador, medidas)    ▼ ao encerrar
                                usa: nucleo/kinematics.py  resultados (dicionário)
                                     nucleo/stabilizer.py    ├─► app/dados/banco.py (salva)
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
| `dados/` | banco, configurações, resultados, interpretação, PDF, exportação, recálculo |

**Testes** — pasta `tests/`: `testar.py` (roda todos os testes), `test_*.py` e
`dados/gravacao_referencia.npz` (pontos de uma mão saudável real, usados pelos testes).

**Ferramentas** — pasta `tools/`: `criar_demonstracao.py` (3 pacientes fictícios com avaliações
simuladas pelo mesmo motor da câmera), `analisar_gravacao.py` (passa um arquivo de pontos pelo motor e
mostra a linha do tempo) e `gerar_hash_registro.py` (pacote e hash SHA-512 para o registro de software,
chamado pelo `gerar_hash_registro.bat`).

## Como acrescentar uma medida nova

1. Calcule em `nucleo/kinematics.py` (por dedo) ou `nucleo/medidas.py` (mão inteira), sem interface.
2. Guarde no resultado em `app/dados/resultados.py` (o banco salva o dicionário inteiro).
3. Mostre no painel (`app/componentes/painel.py`), na ficha ou no CSV, se quiser.
4. Explique a medida em `app/glossario.py` (vale para a dica ao passar o mouse e para a Ajuda) e use `explain(widget, "chave")` onde ela aparece.
5. Escreva um teste em `tests/test_medidas.py` com um caso de resposta conhecida.
6. Rode `tests\testar.py`.
7. Para as avaliações já salvas ganharem a medida: Configurações > **Recalcular avaliações**
   (`app/dados/recalculo.py`). Ele passa os pontos gravados pelo cálculo atual, mostra o que
   muda antes de gravar e guarda o resultado anterior dentro da avaliação (`"original"`).
   Avaliações sem pontos gravados (antes de 15/10/2026) ficam como estão.

O motor usa o horário de cada quadro (`raw["t"]`), não o relógio do computador: por isso
recalcular a partir dos pontos dá exatamente o mesmo resultado da avaliação ao vivo
(há um teste para isso em `tests/test_medidas.py`).

## Banco de dados

O banco se atualiza sozinho ao abrir: colunas novas são acrescentadas em `Banco.__init__`
(`app/dados/banco.py`), sem apagar nada. Para acrescentar um campo do paciente, inclua em
`FIELDS`, no `SCHEMA` e na lista de colunas novas.

## Combinados do projeto

- Os números mostrados são **crus**: nada de filtro de suavização na tela (não há
  EMA nem Kalman). A média de 8 quadros serve só para o contador de repetições
  decidir, e a derivada de Savitzky–Golay (5 pontos) só para a velocidade de pico
  e a suavidade (SPARC).
- Interpretação por regras explícitas, com "sugestivo de": apoio à decisão, não diagnóstico.
- Textos da interface em português, sem emojis.
- A mão 3D é gerada pelo próprio código (sem modelo de terceiros). A cor de cada
  articulação segue a mesma regra dos cartões dos dedos (`kin.grade`).
- Bibliotecas de terceiros e licenças: `AVISOS_TERCEIROS.md`.
