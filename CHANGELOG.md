# Histórico de versões

Da versão mais nova para a mais antiga. Como o método de cálculo funciona hoje: [docs/METODOLOGIA.md](docs/METODOLOGIA.md).

## 1.4.1 — 18/11/2026

Só documentação. O programa e os cálculos são os mesmos da 1.4.0 (as avaliações continuam registrando a
versão 1.4.0).

- README reescrito para quem usa ou avalia o sistema.
- Novos: [docs/METODOLOGIA.md](docs/METODOLOGIA.md) (ângulos, tratamento do sinal, definição das medidas,
  verificação dos cálculos e referências) e este histórico de versões.
- O pacote para o registro de software, a linha de comando e a estrutura de pastas foram para o
  [DESENVOLVIMENTO.md](DESENVOLVIMENTO.md).

## 1.4.0 — 18/11/2026

Organização e limpeza do código, sem mudança de cálculo: todos os números são idênticos aos da 1.3.0.

- Código em camadas no pacote `manumetria/` ([docs/ARQUITETURA.md](docs/ARQUITETURA.md)), com um teste
  automático que confere as camadas.
- Com outro banco (`sistema.py --banco`), os pontos da mão ficam em `pontos/` ao lado dele.
- O logotipo escolhido em Configurações é copiado para `dados_locais/`; o logotipo padrão não é mais
  sobrescrito.
- Registro da auditoria: [docs/AUDITORIA_ORGANIZACAO.md](docs/AUDITORIA_ORGANIZACAO.md).

## 1.3.0 — 17/11/2026

Dataset de pesquisa e rastreabilidade.

- **Exportar dados > Dataset para pesquisa**: pasta pseudonimizada com pacientes, avaliações, dedos,
  repetições e quadros, dicionário de dados, LEIA-ME e checksums.
- Banco com migração automática e cópia de segurança antes de atualizar; sexo e pseudônimo de pesquisa do
  paciente; código fixo de cada avaliação no paciente (A01, A02...).
- Cada avaliação passa a guardar a versão do ManuMetria, o método dos ângulos e o fuso do horário.
  Avaliações salvas antes da 1.3.0 não têm esse registro.

## 1.2.0 — 17/11/2026

Auditoria dos cálculos ([docs/AUDITORIA_CALCULOS.md](docs/AUDITORIA_CALCULOS.md)) e **mudança de método**:

- ângulos por decomposição por osso, recomendação ISB (Wu et al., 2005): a abdução não entra mais na
  flexão;
- amplitude, classificação, velocidades e excursão de cada repetição pelos dados brutos, com início e fim
  pelo critério da meia sensibilidade (pausas não entram no tempo);
- déficit de extensão sem a tolerância de 3°;
- independência com o mesmo sinal no numerador e no denominador;
- SPARC sobre a norma das velocidades articulares;
- na ficha, a mudança da extensão é classificada pelo déficit (aumentar a hiperextensão não conta como
  melhora);
- retiradas dos textos as afirmações sem evidência no repositório.

**Avaliações antigas.** As avaliações salvas antes da 1.2.0 **não são comparáveis** às novas até serem
atualizadas: abra **Configurações > Recalcular avaliações**. O recálculo passa os pontos gravados pelo
cálculo novo, mostra o que muda antes de gravar e guarda o resultado anterior na própria avaliação. As
avaliações feitas antes de 15/10/2026 não têm pontos gravados e **ficam no método antigo**.

## 1.1.0 — 17/11/2026

Filtros de suavização.

- **Configurações > Suavização do sinal**: Desligada, EMA, Kalman ou EMA + Kalman (padrão).
- Por padrão, o filtro vale só para a exibição ao vivo; as medidas continuam nos dados brutos. A opção
  "Aplicar a suavização também nas medidas" aplica o filtro também às medidas.
- Cada avaliação registra o filtro usado (PDF, CSV e dicionário de dados).

## 1.0.0 — 17/11/2026

Primeira versão com o nome ManuMetria.

- Nome e subtítulo "Avaliação cinemática da mão por visão computacional" na janela, no PDF, no CSV e na
  documentação.
- Mão 3D gerada pelo próprio sistema, com as articulações coloridas pelo % do normal do dedo e a dica com
  o nome e os valores de cada articulação.
- A avaliação abre com a câmera em destaque e a mão 3D na miniatura.
- Avisos de terceiros e licenças ([AVISOS_TERCEIROS.md](AVISOS_TERCEIROS.md)).
