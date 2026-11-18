"""Qualidade da captura nos últimos 2 s (luz, quadros por segundo e detecção da mão),
mostrada no topo da tela de avaliação. Sem interface."""

import numpy as np


class CaptureQuality:
    """Qualidade da captura nos últimos 2 s: fps, luz e quanto a mão é detectada.
    Vira um texto curto no topo, com o motivo quando não está boa."""

    WINDOW_S = 2.0

    def __init__(self):
        self.samples = []          # (t, mão presente, brilho)

    def add(self, raw):
        """Acrescenta um quadro à janela dos últimos WINDOW_S segundos."""
        t = raw["t"]
        self.samples.append((t, raw["world"] is not None, raw.get("brightness")))
        while self.samples and t - self.samples[0][0] > self.WINDOW_S:
            self.samples.pop(0)

    def evaluate(self, judge_detection=True):
        """judge_detection=False antes da avaliação: a mão ainda nem foi
        mostrada, então "mão sumindo" seria um falso alarme."""
        if len(self.samples) < 5:
            return "boa", "", ""
        span = self.samples[-1][0] - self.samples[0][0]
        fps = (len(self.samples) - 1) / span if span > 0 else 0
        detect = np.mean([s[1] for s in self.samples])
        lights = [s[2] for s in self.samples if s[2] is not None]
        light = np.mean(lights) if lights else None
        problems = []                                  # (gravidade, texto)
        if light is not None and light < 50:
            problems.append((2, "pouca luz"))
        elif light is not None and light < 80:
            problems.append((1, "luz fraca"))
        if fps < 15:
            problems.append((2, "imagem lenta (mais luz ajuda)"))
        elif fps < 22:
            problems.append((1, "imagem um pouco lenta"))
        if judge_detection and detect < 0.6:
            problems.append((2, "mão sumindo com frequência"))
        elif judge_detection and detect < 0.85:
            problems.append((1, "mão some às vezes"))
        details = (f"{fps:.0f} quadros por segundo · mão detectada em {detect * 100:.0f}% dos quadros"
                   + (f" · brilho {light:.0f}/255" if light is not None else ""))
        if not problems:
            return "boa", f"Captura boa · {fps:.0f} fps", details
        severity = max(p[0] for p in problems)
        worst = [p[1] for p in problems if p[0] == severity]
        level = "ruim" if severity == 2 else "regular"
        return level, f"Captura {level}: {', '.join(worst)}", details
