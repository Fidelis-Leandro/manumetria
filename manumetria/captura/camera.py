"""
Webcam + MediaPipe Hand Landmarker (numa thread separada) e o desenho do esqueleto.

Toda fonte de quadros entrega o mesmo dicionário "raw" via latest():
CameraSource (esta), gravacao.ReplaySource (arquivo de pontos) e
simulacao.DemoHand (mão simulada).

Formato "raw":
  t           instante (s)                world   (21,3) metros ou None (sem mão)
  img         (21,2) 0..1 na imagem       confidence  0..1
  handedness  "Left"/"Right" (mão REAL)   aspect  largura/altura
  frame       imagem RGB ou None          fps / brightness / inference_ms  (qualidade)
"""

import os
import sys
import threading
import time
import urllib.request

import numpy as np

from manumetria.calculo.geometria import FINGERTIPS, HAND_CONNECTIONS
from manumetria.caminhos import MODEL_PATH

# A API Tasks do MediaPipe precisa de um arquivo de modelo (.task), baixado na instalação
# ou na primeira execução (MODEL_PATH, em manumetria/recursos/; fica fora do Git).
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/latest/hand_landmarker.task")

# Limiares do MediaPipe (0..1). Mais baixos = insiste mais em manter a mão,
# com mais risco de "achar" mão onde não tem. Padrão do MediaPipe = 0.5.
DETECTION_CONFIDENCE = 0.5
PRESENCE_CONFIDENCE = 0.5
TRACKING_CONFIDENCE = 0.5

def ensure_model():
    """Baixa o modelo do MediaPipe se ainda não estiver na pasta (o Instalar sistema.bat
    chama na instalação; a câmera chama de novo por garantia)."""
    if not os.path.exists(MODEL_PATH):
        print(f"Baixando modelo do MediaPipe para {MODEL_PATH} ...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)


class _Stats:
    """fps medido e média móvel de brilho / tempo de inferência."""

    def __init__(self):
        self.last_t = None
        self.fps = 0.0
        self.brightness = 0.0
        self.inference_ms = 0.0

    def update(self, t, brightness, inference_ms):
        if self.last_t is not None and t > self.last_t:
            inst = 1.0 / (t - self.last_t)
            self.fps = inst if self.fps == 0 else 0.9 * self.fps + 0.1 * inst
        self.last_t = t
        a = 0.1 if self.brightness else 1.0
        self.brightness += a * (brightness - self.brightness)
        self.inference_ms += a * (inference_ms - self.inference_ms)


# =============================================================================
# Webcam
# =============================================================================
class CameraSource:
    """Webcam + MediaPipe numa thread: latest() devolve o último "raw" (formato no
    início do módulo) e stop() fecha tudo. settings = limiares e resolução usados."""

    def __init__(self, cam_index=0, width=640, height=480, detection=DETECTION_CONFIDENCE,
                 presence=PRESENCE_CONFIDENCE, tracking=TRACKING_CONFIDENCE):
        import cv2
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
        self.cv2, self.mp = cv2, mp

        ensure_model()

        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        self.cap = cv2.VideoCapture(cam_index, backend)
        if not self.cap.isOpened():
            raise RuntimeError(f"não consegui abrir a câmera {cam_index}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        self.settings = {"detection": detection, "presence": presence, "tracking": tracking,
                         "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                         "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}
        self.landmarker = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.VIDEO, num_hands=1,
            min_hand_detection_confidence=detection,
            min_hand_presence_confidence=presence,
            min_tracking_confidence=tracking))

        self.stats = _Stats()
        self._lock = threading.Lock()
        self._raw, self._seq, self._seq_read = None, 0, 0
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        cv2 = self.cv2
        last_ts = 0
        while self._running:
            ok, bgr = self.cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            bgr = cv2.flip(bgr, 1)                    # espelho (modo "selfie")
            now = time.monotonic()
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            ts = max(int(now * 1000), last_ts + 1)    # modo VIDEO: tempo estritamente crescente
            last_ts = ts
            t0 = time.perf_counter()
            result = self.landmarker.detect_for_video(
                self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb), ts)
            inference_ms = 1000 * (time.perf_counter() - t0)
            self.stats.update(now, float(rgb[::8, ::8].mean()), inference_ms)
            raw = result_to_raw(result, now, rgb)
            raw.update(fps=self.stats.fps, brightness=self.stats.brightness,
                       inference_ms=self.stats.inference_ms)
            if raw["world"] is not None:
                draw_skeleton(cv2, rgb, raw["img"])
            with self._lock:
                self._raw = raw
                self._seq += 1

    def latest(self):
        """Último resultado, ou None se nenhum quadro chegou desde a última chamada."""
        with self._lock:
            if self._seq == self._seq_read:
                return None
            self._seq_read = self._seq
            return self._raw

    def stop(self):
        """Para a thread e libera a câmera e o MediaPipe."""
        self._running = False
        self._thread.join(timeout=1.0)
        self.cap.release()
        self.landmarker.close()


def result_to_raw(result, now, rgb):
    """Resultado do MediaPipe -> raw. A imagem foi espelhada antes da detecção,
    e o rótulo descreve a mão como ela aparece na imagem: a mão real é a oposta."""
    h, w = rgb.shape[:2]
    raw = {"t": now, "world": None, "img": None, "confidence": 0.0, "handedness": None,
           "aspect": w / h, "frame": rgb}
    if result.hand_landmarks:
        category = result.handedness[0][0]
        raw.update(
            world=np.array([[p.x, p.y, p.z] for p in result.hand_world_landmarks[0]]),
            img=np.array([[p.x, p.y] for p in result.hand_landmarks[0]]),
            confidence=float(category.score),
            handedness={"Left": "Right", "Right": "Left"}.get(category.category_name))
    return raw


def draw_skeleton(cv2, rgb, img):
    """Desenha os 21 pontos e as ligações da mão na imagem RGB (na própria imagem);
    pontas dos dedos em outra cor. img = pontos (21,2) de 0 a 1."""
    h, w = rgb.shape[:2]
    pts = [(int(x * w), int(y * h)) for x, y in img]
    for i, j in HAND_CONNECTIONS:
        cv2.line(rgb, pts[i], pts[j], (150, 165, 180), 2, cv2.LINE_AA)
    for k, p in enumerate(pts):
        color = (38, 198, 218) if k in FINGERTIPS else (0, 230, 118)
        cv2.circle(rgb, p, 5, color, -1, cv2.LINE_AA)
