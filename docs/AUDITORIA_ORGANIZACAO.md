# Auditoria de organização e limpeza do código (ManuMetria 1.4.0)

Registro da auditoria feita antes do pacote para o registro de software: o que foi encontrado, o que o
autor decidiu e o que foi feito. É uma reorganização: o comportamento do sistema e todos os números
calculados ficaram idênticos (seção "Não regressão"). A arquitetura resultante está em
[ARQUITETURA.md](ARQUITETURA.md).

## 1. Situação encontrada (versão 1.3.0)

**Pastas:** `nucleo/` (cálculo sem interface: `kinematics.py`, `medidas.py`, `filtros.py`,
`stabilizer.py`, `geometria.py`, `capture.py`, `caminhos.py`) e `app/` (interface, motor da avaliação,
dados e relatórios), mais `assets/` (logotipo) e o modelo `hand_landmarker.task` solto na raiz.

**Responsabilidades misturadas:**

- o motor (`app/avaliador.py`) e o formato dos resultados (`app/dados/resultados.py`) não usavam Qt, mas
  ficavam na pasta da interface; `dados.recalculo` e `dados.dataset` dependiam do motor, e o motor de
  `dados.resultados` (ciclo entre camadas);
- o PDF (`app/dados/documento.py`) e as regras clínicas (`app/dados/interpretacao.py`) estavam em `dados/`;
- `CaptureQuality` (limiares de luz, fps e detecção) estava dentro de um componente visual
  (`app/componentes/topo.py`);
- `resultados.py` misturava o formato do resultado com a formatação do CSV;
- `kinematics.py` (734 linhas) juntava ângulos, sinal, repetições, calibração e sessão; nomes de
  arquivos em inglês e português misturados;
- 15 arquivos usavam `from app.tema import *`, e o tema reexportava a formatação e a configuração;
- escolher um logotipo em Configurações sobrescrevia o arquivo versionado `assets/logo_relatorio.png`.

**Código morto** (análise por AST, conferindo também `connect`/`emit` do Qt, reimplementações de eventos,
testes e `.bat`): `resultados.calculation_version`, `caminhos.BACKUP_DIR`, a constante
`filtros.REFERENCIA` (só documentação) e, em `dataset.py`, as chaves `n_frames`, `settings` e
`diferencas` (gravadas e nunca lidas). Os imports "sem uso" de `tema.py` eram reexportações.

**Arquivos sem uso:** `docs/mao3d_procedural.png` e `docs/mao3d_procedural_vista.png` (213 KB, sem
referência). Nada versionado que devesse estar no `.gitignore`; faltava `*.gravando`.

**Comentários:** cerca de 30 com histórico ou número de versão do app ("Agora o lado é FIXADO", "até a
1.2.0", "(ManuMetria 1.3.0)", "D3", "D9", "v1.2.0"); 226 funções e classes públicas sem docstring.

## 2. Decisões do autor

1. Estrutura em camadas `calculo → captura → avaliacao → dados → relatorios → interface`, com os
   utilitários `caminhos`, `versao` e `formato` na raiz do pacote, e um teste de arquitetura.
2. `kinematics.py` dividido em `goniometria.py`, `sinal.py`, `repeticoes.py` e `sessao.py`, sem módulo de
   compatibilidade.
3. Classes e funções continuam em inglês; arquivos, pastas, docstrings e comentários em português.
4. O logotipo escolhido vai para `dados_locais/`; o padrão (`manumetria/recursos/`) nunca é sobrescrito;
   o `config.json` que aponta para `assets/logo_relatorio.png` usa o padrão.
5. `docs/mao3d_procedural_vista.png` no README ("Como usar"); `docs/mao3d_procedural.png` apagada.
6. Imports explícitos no lugar de `from app.tema import *`; o tema deixa de reexportar.
7. Formatos gravados descritos como "formato N" e "esquema N", sem versão do app nem histórico.
8. Erros anotados: (a) e (b) corrigidos; (c) só documentado (abaixo).

## 3. Erros anotados

- **(a) corrigido.** `tools/criar_demonstracao.py outro.sqlite` gravava os pontos ao lado do banco, mas
  guardava o caminho relativo à pasta do projeto (com `..`; em outro disco o caminho relativo nem
  existe). Agora o caminho é relativo à pasta do banco.
- **(b) corrigido.** `sistema.py --banco outro.sqlite` gravava os pontos em `dados_locais/pontos` do
  projeto. Agora grava em `pontos/` ao lado desse banco. Com o banco padrão nada muda
  (`caminhos.pastas_do_banco`). Teste: `tests/test_pastas.py`.
- **(c) documentado, não corrigido.** O horário `inicio` de uma avaliação é o começo da sessão
  (preparação, antes da calibração), não o começo da medição; a duração da medição é calculada à parte e
  nenhum número muda. Documentado no dicionário de dados (dataset e planilha), no glossário (Ajuda) e em
  ARQUITETURA.md.
- **Cálculos:** nenhum erro encontrado nesta auditoria (a auditoria dos cálculos,
  [AUDITORIA_CALCULOS.md](AUDITORIA_CALCULOS.md), continua valendo).

## 4. De → para

| De | Para |
|---|---|
| `nucleo/kinematics.py` | `manumetria/calculo/goniometria.py`, `sinal.py`, `repeticoes.py`, `sessao.py` |
| `nucleo/medidas.py`, `filtros.py`, `geometria.py` | `manumetria/calculo/` |
| `nucleo/stabilizer.py` | `manumetria/calculo/estabilizador.py` |
| `nucleo/capture.py` | `manumetria/captura/camera.py` e `gravacao.py` |
| `nucleo/caminhos.py` | `manumetria/caminhos.py` |
| `app/simulacao.py` | `manumetria/captura/simulacao.py` |
| `CaptureQuality` (em `app/componentes/topo.py`) | `manumetria/captura/qualidade.py` |
| `app/avaliador.py` | `manumetria/avaliacao/motor.py` |
| `app/dados/resultados.py` | `manumetria/avaliacao/resultados.py` (a parte do CSV foi para `dados/planilha.py`) |
| `app/dados/interpretacao.py` | `manumetria/avaliacao/interpretacao.py` |
| `app/dados/banco.py`, `recalculo.py`, `dataset.py` | `manumetria/dados/` |
| `app/dados/config.py` | `manumetria/dados/configuracoes.py` |
| `app/dados/exportacao.py` | `manumetria/dados/planilha.py` |
| `app/dados/documento.py` | `manumetria/relatorios/pdf.py` |
| `app/formato.py`, `app/versao.py` | `manumetria/` |
| `app/janela.py`, `tema.py`, `icones.py`, `glossario.py`, `telas/`, `componentes/` | `manumetria/interface/` |
| `assets/logo_relatorio.png` | `manumetria/recursos/logo_relatorio.png` |
| `hand_landmarker.task` (raiz, fora do Git) | `manumetria/recursos/hand_landmarker.task` |
| `tests/test_kinematics.py`, `test_stabilizer.py` | `tests/test_cinematica.py`, `test_estabilizador.py` |
| (novos) | `tests/test_arquitetura.py`, `test_reorganizacao.py`, `test_pastas.py`, `tests/dados/referencia_resultados.json`, `docs/ARQUITETURA.md`, este arquivo |
| `docs/mao3d_procedural.png` | apagado |

Os `.bat` continuam na raiz com os mesmos nomes; o `Instalar sistema.bat` baixa o modelo para
`manumetria/recursos/`. O atalho da Área de Trabalho aponta para o `Abrir sistema.bat` e continua valendo.

## 5. Não regressão

Antes de mover qualquer arquivo foi gerada uma linha de base (fora do repositório): a saída de todos os
testes, o resultado completo da gravação de referência (suavização padrão e EMA + Kalman nas medidas), o
dataset e a planilha exportados de um banco de demonstração temporário (mesma semente e mesma data), o
texto de um PDF de demonstração e a lista de arquivos versionados. Depois da reorganização a mesma geração
foi repetida e comparada. O resultado da gravação de referência ficou guardado em
`tests/dados/referencia_resultados.json` e é conferido a cada execução por `tests/test_reorganizacao.py`.
