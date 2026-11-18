"""
Testes da suavização do sinal (manumetria/calculo/filtros.py) e do seu uso no motor da
avaliação (manumetria/avaliacao/motor.py): EMA, Kalman e a cascata EMA -> Kalman com os
parâmetros da implementação de referência (docs/METODOLOGIA.md).

    .venv\\Scripts\\python.exe tests\\test_filtros.py
"""

import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from manumetria.avaliacao.motor import Avaliador, analisar  # noqa: E402
from manumetria.avaliacao.resultados import smoothing_text  # noqa: E402
from manumetria.calculo import filtros, geometria, goniometria  # noqa: E402
from manumetria.captura import gravacao  # noqa: E402
from manumetria.dados import recalculo  # noqa: E402

FPS = 30
MODES = list(filtros.MODOS)
ON = [filtros.EMA_MODO, filtros.KALMAN_MODO, filtros.CASCATA]
failures = []


def check(name, ok, detail=""):
    print(f"[{'ok' if ok else 'FALHOU'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def run(mode, signal):
    f = filtros.criar(filtros.registro(mode))
    return np.array([f.update(v) for v in signal])


# ------------------------------------------- fidelidade às equações da referência
def paper_series(signal, alpha, q, r, use_ema=True, use_kalman=True):
    """Transcrição literal de SeriesFilter.update / update_ema_only / update_kalman_only
    (smoothing.py do repositório computer-vision-based-hand-kinematic-assessment)."""
    ema, x, p, out = None, None, 1.0, []
    for raw in signal:
        if use_ema:
            ema = raw if ema is None else alpha * raw + (1.0 - alpha) * ema
            z = ema
        else:
            z = raw
        if not use_kalman:
            out.append(z)
            continue
        if x is None:
            x = z
            out.append(x)
            continue
        p_minus = p + q
        k = p_minus / (p_minus + r)
        x = x + k * (z - x)
        p = (1.0 - k) * p_minus
        out.append(x)
    return np.array(out)


rng = np.random.default_rng(7)
sig = 40 + 30 * np.sin(np.linspace(0, 12, 400)) + rng.normal(0, 2, 400)
a, q, r = filtros.EMA_ALPHA, filtros.KALMAN_Q, filtros.KALMAN_R
check("parâmetros da referência: alfa 0,30, Q 0,01, R 0,10, P0 1,0",
      (a, q, r, filtros.KALMAN_P0) == (0.30, 0.01, 0.10, 1.0))
check("modo padrão = EMA + Kalman", filtros.PADRAO == "ema_kalman")
for mode, (e, k) in {"ema": (True, False), "kalman": (False, True), "ema_kalman": (True, True)}.items():
    diff = np.abs(run(mode, sig) - paper_series(sig, a, q, r, e, k)).max()
    check(f"{mode}: igual à implementação de referência", diff < 1e-12, f"maior diferença {diff:.1e}")

# o Kalman converge para o ganho estável calculado
kal = filtros.Kalman()
for v in sig:
    kal.update(v)
check("Kalman: ganho converge para o valor estável",
      abs(kal.k - filtros.ganho_kalman_estavel()) < 1e-9, f"K = {kal.k:.4f}")

# ------------------------------------------------------- propriedades básicas
const = np.full(200, 37.5)
for mode in MODES:
    check(f"{mode}: sinal constante passa sem mudar", np.abs(run(mode, const) - 37.5).max() < 1e-9)

step = np.r_[np.zeros(20), np.full(200, 50.0)]
for mode in ON:
    out = run(mode, step)
    settled = int(np.argmax(np.abs(out - 50.0) < 0.5))
    check(f"{mode}: degrau converge", abs(out[-1] - 50.0) < 1e-3 and out[20] < 50.0,
          f"a 0,5° do degrau em {settled - 20} quadros")

noise = rng.normal(0, 3.0, 5000)
var = {mode: float(np.var(run(mode, noise)[50:])) for mode in MODES}
for mode in ON:
    check(f"{mode}: ruído branco tem a variância reduzida", var[mode] < 0.5 * var["desligada"],
          f"{var[mode] / var['desligada'] * 100:.0f}% da variância dos dados brutos")
check("cascata reduz mais que cada filtro sozinho",
      var["ema_kalman"] < min(var["ema"], var["kalman"]))

for mode in ON:
    f = filtros.criar(filtros.registro(mode))
    for v in (10, 20, 30, 40):
        f.update(v)
    f.reset()
    fresh = filtros.criar(filtros.registro(mode))
    seq = [90.0, 70.0, 75.0, 60.0]
    after = [f.update(v) for v in seq]
    check(f"{mode}: reset zera o estado", after[0] == 90.0 and after == [fresh.update(v) for v in seq])

angles = {"index": np.array([10.0, 20.0, 30.0]), "thumb": np.array([5.0, 6.0])}
bank = filtros.BancoFiltros(filtros.registro(filtros.DESLIGADA))
check("Desligada: devolve os dados brutos", all(np.array_equal(bank.aplicar(angles)[k], v) for k, v in angles.items()))
bank = filtros.BancoFiltros(filtros.registro(filtros.CASCATA))
bank.aplicar(angles)
out = bank.aplicar({"index": np.array([20.0, 20.0, 20.0]), "thumb": np.array([5.0, 6.0])})
check("um filtro independente por articulação",
      out["index"][0] > 10 and out["index"][2] < 30 and np.allclose(out["thumb"], [5.0, 6.0]))
bank.reset()
check("banco: reset zera o estado", np.array_equal(bank.aplicar(angles)["index"], angles["index"]))


reg = filtros.registro("ema_kalman")
check("registro guarda modo, parâmetros e onde se aplica (padrão: só na exibição)",
      reg == {"modo": "ema_kalman", "nome": "EMA + Kalman", "nas_medidas": False, "ema_alpha": 0.3,
              "kalman_q": 0.01, "kalman_r": 0.1, "kalman_p0": 1.0, "kalman_modelo": "posição constante"})
check("registro com nas_medidas", filtros.registro("ema", nas_medidas=True)["nas_medidas"] is True
      and filtros.registro("desligada", nas_medidas=True)["nas_medidas"] is False)
check("avaliação sem registro = Desligada", filtros.registro_de(None)["modo"] == "desligada"
      and smoothing_text({}).startswith("Desligada"))
check("registro sem nas_medidas = só na exibição",
      filtros.registro_de({"modo": "ema_kalman"})["nas_medidas"] is False)
check("texto do filtro diz onde foi aplicado",
      "só na exibição" in smoothing_text({"filtro": reg}) and "também nas medidas" in
      smoothing_text({"filtro": filtros.registro("ema_kalman", nas_medidas=True)}),
      smoothing_text({"filtro": reg}))


# ------------------------------------------------- no motor: ao vivo x recálculo
def sequence():
    """Quadros a 30 fps: calibração parada, depois abrir e fechar; com falha curta
    (segura), perda longa da mão, pausa e recalibração no meio."""
    rng = np.random.default_rng(11)
    frames, t = [], 100.0
    for i in range(int(40 * FPS)):
        s = i / FPS
        present = not (8.0 <= s < 8.1 or 14.0 <= s < 15.5)          # 3 quadros / 1,5 s sem mão
        raw = {"t": t, "world": None, "img": None, "confidence": 0.0, "handedness": None, "aspect": 4 / 3}
        if present:
            cyc = 0.0 if s < 4 else (1 - np.cos(2 * np.pi * 0.4 * (s - 4))) / 2
            world = geometria.build_hand_world([3 + 85 * cyc] * 4, 3 + 30 * cyc) + rng.normal(0, 0.00015, (21, 3))
            raw.update(world=world.astype(np.float32).astype(float), img=world[:, :2] + 0.5,
                       confidence=0.95, handedness="Right")
        frames.append(raw)
        t += 1 / FPS
    return frames


def live(mode, in_measures=False):
    av = Avaliador(filtro=mode, nas_medidas=in_measures)
    states = []
    for i, raw in enumerate(sequence()):
        s = i / FPS
        if abs(s - 20.0) < 1e-9 or abs(s - 22.0) < 1e-9:              # pausa de 2 s
            av.toggle_pause(raw["t"])
        if abs(s - 27.0) < 1e-9:                                        # recalibração
            av.recalibrate(raw["t"])
        before = {d: [vars(x).copy() if hasattr(x, "__dict__") else None for x in fs]
                  for d, fs in av.filtro._filtros.items()}
        passo = av.step(raw, raw["t"])
        states.append(passo.state)
        if passo.state == "segurando":
            after = {d: [vars(x).copy() if hasattr(x, "__dict__") else None for x in fs]
                     for d, fs in av.filtro._filtros.items()}
            if repr(after) != repr(before):
                states.append("mudou")
    return av, states


def saved(av):
    with tempfile.TemporaryDirectory() as tmp:
        gravacao.save_recording(os.path.join(tmp, "p.npz"), av.frames)
        return gravacao.load_recording(os.path.join(tmp, "p.npz"))


MEASURES = ("dedos", "mao_inteira", "confiabilidade")
same = lambda res: {k: res[k] for k in MEASURES + ("filtro",)}
results = {}
for in_measures in (False, True):
    where = "nas medidas" if in_measures else "só exibição"
    for mode in MODES:
        av, kinds = live(mode, in_measures)
        rows = saved(av)
        res = av.results(rows[-1]["t"], "")
        results[mode, in_measures] = res
        again = analisar(rows, filtro=res["filtro"]).results(rows[-1]["t"], "")   # como o recálculo
        check(f"{mode} ({where}): recalcular a partir dos pontos dá o mesmo resultado do ao vivo",
              same(res) == same(again), f"{sum(d['movimentos'] for d in res['dedos'].values())} movimentos")
        check(f"{mode} ({where}): o filtro registrado é o usado", res["filtro"]["modo"] == mode
              and res["filtro"]["nas_medidas"] == (in_measures and mode != "desligada"))
        if mode in ON:
            check(f"{mode} ({where}): quadros \"segurando\" não atualizam o filtro",
                  "segurando" in kinds and "mudou" not in kinds)
check("perda longa da mão zera o filtro", not Avaliador(filtro="ema_kalman").filtro._filtros and
      "perdida" in live("ema_kalman")[1])

raw_res = {k: results["desligada", False][k] for k in MEASURES}
for mode in ON:
    check(f"{mode} só na exibição: medidas iguais às dos dados brutos",
          {k: results[mode, False][k] for k in MEASURES} == raw_res)
ref = results["desligada", False]["dedos"]["index"]["articulacoes"][1]["max"]
filt = results["ema_kalman", True]["dedos"]["index"]["articulacoes"][1]["max"]
check("filtro nas medidas muda as medidas (pico da PIP mais baixo)", filt < ref,
      f"PIP máx {ref:.1f}° -> {filt:.1f}°")


def watch(in_measures):
    """Passa a sequência guardando, a cada quadro da avaliação, o que entrou no filtro,
    o que saiu, o que a Session recebeu e o que a exibição recebeu."""
    av = Avaliador(filtro="ema_kalman", nas_medidas=in_measures)
    calls = []
    apply = av.filtro.aplicar
    av.filtro.aplicar = lambda angles: calls.append((angles, apply(angles))) or calls[-1][1]
    out = []
    for raw in sequence()[: 12 * FPS]:
        hand, phase = av.stab.hand, av.phase       # o quadro que termina a calibração não vai à sessão
        calls.clear()
        av.step(raw, raw["t"])
        if calls and phase == "avaliacao":
            given, smooth = calls[-1]
            out.append((goniometria.joint_angles(raw["world"], hand), given, smooth, av))
            out[-1] = out[-1][:3] + (av.session.trackers["index"].joints.copy(), av.display["index"].copy(),
                                     av.display_history[-1][1][1], av.session.history[-1][1][1])
    return out


ok_in, ok_tela, ok_brutos, ok_hist, differ = True, True, True, True, 0
for raw_a, given, smooth, session_j, shown, hist_tam, sess_tam in watch(False):
    ok_in &= bool(np.allclose(given["index"], raw_a["index"]))               # o filtro recebe os dados brutos
    ok_tela &= bool(np.array_equal(shown, smooth["index"]))                  # a tela recebe o suavizado
    ok_brutos &= bool(np.array_equal(session_j, raw_a["index"]))             # a Session, os dados brutos
    ok_hist &= abs(hist_tam - smooth["index"].sum()) < 1e-9 and abs(sess_tam - raw_a["index"].sum()) < 1e-9
    differ += not np.allclose(shown, session_j)
n = len(watch(False))
check("padrão: a tela recebe os valores suavizados (Agora, dica da mão 3D)", ok_in and ok_tela and n > 100,
      f"{n} quadros")
check("padrão: a Session recebe os dados brutos", ok_brutos and differ > 0.9 * n,
      f"{differ} quadros com exibição diferente da medida")
check("padrão: gráfico do TAM com o suavizado; a Session guarda o TAM dos dados brutos", ok_hist)
ok = all(np.array_equal(session_j, smooth["index"]) and np.array_equal(shown, smooth["index"])
         for _, _, smooth, session_j, shown, _, _ in watch(True))
check("nas_medidas: Session e tela recebem os ângulos suavizados", ok)

# ------------------------------------------------------------- recálculo salvo
av, _ = live("desligada")
rows = saved(av)
old = av.results(rows[-1]["t"], "")
del old["filtro"]                                  # avaliação anterior aos filtros
new = recalculo._recalculate(old, rows)
check("recálculo: avaliação sem registro fica com os dados brutos e não muda",
      new["dedos"] == old["dedos"] and "filtro" not in new)
for in_measures in (False, True):
    av, _ = live("ema", in_measures)
    rows = saved(av)
    old = av.results(rows[-1]["t"], "")
    new = recalculo._recalculate(old, rows)
    check(f"recálculo: usa o filtro registrado (nas_medidas = {in_measures})",
          new["dedos"] == old["dedos"] and new["filtro"] == old["filtro"])
old = av.results(rows[-1]["t"], "")                # registrado nas medidas, mas gravado sem a chave
old["filtro"] = {k: v for k, v in old["filtro"].items() if k != "nas_medidas"}
new = recalculo._recalculate(old, rows)
check("recálculo: registro sem nas_medidas = medidas com os dados brutos",
      new["dedos"] == analisar(rows, filtro="desligada").results(rows[-1]["t"], "")["dedos"])


# ------------------- padrão (só na exibição) = Desligada, na gravação de referência
# Com a suavização só na exibição ao vivo, as medidas têm de ser idênticas às do modo Desligada
# no mesmo código: o filtro não pode vazar para as medidas (os números absolutos da gravação
# são conferidos em tests/test_reorganizacao.py).
RECORDING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "gravacao_referencia.npz")
rows = gravacao.load_recording(RECORDING)
desligada = analisar(rows, filtro=filtros.DESLIGADA).results(rows[-1]["t"], "gravação")
app_default = Avaliador(filtro=filtros.PADRAO, nas_medidas=False)   # o que a tela usa no padrão
for raw in rows:
    app_default.step(raw, raw["t"])
for name, res in (("analisar", analisar(rows).results(rows[-1]["t"], "gravação")),
                  ("tela no padrão", app_default.results(rows[-1]["t"], "gravação"))):
    check(f"padrão ({name}): na gravação de referência, medidas idênticas às do modo Desligada "
          "(dedos, mão inteira, confiabilidade)",
          {k: res[k] for k in MEASURES} == {k: desligada[k] for k in MEASURES})

print("\n" + ("Todos os testes passaram." if not failures else f"{len(failures)} falha(s): {failures}"))
sys.exit(1 if failures else 0)
