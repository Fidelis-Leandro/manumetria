"""
Pastas do banco e do logotipo. Com o banco padrão, os pontos ficam em dados_locais/pontos e o caminho
salvo é relativo à pasta do projeto; com outro banco (sistema.py --banco, ou
tools/criar_demonstracao.py outro.sqlite), os pontos ficam em pontos/ ao lado dele e o
caminho salvo é relativo à pasta dele, então a pasta pode ir para outro lugar ou outro
disco. O logotipo escolhido em Configurações vai para dados_locais/ e o padrão
(manumetria/recursos/) nunca é sobrescrito. Tudo em pastas temporárias; ao final confere
que dados_locais não mudou.

    .venv\\Scripts\\python.exe tests\\test_pastas.py
"""

import datetime
import hashlib
import os
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import criar_demonstracao as demo  # noqa: E402
from manumetria import caminhos  # noqa: E402
from manumetria.avaliacao.motor import Avaliador  # noqa: E402
from manumetria.dados import recalculo  # noqa: E402
from manumetria.dados.banco import Banco  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(f"[{'ok' if ok else 'FALHOU'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def fingerprint(folder):
    """SHA-256 de cada arquivo da pasta (vazio se ela não existir)."""
    out = {}
    for base, _, names in os.walk(folder):
        for n in names:
            path = os.path.join(base, n)
            with open(path, "rb") as fh:
                out[os.path.relpath(path, folder)] = hashlib.sha256(fh.read()).hexdigest()
    return out


real_before = fingerprint(caminhos.DATA_DIR)

# banco padrão: nada muda
check("banco padrão: pasta do projeto e dados_locais/pontos",
      caminhos.pastas_do_banco(caminhos.DB_PATH) == (caminhos.ROOT, caminhos.POINTS_DIR))
cwd = os.getcwd()
os.chdir(ROOT)
try:
    check("banco padrão também por caminho relativo",
          caminhos.pastas_do_banco(os.path.join("dados_locais", "avaliacoes.sqlite"))
          == (caminhos.ROOT, caminhos.POINTS_DIR))
finally:
    os.chdir(cwd)
check("avaliação sem banco informado: caminho do padrão, com '/'",
      Avaliador().points_path().startswith("dados_locais/pontos/sessao_"))

with tempfile.TemporaryDirectory() as tmp:
    # 8b: outro banco (como sistema.py --banco): pontos em <pasta do banco>/pontos
    folder = os.path.join(tmp, "outro")
    db = Banco(os.path.join(folder, "outro.sqlite"))
    check("outro banco: pasta base = a do banco; pontos em pontos/ ao lado dele",
          (db.root, db.points_dir) == (folder, os.path.join(folder, "pontos")))
    av = Avaliador(pastas=(db.root, db.points_dir))
    av.started_at = datetime.datetime(2026, 11, 3, 10, 0)
    for raw in demo.frames({"low": [[5, 8, 4]] * 4, "peak": [[60, 80, 50]] * 4, "thumb": (8, 50), "reps": 6,
                            "periodo": 2.5, "variacao": 0.05}, 1000.0, False):
        av.step(raw, raw["t"])
    res = av.results(av.frames[-1]["t"], "simulação")
    pid = db.salvar_paciente({"identificacao": "PASTAS"})
    sid = db.salvar_sessao(pid, res, gravar_pontos=av.write_points)
    saved = db.sessao(sid)["resultados"]["pontos"]
    check("outro banco: caminho salvo relativo à pasta do banco", saved == "pontos/sessao_20261103_100000.npz",
          saved)
    check("outro banco: arquivo gravado ao lado do banco",
          os.path.exists(os.path.join(folder, "pontos", "sessao_20261103_100000.npz")))

    # a janela passa as pastas do banco aberto para a avaliação
    from PyQt5 import QtWidgets  # noqa: E402
    from manumetria.captura.simulacao import DemoHand  # noqa: E402
    from manumetria.interface.janela import AppWindow  # noqa: E402
    qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    win = AppWindow(lambda: (DemoHand(), "simulação"), db_path=os.path.join(folder, "outro.sqlite"))
    win.evaluation.prepare({"id": pid})
    check("janela com --banco: a avaliação grava os pontos ao lado desse banco",
          (win.evaluation.av.root, win.evaluation.av.points_dir) == (folder, os.path.join(folder, "pontos")))
    win.db.con.close()
    win.deleteLater()

    # 8a: demonstração em outro banco (mesmo caminho do criar_demonstracao.main)
    demo_db = Banco(os.path.join(tmp, "demo", "demo.sqlite"))
    demo.add_patient(demo_db, demo.EX, demo.EX_CURVE, demo.EX_PLAN)
    paths = [s["resultados"]["pontos"] for s in demo_db.todas_sessoes()]
    check("demonstração em outro banco: caminhos relativos à pasta dele, sem '..'",
          paths and all(p.startswith("pontos/sessao_") and ".." not in p for p in paths), paths[:2])
    check("demonstração em outro banco: todos os arquivos de pontos existem",
          all(os.path.exists(caminhos.absoluto(p, demo_db.root)) for p in paths))
    demo_db.con.close()
    db.con.close()

    # a pasta inteira muda de lugar (como em outro disco): tudo continua achando os pontos
    moved = os.path.join(tmp, "movida", "demo")
    shutil.move(os.path.join(tmp, "demo"), moved)
    demo_db = Banco(os.path.join(moved, "demo.sqlite"))
    items = recalculo.preparar(demo_db)
    check("pasta movida: Recalcular avaliações acha os pontos de todas",
          items and all(it["novo"] is not None for it in items), [it["motivo"] for it in items][:2])
    sid0 = demo_db.todas_sessoes()[0]["id"]
    rel0 = demo_db.sessao(sid0)["resultados"]["pontos"]
    failed = demo_db.excluir_sessao(sid0)
    check("pasta movida: excluir a avaliação apaga os pontos dela",
          not failed and not os.path.exists(caminhos.absoluto(rel0, demo_db.root)))
    demo_db.con.close()

# logotipo: o escolhido vai para dados_locais; o padrão que acompanha o sistema não é sobrescrito
from manumetria.dados import configuracoes as cfgmod  # noqa: E402
default_logo = os.path.join(caminhos.RESOURCES_DIR, "logo_relatorio.png")
same = lambda a, b: a is not None and os.path.normcase(os.path.abspath(a)) == os.path.normcase(b)
check("logotipo padrão em manumetria/recursos/", same(cfgmod.logo_path(cfgmod.DEFAULTS), default_logo))
check("config.json com assets/logo_relatorio.png usa o padrão de manumetria/recursos/",
      same(cfgmod.logo_path({"logo": "assets/logo_relatorio.png"}), default_logo)
      and same(cfgmod.logo_path({"logo": "assets\\logo_relatorio.png"}), default_logo))
check("logotipo escolhido em Configurações é copiado para dados_locais",
      os.path.normcase(cfgmod.LOGO_DIR) == os.path.normcase(caminhos.DATA_DIR))
check("sem logotipo: nenhum", cfgmod.logo_path({"logo": ""}) is None)

check("dados_locais não mudou (mesmo SHA-256 em todos os arquivos)", fingerprint(caminhos.DATA_DIR) == real_before,
      f"{len(real_before)} arquivos")

print("\n" + ("Todos os testes passaram." if not failures else f"{len(failures)} falha(s): {failures}"))
sys.exit(1 if failures else 0)
