"""
Motor da avaliação (sem interface): recebe cada quadro da câmera e cuida de
preparação -> calibração -> avaliação, do estabilizador, da pausa, do relógio,
das medidas, da suavização dos ângulos e dos pontos gravados.

A tela de avaliação (app/telas/avaliacao.py) só mostra o que este motor
decide. As ferramentas e os testes usam o mesmo motor para analisar uma
gravação (analisar()), então a conta é sempre a mesma em todo lugar.

    av = Avaliador()
    for raw in quadros:
        passo = av.step(raw, agora)        # o que a tela precisa atualizar
    resultados = av.results(agora, "câmera 0")
"""

import datetime
import os
from collections import deque
from dataclasses import dataclass

import numpy as np

from app.dados.resultados import HAND_NAMES, session_results
from nucleo import capture
from nucleo import filtros
from nucleo import kinematics as kin
from nucleo import medidas
from nucleo.caminhos import POINTS_DIR, absoluto, relativo
from nucleo.stabilizer import HandStabilizer

HAND_FRAMES_TO_START = 15     # quadros seguidos com mão para sair da preparação
OPEN_HAND_WAIT_S = 5.0        # depois disso aceita a mão como está (ex.: contratura)
NOTICE_S = 2.5                # duração dos avisos curtos (ex.: "outra mão detectada")


@dataclass
class Passo:
    """O que aconteceu num quadro (para a tela se atualizar)."""
    state: str = None              # estado do estabilizador: ok, segurando, perdida, outra_mao, vista
    pose: dict = None              # quadro usado para desenhar a mão 3D (None = não redesenha)
    calibrou: bool = False         # a calibração terminou neste quadro


class Avaliador:
    def __init__(self, retest=False, frames=None, filtro=filtros.PADRAO, nas_medidas=False):
        """retest = é o reteste (mesma medição repetida logo depois);
        frames = pontos já gravados (o reteste continua a gravação da avaliação);
        filtro = modo da suavização ("desligada", "ema", "kalman", "ema_kalman") ou
        o registro salvo numa avaliação (filtros.registro, que já traz "nas_medidas");
        nas_medidas = a suavização entra também nas medidas (com um modo em texto).
        Sem nas_medidas, o filtro vale só para a exibição ao vivo (self.display e
        self.display_history) e a Session recebe os dados brutos."""
        self.retest = retest
        self.frames = [] if frames is None else frames
        self.started_at = datetime.datetime.now()
        self.phase = "preparacao"      # preparacao | calibracao | avaliacao
        self.hand_frames = 0
        self.calib = None
        self.calib_start = None
        self.calib_labels = []         # lados da mão vistos na calibração (votação)
        self.calibrated = False        # False | True | "aproximada"
        self.session = kin.Session()
        reg = filtro if isinstance(filtro, dict) else filtros.registro(filtro, nas_medidas=nas_medidas)
        self.filtro = filtros.BancoFiltros(reg)   # um filtro por articulação
        self.filter_measures = bool(reg.get("nas_medidas"))
        self._filter_hand = None       # lado usado no cálculo dos ângulos que o filtro recebeu
        # exibição ao vivo (valor "Agora", dica da mão 3D, gráfico): ângulos suavizados
        self.display = None            # {dedo: array} do último quadro medido, ou None sem mão
        self.display_history = deque() # (t, [TAM de cada dedo ou nan]), mesma janela da Session
        self.stab = HandStabilizer()   # lado da mão fixo + tolerância a falhas curtas
        self.hand_name = ""
        self.mirrored = True
        self.paused = False
        self.recalibrating = False
        self.prev_hand = None
        self.paused_total = 0.0        # tempo com o relógio parado (pausa, recalibração, relatório)
        self.clock_stopped_at = None
        self.message = None            # (título, subtítulo) do aviso sobre o palco, ou None
        self._message_until = None     # aviso curto: some sozinho
        # medidas da mão inteira e dados para a confiabilidade da sessão
        self.hand_meas = medidas.HandMeasures()
        self.tremor = medidas.TremorMeter()
        self.counts = {"frames": 0, "ok": 0}
        self.fps_samples, self.bright_samples, self.view_samples = [], [], []
        # registro do último quadro (exportação para pesquisa; não muda nenhuma conta):
        # lado usado nos ângulos, ângulos brutos e suavizados, descarte, vista e se o
        # quadro entrou nas medidas (e de qual Session: n_sessao muda com outra mão)
        self.n_sessao = 0
        self.quadro = {}

    # -------------------------------------------------------------- um quadro
    def step(self, raw, now):
        """Processa um quadro. Devolve um Passo com o que a tela precisa saber."""
        passo = Passo()
        self._record(raw)
        self.quadro = {"lado_angulos": self.stab.hand, "angulos": None, "suavizados": None,
                       "descartado": False, "vista_ruim": False, "estado": None, "medido": None,
                       "pausado": self.paused, "fase": self.frames[-1]["fase"].replace("reteste_", "")}
        if self._message_until is not None and now >= self._message_until:
            self.message, self._message_until = None, None

        # Quadros que não servem para medir viram "falha" no estabilizador:
        #  - ângulo impossível (erro do MediaPipe) -> como mão perdida
        #  - mão de lado (vista ruim para os ângulos) -> estado "vista"
        angles, valid, bad_kind = None, True, "perdida"
        angle_hand = self.stab.hand
        if raw["world"] is not None:
            angles = kin.joint_angles(raw["world"], angle_hand)       # com sinal
            if not kin.plausible(angles):
                valid = False
                if self.phase == "avaliacao" and not self.paused:
                    self.session.discarded += 1
            elif not kin.good_view(raw["world"], self.stab.hand):
                valid, bad_kind = False, "vista"
            self.quadro.update(angulos=angles, descartado=not kin.plausible(angles),
                               vista_ruim=bad_kind == "vista")
        use, state = self.stab.process(raw, valid, bad_kind)
        passo.state = state
        self.quadro["estado"] = state
        if state != "ok":
            angles = None
        else:
            if raw["handedness"]:
                self.calib_labels.append(raw["handedness"])
            hand = self.stab.hand
            if hand in ("Left", "Right"):
                self.hand_name = HAND_NAMES[hand]
                self.mirrored = hand == "Right"   # imagem espelhada: direita real = geometria esquerda
            passo.pose = use

        if self.paused:                       # imagem ao vivo, medições paradas
            self.tremor.interrupt()
            return passo
        smooth = self._smooth(state, angles, angle_hand)
        self.quadro["suavizados"] = smooth
        # calibração, tremor e medidas da mão inteira usam sempre os dados brutos; as
        # medidas por dedo também, a não ser com a suavização aplicada nas medidas;
        # a exibição ao vivo usa os ângulos suavizados
        self._feed_measures(raw, state, angles, now)
        if self.phase == "preparacao":
            self._preparation(state, now, passo)
        elif self.phase == "calibracao":
            self._calibration(state, angles, now, passo)
        else:
            self._evaluation(state, angles, smooth, now)
        return passo

    def _smooth(self, state, angles, hand):
        """Suavização (nucleo/filtros.py), logo depois do cálculo e do descarte.
        Só quadros "ok" atualizam o filtro ("segurando" não mexe nele); perda longa
        da mão, outra mão, mão de lado ou troca do lado usado nos ângulos o zeram."""
        if state == "ok":
            if hand != self._filter_hand:
                self.filtro.reset()
                self._filter_hand = hand
            return self.filtro.aplicar(angles)
        if state != "segurando":
            self.filtro.reset()
        return None

    def _record(self, raw):
        phase = "pausa" if self.paused else "recalibracao" if self.recalibrating else self.phase
        frame = {k: raw.get(k) for k in capture.FRAME_KEYS}
        frame["fase"] = ("reteste_" if self.retest else "") + phase
        self.frames.append(frame)

    def _feed_measures(self, raw, state, angles, now):
        """Medidas da mão inteira, tremor (também na calibração, com a mão parada)
        e contagem de quadros para a confiabilidade (só durante a avaliação)."""
        if state == "ok" and self.phase in ("calibracao", "avaliacao"):
            self.tremor.add(now, raw["world"], angles)
        elif state != "segurando":
            self.tremor.interrupt()
        if self.phase != "avaliacao" or self.recalibrating:
            return
        self.counts["frames"] += 1
        if raw.get("fps") is not None:
            self.fps_samples.append(raw["fps"])
        if raw.get("brightness") is not None:
            self.bright_samples.append(raw["brightness"])
        if state == "ok":
            self.counts["ok"] += 1
            self.hand_meas.add(raw["world"], angles)
            self.view_samples.append(kin.view_angle(raw["world"], self.stab.hand))

    # ------------------------------------------------------------------ fases
    def _preparation(self, state, now, passo):
        if state == "ok":
            self.hand_frames += 1
        elif state != "segurando":
            self.hand_frames = 0
        if self.recalibrating:
            self.message = ("Recalibrando", "Os dados da sessão continuam guardados. "
                            "Mostre a mão para a câmera, com a palma voltada para ela.")
        elif self.retest:
            self.message = ("Reteste: tire a mão e mostre de novo",
                            "Reposicione a mão como na avaliação: palma para a câmera, "
                            "a cerca de 50 cm. O sistema calibra outra vez.")
        else:
            self.message = ("Mostre a mão para a câmera",
                            "Palma voltada para a câmera, a cerca de 50 cm, com boa luz.")
        if self.hand_frames >= HAND_FRAMES_TO_START:
            self.phase = "calibracao"
            self.calib = kin.Calibration()
            self.calib_start = now
            self.calib_labels = []

    def _calibration(self, state, angles, now, passo):
        if state in ("perdida", "outra_mao"):
            self.phase, self.hand_frames = "preparacao", 0
            return
        if state == "vista":                  # mão de lado: recomeça a contagem
            self.calib.reset()
            self.message = ("Vire a palma para a câmera", "Com a mão de lado a câmera não mede bem os dedos.")
            return
        if state == "segurando":              # falha curta: só espera
            return
        waited = now - self.calib_start
        # mão aberta: pede, mas não trava quem não consegue abrir toda (ex.: contratura)
        if not kin.is_open_hand(angles) and waited < OPEN_HAND_WAIT_S:
            self.calib.reset()
            self.message = ("Abra a mão o máximo que conseguir",
                            "Dedos esticados e afastados, palma voltada para a câmera.")
            return
        self.calib.add(angles)
        timed_out = waited > kin.CALIBRATION_TIMEOUT_S and self.calib.best
        if not self.calib.is_still() and not timed_out:
            self.calib.reset()
            self.message = ("Mantenha a mão parada", "Só por 2 segundos.")
            return
        # contagem regressiva 3-2-1 (número: a tela mostra grande)
        self.message = ("Mantenha a mão aberta e parada", max(3 - int(self.calib.progress * 3), 1))
        if self.calib.done() or timed_out:
            self._finish_calibration(now)
            passo.calibrou = True

    def _finish_calibration(self, now):
        sens = self.calib.sensitivity()       # tempo limite: usa o trecho mais calmo
        self.calibrated = "aproximada" if self.calib.approximate else True
        self.stab.lock(self.calib_labels)     # lado da mão fixo daqui em diante
        self.phase = "avaliacao"
        notice = None
        if self.recalibrating:
            if self.prev_hand and self.stab.locked_hand != self.prev_hand:
                # outra mão: não mistura os dados das duas
                self._new_session(sens, now)
                self.paused_total, self.clock_stopped_at = 0.0, None
                notice = "Outra mão detectada: nova sessão iniciada"
            else:
                for f, tr in self.session.trackers.items():
                    tr.sens = sens[f]
                self.start_clock(now)
            self.recalibrating = False
        else:
            self._new_session(sens, now)
            if self.retest:
                notice = "Reteste: abra e feche a mão algumas vezes, o máximo que conseguir"
        self.message = (notice, None) if notice else None
        self._message_until = now + NOTICE_S if notice else None

    def _evaluation(self, state, angles, smooth, now):
        if state == "ok":
            self._update_session(smooth if self.filter_measures else angles, smooth, now)
        elif state in ("perdida", "outra_mao", "vista"):
            self._update_session(None, None, now)   # perda longa: aí sim recomeça o detector
        # "segurando": nada muda (não zera repetições em andamento)

    def _update_session(self, measured, shown, now):
        """Um caminho só: a Session recebe os ângulos das medidas (dados brutos, ou
        suavizados com nas_medidas) e a exibição recebe os suavizados, no mesmo quadro."""
        self.session.update(measured, now)
        self.quadro["medido"] = measured
        self.display = shown
        tams = [np.nan if shown is None else float(shown[f].sum()) for f in kin.FINGERS]
        self.display_history.append((now, tams))
        while self.display_history and now - self.display_history[0][0] > kin.Session.HISTORY_S:
            self.display_history.popleft()

    def _new_session(self, sens, now):
        self.session = kin.Session(sens, start_time=now)
        self.n_sessao += 1
        self.display, self.display_history = None, deque()

    # ----------------------------------------------------- pausa e relógio
    def toggle_pause(self, now):
        self.paused = not self.paused
        if self.paused:
            self.stop_clock(now)
            self._update_session(None, None, now)   # fecha o "vale" atual: não junta antes e depois
            self.filtro.reset()               # idem para a suavização
            self.message = ("Sessão pausada", "As medições estão paradas. Clique em Retomar para continuar.")
        else:
            self.start_clock(now)
            self.message = None
        self._message_until = None

    def recalibrate(self, now):
        self.recalibrating = True
        self.prev_hand = self.stab.locked_hand
        self.stab.unlock()
        self.filtro.reset()
        self.stop_clock(now)
        self.phase, self.hand_frames = "preparacao", 0

    def stop_clock(self, now):
        if self.clock_stopped_at is None:
            self.clock_stopped_at = now

    def start_clock(self, now):
        if self.clock_stopped_at is not None:
            self.paused_total += now - self.clock_stopped_at
            self.clock_stopped_at = None

    def elapsed(self, now):
        """Segundos de avaliação, sem as pausas."""
        if self.phase != "avaliacao" and not self.recalibrating:
            return 0
        end = self.clock_stopped_at if self.clock_stopped_at is not None else now
        return int(max(0.0, end - self.session.start_time - self.paused_total))

    # ------------------------------------------------------------ resultados
    def reliability(self, now):
        median = lambda v: float(np.median(v)) if v else None
        reps = max(len(tr.reps) for tr in self.session.trackers.values())
        return medidas.session_reliability(
            self.counts["frames"], self.counts["ok"], fps=median(self.fps_samples),
            brightness=median(self.bright_samples), view=median(self.view_samples), reps=reps,
            duration_s=self.elapsed(now))

    def hand_info(self, now):
        """Medidas da mão inteira para o painel (aba Mão e polpa-palma na Amplitude)."""
        return {"tpd": self.hand_meas.tpd_min, "spread": self.hand_meas.spread_max,
                "thumb": self.hand_meas.thumb_max, "tremor": self.tremor.result(),
                "reliability": self.reliability(now)}

    def points_path(self):
        """Caminho (relativo à pasta do projeto) do arquivo de pontos desta avaliação."""
        stamp = self.started_at.strftime("%Y%m%d_%H%M%S")
        return relativo(os.path.join(POINTS_DIR, f"sessao_{stamp}.npz"))

    def write_points(self, rel_path, settings=None):
        """Grava os pontos da mão de todos os quadros (avaliação e reteste)."""
        if self.frames:
            capture.save_recording(absoluto(rel_path), self.frames, settings)

    def results(self, now, source):
        return session_results(self.session, start=self.started_at, duration_s=self.elapsed(now),
                               hand=self.stab.locked_hand, calibrated=self.calibrated, source=source,
                               hand_measures=self.hand_meas, tremor=self.tremor,
                               reliability=self.reliability(now),
                               points=None if self.retest else self.points_path(),
                               smoothing=self.filtro.reg)


def analisar(rows, retest=False, filtro=filtros.PADRAO, por_quadro=None):
    """Passa quadros gravados (capture.load_recording) pelo motor, como a tela
    faria ao vivo. Repete a pausa e a recalibração onde a fase gravada indica.
    filtro = modo ou registro da suavização (o recálculo usa o salvo na avaliação,
    que diz se o filtro entra nas medidas; com um modo em texto, só na exibição).
    por_quadro(raw, passo, av), se dado, é chamado depois de cada quadro (av.quadro tem o
    registro do quadro; usado na exportação para pesquisa).
    Devolve o Avaliador no fim (use .results(rows[-1]["t"], ...))."""
    av = Avaliador(retest=retest, filtro=filtro)
    previous = ""
    for raw in rows:
        phase = raw.get("fase", "").replace("reteste_", "")
        if (phase == "pausa") != av.paused:
            av.toggle_pause(raw["t"])
        if phase == "recalibracao" and previous != "recalibracao":
            av.recalibrate(raw["t"])
        previous = phase
        passo = av.step(raw, raw["t"])
        if por_quadro is not None:
            por_quadro(raw, passo, av)
    return av
