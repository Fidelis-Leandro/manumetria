"""
Resultado de uma sessão como dicionário simples (números, textos e listas).
É o mesmo formato que vai para o banco (JSON), para o relatório e para o CSV,
então uma sessão salva semanas atrás é lida exatamente como uma recém-feita.
"""

from manumetria.calculo import filtros, goniometria, medidas
from manumetria.versao import GONIOMETRIA, VERSAO as APP_VERSION

# Formato do resultado (gravado em "versao"). Os três são lidos; o campo que um formato
# não tem é lido como ausente.
#   formato 1: repetições, amplitude e qualidade do movimento por dedo.
#   formato 2: mais arco funcional, Strickland, polpa-palma, velocidade de pico,
#              suavidade, tendências, mão inteira, tremor, confiabilidade e pontos gravados.
#   formato 3: mais "versao_app" (versão do ManuMetria que calculou as medidas),
#              "goniometria" (método dos ângulos) e "fuso_utc" (fuso do horário de
#              "inicio", ex.: "-03:00"). Sem eles, o método do cálculo não está registrado.
VERSION = 3
HAND_NAMES = {"Right": "Mão direita", "Left": "Mão esquerda"}
CALIBRATION_NAMES = {"completa": "medida na calibração",
                     "aproximada": "aproximada (a mão não ficou parada)",
                     "padrao": "valor padrão (sem calibração)"}


def finger_results(tr, tpd=None):
    """FingerTracker -> dicionário do dedo (também usado no reteste)."""
    counts = tr.counts()
    deficits, arcs, contrib = tr.deficits(), tr.arcs(), tr.contribution()

    def at(arr, i):
        return None if arr is None else float(arr[i])

    joints = []
    for i, n in enumerate(tr.joint_names):
        mn, mx = at(tr.min_joints, i), at(tr.max_joints, i)
        joints.append({"nome": n, "min": mn, "max": mx, "deficit": at(deficits, i), "arco": at(arcs, i),
                       "contribuicao": at(contrib, i), "normal": float(tr.normal_joints[i]),
                       "arco_funcional": medidas.functional_coverage(tr.finger, n, mn, mx)})
    active = tr.active_tam()
    return {
        "movimentos": sum(counts.values()), "parciais": counts["parcial"],
        "completas": counts["completa"],
        "tam_ativo": None if active is None else max(0.0, active),
        "pct_normal": tr.percent_normal(), "tam_max": tr.max_tam, "normal": float(tr.normal),
        "articulacoes": joints, "independencia": tr.independence(),
        "acoplamento": tr.coupling(), "qualidade": tr.quality(),
        "strickland": medidas.strickland(tr.finger, tr.max_joints, deficits),
        "polpa_palma_cm": tpd,
        "amplitudes": [round(float(r.amplitude), 1) for r in tr.reps],
        "tipos": [r.kind for r in tr.reps], "sensibilidade": float(tr.sens),
    }


def session_results(session, *, start, duration_s, hand, calibrated, source,
                    hand_measures=None, tremor=None, reliability=None, points=None, smoothing=None):
    """sessao.Session + dados da sessão -> dicionário serializável em JSON.
    smoothing = registro do filtro de suavização usado (calculo/filtros.py)."""
    calib = {True: "completa", "aproximada": "aproximada", False: "padrao"}[calibrated]
    whole = hand_measures.results() if hand_measures is not None else None
    tpd = (whole or {}).get("polpa_palma_cm", {})
    fingers = {f: finger_results(session.trackers[f], tpd.get(f)) for f in goniometria.FINGERS}
    if whole is not None:
        whole = {k: v for k, v in whole.items() if k != "polpa_palma_cm"}   # já vai em cada dedo
        whole["tremor"] = tremor.result() if tremor is not None else None
    return {"versao": VERSION, "versao_app": APP_VERSION, "goniometria": GONIOMETRIA,
            "inicio": start.isoformat(timespec="seconds"), "fuso_utc": utc_offset(start),
            "duracao_s": int(duration_s), "mao": hand, "calibracao": calib, "fonte": source,
            "pontos": points, "descartados": int(session.discarded),
            "filtro": dict(smoothing) if smoothing else filtros.registro(filtros.DESLIGADA),
            "confiabilidade": reliability, "mao_inteira": whole, "dedos": fingers}


def utc_offset(moment):
    """Fuso do horário local de `moment` (datetime sem fuso), ex.: "-03:00"."""
    off = moment.astimezone().utcoffset()
    minutes = int(off.total_seconds() // 60)
    sign = "-" if minutes < 0 else "+"
    return f"{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"


def retest_summary(results):
    """Só o que o reteste precisa guardar: flexões máx./mín. e TAM de cada dedo."""
    return {"inicio": results["inicio"], "duracao_s": results["duracao_s"],
            "confiabilidade": results.get("confiabilidade"),
            "dedos": {f: {"tam_ativo": d["tam_ativo"], "pct_normal": d["pct_normal"],
                          "articulacoes": [{"nome": j["nome"], "min": j["min"], "max": j["max"]}
                                           for j in d["articulacoes"]]}
                      for f, d in results["dedos"].items()}}


def _br(v):
    return f"{v:g}".replace(".", ",")


def smoothing_name(results):
    """Filtro registrado na avaliação com os parâmetros, ex.: "EMA + Kalman (α = 0,3; ...)".
    Sem registro (avaliação anterior aos filtros) = Desligada."""
    reg = filtros.registro_de(results.get("filtro"))
    params = []
    if "ema_alpha" in reg:
        params.append(f"α = {_br(reg['ema_alpha'])}")
    if "kalman_q" in reg:
        params += [f"Q = {_br(reg['kalman_q'])}", f"R = {_br(reg['kalman_r'])}",
                   f"P0 = {_br(reg['kalman_p0'])}"]
    return reg["nome"] + (f" ({'; '.join(params)})" if params else "")


def smoothing_in_measures(results):
    """True se o filtro registrado entrou nas medidas (não só na exibição ao vivo)."""
    return filtros.registro_de(results.get("filtro"))["nas_medidas"]


def smoothing_text(results):
    """Filtro registrado e onde foi aplicado, em texto (CSV, exportação)."""
    reg = filtros.registro_de(results.get("filtro"))
    if reg["modo"] == filtros.DESLIGADA:
        return "Desligada (medidas e exibição com os dados brutos)"
    if reg["nas_medidas"]:
        return f"{smoothing_name(results)}, aplicada também nas medidas"
    return f"{reg['nome']} só na exibição ao vivo; medidas com os dados brutos"


def mean_pct(results):
    """% do normal médio dos dedos com dado (None se nenhum)."""
    vals = [d["pct_normal"] for d in results["dedos"].values() if d["pct_normal"] is not None]
    return sum(vals) / len(vals) if vals else None


def total_moves(results):
    """Total de movimentos contados (todas as classes, todos os dedos)."""
    return sum(d["movimentos"] for d in results["dedos"].values())


def deficit_total(finger):
    """Soma dos déficits de extensão das articulações do dedo (°); None sem dados."""
    vals = [j["deficit"] for j in finger["articulacoes"] if j["deficit"] is not None]
    return sum(vals) if vals else None
