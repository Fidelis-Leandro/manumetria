"""
Explicação de cada medida, num lugar só.

Usada nas dicas que aparecem ao passar o mouse (tip) e na tela de Ajuda
(ajuda.py monta as seções a partir daqui). Os números vêm das constantes do
cálculo: ao mudar um limite em kinematics.py, medidas.py ou interpretacao.py,
o texto acompanha sozinho.

Cada termo: (nome, explicação curta, detalhe extra só para a Ajuda).
A explicação curta deve caber em duas ou três linhas de dica.
"""

import textwrap

from PyQt5 import QtCore

from app.dados import interpretacao as interp
from nucleo import filtros
from nucleo import kinematics as kin
from nucleo import medidas

_L, _T = kin.NORMAL_JOINT["index"], kin.NORMAL_JOINT["thumb"]
_F = medidas.FUNCTIONAL_ROM
_PCT = lambda x: f"{x * 100:.0f}%"
_BR = lambda x, d=1: f"{x:.{d}f}".replace(".", ",")
_LAG = {m: filtros.atraso_quadros(filtros.registro(m)) for m in (filtros.EMA_MODO, filtros.KALMAN_MODO,
                                                                 filtros.CASCATA)}

TERMS = {
    # ------------------------------------------------------------ dedo
    "flexao": ("Flexão das articulações",
               "Ângulo de cada articulação: positivo é flexão, negativo é hiperextensão.",
               "MCP, PIP e DIP nos dedos longos; MCP e IP no polegar. Na MCP, a linha do punho até a base "
               "do dedo faz o papel do metacarpo (o MediaPipe não marca a base do metacarpo). Os ângulos são "
               "medidos por decomposição por osso, recomendação ISB (Wu et al., 2005): cada osso tem eixos "
               "próprios e a abdução (dedo desviado para o lado) fica separada da flexão. Quadros com "
               f"ângulo impossível (fora de {kin.PLAUSIBLE_RANGE[0]:.0f}° a {kin.PLAUSIBLE_RANGE[1]:.0f}°) "
               "são descartados."),
    "agora": ("Agora", "Flexão da articulação neste momento, suavizada para a exibição (Configurações).",
              "Mínima, máxima e as outras medidas usam os dados brutos, a não ser com a suavização "
              "aplicada também nas medidas."),
    "min": ("Mínima", "Menor flexão da sessão, ou seja, a maior extensão. Negativo = hiperextensão.", ""),
    "max": ("Máxima", "Maior flexão da sessão.", ""),
    "arco": ("Arco de movimento", "Flexão máxima menos flexão mínima: quanto a articulação percorreu.", ""),
    "tam_agora": ("TAM agora", "Soma das flexões das articulações do dedo neste instante (suavizada para a "
                               "exibição).", ""),
    "tam_ativo": ("TAM ativo",
                  "Soma das flexões máximas menos a soma dos déficits de extensão do dedo, como na "
                  "goniometria.",
                  "TAM = total active motion."),
    "pct_normal": ("% do normal",
                   f"TAM ativo comparado a um normal de referência: {sum(_L.values()):.0f}° nos dedos longos "
                   f"e {sum(_T.values()):.0f}° no polegar.",
                   f"Divisão por articulação adotada pelo sistema: MCP {_L['MCP']:.0f}°, PIP {_L['PIP']:.0f}°, "
                   f"DIP {_L['DIP']:.0f}° (polegar: MCP {_T['MCP']:.0f}°, IP {_T['IP']:.0f}°). Os totais aparecem em "
                   "tabelas de resultado do TAM; a divisão por articulação não tem fonte primária conferida. "
                   f"Cor (faixas no estilo da ASSH, fonte secundária): abaixo de {_PCT(kin.GRADE_FAIR)}, "
                   f"de {_PCT(kin.GRADE_FAIR)} até abaixo de {_PCT(kin.GRADE_GOOD)}, e {_PCT(kin.GRADE_GOOD)} ou mais."),
    "deficit": ("Déficit de extensão",
                "Menor flexão que a articulação alcançou: 0° = estendeu por completo.",
                "Déficit = maior valor entre 0 e a menor flexão, como na fórmula do TAM da ASSH: a "
                "hiperextensão conta 0."),
    "arco_funcional": ("Arco funcional",
                       "Quanto da faixa de flexão usada nas atividades diárias o movimento cobre. "
                       "100% = alcança toda a faixa.",
                       f"Faixas de Bain et al. (J Hand Surg Eur, 2015): MCP {_F['MCP'][0]:.0f}–{_F['MCP'][1]:.0f}°, "
                       f"PIP {_F['PIP'][0]:.0f}–{_F['PIP'][1]:.0f}°, DIP {_F['DIP'][0]:.0f}–{_F['DIP'][1]:.0f}°. "
                       "Sem referência para o polegar."),
    "strickland": ("Escore de Strickland",
                   f"(Flexão da PIP + DIP − déficits de extensão) / {medidas.STRICKLAND_TOTAL:.0f}°, nos dedos "
                   "longos. Usado após reparo de tendão flexor.",
                   "85% ou mais excelente, 70–84% bom, 50–69% regular, abaixo ruim."),
    "polpa_palma": ("Distância polpa–palma",
                    "Menor distância da ponta do dedo até a palma na sessão (0 = encostou).",
                    "Os centímetros são aproximados: o MediaPipe usa a escala de uma mão de tamanho médio."),
    # ------------------------------------------------------ repetições
    "movimentos": ("Movimentos, parciais e completas",
                   "Cada vez que o dedo fecha e volta conta um movimento, por menor que seja. "
                   f"Parcial = amplitude de {_PCT(kin.PARTIAL_FRACTION)} a {_PCT(kin.COMPLETE_FRACTION)} "
                   f"do TAM normal; completa = {_PCT(kin.COMPLETE_FRACTION)} ou mais.",
                   f"A média dos últimos {kin.DETECTOR_SMOOTH_FRAMES} quadros do TAM só decide QUANDO há uma "
                   "repetição (o tremor não conta como movimento). A amplitude (pico menos vale), a classificação, "
                   "as velocidades e a excursão de cada articulação saem dos dados brutos."),
    "sensibilidade": ("Sensibilidade",
                      f"Menor movimento que conta: {kin.SENS_FACTOR:.0f}× o tremor da mão parada medido na "
                      f"calibração (entre {kin.SENS_MIN:.0f}° e {kin.SENS_MAX:.0f}°).",
                      "Abaixo disso, o sistema não separa movimento de ruído da câmera. Sem calibração, "
                      f"vale {kin.SENS_DEFAULT:.0f}°."),
    "vel_flexao": ("Velocidade de flexão",
                   f"Amplitude dividida pelo tempo para fechar, média das últimas {kin.QUALITY_LAST_REPS} "
                   "repetições.",
                   "Critério do sistema (sem fonte na literatura): a flexão começa no último instante em que o "
                   "TAM médio esteve a até meia sensibilidade do vale e termina no primeiro instante a até meia "
                   "sensibilidade do pico. Assim uma pausa com a mão aberta ou fechada não entra no tempo."),
    "vel_extensao": ("Velocidade de extensão",
                     "Amplitude da volta dividida pelo tempo para abrir, média das últimas "
                     f"{kin.QUALITY_LAST_REPS} repetições.",
                     "Mesmo critério da flexão: começa no último instante a até meia sensibilidade do pico e "
                     "termina no primeiro a até meia sensibilidade do vale seguinte; pausas não entram."),
    "vel_pico": ("Velocidade de pico",
                 f"Maior velocidade durante a flexão, nas repetições de {kin.MIN_SMOOTH_AMPLITUDE:.0f}° "
                 "ou mais.", ""),
    "sparc": ("Suavidade (SPARC)",
              "Quanto o movimento é contínuo, sem trancos. Mais perto de zero = mais suave: um movimento em "
              "sino dá cerca de −1,5; trancos deixam o valor mais negativo.",
              "SPARC, Balasubramanian et al. (J NeuroEng Rehabil, 2015), com limiar de 0,05 e corte de 10 Hz, "
              "calculado sobre a norma das velocidades das articulações do dedo (MCP, PIP e DIP; polegar: "
              "MCP e IP), como recomenda o artigo."),
    "ciclo": ("Ciclo e cadência",
              "Tempo entre o início de uma repetição e o da seguinte, e quantas repetições cabem num minuto.",
              ""),
    "regularidade": ("Regularidade",
                     f"Quanto a duração do ciclo varia (coeficiente de variação): abaixo de {_PCT(kin.REGULAR_CV)} "
                     f"regular, de {_PCT(kin.REGULAR_CV)} até abaixo de {_PCT(kin.MODERATE_CV)} moderada, "
                     "a partir daí irregular.", ""),
    "amp_fim_inicio": ("Amplitude: fim × início",
                       f"Média das 3 últimas repetições comparada à das 3 primeiras (precisa de "
                       f"{kin.TREND_MIN_REPS}). Uma queda pode indicar fadiga.", ""),
    "vel_tendencia": ("Velocidade: tendência",
                      "Variação da velocidade de flexão do início ao fim da sessão (precisa de "
                      f"{kin.TREND_MIN_REPS} repetições). Uma queda pode indicar fadiga.", ""),
    "esforco": ("Consistência do esforço",
                f"Quanto o fechamento máximo varia entre as {kin.EFFORT_TOP_REPS} repetições mais fortes: "
                f"menos de {_PCT(kin.CONSISTENT_CV)} consistente, {_PCT(kin.CONSISTENT_CV)}–"
                f"{_PCT(kin.MODERATE_EFFORT_CV)} moderada, acima variável.",
                "Pouca variação = o valor máximo é confiável. Muita variação pode ser dor, fadiga, desatenção "
                "ou fechamento incompleto. Não serve para detectar simulação."),
    "repeticoes_fortes": ("Repetições fortes",
                          f"Repetições que chegaram perto do melhor fechamento da sessão (até "
                          f"{_PCT(kin.STRONG_MARGIN)} abaixo). Com {kin.EFFORT_TOP_REPS} delas, o valor "
                          "máximo do dedo é confiável e dá para encerrar.",
                          "Compara com o próprio paciente, não com o normal: quem tem pouca amplitude "
                          "também chega à meta. Dedos que não se moveram (exercício isolado de outro dedo) "
                          "aparecem em cinza e não contam."),
    # ---------------------------------------------------------- padrão
    "independencia": ("Independência do dedo",
                      "Quanto os outros dedos ficaram parados enquanto este se movia (100% = só ele mexeu).",
                      "Ao abrir e fechar a mão inteira, ela é naturalmente baixa."),
    "acompanhamento": ("Movimento junto dos outros dedos",
                       "Quanto cada outro dedo acompanhou o movimento deste, em média.", ""),
    "contribuicao": ("Contribuição de cada articulação",
                     "Parte de cada articulação no movimento do dedo; a barra fina mostra a proporção normal.",
                     ""),
    # ------------------------------------------------------ mão inteira
    "abertura_dedos": ("Abertura dos dedos",
                       "Maior ângulo entre dedos vizinhos na sessão, medido com os dedos pouco flexionados "
                       f"(MCP abaixo de {medidas.SPREAD_MAX_MCP:.0f}°).", ""),
    "abertura_polegar": ("Abertura do polegar", "Ângulo entre os metacarpos do polegar e do indicador.", ""),
    "tremor": ("Tremor",
               f"Oscilação rítmica de {medidas.TREMOR_BAND[0]:.0f} a {medidas.TREMOR_BAND[1]:.0f} Hz nas pontas "
               "dos dedos, nos trechos com a mão parada.",
               "Mesmo sem tremor há uma variação de fundo (ruído do MediaPipe e tremor fisiológico: cerca de "
               "1,2 mm na mão saudável parada da gravação de referência), então só conta um pico bem acima "
               f"dela ({medidas.TREMOR_PEAK_RATIO:.0f}× a mediana do espectro). Frequência com resolução de "
               "0,5 Hz. Valores típicos citados na literatura (fonte primária não conferida): repouso "
               "parkinsoniano ~4–6 Hz; tremor fisiológico ~8–12 Hz."),
    "confiabilidade": ("Confiabilidade da avaliação",
                       "Alta, média ou baixa, pela parte dos quadros com medida válida, a luz, a velocidade da "
                       "imagem, quanto a mão ficou de frente e se a sessão foi curta.",
                       "Uma avaliação de confiabilidade baixa deve ser lida com cautela e não entra no "
                       "cálculo do erro de medida."),
    "qualidade_captura": ("Qualidade da captura",
                          "Velocidade da imagem, luz e quanto a mão está sendo encontrada agora. Amarelo = "
                          f"mão fora do quadro ou de lado (mais de {kin.VIEW_MAX_DEG:.0f}° da palma de frente).",
                          ""),
    "distancia": ("Distância da mão",
                  "Aviso quando a mão fica longe demais (o MediaPipe erra mais os ângulos) ou perto "
                  "demais (os dedos saem da imagem ao abrir). O ideal é cerca de 50 cm.",
                  f"Medido pelo tamanho da mão na imagem; só avisa se durar {medidas.DISTANCE_FRAMES} quadros "
                  "seguidos (cerca de meio segundo a 30 quadros/s)."),
    "suavizacao": ("Suavização do sinal",
                   "Filtro que tira a tremedeira da câmera dos ângulos de cada articulação. Por padrão vale "
                   "só para o que aparece ao vivo (valor Agora, gráfico do TAM): as medidas usam os dados brutos.",
                   f"EMA (média móvel exponencial): cada valor novo entra com peso "
                   f"{_BR(filtros.EMA_ALPHA, 2)} e o anterior com {_BR(1 - filtros.EMA_ALPHA, 2)}; atraso médio "
                   f"de ~{_BR(_LAG['ema'])} quadros. Kalman: estima o ângulo verdadeiro pesando a medida nova "
                   f"contra a estimativa anterior (Q = {_BR(filtros.KALMAN_Q, 2)}, R = {_BR(filtros.KALMAN_R, 2)}), "
                   f"com atraso de ~{_BR(_LAG['kalman'])} quadros depois de estabilizar. EMA + Kalman (padrão): "
                   f"um depois do outro, mais liso e com atraso de ~{_BR(_LAG['ema_kalman'])} quadros "
                   f"(~{_BR(_LAG['ema_kalman'] / 30, 2)} s a 30 quadros/s; mais com câmera lenta). Mesmos "
                   "filtros e parâmetros do artigo EMA × Kalman (Fidelis, ERAMIA-RS 2026). Por que só na "
                   "exibição: o filtro achata os picos. Na gravação de referência (mão saudável), aplicado "
                   "também nas medidas, o EMA + Kalman baixou o TAM ativo do indicador de 98% para 88% do "
                   "normal, a velocidade de pico em até 66% e a contagem de repetições (23 para 19 no "
                   "indicador), e a flexão máxima da MCP do indicador (81,5° para 71,1°) ficou no limite do "
                   "arco funcional. "
                   "Escolha em Configurações; cada avaliação guarda o filtro usado e onde foi aplicado."),
    "suavizacao_medidas": ("Suavização também nas medidas",
                           "Opcional: o filtro entra antes das repetições e de todas as medidas, como no "
                           "pipeline do artigo. Deixa as medidas mais estáveis, mas com picos menores.",
                           "Flexão máxima, TAM ativo, velocidade de pico e repetições ficam menores que com os "
                           "dados brutos e deixam de ser comparáveis com avaliações sem essa opção. O PDF e o "
                           "CSV dizem se a opção estava marcada. Calibração, tremor, abertura dos dedos e "
                           "polpa–palma usam sempre os dados brutos."),
    "tam_ao_vivo": ("TAM nos últimos 20 s",
                    "Soma das flexões de cada dedo ao longo do tempo: o dedo escolhido em destaque, os outros "
                    "em cinza. Cada subida e descida é uma repetição.",
                    "A curva mostrada é suavizada (Configurações); a contagem de repetições usa os dados "
                    "brutos, a não ser com a suavização aplicada também nas medidas."),
    # --------------------------------------------- evolução e ficha
    "reteste": ("Reteste",
                "Repetir a medição logo em seguida, com a mão reposicionada. Comparando os dois, o sistema "
                "estima o próprio erro de medida.",
                ""),
    "erro_medida": ("Erro de medida",
                    "Quanto a medida varia só por repetir (1,96 × desvio das diferenças teste–reteste). "
                    "Mudanças menores que isso podem ser só erro.",
                    f"Precisa de pelo menos {interp.MIN_PAIRS} pares; no % do normal, cada reteste soma 5, "
                    "um por dedo. Retestes de confiabilidade baixa não entram."),
    "mudanca_real": ("Mudança real",
                     "Diferença entre avaliações maior que o erro de medida: verde = melhora, vermelho = piora.",
                     "Sem retestes suficientes, as diferenças aparecem sem essa classificação."),
    "tendencia": ("Tendência",
                  "Melhora, piora ou estável: a última avaliação comparada à anterior, usando o erro de medida.",
                  f"No resumo da ficha, a variação por semana usa as 5 últimas avaliações (precisa de "
                  f"{interp.TREND_MIN_SESSIONS}). Na lista de pacientes, a média dos 5 dedos."),
    "plato": ("Platô",
              f"As {interp.PLATEAU_SESSIONS} últimas avaliações ficaram dentro do erro de medida: o paciente "
              "parou de mudar.",
              "Não é piora. Pode ser hora de dar alta ou de mudar o tratamento."),
    "ultima_avaliacao": ("Última avaliação",
                         "Data da avaliação mais recente. Em amarelo: paciente em tratamento sem avaliação há "
                         f"mais de {interp.OVERDUE_DAYS // 7} semanas.", ""),
    "situacao": ("Situação", "Em tratamento ou de alta (com a data da alta).", ""),
    "resumo": ("Resumo da ficha",
               "Frases geradas por regras: situação da última avaliação, mudança desde a anterior, tendência, "
               "articulações fora do arco funcional e padrões do movimento. Apoio à decisão, não diagnóstico.",
               "Exemplos de padrão: DIP que se move pouco em relação à PIP (sugere déficit do flexor profundo) e "
               "dedo que não se move isoladamente."),
    "mapa": ("Mapa da evolução",
             "Todas as articulações em todas as avaliações, cada célula colorida pela flexão máxima em % do "
             "normal da articulação. Mostra de relance qual articulação está atrasada.",
             "Clique numa célula para abrir o gráfico daquela articulação. Os nomes de articulação no Resumo "
             "(por exemplo, DIP do anelar) também abrem o gráfico."),
    "semanas": ("Semanas desde a lesão",
                "Mostra a evolução pelo tempo desde a lesão ou cirurgia, como nos protocolos de reabilitação. "
                "Precisa da data no cadastro.", ""),
    "faixa_erro": ("Faixa azul do gráfico",
                   "Erro de medida em volta da última avaliação: se a próxima cair fora dela, a mudança é real.",
                   ""),
}


def tip(key):
    """Texto da dica (ao passar o mouse): a explicação curta, em linhas curtas
    (a dica do Qt não quebra a linha sozinha)."""
    return "\n".join(textwrap.wrap(TERMS[key][1], 70))


def explain(widget, *keys):
    """Dica ao passar o mouse + cursor de ajuda (sinal discreto de que há explicação).
    Com mais de uma chave, as explicações aparecem uma embaixo da outra."""
    widget.setToolTip("\n\n".join(tip(k) for k in keys))
    widget.setCursor(QtCore.Qt.WhatsThisCursor)


def explain_columns(table, columns):
    """Dica nos títulos das colunas: columns = {índice da coluna: chave do glossário}."""
    for col, key in columns.items():
        table.horizontalHeaderItem(col).setToolTip(tip(key))


def help_html(key):
    """Parágrafo da Ajuda: nome em negrito, explicação e o detalhe extra."""
    name, short, extra = TERMS[key]
    return f"<p><b>{name}</b>: {short}{' ' + extra if extra else ''}</p>"
