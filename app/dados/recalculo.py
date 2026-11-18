"""
Recalcular avaliações salvas a partir dos pontos da mão gravados, com o
cálculo atual (ex.: depois de corrigir uma conta ou acrescentar uma medida).

Só as avaliações com pontos gravados (salvas a partir de 15/10/2026) podem ser
recalculadas. Data, duração, fonte e observações não mudam; os resultados
anteriores ficam guardados dentro da avaliação, em "original".

Cada avaliação é recalculada com o filtro de suavização registrado nela
("filtro", com "nas_medidas"): as medidas usam os dados brutos, a não ser que
o filtro tenha sido aplicado também nas medidas. As que não têm registro
(anteriores aos filtros) são tratadas como "Desligada" e não mudam.
"""

import datetime
import os

from app.avaliador import analisar
from app.dados.resultados import mean_pct, retest_summary
from nucleo import capture
from nucleo import filtros
from nucleo import caminhos

KEEP = ("inicio", "fuso_utc", "duracao_s", "fonte", "pontos")   # dados da sessão, não do cálculo


def preparar(db, progress=None):
    """Recalcula sem gravar. Devolve uma lista de itens:
    {"sessao", "paciente", "novo" (ou None), "motivo", "antes", "depois", "maior_diferenca"}.
    progress(i, total) é chamado a cada avaliação (para a tela não parecer travada)."""
    patients = {p["id"]: p["identificacao"] for p in db.pacientes("")}
    sessions = db.todas_sessoes()
    items = []
    for i, s in enumerate(sessions):
        if progress:
            progress(i, len(sessions))
        old = s["resultados"]
        item = {"sessao": s, "paciente": patients.get(s["paciente_id"], ""), "novo": None,
                "antes": mean_pct(old), "depois": None, "maior_diferenca": None}
        path = caminhos.absoluto(old["pontos"], caminhos.ROOT) if old.get("pontos") else None
        if not path:
            item["motivo"] = "sem pontos gravados"
        elif not os.path.exists(path):
            item["motivo"] = "pontos não encontrados"
        else:
            item["novo"] = _recalculate(old, capture.load_recording(path))
            item["depois"] = mean_pct(item["novo"])
            item["maior_diferenca"] = _largest_joint_change(old, item["novo"])
            item["motivo"] = "pronta para atualizar"
        items.append(item)
    return items


def _recalculate(old, rows):
    main = [r for r in rows if not r["fase"].startswith("reteste_")]
    reg = filtros.registro_de(old.get("filtro"))     # o filtro usado na própria avaliação
    new = analisar(main, filtro=reg).results(main[-1]["t"], old.get("fonte", ""))
    for key in KEEP:          # "versao_app" e "goniometria" ficam os do cálculo novo
        if key in old:
            new[key] = old[key]
        else:                 # ex.: fuso não registrado (salva antes da 1.3.0): não inventa
            new.pop(key, None)
    if "filtro" not in old:                          # sem registro: fica como estava
        new.pop("filtro", None)
    if old.get("reteste"):
        again = [r for r in rows if r["fase"].startswith("reteste_")]
        if again:
            rt = retest_summary(analisar(again, retest=True, filtro=reg).results(again[-1]["t"], ""))
            rt["inicio"] = old["reteste"].get("inicio", rt["inicio"])
            new["reteste"] = rt
    new["original"] = old.get("original") or {k: v for k, v in old.items() if k != "original"}
    new["recalculado_em"] = datetime.datetime.now().isoformat(timespec="seconds")
    return new


def _largest_joint_change(old, new):
    """Maior diferença (°) entre os resultados antigos e novos, nas flexões máx./mín."""
    diffs = [abs(jn[k] - jo[k])
             for f, d in old["dedos"].items()
             for jo, jn in zip(d["articulacoes"], new["dedos"][f]["articulacoes"])
             for k in ("max", "min") if jo[k] is not None and jn[k] is not None]
    return max(diffs) if diffs else None


def aplicar(db, items):
    """Grava os resultados recalculados. Devolve quantas avaliações mudaram."""
    done = 0
    for item in items:
        if item["novo"] is not None:
            db.atualizar_resultados(item["sessao"]["id"], item["novo"])
            done += 1
    return done
