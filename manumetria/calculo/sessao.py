"""
Calibração e sessão.

  - Calibration: com a mão aberta e parada, mede quanto cada dedo "treme" e daí a
    sensibilidade (o menor movimento contado). Recebe sempre os dados brutos.
  - Session: um FingerTracker por dedo, o histórico do TAM (gráfico ao vivo) e a
    independência de cada repetição (quanto os outros dedos se moveram junto).

Numpy puro, sem interface.
"""

from collections import deque

import numpy as np

from manumetria.calculo.goniometria import FINGERS
from manumetria.calculo.repeticoes import FingerTracker, SENS_DEFAULT, SENS_FACTOR, SENS_MAX, SENS_MIN

CALIBRATION_FRAMES = 60       # ~2 s a 30 fps (45 subestimava o tremor)
STILL_WINDOW = 15             # frames usados para checar se a mão está parada
# Desvio padrão do TAM (°) acima disso = mão se mexendo. Na gravação de
# referência (boa luz), o trecho parado mais calmo teve desvio de 0,5-0,9° por
# dedo (tests/test_auditoria.py). Um limite folgado (12°) aceitava a mão em
# movimento como "parada" e inflava a sensibilidade; se não ficar parada, o
# tempo limite usa o trecho mais calmo.
STILL_MAX_STD = 4.0
CALIBRATION_TIMEOUT_S = 10.0  # sem 2 s parados nesse tempo -> usa o trecho mais calmo
# Mão "aberta" para calibrar: mediana do TAM dos 4 dedos longos abaixo disso.
# Com a mão aberta o MediaPipe raramente dá 0° (na gravação de referência, o
# trecho parado mais calmo teve TAM mediano de ~30°).
OPEN_HAND_MAX_TAM = 90.0


def is_open_hand(angles):
    """Mão aberta para calibrar: mediana do TAM dos 4 dedos longos abaixo de
    OPEN_HAND_MAX_TAM."""
    return float(np.median([angles[f].sum() for f in FINGERS[1:]])) < OPEN_HAND_MAX_TAM


# =============================================================================
# Calibração (mão aberta e parada)
# =============================================================================
class Calibration:
    """Calibração com a mão aberta e parada: guarda o TAM de cada dedo a cada quadro
    e o trecho mais calmo já visto; sensitivity() dá a sensibilidade por dedo."""

    def __init__(self, frames=CALIBRATION_FRAMES):
        self.frames = frames
        self.best = None           # {dedo: desvio} do trecho mais calmo já visto
        self.approximate = False   # True se terminou pelo tempo limite
        self.reset()

    def reset(self):
        """Recomeça a contagem (a mão mexeu). O trecho mais calmo é mantido."""
        self.tams = {f: [] for f in FINGERS}

    def add(self, angles):
        """Acrescenta um quadro e atualiza o trecho mais calmo (janela de STILL_WINDOW
        quadros)."""
        for f in FINGERS:
            self.tams[f].append(float(angles[f].sum()))
        if self.count >= STILL_WINDOW:
            window = {f: float(np.std(v[-STILL_WINDOW:])) for f, v in self.tams.items()}
            if self.best is None or max(window.values()) < max(self.best.values()):
                self.best = window

    @property
    def count(self):
        """Quadros acumulados desde o último reset()."""
        return len(self.tams["index"])

    @property
    def progress(self):
        """Fração da calibração já feita (0..1)."""
        return min(1.0, self.count / self.frames)

    def is_still(self):
        """A mão está parada? (desvio padrão recente do TAM de cada dedo)."""
        if self.count < STILL_WINDOW:
            return True
        return all(np.std(v[-STILL_WINDOW:]) < STILL_MAX_STD for v in self.tams.values())

    def done(self):
        """True quando a calibração juntou os quadros necessários."""
        return self.count >= self.frames

    def sensitivity(self):
        """Menor movimento contado por dedo = 3x o tremor medido parado.
        Se a calibração não completou (tempo limite), usa o trecho mais calmo."""
        if self.done():
            stds = {f: float(np.std(v)) for f, v in self.tams.items()}
        else:
            self.approximate = True
            stds = self.best or {f: SENS_DEFAULT / SENS_FACTOR for f in FINGERS}
        return {f: float(np.clip(SENS_FACTOR * s, SENS_MIN, SENS_MAX)) for f, s in stds.items()}


# =============================================================================
# Sessão
# =============================================================================
class Session:
    """Sessão de medição: um FingerTracker por dedo, o histórico do TAM dos últimos
    HISTORY_S segundos e os quadros descartados; update() a cada quadro."""

    HISTORY_S = 20.0           # janela do gráfico de TAM (e da independência)

    def __init__(self, sensitivity=None, start_time=0.0):
        sensitivity = sensitivity or {}
        self.trackers = {f: FingerTracker(f, sensitivity.get(f, SENS_DEFAULT)) for f in FINGERS}
        self.start_time = start_time
        self.history = deque()     # (t, [TAM de cada dedo ou nan])
        self.discarded = 0         # frames descartados por ângulo impossível

    def update(self, angles, t):
        """angles = joint_angles(...) ou None (sem mão neste frame)."""
        tams = [np.nan if angles is None else float(angles[f].sum()) for f in FINGERS]
        self.history.append((t, tams))
        while self.history and t - self.history[0][0] > self.HISTORY_S:
            self.history.popleft()
        for f, tr in self.trackers.items():
            rep = tr.update(None if angles is None else angles[f], t)
            if rep is not None:
                self._annotate(f, rep)

    def _annotate(self, finger, rep):
        """Independência: quanto os OUTROS dedos se moveram durante esta
        repetição. Do movimento de cada um desconta-se a sensibilidade dele
        (a faixa que o próprio tremor ocupa), para o tremor não parecer movimento.
        Numerador e denominador no mesmo sinal e na mesma janela: o TAM dos dados
        brutos do vale ao pico desta repetição (a amplitude dela é o pico menos o
        vale nessa janela)."""
        if rep.t_start is None:
            return
        window = []
        if rep.t_raw_start is not None:
            window = [vals for tt, vals in self.history if rep.t_raw_start <= tt <= rep.t_raw_peak]
        if len(window) < 3:                  # sem os extremos nos dados brutos: janela do detector
            window = [vals for tt, vals in self.history if rep.t_start - 0.2 <= tt <= rep.t_end]
        if len(window) < 3:
            return
        V = np.array(window)
        coupling = {}
        for i, g in enumerate(FINGERS):
            if g == finger:
                continue
            col = V[:, i][~np.isnan(V[:, i])]
            if len(col) < 3:
                continue
            moved = max(0.0, float(col.max() - col.min()) - self.trackers[g].sens)
            coupling[g] = min(1.5, moved / max(rep.amplitude, 1e-6))
        rep.coupling = coupling
        if coupling:
            rep.independence = float(np.clip(1.0 - np.mean(list(coupling.values())), 0.0, 1.0))
