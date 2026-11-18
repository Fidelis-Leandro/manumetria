# Arquitetura do ManuMetria

O sistema fica no pacote `manumetria/`, dividido em seis camadas e três utilitários. O ponto de entrada é
o `sistema.py`, na raiz, que os arquivos `.bat` chamam.

## Camadas

```
calculo  ->  captura  ->  avaliacao  ->  dados  ->  relatorios  ->  interface
   ^            ^             ^            ^            ^               ^
   +------------+-------------+------------+------------+---------------+
                  caminhos.py · versao.py · formato.py (utilitários)
```

**Regra:** cada camada só importa as camadas à esquerda dela e os utilitários. Os utilitários não
importam nenhuma camada. Só `relatorios` e `interface` usam o PyQt5. O cálculo não sabe que existe câmera,
banco ou tela. O `tests/test_arquitetura.py` lê os imports de todos os arquivos (análise do código, sem
executar) e falha se a regra for quebrada.

| Camada | Responsabilidade | Arquivos |
|---|---|---|
| `calculo/` | contas puras (numpy), sem câmera, banco ou interface | `goniometria.py` (dedos, articulações, valores normais, ângulos ISB com sinal, plausibilidade, vista da mão, classificação do % do normal), `sinal.py` (reamostragem, derivada, SPARC, tendência), `repeticoes.py` (`Rep`, `FingerTracker`), `sessao.py` (`Calibration`, `Session`), `medidas.py` (mão inteira, tremor, confiabilidade), `filtros.py` (EMA, Kalman), `estabilizador.py`, `geometria.py` |
| `captura/` | de onde vêm os quadros e como são gravados | `camera.py` (webcam + MediaPipe), `gravacao.py` (arquivos de pontos .npz), `simulacao.py` (mão simulada), `qualidade.py` (luz, fps e detecção) |
| `avaliacao/` | a avaliação em si, sem interface | `motor.py` (`Avaliador`, `analisar`), `resultados.py` (o resultado como dicionário), `interpretacao.py` (erro de medida, mudança real, tendência, platô, resumo) |
| `dados/` | persistência e exportação | `banco.py` (SQLite, migração), `configuracoes.py`, `recalculo.py`, `planilha.py` (CSV para o Excel), `dataset.py` (dataset para pesquisa) |
| `relatorios/` | o documento da avaliação | `pdf.py` (prévia e PDF, com QTextDocument) |
| `interface/` | janela e telas (PyQt5) | `janela.py`, `tema.py`, `icones.py`, `glossario.py`, `telas/`, `componentes/` |
| utilitários | usados por todas as camadas | `caminhos.py` (todas as pastas e arquivos), `versao.py` (versão e método dos ângulos), `formato.py` (números e datas em português) |
| `recursos/` | arquivos que acompanham o sistema | `logo_relatorio.png` (logotipo padrão), `hand_landmarker.task` (modelo do MediaPipe, baixado na instalação, fora do Git) |

Por que o motor fica em `avaliacao/` e não em `calculo/`: ele usa a captura (o formato dos quadros e a
gravação dos pontos). E fica antes de `dados/` porque o recálculo e o dataset passam os pontos pelo mesmo
motor da tela, então a conta é sempre a mesma em todo lugar.

## Caminho de um quadro

```
câmera ─► captura/camera.py ─► avaliacao/motor.py ──────────► interface/telas/avaliacao.py (mostra)
          (ou gravacao.py,      calculo/estabilizador.py          │
           simulacao.py)        calculo/goniometria.py            ▼ ao encerrar
                                calculo/filtros.py              avaliacao/resultados.py (dicionário)
                                calculo/sessao.py                 ├─► dados/banco.py (salva; pontos via
                                calculo/repeticoes.py             │   captura/gravacao.py)
                                calculo/medidas.py                ├─► relatorios/pdf.py (relatório)
                                                                  └─► avaliacao/interpretacao.py (ficha)
```

1. A fonte (`CameraSource`, `ReplaySource` ou `DemoHand`) entrega um dicionário "raw" por quadro (pontos
   3D e 2D, lado da mão, confiança, fps, brilho).
2. O `Avaliador` passa o quadro pelo estabilizador, calcula os ângulos (`goniometria.joint_angles`),
   descarta ângulos impossíveis e vistas de lado, suaviza para a exibição e entrega à `Session` os dados
   brutos (ou os suavizados, se a suavização vale também nas medidas).
3. A tela só mostra o que o motor decide. Ao encerrar, `Avaliador.results()` monta o dicionário que vai
   para o banco, o relatório, o CSV e o dataset.

## Onde ficam os dados

`caminhos.py` define todas as pastas. Os dados do usuário ficam em `dados_locais/` (fora do Git): banco,
`config.json`, pontos de cada avaliação e o logotipo escolhido em Configurações. O código e os recursos
versionados nunca são alterados pelo uso do sistema.

`caminhos.pastas_do_banco(arquivo)` dá a pasta base dos caminhos salvos e a pasta dos pontos de um banco:
para o banco padrão, a pasta do projeto e `dados_locais/pontos/`; para outro banco
(`sistema.py --banco outro.sqlite`), a pasta dele e `pontos/` ao lado dele. Os caminhos são salvos
relativos a essa pasta base, com `/`, então a pasta pode ser copiada para outro lugar ou outro disco.

## Formatos gravados

- **Resultado de uma avaliação** (`avaliacao/resultados.py`, campo `versao`): formato 3. Os formatos 1 e 2
  continuam legíveis (campo que falta = ausente). O formato 3 registra a versão do ManuMetria que calculou
  as medidas, o método dos ângulos e o fuso do horário.
- **Banco** (`dados/banco.py`, `PRAGMA user_version`): esquema 1, com migração automática, idempotente e
  com cópia de segurança antes.
- **Pontos da mão** (`captura/gravacao.py`): `.npz` com os 21 pontos 3D e 2D de cada quadro, sem vídeo,
  gravado de forma atômica.
- **Horário e duração**: `inicio` marca o início da sessão, quando a preparação começa (antes da
  calibração); `duracao_s` é calculada à parte e conta só a medição, sem a preparação, a calibração, as
  recalibrações e as pausas.

## Testes que protegem a estrutura

- `tests/test_arquitetura.py`: as camadas (imports), sem imports relativos, sem `import *`.
- `tests/test_reorganizacao.py`: o resultado completo da gravação de referência é idêntico ao guardado em
  `tests/dados/referencia_resultados.json`. Uma mudança intencional de cálculo exige gerar de novo esse
  arquivo e documentar a mudança em `docs/AUDITORIA_CALCULOS.md`.
- `tests/test_pastas.py`: pastas do banco padrão e de outro banco, logotipo, e `dados_locais` intacto.

## Convenções

- Arquivos e pastas em português, minúsculas, sem acento; classes e funções em inglês.
- Docstrings e comentários em português, atemporais.
- Imports absolutos (`from manumetria.calculo import goniometria`), um módulo por assunto.
