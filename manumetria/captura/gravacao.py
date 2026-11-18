"""
Arquivos de pontos da mão (.npz, sem vídeo): gravar, ler e reproduzir.

É o que fica em dados_locais/pontos/ para cada avaliação salva. A gravação é
atômica: vai para um arquivo temporário (.gravando) que só no fim troca de nome.
"""

import os
import time

import numpy as np

from manumetria.captura.camera import draw_skeleton

FRAME_KEYS = ("t", "world", "img", "confidence", "handedness", "aspect", "fps", "brightness",
              "inference_ms")


def save_recording(path, rows, settings=None):
    """rows = raws (só as chaves de FRAME_KEYS e "fase") -> .npz compactado."""
    n = len(rows)
    world = np.full((n, 21, 3), np.nan)
    img = np.full((n, 21, 2), np.nan)
    for i, r in enumerate(rows):
        if r["world"] is not None:
            world[i], img[i] = r["world"], r["img"]
    num = lambda k: np.array([np.nan if r.get(k) is None else r[k] for r in rows], dtype=float)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    # grava num arquivo temporário e só então troca pelo definitivo: se o programa fechar no
    # meio, não fica um .npz pela metade com o nome da avaliação
    tmp = path + ".gravando"
    try:
        with open(tmp, "wb") as fh:
            np.savez_compressed(   # pontos em float32: precisão de micrômetros, metade do tamanho
                fh, t=num("t"), world=world.astype(np.float32), img=img.astype(np.float32),
                confidence=num("confidence"), handedness=np.array([r["handedness"] or "" for r in rows]),
                aspect=num("aspect"), fps=num("fps"), brightness=num("brightness"),
                inference_ms=num("inference_ms"), fase=np.array([r.get("fase") or "" for r in rows]),
                settings=np.array(repr(settings or {})))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def load_recording(path):
    """Arquivo de pontos -> lista de raws (sem imagem), na ordem em que aconteceram."""
    with np.load(path) as f:
        d = {k: f[k] for k in f.files}   # lê cada coluna uma vez: f[k] descompacta o arquivo a cada acesso
    phases = d.get("fase")               # arquivo gravado sem a fase: fica vazia
    # valor ausente foi gravado como NaN (ex.: a simulação não mede brilho): volta a ser None
    num = lambda k, i: None if np.isnan(d[k][i]) else float(d[k][i])
    rows = []
    for i in range(len(d["t"])):
        present = not np.isnan(d["world"][i, 0, 0])
        rows.append({
            "t": float(d["t"][i]),
            "world": d["world"][i] if present else None,
            "img": d["img"][i] if present else None,
            "confidence": num("confidence", i),
            "handedness": str(d["handedness"][i]) or None,
            "aspect": num("aspect", i),
            "fps": num("fps", i), "brightness": num("brightness", i),
            "inference_ms": num("inference_ms", i), "frame": None,
            "fase": "" if phases is None else str(phases[i]),
        })
    return rows


class ReplaySource:
    """Reproduz um arquivo de pontos respeitando os tempos originais (para a
    interface se comportar como na sessão gravada). Desenha o esqueleto numa
    imagem escura no lugar do vídeo."""

    def __init__(self, path, loop=True):
        self.rows = load_recording(path)
        if not self.rows:
            raise ValueError(f"gravação vazia: {path}")
        self.loop = loop
        self.t0 = time.monotonic()
        self.i = -1
        try:
            import cv2
            self.cv2 = cv2
        except ImportError:
            self.cv2 = None

    def latest(self):
        """Próximo quadro quando chega a hora dele (tempo da gravação), ou None; com
        loop, recomeça do início ao chegar ao fim."""
        elapsed = time.monotonic() - self.t0
        start = self.rows[0]["t"]
        j = self.i
        while j + 1 < len(self.rows) and self.rows[j + 1]["t"] - start <= elapsed:
            j += 1
        if j == self.i:
            if self.loop and j == len(self.rows) - 1:
                self.t0, self.i = time.monotonic(), -1     # recomeça
            return None
        self.i = j
        raw = dict(self.rows[j])
        raw["t"] = time.monotonic()
        raw["frame"] = self._draw(raw)
        return raw

    def _draw(self, raw):
        if self.cv2 is None:
            return None
        frame = np.full((480, 640, 3), 38, np.uint8)
        # embaixo: no alto, a legenda da miniatura cobriria o texto
        self.cv2.putText(frame, "GRAVACAO", (20, 460), self.cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                         (120, 130, 140), 2, self.cv2.LINE_AA)
        if raw["img"] is not None:
            draw_skeleton(self.cv2, frame, raw["img"])
        return frame
