"""
Suavização dos ângulos das articulações: EMA, Kalman e a cascata EMA -> Kalman.

Reproduz os filtros do sistema usado no artigo EMA × Kalman (Fidelis, ERAMIA-RS
2026), cuja implementação de referência é o repositório oficial
computer-vision-based-hand-kinematic-assessment (smoothing.py: SeriesFilter e
GoniometryFilterBank; parâmetros em config.py: EMA_ALPHA, KALMAN_Q, KALMAN_R;
chamada em workers/processing_worker.py). Os valores são os mesmos no
repositório ARTIGO_Eramia. Só os filtros vieram de lá; a goniometria é a do
ManuMetria (nucleo/kinematics.py).

Onde se aplica (registrado em cada avaliação, chave "nas_medidas"):
  - padrão: SÓ NA EXIBIÇÃO AO VIVO (valor "Agora", dica da mão 3D, gráfico do
    TAM nos últimos 20 s). As medidas da sessão usam os dados brutos, iguais às
    do modo Desligada: a suavização achata os picos (efeito medido na gravação
    de referência: tabela no README);
  - nas_medidas = True (opção em Configurações): também nas medidas, antes do
    contador de repetições, como no pipeline do artigo.

Cada articulação de cada dedo tem o seu filtro, independente dos outros
(como uma instância de SeriesFilter por série no artigo). O filtro só conhece
a SEQUÊNCIA de valores: não usa o relógio. Assim, recalcular a partir dos
pontos gravados dá exatamente o mesmo resultado da avaliação ao vivo.

Equações (n = quadro; z = ângulo medido; tudo escalar):

  EMA      y[0] = z[0]
           y[n] = alfa * z[n] + (1 - alfa) * y[n-1]

  Kalman   modelo de posição constante (passeio aleatório): x[n] = x[n-1] + ruído
           (F = 1, H = 1, um estado só: o ângulo)
           início:   x = z[0], P = P0 (no 1º quadro não há atualização)
           predição: P- = P + Q                    (x- = x)
           ganho:    K  = P- / (P- + R)
           correção: x  = x + K * (z - x)
                     P  = (1 - K) * P-

  EMA + Kalman (padrão do aplicativo do artigo): z -> EMA -> Kalman.

Parâmetros do artigo: alfa = 0,30; Q = 0,01; R = 0,10; P0 = 1,0.
Diferença consciente: o artigo arredondava a SAÍDA a 2 casas (só para exibir e
gravar o CSV, o estado interno não era arredondado); aqui a saída não é
arredondada.
"""

import math

import numpy as np

# Parâmetros do artigo (config.py do repositório oficial)
EMA_ALPHA = 0.30
KALMAN_Q = 0.01
KALMAN_R = 0.10
KALMAN_P0 = 1.0           # covariância inicial (SeriesFilter._p = 1.0)

DESLIGADA, EMA_MODO, KALMAN_MODO, CASCATA = "desligada", "ema", "kalman", "ema_kalman"
MODOS = {DESLIGADA: "Desligada", EMA_MODO: "EMA", KALMAN_MODO: "Kalman", CASCATA: "EMA + Kalman"}
PADRAO = CASCATA          # o aplicativo do artigo sempre usava a cascata ("obrigatória")

REFERENCIA = ("Fidelis, ERAMIA-RS 2026 (EMA × Kalman); parâmetros do repositório "
              "computer-vision-based-hand-kinematic-assessment (smoothing.py, config.py)")


# =============================================================================
# Filtros de uma série (uma articulação)
# =============================================================================
class EMA:
    """Média móvel exponencial. O 1º valor passa direto."""

    def __init__(self, alpha=EMA_ALPHA):
        self.alpha = float(alpha)
        self.y = None

    def update(self, z):
        z = float(z)
        self.y = z if self.y is None else self.alpha * z + (1.0 - self.alpha) * self.y
        return self.y

    def reset(self):
        self.y = None


class Kalman:
    """Kalman escalar de posição constante (passeio aleatório). O 1º valor passa direto."""

    def __init__(self, q=KALMAN_Q, r=KALMAN_R, p0=KALMAN_P0):
        self.q, self.r, self.p0 = float(q), float(r), float(p0)
        self.reset()

    def update(self, z):
        z = float(z)
        if self.x is None:
            self.x = z
            return self.x
        p_minus = self.p + self.q
        self.k = p_minus / (p_minus + self.r)
        self.x = self.x + self.k * (z - self.x)
        self.p = (1.0 - self.k) * p_minus
        return self.x

    def reset(self):
        self.x = None
        self.p = self.p0
        self.k = 1.0


class Cascata:
    """EMA seguido de Kalman (o Kalman recebe a saída do EMA), como no artigo."""

    def __init__(self, alpha=EMA_ALPHA, q=KALMAN_Q, r=KALMAN_R, p0=KALMAN_P0):
        self.ema = EMA(alpha)
        self.kalman = Kalman(q, r, p0)

    def update(self, z):
        return self.kalman.update(self.ema.update(z))

    def reset(self):
        self.ema.reset()
        self.kalman.reset()


class Nenhum:
    """Modo "Desligada": devolve os dados brutos."""

    def update(self, z):
        return float(z)

    def reset(self):
        pass


# =============================================================================
# Configuração registrada na avaliação
# =============================================================================
def registro(modo=PADRAO, alpha=EMA_ALPHA, q=KALMAN_Q, r=KALMAN_R, p0=KALMAN_P0, nas_medidas=False):
    """O que fica salvo no resultado da avaliação (modo, parâmetros e se o filtro
    também entrou nas medidas ou foi só na exibição ao vivo)."""
    if modo not in MODOS:
        modo = PADRAO
    reg = {"modo": modo, "nome": MODOS[modo], "nas_medidas": bool(nas_medidas) and modo != DESLIGADA}
    if modo in (EMA_MODO, CASCATA):
        reg["ema_alpha"] = float(alpha)
    if modo in (KALMAN_MODO, CASCATA):
        reg.update(kalman_q=float(q), kalman_r=float(r), kalman_p0=float(p0),
                   kalman_modelo="posição constante")
    return reg


def registro_de(salvo):
    """Registro salvo numa avaliação -> registro completo. Sem registro (avaliações
    anteriores aos filtros) = "Desligada"; sem "nas_medidas" = só na exibição
    (as medidas usam os dados brutos)."""
    if not salvo:
        return registro(DESLIGADA)
    return registro(salvo.get("modo", DESLIGADA), salvo.get("ema_alpha", EMA_ALPHA),
                    salvo.get("kalman_q", KALMAN_Q), salvo.get("kalman_r", KALMAN_R),
                    salvo.get("kalman_p0", KALMAN_P0), salvo.get("nas_medidas", False))


def criar(reg):
    """Registro -> filtro de UMA série (um objeto novo, com estado próprio)."""
    modo = reg["modo"]
    if modo == EMA_MODO:
        return EMA(reg["ema_alpha"])
    if modo == KALMAN_MODO:
        return Kalman(reg["kalman_q"], reg["kalman_r"], reg["kalman_p0"])
    if modo == CASCATA:
        return Cascata(reg["ema_alpha"], reg["kalman_q"], reg["kalman_r"], reg["kalman_p0"])
    return Nenhum()


# =============================================================================
# Atraso
# =============================================================================
def ganho_kalman_estavel(q=KALMAN_Q, r=KALMAN_R):
    """Ganho K para onde o Kalman converge depois de alguns quadros.
    De P = (P + Q) R / (P + Q + R): P- = (Q + raiz(Q² + 4QR)) / 2 e K = P- / (P- + R)."""
    p_minus = (q + math.sqrt(q * q + 4.0 * q * r)) / 2.0
    return p_minus / (p_minus + r)


def atraso_quadros(reg):
    """Atraso médio (em quadros) que o filtro introduz num movimento lento.
    Um EMA de ganho a atrasa (1 - a) / a quadros; o Kalman, já estável, é um EMA
    de ganho K; na cascata os atrasos se somam."""
    total = 0.0
    if "ema_alpha" in reg:
        a = reg["ema_alpha"]
        total += (1.0 - a) / a
    if "kalman_q" in reg:
        k = ganho_kalman_estavel(reg["kalman_q"], reg["kalman_r"])
        total += (1.0 - k) / k
    return total


# =============================================================================
# Um filtro por articulação
# =============================================================================
class BancoFiltros:
    """Um filtro independente para cada articulação de cada dedo.

        banco = BancoFiltros(registro("ema_kalman"))
        suaves = banco.aplicar(angulos)    # {dedo: array} -> {dedo: array}
        banco.reset()                       # perda longa da mão, recalibração...
    """

    def __init__(self, reg=None):
        self.reg = reg if reg is not None else registro()
        self.modo = self.reg["modo"]
        self._filtros = {}

    @property
    def ligado(self):
        return self.modo != DESLIGADA

    def aplicar(self, angles):
        if not self.ligado:
            return angles
        out = {}
        for dedo, valores in angles.items():
            fs = self._filtros.get(dedo)
            if fs is None or len(fs) != len(valores):
                fs = self._filtros[dedo] = [criar(self.reg) for _ in valores]
            out[dedo] = np.array([f.update(v) for f, v in zip(fs, valores)])
        return out

    def reset(self):
        """Zera o estado: o próximo quadro passa direto e o filtro recomeça dele."""
        self._filtros = {}
