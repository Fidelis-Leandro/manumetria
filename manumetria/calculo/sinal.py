"""
Sinal de um trecho de movimento: reamostragem em grade uniforme, derivada
(velocidade), suavidade (SPARC, Balasubramanian et al. 2015), norma das velocidades
articulares e tendência ao longo das repetições. Numpy puro, sem interface.
"""

import numpy as np

# Frequência (Hz) da grade uniforme em que cada trecho de movimento é reamostrado
# antes da derivada e do SPARC.
SIGNAL_FS = 30.0
# Tendência (fadiga) só com 6 repetições ou mais.
TREND_MIN_REPS = 6


# =============================================================================
# Sinal: velocidade e suavidade de um trecho de movimento
# =============================================================================
def uniform(t, x, fs=SIGNAL_FS):
    """Amostras em intervalos irregulares -> grade uniforme (interpolação linear)."""
    t, x = np.asarray(t, dtype=float), np.asarray(x, dtype=float)
    n = int(np.floor((t[-1] - t[0]) * fs)) + 1
    tu = t[0] + np.arange(n) / fs
    return tu, np.interp(tu, t, x)


def derivative(x, fs=SIGNAL_FS):
    """Derivada por mínimos quadrados em 5 pontos (Savitzky-Golay, 1ª ordem).
    Só entra no CÁLCULO da velocidade (não muda os ângulos exibidos). Com ruído de
    desvio padrão σ por quadro, a diferença entre quadros vizinhos tem desvio
    σ·√2·fs (σ = 1° a 30 Hz -> ~42°/s); a de 5 pontos, σ·fs/√10 (~9°/s)."""
    x = np.asarray(x, dtype=float)
    d = np.gradient(x) * fs
    if len(x) >= 5:
        d[2:-2] = (-2 * x[:-4] - x[1:-3] + x[3:-1] + 2 * x[4:]) / 10.0 * fs
    return d


def sparc(speed, fs=SIGNAL_FS, pad_level=4, fc=10.0, amp_th=0.05):
    """Suavidade do movimento: comprimento do arco espectral (SPARC,
    Balasubramanian et al. 2015). Mais perto de zero = mais suave; um movimento
    em forma de sino dá cerca de -1,5, e trancos o deixam mais negativo."""
    speed = np.asarray(speed, dtype=float)
    if len(speed) < 6 or speed.max() <= 0:
        return None
    nfft = int(2 ** (np.ceil(np.log2(len(speed))) + pad_level))
    f = np.arange(nfft) * fs / nfft
    mag = np.abs(np.fft.fft(speed, nfft))
    mag = mag / mag.max()
    keep = f <= fc
    f, mag = f[keep], mag[keep]
    above = np.nonzero(mag >= amp_th)[0]
    f, mag = f[above[0]:above[-1] + 1], mag[above[0]:above[-1] + 1]
    if len(f) < 2:
        return None
    return float(-np.sum(np.sqrt((np.diff(f) / (f[-1] - f[0])) ** 2 + np.diff(mag) ** 2)))


def trend(values):
    """Variação relativa do início ao fim pela reta de regressão (ex.: -0,12 =
    caiu 12% ao longo das repetições). None com poucos valores."""
    v = np.asarray([x for x in values if x is not None], dtype=float)
    if len(v) < TREND_MIN_REPS:
        return None
    a, b = np.polyfit(np.arange(len(v)), v, 1)
    first, last = b, a * (len(v) - 1) + b
    return float((last - first) / first) if first > 0 else None


def joint_speed(joints, fs=SIGNAL_FS):
    """Norma das velocidades articulares (°/s): raiz da soma dos quadrados da derivada de
    cada articulação (colunas de `joints`, em grade uniforme). Entrada do SPARC, como
    recomendam Balasubramanian et al. (2015): a derivada do TAM se anula quando uma
    articulação flete e outra estende, a norma não."""
    J = np.asarray(joints, dtype=float)
    return np.sqrt(sum(derivative(J[:, k], fs) ** 2 for k in range(J.shape[1])))
