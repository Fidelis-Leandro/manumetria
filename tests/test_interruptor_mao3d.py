"""
Interruptor da mão 3D (manumetria/interface/opcoes.py, MAO_3D_ATIVA): a tela de avaliação
aberta com a mão simulada (--sim) nos dois estados.

  - False (padrão): só a câmera no palco, sem os botões "Câmera / Modelo 3D", sem a legenda
    e a dica "arraste para girar", dicas sem a mão 3D e SEM importar o OpenGL nem o mao3d;
  - True: a mão 3D volta (miniatura, botões, legenda, dica).

O valor original é restaurado no fim.

    .venv\\Scripts\\python.exe tests\\test_interruptor_mao3d.py
"""

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PyQt5 import QtWidgets  # noqa: E402

from manumetria.calculo import goniometria  # noqa: E402
from manumetria.captura.simulacao import DemoHand  # noqa: E402
from manumetria.interface.tema import GRADE_COLOR  # noqa: E402
from manumetria.interface import opcoes  # noqa: E402
from manumetria.interface.telas.avaliacao import EvaluationScreen  # noqa: E402

failures = []
OPENGL = ("OpenGL", "pyqtgraph.opengl", "manumetria.interface.componentes.mao3d")


def check(name, ok, detail=""):
    print(f"[{'ok' if ok else 'FALHOU'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def open_screen(app):
    """Tela de avaliação com a mão simulada, rodando ~3 s de quadros."""
    scr = EvaluationScreen(lambda: (DemoHand(), "simulação"))
    scr.resize(1280, 760)
    scr.show()
    scr.start({"identificacao": "teste"})
    t_end = time.monotonic() + 3.0
    while time.monotonic() < t_end:
        app.processEvents()
        time.sleep(0.01)
    return scr


def tips_text(scr):
    return " ".join(f"{title} {body}" for _w, title, body in scr._tips())


original = opcoes.MAO_3D_ATIVA
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
try:
    # ------------------------------------------------------------ desligada
    opcoes.MAO_3D_ATIVA = False
    scr = open_screen(app)
    check("desligada: sem mão 3D na tela", scr.hand3d is None and scr.stage.gl is None)
    check("desligada: câmera ocupa o palco inteiro", scr.stage.cam.geometry() == scr.stage.rect(),
          f"{scr.stage.cam.geometry()} x {scr.stage.rect()}")
    check("desligada: câmera recebeu imagem", scr.stage._qimage is not None)
    check("desligada: sem miniatura e sem legenda",
          scr.stage.gl_frame is None and scr.stage.mini_caption is None and scr.stage.legend is None)
    tb = scr.toolbar
    check("desligada: sem botões Câmera / Modelo 3D, dica e Centralizar",
          tb.btn_3d is None and tb.btn_cam is None and tb.hint is None and tb.btn_center is None)
    labels = [b.text() for b in tb.findChildren(QtWidgets.QAbstractButton)]
    check("desligada: barra só com Tela cheia e Dicas", sorted(labels) == ["Dicas", "Tela cheia"], str(labels))
    texts = tips_text(scr).lower()
    check("desligada: dicas sem mão 3D nem miniatura", "3d" not in texts and "miniatura" not in texts)
    loaded = [m for m in OPENGL if m in sys.modules]
    check("desligada: OpenGL e mao3d não importados", not loaded, str(loaded))
    scr._refresh_panel(force=True)
    trackers = scr.av.session.trackers
    check("desligada: cartões dos dedos com a cor do % do normal",
          all(c.color == GRADE_COLOR[goniometria.grade(trackers[f].percent_normal())]
              for f, c in scr.chips.items()))
    scr.toggle_expanded()
    app.processEvents()
    scr.toggle_expanded()
    scr.stop()
    scr.deleteLater()
    app.processEvents()

    # ------------------------------------------------------------- ligada
    opcoes.MAO_3D_ATIVA = True
    scr = open_screen(app)
    check("ligada: mão 3D criada", scr.hand3d is not None and scr.stage.gl is scr.hand3d.view)
    check("ligada: miniatura e legenda",
          scr.stage.gl_frame is not None and scr.stage.legend is not None
          and "Modelo 3D" in scr.stage.mini_caption.text())
    tb = scr.toolbar
    check("ligada: botões Câmera / Modelo 3D e dica",
          tb.btn_3d is not None and tb.btn_cam is not None and tb.hint is not None and tb.btn_center is not None)
    check("ligada: dicas falam da mão 3D", "mão 3D" in tips_text(scr))
    check("ligada: OpenGL importado", "pyqtgraph.opengl" in sys.modules)
    scr.stage.set_camera_main(False)
    app.processEvents()
    check("ligada: troca para o modelo 3D", scr.stage.gl_frame.geometry() == scr.stage.rect()
          and tb.btn_3d.isChecked())
    scr.stop()
    scr.deleteLater()
    app.processEvents()
finally:
    opcoes.MAO_3D_ATIVA = original
check("valor original restaurado", opcoes.MAO_3D_ATIVA is original)

print("\n" + ("Todos os testes passaram." if not failures else f"{len(failures)} falha(s): {failures}"))
sys.exit(1 if failures else 0)
