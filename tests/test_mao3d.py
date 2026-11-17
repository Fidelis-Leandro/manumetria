"""
Testes da mão 3D procedural (app/componentes/mao3d.py), sem abrir janelas:
  1) as esferas coloridas são exatamente as articulações medidas (kin.JOINTS)
  2) a malha passa pelos 21 pontos e tem o tamanho esperado
  3) cada esfera medida recebe a cor do seu dedo; as outras ficam neutras
  4) desempenho por quadro

    .venv\\Scripts\\python.exe tests\\test_mao3d.py
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.componentes import mao3d  # noqa: E402
from nucleo import geometria  # noqa: E402
from nucleo import kinematics as kin  # noqa: E402

failures = []


def check(cond, msg):
    print(("ok    " if cond else "FALHOU") + " " + msg)
    if not cond:
        failures.append(msg)


# 1) articulações medidas: 2 no polegar + 3 em cada dedo longo
expected = {tri[1] for joints in kin.JOINTS.values() for _, tri in joints}
check(set(mao3d.MEASURED) == expected and len(expected) == 14,
      f"14 articulações coloridas (MCP/PIP/DIP e MCP/IP do polegar): {sorted(mao3d.MEASURED)}")

# 2) malha da mão sintética
P = geometria.world_to_gl(geometria.build_hand_world([40, 60, 80, 20], 30))
red = (1.0, 0.0, 0.0, 1.0)
v, f, n, c = mao3d.build_mesh(P, {lm: red for lm, (finger, _) in mao3d.MEASURED.items() if finger == "ring"})
check(f.max() < len(v) and len(v) == len(n) == len(c), f"malha consistente: {len(v)} vértices, {len(f)} triângulos")
check(np.allclose(np.linalg.norm(n, axis=1), 1, atol=1e-3), "normais unitárias")
size = np.linalg.norm(P[9] - P[0])
dist = np.array([np.min(np.linalg.norm(v - p, axis=1)) for p in P])
check(dist.max() < mao3d.JOINT_RADIUS * size * 1.01, "a malha passa por todos os 21 pontos")
lo, hi = v.min(0), v.max(0)
check(np.all(lo >= P.min(0) - 0.2 * size) and np.all(hi <= P.max(0) + 0.2 * size),
      "a malha não sai da região da mão")

# 3) cores: esferas do anelar vermelhas, as dos outros dedos neutras
ring_lms = [lm for lm, (finger, _) in mao3d.MEASURED.items() if finger == "ring"]
other_lms = [lm for lm in mao3d.MEASURED if lm not in ring_lms]


def color_near(lm):
    """Cor dos vértices da esfera da articulação (a uma distância = raio da esfera)."""
    d = np.linalg.norm(v - P[lm], axis=1)
    on_sphere = np.abs(d - mao3d.JOINT_RADIUS * size) < 1e-3 * size
    colors = {tuple(float(round(float(x), 3)) for x in rgba) for rgba in c[on_sphere]}
    return colors.pop() if len(colors) == 1 else colors


check(all(color_near(lm) == red for lm in ring_lms), "articulações do anelar com a cor do dedo")
check(all(color_near(lm) == tuple(round(x, 3) for x in mao3d.NEUTRAL_COLOR) for lm in other_lms),
      "articulações sem cor definida ficam neutras")

# 4) desempenho
t0 = time.perf_counter()
for _ in range(200):
    mao3d.build_mesh(P, {})
ms = (time.perf_counter() - t0) / 200 * 1000
check(ms < 15, f"tempo por quadro: {ms:.2f} ms")

print("\n" + ("Todos os testes passaram." if not failures else f"{len(failures)} falha(s): {failures}"))
sys.exit(1 if failures else 0)
