"""
Auditoria dos cálculos: testes de resposta conhecida para cada medida, casos-limite,
coerência entre o que é calculado, salvo, exportado e recalculado, e conferência dos números
afirmados nos textos (README, Ajuda, PDF, dicionário de dados, comentários) contra a gravação
de referência. Relatório completo: docs/AUDITORIA_CALCULOS.md.

    .venv\\Scripts\\python.exe tests\\test_auditoria.py
"""

import os
import shutil
import sys
import tempfile

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")      # símbolos (π, √, ×) no console do Windows
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from manumetria.avaliacao import interpretacao as interp  # noqa: E402
from manumetria.avaliacao.motor import analisar  # noqa: E402
from manumetria.calculo import geometria, goniometria, medidas, repeticoes, sessao, sinal  # noqa: E402
from manumetria.captura import gravacao  # noqa: E402
from manumetria.dados import planilha, recalculo  # noqa: E402
from manumetria.dados.banco import Banco  # noqa: E402

RECORDING = os.path.join(ROOT, "tests", "dados", "gravacao_referencia.npz")
FS = 30.0
SHARE = np.array([0.6, 1.0, 0.7]) / 2.3          # divisão do TAM entre MCP, PIP e DIP nos sinais sintéticos
failures = []


def check(name, ok, detail=""):
    print(f"[{'ok' if ok else 'FALHOU'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def mirror(world):
    w = np.array(world, float)
    w[:, 0] *= -1
    return w


# =============================================================================
# 1. Ângulos das articulações (decomposição por osso, ISB)
# =============================================================================
# Modelo de mão do Hand Filter Lab / sistema-mao-web (core/modelo-mao.js, fk), em mm, quiralidade
# de mão esquerda, com a sequência da ISB (abdução, depois flexão da MCP). Os ângulos dele são a
# verdade por construção; o autoteste do lab (gonioSelfTest) usa os mesmos casos.
def _n(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def _rot(v, k, deg):
    t = np.radians(deg)
    return v * np.cos(t) + np.cross(k, v) * np.sin(t) + k * (k @ v) * (1 - np.cos(t))


LAB_MCP = {"index": [-22.0, 85, 0], "middle": [-3.0, 88, 0], "ring": [15.0, 83, 0], "pinky": [31.0, 73, 0]}
LAB_LEN = {"index": [40, 25, 20], "middle": [45, 28, 21], "ring": [42, 27, 21], "pinky": [33, 20, 18],
           "thumb": [40, 32, 26]}
ABD_SIGN = {"index": -1, "middle": 1, "ring": 1, "pinky": 1}


def lab_hand(pose):
    """pose = {dedo: (mcp, pip, dip, abd)}, "thumb": (opp, mcp, ip)} -> 21 pontos do modelo do lab."""
    lm = np.zeros((21, 3))
    cmc = np.array([-18.0, 22, 4])
    lat = _n(np.subtract(LAB_MCP["pinky"], LAB_MCP["index"]))
    palm_n = _n(np.cross(LAB_MCP["index"], LAB_MCP["pinky"]))
    opp, tm_, ti_ = pose.get("thumb", (0.05, 0.0, 0.0))
    m = _n(_n([-0.55, 0.8, 0.22]) * (1 - opp) + _n([0.42, 0.5, 0.76]) * opp)
    k = _n(palm_n - m * (palm_n @ m))
    lm[1] = cmc
    lm[2] = cmc + m * LAB_LEN["thumb"][0]
    lm[3] = lm[2] + _rot(m, k, tm_) * LAB_LEN["thumb"][1]
    lm[4] = lm[3] + _rot(m, k, tm_ + ti_) * LAB_LEN["thumb"][2]
    for f, b in goniometria.LONG_BASES.items():
        mcp, pip, dip, abd = pose.get(f, (0.0, 0.0, 0.0, 0.0))
        d0 = _n(LAB_MCP[f])
        k2 = _n(lat - d0 * (lat @ d0))
        a1 = _rot(_rot(d0, _n(np.cross(d0, k2)), abd * ABD_SIGN[f]), k2, mcp)
        kp = _n(k2 - a1 * (k2 @ a1))
        a2, a3 = _rot(a1, kp, pip), _rot(a1, kp, pip + dip)
        lm[b] = LAB_MCP[f]
        lm[b + 1] = lm[b] + a1 * LAB_LEN[f][0]
        lm[b + 2] = lm[b + 1] + a2 * LAB_LEN[f][1]
        lm[b + 3] = lm[b + 2] + a3 * LAB_LEN[f][2]
    return lm


def lab_to_world(lm, real_hand="Right"):
    """Pontos do lab -> world do MediaPipe (m) de uma mão REAL com a imagem espelhada."""
    sx = -1.0 if real_hand == "Left" else 1.0
    return np.column_stack([sx * lm[:, 0], -lm[:, 1], -lm[:, 2]]) / 1000.0


SELF_TEST = [   # casos do gonioSelfTest do lab: (pose, dedo, verdade)
    ({}, "index", (0, 0, 0)),
    ({"index": (60, 45, 20, 0)}, "index", (60, 45, 20)),
    ({"index": (0, 0, 0, 20)}, "index", (0, 0, 0)),
    ({"index": (60, 0, 0, 20)}, "index", (60, 0, 0)),
    ({"index": (40, 70, 30, 15)}, "index", (40, 70, 30)),
    ({"index": (-20, 0, 0, 0)}, "index", (-20, 0, 0)),
    ({"index": (-20, 90, 60, 0)}, "index", (-20, 90, 60)),
    ({"index": (0, 0, 0, -10)}, "index", (0, 0, 0)),
    ({"pinky": (50, 30, 0, 25)}, "pinky", (50, 30, 0)),
    ({"thumb": (0.05, 30, 40)}, "thumb", (30, 40)),
]
worst = 0.0
for pose, f, truth in SELF_TEST:
    for hand in ("Right", "Left"):
        worst = max(worst, float(np.abs(goniometria.joint_angles(lab_to_world(lab_hand(pose), hand), hand)[f] - truth).max()))
check("autoteste do lab portado (10 casos, mão direita e esquerda): erro ~0", worst < 1e-9, f"{worst:.1e}")

# mão inteira girada 70° no espaço (caso do autoteste do lab): os ângulos não mudam
lm = lab_hand({"index": (60, 45, 20, 10)})
lm_rot = np.array([_rot(p, _n([0.3, 1, 0.5]), 70) for p in lm])
a = goniometria.joint_angles(lab_to_world(lm_rot), "Right")["index"]
check("mão girada 70° no espaço: 60/45/20 (com 10° de abdução)", np.allclose(a, [60, 45, 20], atol=1e-9), f"{a}")
a = goniometria.joint_angles(lab_to_world(lab_hand({"index": (60, 0, 0, 20)})), "Right")["index"]
check("D1: MCP 60° com 20° de abdução -> 60,0° (a abdução não entra na flexão)", abs(a[0] - 60) < 1e-9, f"{a[0]:.4f}")
a = goniometria.joint_angles(lab_to_world(lab_hand({"index": (40, 70, 30, 15)})), "Right")["index"]
check("D1: 40/70/30 com 15° de abdução -> 40/70/30", np.allclose(a, [40, 70, 30], atol=1e-9), f"{a}")

rng = np.random.default_rng(7)
worst = 0.0
for _ in range(300):
    pose = {f: (rng.uniform(-15, 90), rng.uniform(0, 110), rng.uniform(0, 80), rng.uniform(-10, 25))
            for f in goniometria.LONG_BASES}
    pose["thumb"] = (rng.uniform(0, 1), rng.uniform(-10, 60), rng.uniform(-10, 80))
    hand = "Right" if rng.random() < 0.5 else "Left"
    ang = goniometria.joint_angles(lab_to_world(lab_hand(pose), hand), hand)
    for f in goniometria.FINGERS:
        truth = pose[f][1:] if f == "thumb" else pose[f][:3]
        worst = max(worst, float(np.abs(ang[f] - truth).max()))
check("300 poses aleatórias com abdução (mãos direita e esquerda): erro ~0", worst < 1e-9, f"{worst:.1e}")

# mão sintética do próprio sistema (geometria.build_hand_world): a flexão é aplicada em torno do eixo x
# da imagem, e o metacarpo (linha punho -> base) fica oblíquo ao dedo: na convenção ISB isso é uma
# pequena abdução, então a MCP difere até ~3,4°; PIP, DIP e polegar ficam perto da verdade.
for fl, th in [(0, 0), (30, 20), (90, 60), (-20, -10)]:
    w = geometria.build_hand_world([fl] * 4, th)
    a, b = goniometria.joint_angles(w, "Right"), goniometria.joint_angles(mirror(w), "Left")
    check(f"mão esquerda (espelhada) = direita, PIP {fl}°", all(np.allclose(a[f], b[f], atol=1e-9) for f in goniometria.FINGERS))
    check(f"mão sintética: PIP {fl}° e DIP {0.7 * fl:.0f}° (±2°), MCP {0.6 * fl:.0f}° (±3,5°)",
          all(abs(a[f][1] - fl) < 2 and abs(a[f][2] - 0.7 * fl) < 2 and abs(a[f][0] - 0.6 * fl) < 3.5
              for f in goniometria.FINGERS[1:]), f"indicador {np.round(a['index'], 1)}")
    check(f"mão sintética: polegar MCP {0.4 * th:.0f}° e IP {th}° (±0,5°)",
          abs(a["thumb"][0] - 0.4 * th) < 0.5 and abs(a["thumb"][1] - th) < 0.5)
w = geometria.build_hand_world([-20] * 4, -10)
check("hiperextensão sai negativa (dedos e polegar)", all(goniometria.joint_angles(w, "Right")[f][1] < -9 for f in goniometria.FINGERS))
check("sem lado: ângulo 3D sem sinal (>= 0)", all((goniometria.joint_angles(w)[f] >= 0).all() for f in goniometria.FINGERS))
check("lado trocado inverte o sinal", goniometria.joint_angles(geometria.build_hand_world([40] * 4, 0), "Left")["index"][1] < 0)
check("ângulo impossível: quadro descartado", not goniometria.plausible({"index": np.array([0, 131.0, 0])})
      and not goniometria.plausible({"index": np.array([-61.0, 0, 0])}) and goniometria.plausible({"index": np.array([-60.0, 130, 0])}))

# vista da palma
w = geometria.build_hand_world([0] * 4, 0)
check("vista: palma de frente = 0°, mão esquerda espelhada também",
      goniometria.view_angle(w, "Right") < 0.01 and goniometria.view_angle(mirror(w), "Left") < 0.01)
for deg in (30, 59, 61, 90, 150):
    t = np.radians(deg)
    Ry = np.array([[np.cos(t), 0, np.sin(t)], [0, 1, 0], [-np.sin(t), 0, np.cos(t)]])
    v = goniometria.view_angle(w @ Ry.T, "Right")
    check(f"vista: mão girada {deg}° = {deg}° ({'fora' if deg > 60 else 'dentro'} da medida)",
          abs(v - deg) < 0.01 and goniometria.good_view(w @ Ry.T, "Right") == (deg <= 60), f"{v:.3f}")


# =============================================================================
# 2. TAM, TAM ativo, déficit (sem tolerância), arco, % do normal, classificação
# =============================================================================
def tracker_with(frames, finger="index"):
    tr = repeticoes.FingerTracker(finger, sensitivity=5.0)
    for i, j in enumerate(frames):
        tr.update(np.array(j, float), i / FS)
    return tr


tr = tracker_with([[10, 20, 5], [80, 100, 60], [2, -5, 1]])
check("máximo e mínimo por articulação", np.allclose(tr.max_joints, [80, 100, 60]) and np.allclose(tr.min_joints, [2, -5, 1]))
check("D5: déficit = max(0, menor flexão): 2 / 0 (hiperextensão) / 1", np.allclose(tr.deficits(), [2, 0, 1]))
check("TAM ativo = 240 - 3 = 237; % = 237/260",
      abs(tr.active_tam() - 237) < 1e-9 and abs(tr.percent_normal() - 237 / 260) < 1e-12)
check("arco = máx - mín", np.allclose(tr.arcs(), [78, 105, 59]))
check("TAM máximo simultâneo = 240", abs(tr.max_tam - 240) < 1e-9)
tr = tracker_with([[30, 40, 20], [70, 90, 50]])
check("déficit = menor flexão; TAM ativo = 210 - 90 = 120", np.allclose(tr.deficits(), [30, 40, 20])
      and abs(tr.active_tam() - 120) < 1e-9)
check("D5: sem tolerância (0,5° já conta)", tracker_with([[0.5, 0, -0.5]]).deficits().tolist() == [0.5, 0, 0])
tr = tracker_with([[0, 0], [50, 70]], "thumb")
check("polegar: normal 140°, TAM ativo 120 -> 85,7%", tr.normal == 140 and abs(tr.percent_normal() - 120 / 140) < 1e-12)
check("sem dados: TAM ativo, % e arcos None", repeticoes.FingerTracker("index").active_tam() is None
      and repeticoes.FingerTracker("index").percent_normal() is None and repeticoes.FingerTracker("index").arcs() is None)
check("TAM ativo negativo (dedo rígido em flexão): 0%", tracker_with([[60, 70, 50]]).percent_normal() == 0.0)
check("classificação: 49% ruim, 50% regular, 74,9% regular, 75% bom",
      [goniometria.grade(x) for x in (0.49, 0.50, 0.749, 0.75, None)] == ["ruim", "regular", "regular", "bom", None])
check("D4: normais mantidos: dedos 85/105/70 = 260, polegar 60/80 = 140",
      goniometria.normal_tam("index") == 260 and goniometria.normal_tam("thumb") == 140
      and (goniometria.GRADE_FAIR, goniometria.GRADE_GOOD) == (0.50, 0.75))


# =============================================================================
# 3. Repetições, velocidades, ciclo, cadência, tendências, esforço
# =============================================================================
def tam_series(amps, period=2.0, base=10.0, rest_before=0.3, rest_after=1.0, hold=0.0):
    """TAM do dedo quadro a quadro: repouso, cossenos (com `hold` s parado no topo), repouso."""
    x = [base] * int(round(rest_before * FS))
    n = int(round(period * FS))
    for A in amps:
        up = [base + A * (1 - np.cos(np.pi * i / (n / 2))) / 2 for i in range(n // 2)]
        x += up + [base + A] * int(round(hold * FS)) + [base + A * (1 + np.cos(np.pi * i / (n / 2))) / 2
                                                         for i in range(n // 2)]
    return np.array(x + [base] * int(round(rest_after * FS)))


def run_tam(x, finger="index", sens=5.0):
    tr = repeticoes.FingerTracker(finger, sensitivity=sens)
    share = SHARE if finger != "thumb" else np.array([0.4, 0.6])
    for i, v in enumerate(x):
        tr.update(share * v, i / FS)
    return tr


def expected_times(x, sens=5.0, n_avg=repeticoes.DETECTOR_SMOOTH_FRAMES):
    """Critério dos tempos da repetição refeito à parte, para UMA repetição: média de n_avg quadros; início = último
    instante a até sens/2 do vale antes do pico; fim = primeiro instante a até sens/2 do pico."""
    t = np.arange(len(x)) / FS
    avg = np.convolve(x, np.ones(n_avg) / n_avg, mode="valid")
    ta = t[n_avg - 1:]
    ip = int(np.argmax(avg))
    valley = avg[:ip].min()
    start = ta[:ip][avg[:ip] <= valley + sens / 2][-1]
    peak_t = ta[avg >= avg[ip] - sens / 2][0]
    return start, peak_t


x = tam_series([200] * 8)
tr = run_tam(x)
q = tr.quality()
amps = [r.amplitude for r in tr.reps]
check("8 ciclos -> 8 repetições", len(tr.reps) == 8, str(tr.counts()))
check("D2: amplitude de cada repetição nos dados brutos = 200° (±2°)", all(abs(a - 200) <= 2 for a in amps),
      f"{np.round(amps, 2)}")
check("D2: classificação, TAM no pico e excursão pelos dados brutos (200° -> completa; pico 210°; 0,6/1/0,7)",
      all(r.kind == "completa" for r in tr.reps) and all(abs(r.peak_tam - 210) < 1e-9 for r in tr.reps)
      and np.allclose(tr.reps[3].excursion, SHARE * 200, atol=1e-6))
check("ciclo = 2,0 s e cadência = 30/min", abs(q["cycle_s"] - 2.0) < 0.04 and abs(q["cadence"] - 30) < 0.6,
      f"{q['cycle_s']:.3f} s, {q['cadence']:.2f}/min")
check("velocidade de pico = A·π/T = 314°/s (±2%)", abs(q["peak_velocity"] / (200 * np.pi / 2) - 1) < 0.02,
      f"{q['peak_velocity']:.1f}")
one = tam_series([200], rest_before=1.0)
start, peak_t = expected_times(one)
r1 = run_tam(one).reps[0]
check("D3: início e fim da flexão pelo critério da meia sensibilidade (refeito à parte)",
      abs(r1.t_start - start) < 1e-9 and abs(r1.t_peak - peak_t) < 1e-9,
      f"{r1.t_start:.3f}/{r1.t_peak:.3f} x {start:.3f}/{peak_t:.3f}")
check("D3: velocidade média de flexão = amplitude bruta / (fim - início)",
      abs(r1.flex_velocity - 200 / (peak_t - start)) < 1e-6, f"{r1.flex_velocity:.1f}")
x = tam_series([200] * 6, rest_before=3.0)
tr3 = run_tam(x)
v = [r.flex_velocity for r in tr3.reps]
check("D3: 3 s parado antes da 1ª repetição não altera a velocidade dela (≤ 5% das outras)",
      abs(v[0] / np.mean(v[1:]) - 1) <= 0.05, f"{np.round(v, 1)}")
x = tam_series([200] * 6, hold=1.5)
tr4 = run_tam(x)
ev = [r.ext_velocity for r in tr4.reps if r.ext_velocity is not None]
fv = [r.flex_velocity for r in tr4.reps]
check("D3: pausa de 1,5 s com a mão fechada não entra na flexão nem na extensão",
      abs(np.mean(fv) / np.mean(v[1:]) - 1) <= 0.05 and abs(np.mean(ev) / np.mean(v[1:]) - 1) <= 0.05,
      f"flexão {np.mean(fv):.0f}, extensão {np.mean(ev):.0f}°/s")
check("ciclo fixo: Regular", q["regularity"] == "Regular" and q["cv"] < 0.05, f"{q['cv']:.3f}")
check("contribuição = 0,6/1/0,7 normalizado", np.allclose(tr.contribution(), SHARE, atol=1e-6))
check("SPARC do cosseno entre -1,8 e -1,2", -1.8 < q["sparc"] < -1.2, f"{q['sparc']:.2f}")
check("sem fadiga: tendências de amplitude e velocidade ~0", abs(q["amp_trend"]) < 0.01 and abs(q["vel_trend"]) < 0.03,
      f"{q['amp_trend']:.3f} / {q['vel_trend']:.3f}")
check("esforço igual: Consistente; 8 repetições fortes", q["effort"] == "Consistente" and tr.strong_reps() == 8)
for kind, A in (("movimento", 40), ("parcial", 120), ("completa", 196)):
    t_ = run_tam(tam_series([A] * 3))
    check(f"classificação: amplitude {A}° -> {kind}", [r.kind for r in t_.reps] == [kind] * 3,
          f"{[r.kind for r in t_.reps]}")
lin = np.linspace(200, 140, 10)
tr = run_tam(tam_series(lin))
q = tr.quality()
check("tendência de amplitude 200 -> 140 = -30% (±1 pp)", abs(q["amp_trend"] + 0.30) < 0.01, f"{q['amp_trend']:.3f}")
check("amplitude fim × início = (média 3 últimas) / (média 3 primeiras) - 1",
      abs(q["amp_change"] - (np.mean(lin[-3:]) / np.mean(lin[:3]) - 1)) < 0.005, f"{q['amp_change']:.4f}")
tr = run_tam(tam_series([200]))
q = tr.quality()
check("uma repetição só: sem ciclo, cadência, regularidade, tendência e esforço",
      all(q[k] is None for k in ("cycle_s", "cadence", "cv", "regularity", "amp_trend", "vel_trend", "effort")))
check("sem repetições: qualidade toda None", all(v is None for v in repeticoes.FingerTracker("index").quality().values()))
check("sem repetições: independência, contribuição e repetições fortes vazias",
      repeticoes.FingerTracker("index").independence() is None and repeticoes.FingerTracker("index").contribution() is None
      and repeticoes.FingerTracker("index").strong_reps() == 0)
tr = repeticoes.FingerTracker("index", 5.0)
for i, v in enumerate(tam_series([200] * 2)):
    tr.update(SHARE * v)                          # quadros sem horário: sem dados brutos com tempo
check("sem horário nos quadros: conta as repetições (valores no TAM médio), sem velocidades",
      len(tr.reps) == 2 and all(r.flex_velocity is None for r in tr.reps))
check("tendência: menos de 6 valores ou início <= 0 -> None", sinal.trend([1] * 5) is None and sinal.trend(range(6)) is None)

# derivada e SPARC
xs = np.sin(2 * np.pi * np.arange(90) / FS)
H = (2 * np.sin(2 * 2 * np.pi / FS) + np.sin(2 * np.pi / FS)) / 5 / (2 * np.pi / FS)   # resposta da derivada SG
check("derivada de Savitzky-Golay de um seno de 1 Hz: 2π·cos × resposta teórica do filtro",
      np.allclose(sinal.derivative(xs, FS)[2:-2], H * 2 * np.pi * np.cos(2 * np.pi * np.arange(90) / FS)[2:-2], atol=1e-9))
check("SPARC: velocidade nula ou curta -> None", sinal.sparc(np.zeros(20)) is None and sinal.sparc(np.ones(5)) is None)
s_ = np.linspace(0, 1, 31)
mj = 60 * (10 * s_ ** 3 - 15 * s_ ** 4 + 6 * s_ ** 5)         # mínimo jerk: 0 -> 60°
J = np.column_stack([mj, -mj, np.zeros_like(mj)])            # MCP flete, PIP estende na mesma velocidade
check("D7: uma articulação flete e outra estende: derivada do TAM = 0 (SPARC impossível) ...",
      np.allclose(sinal.derivative(J.sum(axis=1)), 0) and sinal.sparc(np.abs(sinal.derivative(J.sum(axis=1)))) is None)
sp = sinal.sparc(sinal.joint_speed(J))
check("D7: ... mas o SPARC da norma das velocidades é calculado (= o de uma articulação só)",
      sp is not None and abs(sp - sinal.sparc(np.abs(sinal.derivative(mj)))) < 1e-9, f"{sp}")


# =============================================================================
# 4. Independência, acoplamento, calibração
# =============================================================================
def session_moving(movers, A=200.0, sens=5.0):
    s = sessao.Session({f: sens for f in goniometria.FINGERS})
    x = tam_series([A] * 4)
    for i, v in enumerate(x):
        s.update({f: (np.ones(2) / 2 if f == "thumb" else np.ones(3) / 3) * (v if f in movers else 10.0)
                  for f in goniometria.FINGERS}, i / FS)
    return s


ind = session_moving({"index"}).trackers["index"].independence()
check("independência: só o indicador se move -> 100%", ind == 1.0, f"{ind}")
s = session_moving(set(goniometria.FINGERS))
cp = s.trackers["index"].coupling()
check("D6: mesmo movimento nos dois dedos -> acoplamento = (A - sensibilidade)/A = 0,975",
      all(abs(v - 195 / 200) < 1e-9 for v in cp.values()), f"{cp}")
check("D6: independência = 1 - 0,975 = 2,5%", abs(s.trackers["index"].independence() - 0.025) < 1e-9)

cal = sessao.Calibration()
rng = np.random.default_rng(3)
while not cal.done():
    cal.add({f: rng.normal(0, 1.0 / np.sqrt(2 if f == "thumb" else 3), 2 if f == "thumb" else 3) for f in goniometria.FINGERS})
stds = {f: np.std(v) for f, v in cal.tams.items()}
sens = cal.sensitivity()
check("sensibilidade = 3 × desvio padrão do TAM na calibração", all(abs(sens[f] - 3 * stds[f]) < 1e-9 for f in sens))
check("sensibilidade sem calibração = 5°", all(v == 5.0 for v in sessao.Calibration().sensitivity().values()))

# =============================================================================
# 5. Medidas da mão inteira
# =============================================================================
check("arco funcional (Bain 2015): cobertura da faixa",
      medidas.functional_coverage("index", "MCP", 0, 90) == 1.0
      and abs(medidas.functional_coverage("index", "PIP", 23, 55) - 0.5) < 1e-12
      and medidas.functional_coverage("index", "DIP", 70, 90) == 0.0
      and medidas.functional_coverage("thumb", "MCP", 0, 90) is None)
check("arco funcional: faixas 19-71, 23-87, 10-64",
      medidas.FUNCTIONAL_ROM == {"MCP": (19.0, 71.0), "PIP": (23.0, 87.0), "DIP": (10.0, 64.0)})
v = medidas.strickland("index", np.array([80, 100, 75.0]), np.array([0, 10, 5.0]))
check("Strickland = (100 + 75 - 10 - 5) / 175", abs(v - 160 / 175) < 1e-12)
check("Strickland: classes 85 / 70 / 50%", [medidas.strickland_grade(x) for x in (0.85, 0.849, 0.70, 0.50, 0.49)]
      == ["excelente", "bom", "bom", "regular", "ruim"] and medidas.strickland("thumb", np.ones(2), np.zeros(2)) is None)


def flat_hand(dirs_deg):
    P = np.zeros((21, 3))
    P[0] = [0, 0.09, 0]
    for (b, x0), ang in zip({5: -0.025, 9: 0.0, 13: 0.02, 17: 0.04}.items(), dirs_deg):
        P[b] = [x0, 0, 0]
        d = np.array([np.sin(np.radians(ang)), -np.cos(np.radians(ang)), 0])
        for k in range(1, 4):
            P[b + k] = P[b] + d * 0.02 * k
    P[1:5] = [[-0.03, 0.07, 0], [-0.05, 0.05, 0], [-0.06, 0.03, 0], [-0.07, 0.01, 0]]
    return P


P = flat_hand([-10, 0, 8, 20])
check("abertura dos dedos: 10° / 8° / 12°",
      np.allclose(medidas.finger_spread(P, goniometria.joint_angles(P, "Right")), [10, 8, 12], atol=1e-5))
u, v = P[2] - P[1], P[5] - P[0]
check("abertura do polegar = ângulo entre metacarpo do polegar e punho-base do indicador",
      abs(medidas.thumb_opening(P) - np.degrees(np.arccos(u @ v / np.linalg.norm(u) / np.linalg.norm(v)))) < 1e-6)
P2 = P.copy()
P2[8] = P2[5] + np.array([0.01, 0.0, -0.05])
palm = np.linalg.norm(P2[9] - P2[0])
check("polpa-palma: 5 cm menos o zero do dedo",
      abs(medidas.tip_to_palm_cm(P2)["index"] - (5.0 - medidas.TPD_ZERO["index"] * palm * 100)) < 1e-9)


def tremor_run(freq, amp_m, secs=6.0):
    tm = medidas.TremorMeter()
    base = geometria.build_hand_world([0] * 4, 0)
    ang = goniometria.joint_angles(base, "Right")
    for i in range(int(secs * FS)):
        w = base.copy()
        w[[4, 8, 12, 16, 20], 0] += amp_m * np.sin(2 * np.pi * freq * i / FS)
        tm.add(i / FS, w, ang)
    return tm.result()


for f_hz, amp in ((6.0, 0.002), (9.0, 0.001)):
    r = tremor_run(f_hz, amp)
    check(f"tremor de {f_hz:.0f} Hz: frequência {f_hz:.0f} Hz e RMS = A/√2 = {amp / np.sqrt(2) * 1000:.2f} mm",
          r["ritmico"] and abs(r["frequencia_hz"] - f_hz) <= 0.5 and abs(r["rms_mm"] - amp / np.sqrt(2) * 1000) < 0.02,
          str(r))
check("tremor: sem dados -> nada medido", medidas.TremorMeter().result()["frequencia_hz"] is None)
check("confiabilidade: sem quadros -> baixa", medidas.session_reliability(0, 0)["nivel"] == "baixa")


# =============================================================================
# 6. Erro de medida (MDC), mudança real, extensão, tendência
# =============================================================================
def fake(pct, mx, rt_pct, rt_mx, nivel="alta"):
    j = lambda m: [{"nome": "MCP", "min": 0.0, "max": m, "deficit": 0, "arco": m}]
    return {"confiabilidade": {"nivel": nivel},
            "dedos": {f: {"pct_normal": pct, "articulacoes": j(mx)} for f in goniometria.FINGERS},
            "reteste": {"confiabilidade": {"nivel": nivel},
                        "dedos": {f: {"pct_normal": rt_pct, "articulacoes": j(rt_mx)} for f in goniometria.FINGERS}}}


pairs = [(0.80, 0.76), (0.60, 0.65), (0.90, 0.88)]
e = interp.measurement_error([fake(p, 70 + 10 * p, q, 70 + 10 * q) for p, q in pairs])
d = np.repeat([(p - q) * 100 for p, q in pairs], 5)               # 5 dedos por reteste
mdc_hand = 1.96 * np.sqrt(((d - d.mean()) ** 2).sum() / (len(d) - 1))  # 1,96 × DP amostral das diferenças
check("MDC (% do normal) = 1,96 × DP das diferenças, feito à mão = 7,83 pp",
      abs(e["tam_pp"]["mdc"] - mdc_hand) < 1e-9 and abs(mdc_hand - 7.8283) < 1e-3, f"{e['tam_pp']['mdc']:.4f}")
check("viés = média das diferenças (teste - reteste)", abs(e["tam_pp"]["vies"] - d.mean()) < 1e-12)
dj = np.concatenate([np.concatenate([np.repeat((p - q) * 10, 5), np.zeros(5)]) for p, q in pairs])  # máx e mín
check("MDC por articulação junta máximos e mínimos", abs(e["articulacao"]["mdc"] - 1.96 * dj.std(ddof=1)) < 1e-9)
check("par com confiabilidade baixa não entra", interp.measurement_error(
    [fake(p, 1, q, 1) for p, q in pairs] + [fake(0.1, 1, 0.9, 99, "baixa")])["retestes"] == 3)
check("menos de 10 pares: sem MDC", interp.measurement_error([fake(0.5, 1, 0.5, 1)])["tam_pp"]["mdc"] is None)
check("mudança real só acima do MDC (igual ao MDC = estável)",
      interp.change(5, 5) == "estavel" and interp.change(5.01, 5) == "melhora" and interp.change(-5.01, 5) == "piora"
      and interp.change(None, 5) is None and interp.change(3, None) is None)
ec = interp.extension_change
check("D9: extensão pelo déficit: 20° -> 5° melhora; 5° -> 20° piora; 5° -> 7° estável",
      ec(20, 5, 5) == "melhora" and ec(5, 20, 5) == "piora" and ec(5, 7, 5) == "estavel")
check("D9: déficit 10° -> hiperextensão de 10° = melhora (déficit 10 -> 0)", ec(10, -10, 5) == "melhora")
check("D9: aumentar a hiperextensão (0 -> -15, -5 -> -20) fica sem classificação",
      ec(0, -15, 5) is None and ec(-5, -20, 5) is None and ec(-20, -5, 5) is None)
ses = lambda day, pct: {"inicio": f"2026-01-{1 + day:02d}T10:00:00",
                        "resultados": {"dedos": {f: {"pct_normal": pct} for f in goniometria.FINGERS}}}
t_up = interp.trend([ses(0, 0.40), ses(7, 0.45), ses(14, 0.50), ses(21, 0.55)], "index", mdc_pp=3)
check("tendência: +5 pp por semana; platô só se as 3 últimas variam até o MDC",
      abs(t_up["pp_semana"] - 5) < 1e-9 and t_up["plato"] is False
      and interp.trend([ses(0, 0.4), ses(7, 0.5), ses(14, 0.51), ses(21, 0.52)], "index", mdc_pp=3)["plato"])

# =============================================================================
# 7. Gravação de referência: tela = salvo = CSV = recálculo, e os números afirmados nos textos
# =============================================================================
rows = gravacao.load_recording(RECORDING)
av = analisar(rows)
out = av.results(rows[-1]["t"], "gravação")
same = True
for f in goniometria.FINGERS:
    tr, d = av.session.trackers[f], out["dedos"][f]
    same &= d["pct_normal"] == tr.percent_normal() and d["tam_ativo"] == max(0.0, tr.active_tam())
    same &= [j["max"] for j in d["articulacoes"]] == tr.max_joints.tolist()
    same &= [j["deficit"] for j in d["articulacoes"]] == tr.deficits().tolist()
    same &= d["qualidade"] == tr.quality() and d["movimentos"] == len(tr.reps)
check("resultado salvo = valores que a tela mostra (mesmo FingerTracker)", same)
row = planilha.finger_row("index", out["dedos"]["index"])
col = {c: row[i] for i, c in enumerate(planilha.CSV_HEADER)}
di = out["dedos"]["index"]
check("CSV: % do normal × 100, contribuição em %, graus arredondados",
      col["pct_normal"] == planilha.csv_num(di["pct_normal"] * 100)
      and col["mcp_contribuicao_pct"] == planilha.csv_num(di["articulacoes"][0]["contribuicao"] * 100)
      and col["dip_flexao_max"] == planilha.csv_num(di["articulacoes"][2]["max"])
      and col["independencia_pct"] == planilha.csv_num(di["independencia"] * 100)
      and col["sensibilidade"] == planilha.csv_num(di["sensibilidade"], 1))
check("dicionário de dados: uma descrição (com unidade) para cada coluna",
      [r[0] for r in planilha._finger_descriptions()] == planilha.CSV_HEADER
      and all(u == "%" for c, _, u in planilha._finger_descriptions() if c.endswith("_pct") or c == "pct_normal"))
check("checagem clínica: a mão saudável da gravação não recebe nenhuma limitação", not interp.limitations(out),
      f"{interp.limitations(out)}")

# recálculo num banco temporário (não toca em dados_locais)
with tempfile.TemporaryDirectory() as tmp:
    db = Banco(os.path.join(tmp, "teste.sqlite"))
    pid = db.salvar_paciente({"identificacao": "AUDITORIA"})
    os.makedirs(db.points_dir)                    # pontos ao lado do banco temporário
    shutil.copy(RECORDING, db.points_dir)
    sid = db.salvar_sessao(pid, dict(out, pontos="pontos/" + os.path.basename(RECORDING)))
    items = recalculo.preparar(db)
    n = recalculo.aplicar(db, items)
    new = db.sessao(sid)["resultados"]
    check("Recalcular avaliações (banco temporário): mesmo resultado da avaliação",
          n == 1 and new["dedos"] == out["dedos"] and new["mao_inteira"] == out["mao_inteira"]
          and items[0]["maior_diferenca"] == 0 and "original" in new)
    db.con.close()

# números afirmados nos comentários e textos
present = [r for r in rows if r["world"] is not None]
A = [goniometria.joint_angles(r["world"], "Right") for r in present]      # lado fixado na calibração: direita
bad = [i for i, a in enumerate(A) if not goniometria.plausible(a)]
views = sorted(round(goniometria.view_angle(present[i]["world"], "Right")) for i in bad)
check("texto: 3 de 1.550 quadros com ângulo impossível, com a mão a 75-128° da palma; 3 descartados na avaliação",
      (len(bad), len(present)) == (3, 1550) and (views[0], views[-1]) == (75, 128) and out["descartados"] == 3,
      f"{views}")
tam = np.array([[a[f].sum() for f in goniometria.FINGERS] for a in A])
calm = min(range(len(tam) - 60), key=lambda i: tam[i:i + 60].std(axis=0).max())
sd = tam[calm:calm + 60].std(axis=0)
check("texto: TAM parado com desvio de 0,5-0,9° por dedo; TAM mediano da mão aberta ~30°",
      0.5 < sd.min() and sd.max() < 0.9 and abs(np.median(tam[calm:calm + 60, 1:]) - 30) < 1, f"{np.round(sd, 2)}")
check("texto: tremor da mão saudável parada ~1,2 mm, sem oscilação rítmica",
      abs(out["mao_inteira"]["tremor"]["rms_mm"] - 1.2) < 0.05 and not out["mao_inteira"]["tremor"]["ritmico"])
openf = [a for a in A if goniometria.plausible(a) and max(a[f].sum() for f in goniometria.FINGERS[1:]) < 60]
check("texto: mão aberta (TAM < 60°): PIP até 44°, MCP até -45°",
      round(max(max(a[f][1] for f in goniometria.FINGERS[1:]) for a in openf)) == 44
      and round(min(min(a[f][0] for f in goniometria.FINGERS[1:]) for a in openf)) == -45)
sizes = [medidas.hand_image_size(r["img"], r["aspect"] or 1) for r in present]
check("texto: tamanho da mão na imagem com mediana 0,27 (P10-P90 0,23-0,29)",
      round(np.median(sizes), 2) == 0.27 and round(np.percentile(sizes, 10), 2) == 0.23
      and round(np.percentile(sizes, 90), 2) == 0.29)

# tabela da suavização no README (EMA + Kalman aplicada também nas medidas)
from manumetria.calculo import filtros  # noqa: E402
smooth = analisar(rows, filtro=filtros.registro(filtros.CASCATA, nas_medidas=True)).results(rows[-1]["t"], "g")["dedos"]
readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
missing = []
for f in goniometria.FINGERS:
    a, b = out["dedos"][f], smooth[f]
    pa, pb = a["qualidade"]["peak_velocity"], b["qualidade"]["peak_velocity"]
    line = (f"| {goniometria.NAME[f]} | {a['movimentos']} → {b['movimentos']} | {a['pct_normal'] * 100:.0f} → "
            f"{b['pct_normal'] * 100:.0f} | {pa:.0f} → {pb:.0f} ({(pb / pa - 1) * 100:+.0f}%) |").replace("-", "−")
    if line not in readme:
        missing.append(line)
mcp = (out["dedos"]["index"]["articulacoes"][0]["max"], smooth["index"]["articulacoes"][0]["max"])
check("README: tabela da suavização e MCP do indicador conferidas na gravação", not missing
      and f"{mcp[0]:.1f}° para {mcp[1]:.1f}°".replace(".", ",") in readme, f"{missing} {mcp}")

# afirmações sem evidência no repositório, ou que não valem para o método de cálculo em uso
from manumetria.interface import glossario  # noqa: E402
from manumetria.interface.telas import ajuda  # noqa: E402
from manumetria.relatorios import pdf  # noqa: E402
texts = (pdf.METHOD_NOTE + ajuda.help_html() + " ".join(" ".join(t) for t in glossario.TERMS.values())
         + " ".join(" ".join(r) for r in planilha.SESSION_COLUMNS) + str(planilha.FINGER_DESCRIPTIONS)
         + open(os.path.join(ROOT, "README.md"), encoding="utf-8").read())
gone = ("entre 5° e 15°", "6° a 36°", "cerca de 1 mm de ruído", "abaixo de −3", "no plano do movimento",
        "10 a 23%", "10% a 23%", "média de 8 quadros e fica abaixo", "contam como 0° (erro de medida)",
        "parte do desvio entra como flexão")
check("textos sem afirmações sem fonte ou que deixaram de valer", not [g for g in gone if g in texts],
      f"{[g for g in gone if g in texts]}")

print("\n" + ("Todos os testes passaram." if not failures else f"{len(failures)} falha(s): {failures}"))
sys.exit(1 if failures else 0)
