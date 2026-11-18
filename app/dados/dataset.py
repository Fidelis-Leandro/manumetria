"""
Exportação "Dataset para pesquisa": uma pasta com tabelas ligadas por IDs,
pseudonimizada, reprodutível e documentada.

    pacientes.csv            uma linha por paciente (id_pesquisa, sem nome nem data de nascimento)
    avaliacoes.csv           uma linha por avaliação
    dedos.csv                uma linha por avaliação x etapa (avaliação/reteste) x dedo
    repeticoes.csv           uma linha por repetição
    quadros/<id>.csv.gz      uma linha por quadro gravado (um arquivo por avaliação)
    dicionario_de_dados.csv  arquivo, coluna, descrição, unidade, tipo, valores, faltante
    LEIA-ME.md               estrutura, métodos, versão, avisos
    checksums.sha256         SHA-256 de todos os arquivos

Formato: UTF-8 sem BOM, vírgula entre campos, ponto decimal, fim de linha "\\n",
nomes de colunas em snake_case sem acento, faltante = campo vazio, sim/não = 1/0.
Os .csv.gz são gravados com data zerada no cabeçalho: o mesmo banco gera os mesmos
bytes (só o LEIA-ME e os checksums mudam, pela data da exportação).

As medidas das avaliações com pontos gravados são RECALCULADAS dos pontos com o
cálculo desta versão (o mesmo motor da tela, app/avaliador.py), para que dedos.csv,
repeticoes.csv e quadros.csv venham do mesmo cálculo e possam ser conferidos uns
contra os outros. avaliacoes.csv diz se o recálculo confere com o que foi salvo
(e mostrado no relatório e no PDF) e a maior diferença. Sem pontos, as medidas
são as salvas (sem repetições nem quadros). O banco não é alterado.
"""

import csv
import datetime
import gzip
import hashlib
import io
import math
import os
from dataclasses import dataclass

import numpy as np

from app.avaliador import analisar
from app.dados.resultados import retest_summary
from app.versao import GONIOMETRIA, GONIOMETRIA_TEXTO, VERSAO
from nucleo import caminhos, capture, filtros
from nucleo import kinematics as kin

DECIMALS = 4                     # casas decimais dos números (ângulos: 0,0001°)
LANDMARK_DECIMALS = 6            # coordenadas (m): micrômetro (os pontos são guardados em float32)
FINGER = {"thumb": "polegar", "index": "indicador", "middle": "medio", "ring": "anelar", "pinky": "minimo"}
SLOTS = [("mcp", ("MCP",)), ("pip_ou_ip", ("PIP", "IP")), ("dip", ("DIP",))]
HAND = {"Right": "direita", "Left": "esquerda"}
LANDMARKS = ["punho", "polegar_cmc", "polegar_mcp", "polegar_ip", "polegar_ponta",
             "indicador_mcp", "indicador_pip", "indicador_dip", "indicador_ponta",
             "medio_mcp", "medio_pip", "medio_dip", "medio_ponta",
             "anelar_mcp", "anelar_pip", "anelar_dip", "anelar_ponta",
             "minimo_mcp", "minimo_pip", "minimo_dip", "minimo_ponta"]
JOINT_COLUMNS = [(f, i, f"{FINGER[f]}_{name.lower()}") for f in kin.FINGERS
                 for i, (name, _) in enumerate(kin.JOINTS[f])]
# tolerância da conferência "salvo x recalculado": os pontos ficam em float32 (diferença
# relativa de até ~3e-5 nos ângulos, medida nas 22 avaliações de demonstração)
MATCH_ABS, MATCH_REL = 1e-3, 1e-4
IGNORE_IN_MATCH = {"original", "recalculado_em", "versao", "versao_app", "goniometria", "fuso_utc",
                   "inicio", "fonte", "pontos", "filtro"}


@dataclass
class Opcoes:
    """Escolhas de quem exporta (padrão: o mínimo necessário, LGPD)."""
    incluir_texto_livre: bool = False   # condição/diagnóstico do cadastro em pacientes.csv
    datas_exatas: bool = False          # data e hora de início em avaliacoes.csv
    incluir_imagem: bool = False        # coordenadas 2D dos pontos na imagem em quadros


# =============================================================================
# formatação
# =============================================================================
def num(v, decimals=DECIMALS):
    """Número -> texto com ponto decimal; None/NaN -> vazio; bool -> 1/0."""
    if v is None:
        return ""
    if isinstance(v, (bool, np.bool_)):
        return "1" if v else "0"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    v = float(v)
    if not math.isfinite(v):
        return ""
    text = f"{round(v, decimals) + 0.0:.{decimals}f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def pct(v):
    return None if v is None else v * 100.0


def flag(v):
    return "" if v is None else ("1" if v else "0")


def _csv_bytes(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def _write_gz(path, data):
    """gzip sem nome nem data no cabeçalho: mesmo conteúdo = mesmos bytes."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as gz:
        gz.write(data)


# =============================================================================
# idade, datas, fonte
# =============================================================================
def idade_anos(nascimento, data_avaliacao):
    """(data da avaliação - data de nascimento) em anos de 365,25 dias, 1 casa decimal.
    None se faltar a data de nascimento ou ela for inválida."""
    if not nascimento:
        return None
    try:
        born = datetime.date.fromisoformat(nascimento[:10])
    except ValueError:
        return None
    return round((data_avaliacao - born).days / 365.25, 1)


def _source_kind(fonte):
    """Tipo da fonte, sem o texto livre (o nome da gravação pode ter um caminho)."""
    f = (fonte or "").lower()
    if f.startswith("câmera") or f.startswith("camera"):
        return "camera"
    if f.startswith("simula"):
        return "simulacao"
    if f.startswith("grava"):
        return "gravacao"
    return "outra" if f else ""


# =============================================================================
# repassar os pontos pelo motor, registrando cada quadro
# =============================================================================
class _Replay:
    """Uma etapa (avaliação ou reteste) passada pelo motor com o registro de cada quadro."""

    def __init__(self, rows, index0, t0, retest, reg, fonte):
        self.frames = []
        self.index0, self.t0 = index0, t0
        self.av = analisar(rows, retest=retest, filtro=reg, por_quadro=self._on_frame)
        self.results = self.av.results(rows[-1]["t"], fonte)
        final = self.av.n_sessao
        for fr in self.frames:          # só a última Session entra nas medidas (outra mão = nova)
            fr["entra"] = fr["medido"] and fr["n_sessao"] == final

    def _on_frame(self, raw, passo, av):
        q = av.quadro
        hand = q["lado_angulos"]
        view = None
        if raw["world"] is not None and hand in ("Right", "Left"):
            view = kin.view_angle(raw["world"], hand)
        self.frames.append({
            "raw": raw, "fase": q["fase"],
            "lado_angulos": hand, "estado": q["estado"], "descartado": q["descartado"],
            "vista_ruim": q["vista_ruim"], "angulo_vista": view, "angulos": q["angulos"],
            "suavizados": q["suavizados"], "medido": q["medido"] is not None,
            "n_sessao": av.n_sessao, "pausado": q["pausado"]})


def _split(rows):
    main = [r for r in rows if not r["fase"].startswith("reteste_")]
    again = [r for r in rows if r["fase"].startswith("reteste_")]
    return main, again


def _compare(old, new, path=""):
    """(confere, lista de diferenças) entre resultados salvos e recalculados."""
    diffs = []

    def walk(a, b, p):
        if isinstance(a, dict) and isinstance(b, dict):
            for k in set(a) | set(b):
                if k in IGNORE_IN_MATCH and p == "":
                    continue
                if k not in a or k not in b:
                    diffs.append(p + "/" + k)
                else:
                    walk(a[k], b[k], p + "/" + k)
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                diffs.append(p)
            else:
                for i, (x, y) in enumerate(zip(a, b)):
                    walk(x, y, f"{p}[{i}]")
        elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
            if not math.isclose(a, b, rel_tol=MATCH_REL, abs_tol=MATCH_ABS):
                diffs.append(p)
        elif a != b:
            diffs.append(p)
    walk(old, new, path)
    return not diffs, diffs


def _largest_joint_change(old, new):
    """Maior diferença (°) nas flexões máx./mín. entre salvo e recalculado (avaliação e reteste)."""
    diffs = []
    for key in ("dedos",):
        for f, d in (old.get(key) or {}).items():
            for jo, jn in zip(d["articulacoes"], new[key][f]["articulacoes"]):
                diffs += [abs(jn[k] - jo[k]) for k in ("max", "min") if jo[k] is not None and jn[k] is not None]
    ro, rn = old.get("reteste") or {}, new.get("reteste") or {}
    for f, d in (ro.get("dedos") or {}).items():
        for jo, jn in zip(d["articulacoes"], ((rn.get("dedos") or {}).get(f) or {}).get("articulacoes", [])):
            diffs += [abs(jn[k] - jo[k]) for k in ("max", "min") if jo[k] is not None and jn[k] is not None]
    return max(diffs) if diffs else None


def _evaluate(saved, root):
    """Avaliação salva -> {"main": _Replay, "retest": _Replay|None, "t0", "n_frames"} ou None
    (sem pontos gravados ou arquivo não encontrado)."""
    if not saved.get("pontos"):
        return None
    path = caminhos.absoluto(saved["pontos"], root)
    if not os.path.exists(path):
        return None
    rows = capture.load_recording(path)
    if not rows:
        return None
    reg = filtros.registro_de(saved.get("filtro"))
    main, again = _split(rows)
    t0 = rows[0]["t"]
    out = {"t0": t0, "n_frames": len(rows), "main": _Replay(main, 0, t0, False, reg, saved.get("fonte", "")),
           "retest": None, "settings": None}
    if saved.get("reteste") and again:
        out["retest"] = _Replay(again, len(main), t0, True, reg, "")
    return out


# =============================================================================
# linhas de cada arquivo
# =============================================================================
PATIENT_COLUMNS = [
    ("id_pesquisa", "Pseudônimo do paciente (aleatório, estável entre exportações do mesmo banco; não "
                    "deriva do nome nem da ordem de cadastro)", "", "texto", "P-XXXXXX"),
    ("sexo", "Sexo informado no cadastro", "", "categoria", "feminino; masculino"),
    ("mao_dominante", "Mão dominante (cadastro)", "", "categoria", "direita; esquerda; ambidestro"),
    ("mao_avaliada", "Mão avaliada (cadastro)", "", "categoria", "direita; esquerda; ambas"),
    ("situacao", "Situação no fim da exportação", "", "categoria", "tratamento; alta"),
    ("n_avaliacoes", "Avaliações exportadas do paciente", "avaliações", "inteiro", ">= 0"),
]
FREE_TEXT_COLUMNS = [
    ("condicao", "Condição / diagnóstico (texto livre do cadastro; só com a opção de incluir texto livre)",
     "", "texto", "texto livre"),
]


def _patient_row(p, n, opts):
    lower = lambda v: (v or "").strip().lower()
    row = [p["id_pesquisa"], lower(p.get("sexo")), lower(p.get("mao_dominante")), lower(p.get("mao_avaliada")),
           "alta" if p.get("situacao") == "alta" else "tratamento", n]
    if opts.incluir_texto_livre:
        row.append((p.get("condicao") or "").strip())
    return row


EVAL_COLUMNS = [
    ("id_avaliacao", "Identificador fixo da avaliação: id_pesquisa + código da avaliação no paciente (A01, "
                     "A02...; atribuído ao salvar e nunca renumerado: uma avaliação apagada deixa um buraco)", "",
     "texto", "P-XXXXXX-A01"),
    ("id_pesquisa", "Paciente (liga com pacientes.csv)", "", "texto", "P-XXXXXX"),
    ("ordem_avaliacao", "Ordem da avaliação entre as do paciente (1 = primeira)", "", "inteiro", ">= 1"),
    ("dia_relativo", "Dias desde a primeira avaliação exportada do paciente (0 = primeira)", "dias", "inteiro",
     ">= 0"),
    ("idade_na_avaliacao_anos", "(data da avaliação - data de nascimento) / 365,25, com 1 casa decimal, "
                                "calculada na exportação", "anos", "decimal", ">= 0"),
    ("dias_desde_lesao", "Dias entre a data da lesão ou cirurgia (cadastro) e a avaliação", "dias", "inteiro", ""),
    ("mao_medida", "Mão detectada pela câmera e fixada na calibração", "", "categoria", "direita; esquerda"),
    ("fonte", "Origem dos quadros", "", "categoria", "camera; simulacao; gravacao; outra"),
    ("versao_manumetria_exportacao", "Versão do ManuMetria que gerou esta exportação (e o recálculo)", "",
     "texto", ""),
    ("versao_calculo_salvo", "Versão do ManuMetria que calculou os resultados salvos (vazio = não registrada: "
                             "salvos antes da 1.3.0)", "", "texto", ""),
    ("medidas_origem", "De onde vêm as medidas de dedos.csv: recalculadas dos pontos gravados com a versão "
                       "desta exportação, ou as salvas (sem pontos gravados)", "", "categoria",
     "recalculadas_dos_pontos; salvas"),
    ("confere_com_salvo", f"O recálculo confere com o resultado salvo (e mostrado no relatório/PDF), com "
                          f"tolerância de {MATCH_ABS}° ou {MATCH_REL:.0e} relativo. 0 = o salvo foi calculado "
                          f"por outra versão (veja versao_calculo_salvo)", "", "booleano", "0; 1"),
    ("maior_diferenca_salvo_graus", "Maior diferença entre salvo e recalculado nas flexões máximas e mínimas "
                                    "(avaliação e reteste)", "graus", "decimal", ">= 0"),
    ("metodo_goniometria", "Método dos ângulos das medidas exportadas", "", "categoria",
     f"{GONIOMETRIA}; nao_registrado"),
    ("filtro_modo", "Filtro de suavização registrado na avaliação (sem registro = desligada)", "", "categoria",
     "desligada; ema; kalman; ema_kalman"),
    ("filtro_nas_medidas", "O filtro entrou nas medidas (1) ou só na exibição ao vivo (0: medidas com os "
                           "dados brutos)", "", "booleano", "0; 1"),
    ("filtro_ema_alpha", "Alfa do EMA", "", "decimal", "0-1"),
    ("filtro_kalman_q", "Variância do processo (Q) do Kalman", "graus²", "decimal", "> 0"),
    ("filtro_kalman_r", "Variância da medida (R) do Kalman", "graus²", "decimal", "> 0"),
    ("filtro_kalman_p0", "Covariância inicial (P0) do Kalman", "graus²", "decimal", "> 0"),
    ("calibracao", "Como a sensibilidade foi obtida", "", "categoria", "completa; aproximada; padrao"),
    ("sensibilidade_media_graus", "Média das sensibilidades dos 5 dedos (por dedo em dedos.csv): 3 x desvio "
                                  "padrão do TAM parado na calibração, entre 2 e 30", "graus", "decimal", "2-30"),
    ("duracao_s", "Tempo de avaliação, sem pausas", "s", "inteiro", ">= 0"),
    ("fps_efetivo", "Quadros por segundo efetivos na fase de avaliação: 1 / mediana do intervalo entre quadros "
                    "consecutivos", "quadros/s", "decimal", "> 0"),
    ("fps_camera_mediana", "Mediana do fps informado pela captura (média móvel) na fase de avaliação",
     "quadros/s", "decimal", "> 0"),
    ("quadros_gravados", "Quadros no arquivo de pontos da etapa avaliação (todas as fases)", "quadros",
     "inteiro", ">= 0"),
    ("quadros_avaliacao", "Quadros na fase de avaliação (sem pausas nem recalibração): denominador da "
                          "confiabilidade", "quadros", "inteiro", ">= 0"),
    ("quadros_validos", "Quadros da fase de avaliação que viraram medida (estado ok)", "quadros", "inteiro", ">= 0"),
    ("quadros_validos_pct", "quadros_validos / quadros_avaliacao", "%", "decimal", "0-100"),
    ("quadros_descartados", "Quadros descartados por ângulo impossível (fora de -60° a 130°) na avaliação",
     "quadros", "inteiro", ">= 0"),
    ("quadros_vista_ruim", "Quadros da fase de avaliação com a palma a mais de 60° da câmera", "quadros",
     "inteiro", ">= 0"),
    ("quadros_sem_mao", "Quadros da fase de avaliação sem mão detectada", "quadros", "inteiro", ">= 0"),
    ("quadros_segurando", "Quadros da fase de avaliação em falha curta (pose anterior mantida, sem medida)",
     "quadros", "inteiro", ">= 0"),
    ("quadros_perdidos_estimados", "Quadros que a câmera não entregou, estimados pelos intervalos: soma de "
                                   "arredondar(intervalo / intervalo mediano) - 1", "quadros", "inteiro", ">= 0"),
    ("confiabilidade", "Confiabilidade da captura", "", "categoria", "alta; media; baixa"),
    ("confiabilidade_motivos", "Motivos quando não é alta (texto gerado pelo sistema)", "", "texto", ""),
    ("tem_reteste", "A avaliação tem reteste (medição repetida logo depois)", "", "booleano", "0; 1"),
    ("abertura_ind_med_graus", "Abertura máxima entre indicador e médio (MCP dos dois até 30°)", "graus",
     "decimal", ""),
    ("abertura_med_ane_graus", "Abertura máxima entre médio e anelar", "graus", "decimal", ""),
    ("abertura_ane_min_graus", "Abertura máxima entre anelar e mínimo", "graus", "decimal", ""),
    ("abertura_total_graus", "Soma das três aberturas", "graus", "decimal", ""),
    ("abertura_polegar_graus", "Ângulo máximo entre o metacarpo do polegar e a linha punho-base do indicador",
     "graus", "decimal", ""),
    ("tremor_ritmico", "Oscilação rítmica com a mão parada (pico >= 4x a mediana do espectro 3-12 Hz)", "",
     "booleano", "0; 1"),
    ("tremor_frequencia_hz", "Frequência da oscilação rítmica", "Hz", "decimal", "3-12"),
    ("tremor_rms_mm", "Variação RMS 3D da posição média das pontas dos dedos em relação ao punho, mão parada",
     "mm", "decimal", ">= 0"),
    ("tremor_segundos", "Tempo com a mão parada analisado", "s", "decimal", ">= 0"),
]
EXACT_DATE_COLUMNS = [
    ("data_hora_inicio", "Data e hora de início (ISO 8601, hora local; com o fuso quando registrado). Só com a "
                         "opção de datas exatas", "", "data-hora", "aaaa-mm-ddThh:mm:ss[+hh:mm]"),
]


def _phase_stats(rep):
    """Contagens e fps da fase de avaliação de uma etapa (quadros do motor)."""
    ev = [fr for fr in rep.frames if fr["fase"] == "avaliacao" and not fr["pausado"]]
    t = np.array([fr["raw"]["t"] for fr in ev])
    dt = np.diff(t) if len(t) > 1 else np.array([])
    dt = dt[dt > 0]
    med = float(np.median(dt)) if len(dt) else None
    lost = int(sum(max(0, round(d / med) - 1) for d in dt)) if med else 0
    fps_cam = [fr["raw"]["fps"] for fr in ev if fr["raw"].get("fps") is not None]
    return {"fps_efetivo": 1.0 / med if med else None,
            "fps_camera_mediana": float(np.median(fps_cam)) if fps_cam else None,
            "vista_ruim": sum(fr["vista_ruim"] for fr in ev),
            "sem_mao": sum(fr["raw"]["world"] is None for fr in ev),
            "segurando": sum(fr["estado"] == "segurando" for fr in ev),
            "perdidos": lost}


def _eval_row(e, opts):
    res, saved, p = e["res"], e["saved"], e["patient"]
    reg = filtros.registro_de(saved.get("filtro"))
    rel = res.get("confiabilidade") or {}
    det = rel.get("detalhes") or {}
    whole = res.get("mao_inteira") or {}
    spread = whole.get("abertura_dedos") or [None, None, None]
    tremor = whole.get("tremor") or {}
    sens = [d["sensibilidade"] for d in res["dedos"].values() if d.get("sensibilidade") is not None]
    replay = e["replay"]
    if replay:
        av, st = replay["main"].av, _phase_stats(replay["main"])
        frames_eval, frames_ok = av.counts["frames"], av.counts["ok"]
        n_main = len(replay["main"].frames)
    else:
        st = {k: None for k in ("fps_efetivo", "fps_camera_mediana", "vista_ruim", "sem_mao", "segurando",
                                "perdidos")}
        frames_eval = det.get("quadros")
        frames_ok = (None if frames_eval is None or det.get("validos_pct") is None
                     else round(frames_eval * det["validos_pct"] / 100))
        n_main = None
    injury = p.get("data_lesao")
    row = [e["id"], p["id_pesquisa"], e["ordem"], e["dia"]]
    if opts.datas_exatas:
        row.append(saved["inicio"] + (saved.get("fuso_utc") or ""))
    row += [num(idade_anos(p.get("nascimento"), e["data"]), 1),
            (e["data"] - datetime.date.fromisoformat(injury[:10])).days if injury else "",
            HAND.get(res.get("mao"), ""), _source_kind(saved.get("fonte")), VERSAO,
            saved.get("versao_app") or "", "recalculadas_dos_pontos" if replay else "salvas",
            flag(e["confere"]) if replay else "", num(e["maior_diferenca"]),
            GONIOMETRIA if (replay or saved.get("goniometria")) else "nao_registrado",
            reg["modo"], flag(reg["nas_medidas"]), num(reg.get("ema_alpha"), 6), num(reg.get("kalman_q"), 6),
            num(reg.get("kalman_r"), 6), num(reg.get("kalman_p0"), 6), res.get("calibracao", ""),
            num(sum(sens) / len(sens) if sens else None), res.get("duracao_s"), num(st["fps_efetivo"], 2),
            num(st["fps_camera_mediana"], 2), n_main if n_main is not None else "",
            "" if frames_eval is None else frames_eval, "" if frames_ok is None else frames_ok,
            num(None if not frames_eval or frames_ok is None else 100.0 * frames_ok / frames_eval, 2),
            res.get("descartados"), "" if st["vista_ruim"] is None else st["vista_ruim"],
            "" if st["sem_mao"] is None else st["sem_mao"], "" if st["segurando"] is None else st["segurando"],
            "" if st["perdidos"] is None else st["perdidos"], rel.get("nivel", ""),
            " / ".join(rel.get("motivos", [])), flag(bool(saved.get("reteste"))),
            num(spread[0]), num(spread[1]), num(spread[2]), num(whole.get("abertura_dedos_total")),
            num(whole.get("abertura_polegar")),
            flag(tremor.get("ritmico")) if tremor else "", num(tremor.get("frequencia_hz")),
            num(tremor.get("rms_mm")), num(tremor.get("segundos"))]
    return row


def _finger_columns():
    cols = [("id_avaliacao", "Avaliação (liga com avaliacoes.csv)", "", "texto", ""),
            ("etapa", "Avaliação ou reteste (medição repetida logo depois, mão reposicionada)", "", "categoria",
             "avaliacao; reteste"),
            ("dedo", "Dedo", "", "categoria", "; ".join(FINGER.values())),
            ("repeticoes", "Repetições contadas (qualquer amplitude acima da sensibilidade)", "repetições",
             "inteiro", ">= 0"),
            ("parciais", "Repetições com amplitude >= 25% e < 75% do TAM normal", "repetições", "inteiro", ">= 0"),
            ("completas", "Repetições com amplitude >= 75% do TAM normal", "repetições", "inteiro", ">= 0"),
            ("tam_ativo", "TAM ativo = soma das flexões máximas - soma dos déficits de extensão (mínimo 0)",
             "graus", "decimal", ">= 0"),
            ("pct_normal", "TAM ativo em % do TAM normal", "%", "decimal", ">= 0"),
            ("tam_normal", "TAM normal de referência (260° dedos longos, 140° polegar)", "graus", "decimal", ""),
            ("classificacao_tam", "Faixa do % do normal: ruim < 50%, regular < 75%, bom >= 75%", "", "categoria",
             "ruim; regular; bom"),
            ("tam_max_simultaneo", "Maior soma das flexões num mesmo instante", "graus", "decimal", "")]
    for slot, names in SLOTS:
        who = "/".join(names)
        cols += [(f"{slot}_flexao_max", f"{who}: maior flexão na etapa", "graus", "decimal", "-60 a 130"),
                 (f"{slot}_flexao_min", f"{who}: menor flexão (negativo = hiperextensão)", "graus", "decimal",
                  "-60 a 130"),
                 (f"{slot}_deficit_extensao", f"{who}: déficit de extensão = max(0, flexão mínima)", "graus",
                  "decimal", ">= 0"),
                 (f"{slot}_arco", f"{who}: arco = flexão máxima - mínima", "graus", "decimal", ">= 0"),
                 (f"{slot}_contribuicao_pct", f"{who}: participação média da articulação na excursão das "
                                              f"repetições", "%", "decimal", "0-100"),
                 (f"{slot}_arco_funcional_pct", f"{who}: parte da faixa funcional coberta (Bain 2015; dedos "
                                                f"longos)", "%", "decimal", "0-100"),
                 (f"{slot}_normal", f"{who}: flexão normal de referência", "graus", "decimal", "")]
    cols += [("strickland_pct", "Strickland: (flexão PIP + DIP - déficits) / 175° (dedos longos)", "%", "decimal",
              ">= 0"),
             ("polpa_palma_cm", "Menor distância estimada da ponta do dedo à palma (escala de mão média; dedos "
                                "longos)", "cm", "decimal", ">= 0"),
             ("independencia_pct", "1 - média do acoplamento dos outros dedos nas repetições", "%", "decimal",
              "0-100")]
    cols += [(f"acoplamento_{FINGER[g]}_pct", f"Quanto o {FINGER[g]} se moveu junto (movimento dele menos a "
                                             f"sensibilidade / amplitude da repetição; até 150%; vazio no "
                                             f"próprio dedo)", "%", "decimal", "0-150") for g in kin.FINGERS]
    cols += [("vel_flexao_media", "Amplitude / tempo de subida, média das últimas 10 repetições", "graus/s",
              "decimal", ">= 0"),
             ("vel_extensao_media", "Amplitude da volta / tempo de descida, média das últimas 10", "graus/s",
              "decimal", ">= 0"),
             ("vel_pico_media", "Maior velocidade na flexão (Savitzky-Golay 5 pontos, TAM a 30 Hz), média das "
                                "últimas 10 repetições de 15° ou mais", "graus/s", "decimal", ">= 0"),
             ("suavidade_sparc", "SPARC (Balasubramanian 2015) da norma das velocidades articulares, média de "
                                 "flexões e extensões das últimas 10 repetições de 15° ou mais", "adimensional",
              "decimal", "<= 0"),
             ("ciclo_s", "Mediana do tempo entre inícios de repetições (últimas 10)", "s", "decimal", "> 0"),
             ("cadencia_por_min", "60 / ciclo (com 3 ou mais repetições)", "repetições/min", "decimal", "> 0"),
             ("regularidade", "Variação do ciclo: regular < 15%, moderada < 30%, irregular", "", "categoria",
              "regular; moderada; irregular"),
             ("variacao_ciclo_pct", "Coeficiente de variação do ciclo", "%", "decimal", ">= 0"),
             ("variacao_amplitude_pct", "Média das 3 últimas amplitudes vs. 3 primeiras (6+ repetições)", "%",
              "decimal", ""),
             ("tendencia_amplitude_pct", "Variação da amplitude do início ao fim pela reta de regressão "
                                         "(6+ repetições)", "%", "decimal", ""),
             ("tendencia_velocidade_pct", "Variação da velocidade de flexão do início ao fim pela reta", "%",
              "decimal", ""),
             ("consistencia_esforco_pct", "CV do TAM no pico entre as 5 repetições mais fortes", "%", "decimal",
              ">= 0"),
             ("consistencia_esforco", "consistente < 10%, moderada < 20%, variavel", "", "categoria",
              "consistente; moderada; variavel"),
             ("amplitude_primeira", "Amplitude da primeira repetição (pico - vale do TAM, dados brutos)",
              "graus", "decimal", ">= 0"),
             ("amplitude_ultima", "Amplitude da última repetição", "graus", "decimal", ">= 0"),
             ("sensibilidade", "Menor movimento contado: 3 x desvio padrão do TAM parado na calibração, entre 2 "
                               "e 30; 5 sem calibração", "graus", "decimal", "2-30")]
    return cols


FINGER_COLUMNS = _finger_columns()
_ASCII = {"Regular": "regular", "Moderada": "moderada", "Irregular": "irregular",
          "Consistente": "consistente", "Variável": "variavel"}


def _finger_row(eid, stage, f, d):
    """Linha de dedos.csv. d = dicionário do dedo (resultados completos ou resumo do reteste)."""
    q = d.get("qualidade") or {}
    amps = d.get("amplitudes") or []
    coup = d.get("acoplamento") or {}
    normal = d.get("normal", kin.normal_tam(f))
    row = [eid, stage, FINGER[f], d.get("movimentos"), d.get("parciais"), d.get("completas"),
           num(d.get("tam_ativo")), num(pct(d.get("pct_normal"))), num(normal),
           kin.grade(d.get("pct_normal")) or "", num(d.get("tam_max"))]
    by_name = {j["nome"]: j for j in d["articulacoes"]}
    normals = dict(zip([n for n, _ in kin.JOINTS[f]], kin.NORMAL_JOINT[f].values()))
    for _, names in SLOTS:
        name = next((n for n in names if n in by_name), None)
        j = by_name.get(name, {})
        row += [num(j.get("max")), num(j.get("min")), num(j.get("deficit")), num(j.get("arco")),
                num(pct(j.get("contribuicao"))), num(pct(j.get("arco_funcional"))),
                num(normals.get(name)) if name else ""]
    row += [num(pct(d.get("strickland"))), num(d.get("polpa_palma_cm")), num(pct(d.get("independencia")))]
    row += [num(pct(coup.get(g))) if g != f else "" for g in kin.FINGERS]
    row += [num(q.get("flex_velocity")), num(q.get("ext_velocity")), num(q.get("peak_velocity")),
            num(q.get("sparc")), num(q.get("cycle_s")), num(q.get("cadence")),
            _ASCII.get(q.get("regularity"), q.get("regularity") or ""), num(pct(q.get("cv"))),
            num(pct(q.get("amp_change"))), num(pct(q.get("amp_trend"))), num(pct(q.get("vel_trend"))),
            num(pct(q.get("effort_cv"))), _ASCII.get(q.get("effort"), q.get("effort") or ""),
            num(amps[0] if amps else None), num(amps[-1] if amps else None), num(d.get("sensibilidade"))]
    return row


REP_COLUMNS = [
    ("id_avaliacao", "Avaliação (liga com avaliacoes.csv)", "", "texto", ""),
    ("etapa", "Avaliação ou reteste", "", "categoria", "avaliacao; reteste"),
    ("dedo", "Dedo", "", "categoria", "; ".join(FINGER.values())),
    ("n_repeticao", "Ordem da repetição no dedo (1 = primeira)", "", "inteiro", ">= 1"),
    ("t_inicio_s", "Início da flexão: último instante a até meia sensibilidade do vale (TAM médio de 8 quadros)",
     "s", "decimal", "mesma base de t_s de quadros"),
    ("t_pico_s", "Fim da flexão: primeiro instante a até meia sensibilidade do pico", "s", "decimal", ""),
    ("t_inicio_extensao_s", "Início da extensão: último instante a até meia sensibilidade do pico", "s",
     "decimal", ""),
    ("t_fim_s", "Instante em que a repetição foi fechada (TAM médio caiu uma sensibilidade abaixo do pico)",
     "s", "decimal", ""),
    ("t_fim_extensao_s", "Fim da extensão: primeiro instante a até meia sensibilidade do vale seguinte (vazio se "
                         "não houve vale seguinte)", "s", "decimal", ""),
    ("t_vale_bruto_s", "Instante do vale nos dados brutos", "s", "decimal", ""),
    ("t_pico_bruto_s", "Instante do pico nos dados brutos", "s", "decimal", ""),
    ("amplitude_graus", "Pico - vale do TAM nos dados brutos", "graus", "decimal", "> 0"),
    ("tam_pico_graus", "TAM no pico (dados brutos)", "graus", "decimal", ""),
    ("amplitude_extensao_graus", "Pico - vale seguinte do TAM nos dados brutos", "graus", "decimal", ""),
    ("classificacao", "movimento < 25% do TAM normal <= parcial < 75% <= completa", "", "categoria",
     "movimento; parcial; completa"),
    ("vel_flexao_graus_s", "Amplitude / (t_pico - t_inicio), se o tempo for > 0,05 s", "graus/s", "decimal", ""),
    ("vel_extensao_graus_s", "Amplitude da extensão / (t_fim_extensao - t_inicio_extensao)", "graus/s",
     "decimal", ""),
    ("vel_pico_graus_s", "Maior velocidade do TAM na flexão (só repetições de 15° ou mais)", "graus/s",
     "decimal", ""),
    ("sparc_flexao", "SPARC da flexão (15° ou mais)", "adimensional", "decimal", "<= 0"),
    ("sparc_extensao", "SPARC da extensão (15° ou mais)", "adimensional", "decimal", "<= 0"),
    ("independencia_pct", "1 - média do acoplamento dos outros dedos nesta repetição", "%", "decimal", "0-100"),
    ("excursao_mcp_graus", "Quanto a MCP se moveu na flexão (máximo - valor no vale)", "graus", "decimal", ">= 0"),
    ("excursao_pip_ou_ip_graus", "Quanto a PIP (polegar: IP) se moveu na flexão", "graus", "decimal", ">= 0"),
    ("excursao_dip_graus", "Quanto a DIP se moveu na flexão (vazio no polegar)", "graus", "decimal", ">= 0"),
]


def _rep_rows(eid, stage, rep, t0):
    rows = []
    rel = lambda t: None if t is None else t - t0
    for f in kin.FINGERS:
        for i, r in enumerate(rep.av.session.trackers[f].reps, 1):
            exc = list(r.excursion) + [None] * (3 - len(r.excursion))
            rows.append([eid, stage, FINGER[f], i, num(rel(r.t_start)), num(rel(r.t_peak)),
                         num(rel(r.t_ext_start)), num(rel(r.t_end)), num(rel(r.t_ext_end)),
                         num(rel(r.t_raw_start)), num(rel(r.t_raw_peak)), num(r.amplitude), num(r.peak_tam),
                         num(r.ext_amplitude), r.kind, num(r.flex_velocity), num(r.ext_velocity),
                         num(r.peak_velocity), num(r.sparc_flex), num(r.sparc_ext), num(pct(r.independence)),
                         num(exc[0]), num(exc[1]), num(exc[2])])
    return rows


def _frame_columns(opts):
    cols = [("id_avaliacao", "Avaliação (liga com avaliacoes.csv)", "", "texto", ""),
            ("etapa", "Avaliação ou reteste", "", "categoria", "avaliacao; reteste"),
            ("quadro", "Índice do quadro no arquivo de pontos (0 = primeiro)", "", "inteiro", ">= 0"),
            ("t_s", "Tempo desde o primeiro quadro do arquivo (relógio monotônico da captura)", "s", "decimal",
             ">= 0"),
            ("fase", "Fase do motor no quadro (a mesma gravada no arquivo de pontos)", "", "categoria",
             "preparacao; calibracao; avaliacao; pausa; recalibracao"),
            ("mao_presente", "O MediaPipe achou uma mão neste quadro", "", "booleano", "0; 1"),
            ("mao_detectada", "Lado informado pelo MediaPipe (mão real; a imagem é espelhada)", "", "categoria",
             "direita; esquerda"),
            ("confianca_lateralidade", "Confiança do MediaPipe na classificação direita/esquerda (score da "
                                       "handedness)", "", "decimal", "0-1"),
            ("fps_captura", "fps informado pela captura (média móvel)", "quadros/s", "decimal", "> 0"),
            ("brilho", "Brilho médio da imagem (média móvel)", "0-255", "decimal", "0-255"),
            ("inferencia_ms", "Tempo de inferência do MediaPipe (média móvel)", "ms", "decimal", ">= 0"),
            ("lado_angulos", "Lado usado no cálculo dos ângulos; vazio = ainda não fixado (ângulo 3D sem sinal)",
             "", "categoria", "direita; esquerda"),
            ("estado", "Estado do estabilizador: ok (medida), segurando (falha curta, pose anterior), perdida, "
                       "outra_mao, vista (palma de lado)", "", "categoria",
             "ok; segurando; perdida; outra_mao; vista"),
            ("descartado_angulo_impossivel", "Algum ângulo fora de -60° a 130° (quadro descartado)", "",
             "booleano", "0; 1"),
            ("vista_ruim", "Palma a mais de 60° da câmera (quadro não entra nas medidas)", "", "booleano", "0; 1"),
            ("angulo_vista_graus", "Ângulo entre a palma e a câmera (0 = de frente, 90 = de lado)", "graus",
             "decimal", "0-180"),
            ("entra_nas_medidas", "O quadro entrou nas medidas de dedos.csv desta etapa (fase avaliação, estado "
                                  "ok, sem pausa, última calibração com a mesma mão)", "", "booleano", "0; 1")]
    for i, name in enumerate(LANDMARKS):
        for ax in "xyz":
            cols.append((f"lm{i:02d}_{ax}", f"Ponto {i} ({name}), coordenada {ax} 3D do MediaPipe (world "
                                            f"landmarks: origem perto do centro da mão, imagem espelhada)",
                         "m", "decimal", ""))
    if opts.incluir_imagem:
        for i, name in enumerate(LANDMARKS):
            for ax in "xy":
                cols.append((f"lm{i:02d}_img_{ax}", f"Ponto {i} ({name}), coordenada {ax} na imagem espelhada, "
                                                    f"normalizada pela {'largura' if ax == 'x' else 'altura'}",
                             "0-1", "decimal", ""))
    for f, i, col in JOINT_COLUMNS:
        cols.append((f"{col}_bruto", f"Flexão {kin.JOINTS[f][i][0]} do {FINGER[f]}, dados brutos (com sinal: "
                                     f"positivo = flexão)", "graus", "decimal", ""))
    for f, i, col in JOINT_COLUMNS:
        cols.append((f"{col}_suavizado", f"Mesma flexão depois do filtro de suavização (vazio com o filtro "
                                         f"desligado ou fora do estado ok)", "graus", "decimal", ""))
    return cols


def _frame_rows(eid, stage, rep, t0, opts):
    rows = []
    off = filtros.registro_de(None)["modo"]
    smoothing_on = rep.av.filtro.reg["modo"] != off
    for k, fr in enumerate(rep.frames):
        raw = fr["raw"]
        world, img = raw["world"], raw.get("img")
        row = [eid, stage, rep.index0 + k, num(raw["t"] - t0, 6), fr["fase"], flag(world is not None),
               HAND.get(raw.get("handedness"), ""), num(raw.get("confidence")), num(raw.get("fps"), 2),
               num(raw.get("brightness"), 2), num(raw.get("inference_ms"), 2), HAND.get(fr["lado_angulos"], ""),
               fr["estado"] or "", flag(fr["descartado"]) if world is not None else "",
               flag(fr["vista_ruim"]) if world is not None else "", num(fr["angulo_vista"], 2),
               flag(fr["entra"])]
        if world is not None:
            row += [num(v, LANDMARK_DECIMALS) for v in np.asarray(world, dtype=float).ravel()]
        else:
            row += [""] * 63
        if opts.incluir_imagem:
            row += ([num(v, LANDMARK_DECIMALS) for v in np.asarray(img, dtype=float).ravel()]
                    if img is not None else [""] * 42)
        ang, smo = fr["angulos"], fr["suavizados"] if smoothing_on else None
        row += [num(ang[f][i]) if ang is not None else "" for f, i, _ in JOINT_COLUMNS]
        row += [num(smo[f][i]) if smo is not None else "" for f, i, _ in JOINT_COLUMNS]
        rows.append(row)
    return rows


DICTIONARY_COLUMNS = [
    ("arquivo", "Arquivo descrito (quadros/*.csv.gz = todos os arquivos de quadros)", "", "texto", ""),
    ("coluna", "Nome da coluna", "", "texto", ""),
    ("descricao", "O que a coluna contém", "", "texto", ""),
    ("unidade", "Unidade (vazio = sem unidade)", "", "texto", ""),
    ("tipo", "Tipo do valor", "", "categoria", "texto; categoria; inteiro; decimal; booleano; data-hora"),
    ("valores_possiveis", "Faixa ou categorias possíveis (separadas por ;)", "", "texto", ""),
    ("codigo_faltante", "Como o dado faltante aparece no arquivo", "", "categoria", "vazio"),
]


# =============================================================================
# exportação
# =============================================================================
def _collect(db, root, progress):
    """Pacientes (ordenados pelo pseudônimo) e avaliações com o recálculo."""
    patients = sorted(db.pacientes(""), key=lambda p: p["id_pesquisa"])
    by_patient = {}
    for s in db.todas_sessoes():
        by_patient.setdefault(s["paciente_id"], []).append(s)
    total = sum(len(v) for v in by_patient.values())
    evals, done = [], 0
    for p in patients:
        sessions = sorted(by_patient.get(p["id"], []), key=lambda s: s["inicio"])
        first = datetime.date.fromisoformat(sessions[0]["inicio"][:10]) if sessions else None
        for k, s in enumerate(sessions, 1):
            if progress:
                progress(done, total)
            done += 1
            saved = s["resultados"]
            day = datetime.date.fromisoformat(saved["inicio"][:10])
            replay = _evaluate(saved, root)
            e = {"id": f"{p['id_pesquisa']}-{s['codigo']}", "ordem": k, "dia": (day - first).days, "data": day,
                 "patient": p, "saved": saved, "replay": replay, "confere": None, "maior_diferenca": None}
            if replay:
                res = replay["main"].results
                if "filtro" not in saved:
                    res.pop("filtro", None)
                if replay["retest"] is not None:
                    res["reteste"] = replay["retest"].results
                e["res"] = res
                comparable = dict(res)
                if saved.get("reteste") and replay["retest"] is not None:
                    comparable["reteste"] = retest_summary(replay["retest"].results)
                    comparable["reteste"]["inicio"] = saved["reteste"].get("inicio")
                e["confere"], e["diferencas"] = _compare(saved, comparable)
                e["maior_diferenca"] = _largest_joint_change(saved, comparable)
            else:
                e["res"] = saved
            evals.append(e)
    if progress:
        progress(total, total)
    return patients, evals


def exportar(db, pasta, opcoes=None, root=None, progress=None):
    """Grava o dataset em `pasta` (criada; não pode existir com arquivos). root = pasta a que
    os caminhos dos pontos são relativos (padrão: a do projeto). Devolve um resumo."""
    opts = opcoes or Opcoes()
    root = root or caminhos.ROOT
    if os.path.isdir(pasta) and os.listdir(pasta):
        raise FileExistsError(f"a pasta já tem arquivos: {pasta}")
    os.makedirs(pasta, exist_ok=True)
    patients, evals = _collect(db, root, progress)
    count = {}
    for e in evals:
        count[e["patient"]["id"]] = count.get(e["patient"]["id"], 0) + 1

    files = {}
    pcols = PATIENT_COLUMNS + (FREE_TEXT_COLUMNS if opts.incluir_texto_livre else [])
    files["pacientes.csv"] = _csv_bytes([c[0] for c in pcols],
                                        [_patient_row(p, count.get(p["id"], 0), opts) for p in patients])
    ecols = EVAL_COLUMNS[:4] + (EXACT_DATE_COLUMNS if opts.datas_exatas else []) + EVAL_COLUMNS[4:]
    files["avaliacoes.csv"] = _csv_bytes([c[0] for c in ecols], [_eval_row(e, opts) for e in evals])

    finger_rows, rep_rows, frame_files = [], [], {}
    fcols = _frame_columns(opts)
    for e in evals:
        res, replay = e["res"], e["replay"]
        for f in kin.FINGERS:
            finger_rows.append(_finger_row(e["id"], "avaliacao", f, res["dedos"][f]))
        retest = res.get("reteste")
        if retest:
            for f in kin.FINGERS:
                finger_rows.append(_finger_row(e["id"], "reteste", f, retest["dedos"][f]))
        if replay:
            rep_rows += _rep_rows(e["id"], "avaliacao", replay["main"], replay["t0"])
            frows = _frame_rows(e["id"], "avaliacao", replay["main"], replay["t0"], opts)
            if replay["retest"] is not None:
                rep_rows += _rep_rows(e["id"], "reteste", replay["retest"], replay["t0"])
                frows += _frame_rows(e["id"], "reteste", replay["retest"], replay["t0"], opts)
            frame_files[f"quadros/{e['id']}.csv.gz"] = _csv_bytes([c[0] for c in fcols], frows)
    files["dedos.csv"] = _csv_bytes([c[0] for c in FINGER_COLUMNS], finger_rows)
    files["repeticoes.csv"] = _csv_bytes([c[0] for c in REP_COLUMNS], rep_rows)

    dictionary = [("pacientes.csv", pcols), ("avaliacoes.csv", ecols), ("dedos.csv", FINGER_COLUMNS),
                  ("repeticoes.csv", REP_COLUMNS), ("quadros/*.csv.gz", fcols)]
    dictionary.append(("dicionario_de_dados.csv", DICTIONARY_COLUMNS))
    drows = [[arq, c[0], c[1], c[2], c[3], c[4], "vazio"] for arq, cols in dictionary for c in cols]
    files["dicionario_de_dados.csv"] = _csv_bytes(
        [c[0] for c in DICTIONARY_COLUMNS], drows)
    exported_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    summary = {"pasta": pasta, "pacientes": len(patients), "avaliacoes": len(evals),
               "com_pontos": sum(e["replay"] is not None for e in evals),
               "conferem": sum(bool(e["confere"]) for e in evals),
               "nao_conferem": [(e["id"], e["maior_diferenca"]) for e in evals
                                if e["replay"] is not None and not e["confere"]],
               "repeticoes": len(rep_rows), "exportado_em": exported_at, "opcoes": opts}
    files["LEIA-ME.md"] = _readme(summary, opts).encode("utf-8")

    for name, data in files.items():
        _write(os.path.join(pasta, name), data)
    for name, data in frame_files.items():
        _write_gz(os.path.join(pasta, *name.split("/")), data)
    names = sorted(list(files) + list(frame_files))
    lines = [f"{_sha256(os.path.join(pasta, *n.split('/')))}  {n}" for n in names]
    _write(os.path.join(pasta, "checksums.sha256"), ("\n".join(lines) + "\n").encode("utf-8"))
    summary["arquivos"] = names + ["checksums.sha256"]
    summary["bytes"] = sum(os.path.getsize(os.path.join(pasta, *n.split("/"))) for n in summary["arquivos"])
    return summary


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def conferir_checksums(pasta):
    """Lista dos arquivos cujo SHA-256 não confere com checksums.sha256 (vazia = tudo certo)."""
    bad = []
    with open(os.path.join(pasta, "checksums.sha256"), encoding="utf-8") as fh:
        for line in fh:
            digest, name = line.rstrip("\n").split("  ", 1)
            path = os.path.join(pasta, *name.split("/"))
            if not os.path.exists(path) or _sha256(path) != digest:
                bad.append(name)
    return bad


def _readme(s, opts):
    yes = lambda v: "sim" if v else "não"
    mismatch = ""
    if s["nao_conferem"]:
        mismatch = (f"\n**Atenção:** em {len(s['nao_conferem'])} avaliação(ões) o recálculo não confere com o "
                    "resultado salvo (`confere_com_salvo = 0`), normalmente porque foram salvas por uma versão "
                    "anterior do cálculo (a 1.2.0 mudou a goniometria). Este dataset traz as medidas "
                    "recalculadas; o relatório/PDF dessas avaliações mostra as antigas. A coluna "
                    "`maior_diferenca_salvo_graus` dá o tamanho da diferença.\n")
    return f"""# Dataset ManuMetria (pesquisa)

Exportado em {s['exportado_em']} pelo ManuMetria {VERSAO}.
{s['pacientes']} paciente(s), {s['avaliacoes']} avaliação(ões), {s['com_pontos']} com pontos gravados,
{s['repeticoes']} repetição(ões).

Opções desta exportação: texto livre (condição) incluído: {yes(opts.incluir_texto_livre)}; datas exatas:
{yes(opts.datas_exatas)}; coordenadas 2D da imagem: {yes(opts.incluir_imagem)}.
{mismatch}
## Aviso ético e legal (LGPD)

- Dados de saúde são **dados pessoais sensíveis** (LGPD, art. 5º, II, e art. 11).
- As **coordenadas 3D da mão** (`quadros/`) descrevem a geometria da mão de uma pessoa: são **dado
  biométrico**, também dado pessoal sensível (LGPD, art. 5º, II).
- Os arquivos são **pseudonimizados, não anônimos**. O `id_pesquisa` é um código aleatório guardado só no
  banco local do ManuMetria: **não pode ser revertido sem esse banco**, e quem tem o banco consegue religar
  o código ao paciente. Não tente reidentificar participantes.
- Compartilhe este dataset **só com acesso controlado** (pessoas autorizadas, armazenamento protegido), sob
  **aprovação do Comitê de Ética em Pesquisa (CEP)** e com o **consentimento** dos participantes, e apenas
  para o que foi aprovado.

Licença dos dados: **a definir com o NIT**.

## Arquivos e relações

| Arquivo | Uma linha por | Chave | Liga com |
|---|---|---|---|
| `pacientes.csv` | paciente | `id_pesquisa` | — |
| `avaliacoes.csv` | avaliação | `id_avaliacao` | `pacientes.csv` por `id_pesquisa` |
| `dedos.csv` | avaliação × etapa × dedo | `id_avaliacao`, `etapa`, `dedo` | `avaliacoes.csv` |
| `repeticoes.csv` | repetição | `id_avaliacao`, `etapa`, `dedo`, `n_repeticao` | `avaliacoes.csv`, `dedos.csv` |
| `quadros/<id_avaliacao>.csv.gz` | quadro gravado | `id_avaliacao`, `quadro` | `avaliacoes.csv`; `t_s` é a mesma base de tempo dos `t_*_s` de `repeticoes.csv` |
| `dicionario_de_dados.csv` | coluna de cada arquivo | `arquivo`, `coluna` | descrição, unidade, tipo, valores possíveis |
| `checksums.sha256` | arquivo | — | SHA-256 de todos os arquivos (`sha256sum -c checksums.sha256`) |

`etapa` = `avaliacao` ou `reteste` (a mesma medição repetida logo depois, com a mão reposicionada e nova
calibração; serve para o erro de medida). Avaliações sem pontos gravados (salvas antes de 15/10/2026) têm
só `avaliacoes.csv` e `dedos.csv`, com as medidas salvas (`medidas_origem = salvas`).

## Formato

UTF-8 sem BOM; vírgula entre campos; ponto decimal; fim de linha LF; nomes de colunas em snake_case sem
acento; **faltante = campo vazio** (nunca 0 nem NaN); sim/não = 1/0; datas ISO 8601. Ângulos com 4 casas
decimais; coordenadas com 6 (metros). As datas são **relativas** por padrão (`dia_relativo` = dias desde a
primeira avaliação do paciente); a idade é calculada na exportação a partir da data de nascimento, que não
é exportada.

Leitura: Python `pandas.read_csv("dedos.csv")`; quadros: `pandas.read_csv("quadros/P-XXXXXX-A01.csv.gz")`.
R: `read.csv("dedos.csv", encoding = "UTF-8")`. Excel: Dados > De Texto/CSV, origem UTF-8, delimitador
vírgula (a planilha para o Excel continua em "Exportar dados > Planilha").

## Métodos

- **Pontos da mão**: MediaPipe Hand Landmarker (21 pontos; coordenadas 3D "world", em metros), webcam
  comum, imagem espelhada antes da detecção. O lado da mão é fixado na calibração.
- **Ângulos** ({GONIOMETRIA}): {GONIOMETRIA_TEXTO}. Positivo = flexão, negativo = hiperextensão. Antes de o
  lado ser fixado, o ângulo é 3D sem sinal (`lado_angulos` vazio).
- **Descarte**: quadros com ângulo fora de −60° a 130° e quadros com a palma a mais de 60° da câmera não
  entram nas medidas; falhas curtas (até 0,4 s) mantêm a pose anterior sem medir (`estado = segurando`).
- **Suavização** (EMA, Kalman ou EMA + Kalman; `filtro_*` em `avaliacoes.csv`): por padrão só na exibição
  ao vivo; as medidas usam os dados brutos, a não ser com `filtro_nas_medidas = 1`.
- **Medidas por dedo**: flexão máxima e mínima de cada articulação entre os quadros com
  `entra_nas_medidas = 1` (colunas `*_bruto`, ou `*_suavizado` com `filtro_nas_medidas = 1`); TAM ativo =
  soma das máximas − soma dos déficits (déficit = max(0, mínima)), fórmula da ASSH; % do normal com 260°
  (dedos longos) e 140° (polegar).
- **Repetições**: detectadas na média móvel de 8 quadros do TAM, com histerese igual à sensibilidade (3 × o
  desvio padrão do TAM parado na calibração, entre 2° e 30°); amplitude e velocidades nos dados brutos;
  velocidade de pico pela derivada de Savitzky–Golay (5 pontos) do TAM reamostrado a 30 Hz; suavidade pelo
  SPARC (Balasubramanian et al., 2015) da norma das velocidades articulares.
- Detalhes, fontes e a auditoria dos cálculos: `README.md` e `docs/AUDITORIA_CALCULOS.md` do ManuMetria.

Referências: Wu G. et al. ISB recommendation on definitions of joint coordinate systems... Part II: shoulder,
elbow, wrist and hand. J Biomech 2005;38:981-992. Balasubramanian S. et al. On the analysis of movement
smoothness. J NeuroEng Rehabil 2015;12:112. Bain G.I. et al. The functional range of motion of the finger
joints. J Hand Surg Eur 2015;40:406-411.

## Reprodutibilidade

As medidas das avaliações com pontos foram **recalculadas dos pontos gravados** com o cálculo do ManuMetria
{VERSAO}, o mesmo da tela. Com `quadros/` dá para refazer, sem o programa, as flexões máximas e mínimas,
déficits, arcos e TAM de `dedos.csv` (tolerância: 0,001°, pelo arredondamento) e conferir as repetições.
`confere_com_salvo` diz se o recálculo bate com o resultado salvo na avaliação (o do relatório e do PDF).
O mesmo banco exportado de novo gera os mesmos bytes nos CSV (só este LEIA-ME e os checksums mudam).

Estimativas por câmera: não substituem a goniometria clínica. ManuMetria é software de pesquisa e não é
dispositivo médico registrado na ANVISA.
"""
