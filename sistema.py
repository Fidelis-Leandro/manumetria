"""
ManuMetria: avaliação cinemática da mão por visão computacional. Ponto de entrada.

Executar:  .venv\\Scripts\\python.exe sistema.py                  (webcam 0)
           .venv\\Scripts\\python.exe sistema.py --sim            (mão simulada)
           .venv\\Scripts\\python.exe sistema.py --replay ARQUIVO (toca um arquivo de pontos
                                                                  como se fosse a câmera)
           .venv\\Scripts\\python.exe sistema.py --help           (todas as opções)
Ou com dois cliques em "Abrir sistema.bat".

Estrutura do código: veja DESENVOLVIMENTO.md.
"""

import argparse
import os
import sys

import pyqtgraph as pg
from PyQt5 import QtWidgets, sip

from manumetria.captura import camera, gravacao
from manumetria.captura.simulacao import DemoHand
from manumetria.dados import configuracoes as cfgmod
from manumetria.interface.janela import AppWindow


def make_source_factory(args):
    """Cria uma fonte de quadros para cada avaliação: câmera, simulação ou arquivo de pontos."""
    def factory():
        if args.replay:
            return gravacao.ReplaySource(args.replay, loop=False), f"gravação {args.replay}"
        if args.sim:
            return DemoHand(), "simulação"
        w, h = (int(v) for v in args.resolucao.lower().split("x"))
        source = camera.CameraSource(args.cam, w, h, detection=args.confianca,
                                     presence=args.confianca, tracking=args.confianca)
        return source, f"câmera {args.cam}"
    return factory


def main():
    """Lê as opções da linha de comando e abre a janela principal."""
    parser = argparse.ArgumentParser(description="ManuMetria - avaliação cinemática da mão por visão computacional")
    parser.add_argument("--sim", action="store_true", help="usar a mão simulada")
    parser.add_argument("--cam", type=int, default=0, help="índice da webcam (padrão 0)")
    parser.add_argument("--replay", metavar="ARQUIVO",
                        help="tocar um arquivo de pontos (.npz, ex.: dados_locais/pontos/...)")
    parser.add_argument("--resolucao", default="640x480", help="resolução da câmera, ex.: 1280x720")
    parser.add_argument("--confianca", type=float, default=camera.DETECTION_CONFIDENCE,
                        help="limiar do MediaPipe 0..1 (padrão 0.5; menor = insiste mais na mão)")
    parser.add_argument("--banco", metavar="ARQUIVO", help="outro arquivo de banco (SQLite)")
    args = parser.parse_args()

    pg.setConfigOptions(antialias=True)
    scale = float(cfgmod.load().get("escala", 1.0))  # tamanho da interface (Configurações)
    if abs(scale - 1.0) > 0.01:
        os.environ["QT_SCALE_FACTOR"] = f"{scale:g}"  # precisa vir antes do QApplication
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("ManuMetria")
    app.setApplicationDisplayName("ManuMetria")
    kwargs = {"db_path": args.banco} if args.banco else {}
    win = AppWindow(make_source_factory(args), **kwargs)
    win.show()
    code = app.exec_()
    # destrói a janela (prévia do relatório, OpenGL se a mão 3D estiver ligada...) enquanto o QApplication existe;
    # deixar isso para o encerramento do Python derrubava o processo ao sair (~1 em 3)
    sip.delete(win)
    sys.exit(code)


if __name__ == "__main__":
    main()
