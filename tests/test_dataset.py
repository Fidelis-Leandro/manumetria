"""
Exportação "Dataset para pesquisa" (manumetria/dados/dataset.py), num banco temporário com
pacientes de teste (mão simulada com reteste, gravação de referência com o filtro
nas medidas, avaliação sem pontos). Nada aqui toca em dados_locais.

    .venv\\Scripts\\python.exe tests\\test_dataset.py
    .venv\\Scripts\\python.exe tests\\test_dataset.py --copia-do-banco   (também exporta uma CÓPIA de
                                                                    dados_locais, se existir; ~2 min)

Lê os arquivos com o pandas quando ele está instalado (não é dependência do sistema);
sem ele, as mesmas conferências são feitas com o módulo csv.
"""

import csv
import datetime
import gzip
import io
import math
import os
import re
import shutil
import sys
import tempfile

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import criar_demonstracao as demo  # noqa: E402
from manumetria.avaliacao.motor import Avaliador, analisar  # noqa: E402
from manumetria.avaliacao.resultados import retest_summary  # noqa: E402
from manumetria.calculo import filtros  # noqa: E402
from manumetria.captura import gravacao  # noqa: E402
from manumetria.dados import dataset  # noqa: E402
from manumetria.dados.banco import Banco  # noqa: E402

try:
    import pandas as pd
except ImportError:
    pd = None

RECORDING = os.path.join(ROOT, "tests", "dados", "gravacao_referencia.npz")
TOL_DEG = 1e-3        # recálculo a partir de quadros.csv: os ângulos saem com 4 casas (erro <= 0,0001° cada)
failures = []


def check(name, ok, detail=""):
    print(f"[{'ok' if ok else 'FALHOU'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


# =============================================================================
# banco de teste
# =============================================================================
PATIENTS = [
    {"identificacao": "Ana Beatriz Quintanilha", "nascimento": "1971-03-12", "sexo": "feminino",
     "mao_dominante": "Direita", "mao_avaliada": "Direita", "condicao": "Tenorrafia secreta do FDP zona II",
     "data_lesao": "2026-08-20", "profissional": "Ft. Teste", "observacoes": "Mora na Rua Imaginária, 123"},
    {"identificacao": "Bernardo Vasconcelos", "nascimento": "1990-11-30", "sexo": "masculino",
     "mao_dominante": "Esquerda", "mao_avaliada": "Direita", "condicao": "Rigidez pós-fratura"},
]
PLAN = {"low": [[5, 8, 4]] * 4, "peak": [[60, 80, 50]] * 4, "thumb": (8, 50), "reps": 6, "periodo": 2.5,
        "variacao": 0.05}


def simulated(root, start, with_retest):
    """Avaliação da mão simulada (motor da câmera), com os pontos gravados em `root`
    (a pasta do banco temporário: os caminhos salvos são relativos a ela)."""
    av = Avaliador()
    av.started_at = start
    for raw in demo.frames(PLAN, 1000.0, False):
        av.step(raw, raw["t"])
    out = av.results(av.frames[-1]["t"], "simulação")
    if with_retest:
        again = Avaliador(retest=True, frames=av.frames)
        again.started_at = start + datetime.timedelta(minutes=3)
        for raw in demo.frames(dict(PLAN, peak=[[55, 75, 45]] * 4), av.frames[-1]["t"] + 60, False):
            again.step(raw, raw["t"])
        out["reteste"] = retest_summary(again.results(again.frames[-1]["t"], "simulação"))
    out["pontos"] = f"pontos/sessao_{start:%Y%m%d_%H%M%S}.npz"
    gravacao.save_recording(os.path.join(root, *out["pontos"].split("/")), av.frames)
    return out


def build(root):
    db = Banco(os.path.join(root, "dados_locais", "avaliacoes.sqlite"))
    a = db.salvar_paciente(PATIENTS[0])
    b = db.salvar_paciente(PATIENTS[1])
    db.salvar_sessao(a, simulated(db.root, datetime.datetime(2026, 9, 24, 14, 0), True), "Sem dor. Nome: Ana B.")
    db.salvar_sessao(a, simulated(db.root, datetime.datetime(2026, 10, 1, 14, 30), False), "")
    # gravação de referência (mão saudável real) com EMA + Kalman também nas medidas
    rows = gravacao.load_recording(RECORDING)
    out = analisar(rows, filtro=filtros.registro(filtros.CASCATA, nas_medidas=True)).results(
        rows[-1]["t"], f"gravação {RECORDING}")
    out["inicio"] = "2026-10-03T09:00:00"
    out["pontos"] = "pontos/referencia.npz"
    shutil.copy(RECORDING, os.path.join(db.points_dir, "referencia.npz"))
    db.salvar_sessao(b, out, "")
    # avaliação sem pontos gravados (como as anteriores a 15/10/2026)
    old = dict(out, inicio="2026-09-01T09:00:00", pontos=None)
    for k in ("versao_app", "goniometria", "fuso_utc"):
        old.pop(k)
    db.salvar_sessao(b, old, "")
    return db


# =============================================================================
# leitura
# =============================================================================
def raw_bytes(folder, name):
    path = os.path.join(folder, *name.split("/"))
    data = open(path, "rb").read()
    return gzip.decompress(data) if name.endswith(".gz") else data


def table(folder, name):
    """Lista de dicionários (texto) de um CSV do dataset."""
    text = raw_bytes(folder, name).decode("utf-8")
    return list(csv.DictReader(io.StringIO(text, newline="")))


def all_files(folder):
    out = []
    for base, _, files in os.walk(folder):
        for f in files:
            out.append(os.path.relpath(os.path.join(base, f), folder).replace(os.sep, "/"))
    return sorted(out)


def check_export(folder, db, label, opts, expect_match=True):
    files = all_files(folder)
    csvs = [f for f in files if f.endswith(".csv") or f.endswith(".csv.gz")]
    frames_files = [f for f in files if f.startswith("quadros/")]
    print(f"\n--- {label}: {len(files)} arquivos")
    t = {n: table(folder, n) for n in ("pacientes.csv", "avaliacoes.csv", "dedos.csv", "repeticoes.csv")}
    frames = {f: table(folder, f) for f in frames_files}
    dic = table(folder, "dicionario_de_dados.csv")

    # leitura com pandas (ou csv): números leem como números
    if pd is not None:
        frames_pd = {n: pd.read_csv(os.path.join(folder, *n.split("/"))) for n in csvs}
        numeric = {(d["arquivo"], d["coluna"]) for d in dic if d["tipo"] in ("decimal", "inteiro", "booleano")}
        bad = [(n, c) for n, df in frames_pd.items() for c in df.columns
               if (("quadros/*.csv.gz" if n.startswith("quadros/") else n), c) in numeric
               and not pd.api.types.is_numeric_dtype(df[c])]
        check(f"{label}: pandas lê todos os arquivos e as colunas numéricas como números", not bad, f"{bad[:5]}")
        ev = frames_pd["avaliacoes.csv"]
        check(f"{label}: pandas: faltante vira NaN (vazio no arquivo), não 0",
              ev["versao_calculo_salvo"].isna().sum() == sum(r["versao_calculo_salvo"] == "" for r in t["avaliacoes.csv"]))
    else:
        bad = []
        numeric = {(d["arquivo"], d["coluna"]) for d in dic if d["tipo"] in ("decimal", "inteiro", "booleano")}
        for n in csvs:
            key = "quadros/*.csv.gz" if n.startswith("quadros/") else n
            for row in (frames[n] if n in frames else t.get(n, [])):
                for c, v in row.items():
                    if (key, c) in numeric and v != "":
                        try:
                            float(v)
                        except ValueError:
                            bad.append((n, c, v))
        check(f"{label}: (pandas não instalado) colunas numéricas leem como número com o csv", not bad, f"{bad[:5]}")

    # formato
    heads = {n: raw_bytes(folder, n).split(b"\n", 1)[0].decode("utf-8") for n in csvs}
    check(f"{label}: UTF-8 sem BOM, vírgula entre campos, fim de linha LF",
          all(not raw_bytes(folder, n).startswith(b"\xef\xbb\xbf") and b"\r\n" not in raw_bytes(folder, n)
              for n in csvs))
    check(f"{label}: nomes de colunas em snake_case sem acento",
          all(re.fullmatch(r"[a-z0-9_]+", c) for h in heads.values() for c in h.split(",")))
    junk = [(n, v) for n in csvs for v in ("nan", "NaN", "None", "inf")
            if re.search(rf"(^|,){v}(,|$)", raw_bytes(folder, n).decode("utf-8"), re.M)]
    comma_decimal = [n for n in csvs if n != "dicionario_de_dados.csv"
                     and re.search(r'(^|,)"-?\d+,\d+"(,|$)', raw_bytes(folder, n).decode("utf-8"), re.M)]
    check(f"{label}: faltante = vazio (sem nan/None), ponto decimal", not junk and not comma_decimal,
          f"{junk[:3]} {comma_decimal[:3]}")

    # IDs que ligam os níveis
    pids = {r["id_pesquisa"] for r in t["pacientes.csv"]}
    eids = {r["id_avaliacao"] for r in t["avaliacoes.csv"]}
    orphans = ({r["id_avaliacao"] for r in t["dedos.csv"]} | {r["id_avaliacao"] for r in t["repeticoes.csv"]}
               | {r["id_avaliacao"] for rows in frames.values() for r in rows}) - eids
    check(f"{label}: todo id_avaliacao de dedos/repeticoes/quadros existe em avaliacoes", not orphans, f"{orphans}")
    check(f"{label}: todo id_pesquisa de avaliacoes existe em pacientes",
          {r["id_pesquisa"] for r in t["avaliacoes.csv"]} <= pids)
    check(f"{label}: chaves únicas (paciente; avaliação; avaliação x etapa x dedo)",
          len(pids) == len(t["pacientes.csv"]) and len(eids) == len(t["avaliacoes.csv"])
          and len({(r["id_avaliacao"], r["etapa"], r["dedo"]) for r in t["dedos.csv"]}) == len(t["dedos.csv"]))
    check(f"{label}: um arquivo de quadros por avaliação com pontos",
          {f[len("quadros/"):-len(".csv.gz")] for f in frames_files}
          == {r["id_avaliacao"] for r in t["avaliacoes.csv"] if r["medidas_origem"] == "recalculadas_dos_pontos"})

    # recalcular dedos.csv a partir de quadros.csv
    ev = {r["id_avaliacao"]: r for r in t["avaliacoes.csv"]}
    worst, compared = 0.0, 0
    for f, rows in frames.items():
        eid = f[len("quadros/"):-len(".csv.gz")]
        suffix = "_suavizado" if ev[eid]["filtro_nas_medidas"] == "1" else "_bruto"
        for stage in ("avaliacao", "reteste"):
            use = [r for r in rows if r["etapa"] == stage and r["entra_nas_medidas"] == "1"]
            for d in (x for x in t["dedos.csv"] if x["id_avaliacao"] == eid and x["etapa"] == stage):
                joints = ["mcp", "ip"] if d["dedo"] == "polegar" else ["mcp", "pip", "dip"]
                if not use:
                    worst = math.inf
                    continue
                sum_max = sum_def = 0.0
                for j, slot in zip(joints, ["mcp", "pip_ou_ip", "dip"]):
                    vals = np.array([float(r[f"{d['dedo']}_{j}{suffix}"]) for r in use])
                    mx, mn = vals.max(), vals.min()
                    worst = max(worst, abs(mx - float(d[f"{slot}_flexao_max"])),
                                abs(mn - float(d[f"{slot}_flexao_min"])),
                                abs(max(0.0, mn) - float(d[f"{slot}_deficit_extensao"])),
                                abs(mx - mn - float(d[f"{slot}_arco"])))
                    sum_max, sum_def = sum_max + mx, sum_def + max(0.0, mn)
                worst = max(worst, abs(max(0.0, sum_max - sum_def) - float(d["tam_ativo"])))
                n_reps = sum(1 for r in t["repeticoes.csv"] if r["id_avaliacao"] == eid and r["etapa"] == stage
                             and r["dedo"] == d["dedo"])
                worst = max(worst, abs(n_reps - int(d["repeticoes"])))
                compared += 1
    check(f"{label}: medidas de dedos.csv recalculadas de quadros.csv (máx., mín., déficit, arco, TAM ativo, "
          f"nº de repetições) batem, tolerância {TOL_DEG}°", compared > 0 and worst <= TOL_DEG,
          f"{compared} dedos, maior diferença {worst:.6f}")
    if expect_match:
        check(f"{label}: recálculo confere com o salvo (= tela, PDF e planilha) em todas as avaliações com pontos",
              all(r["confere_com_salvo"] == "1" for r in t["avaliacoes.csv"]
                  if r["medidas_origem"] == "recalculadas_dos_pontos"),
              f"{[(r['id_avaliacao'], r['maior_diferenca_salvo_graus']) for r in t['avaliacoes.csv'] if r['confere_com_salvo'] == '0']}")

    # dicionário cobre 100% das colunas
    documented = {(d["arquivo"], d["coluna"]) for d in dic}
    used = {("quadros/*.csv.gz" if n.startswith("quadros/") else n, c) for n, h in heads.items() for c in h.split(",")}
    check(f"{label}: dicionário cobre 100% das colunas (e só elas)", used == documented,
          f"faltam {sorted(used - documented)[:5]}, sobram {sorted(documented - used)[:5]}")
    check(f"{label}: dicionário com descrição, tipo e código de faltante em todas as linhas",
          all(d["descricao"] and d["tipo"] and d["codigo_faltante"] == "vazio" for d in dic))

    # privacidade: nenhum nome, data de nascimento, observação ou caminho de arquivo
    text = "\n".join(raw_bytes(folder, n).decode("utf-8") for n in files).lower()
    leaks = []
    for p in db.pacientes(""):
        words = [w for w in re.split(r"\W+", p["identificacao"]) if len(w) >= 4]
        leaks += [w for w in words if w.lower() in text]
        y, m, d = p["nascimento"].split("-")
        leaks += [s for s in (f"{y}-{m}-{d}", f"{d}/{m}/{y}", f"{y}{m}{d}") if s in text]
        if p.get("observacoes"):
            leaks += [p["observacoes"]] if p["observacoes"].lower() in text else []
        if not opts.incluir_texto_livre and p.get("condicao") and p["condicao"].lower() in text:
            leaks.append(p["condicao"])
    leaks += [s for s in ("sessao_", ".npz", "dados_locais", "gravacao_referencia", "ft. teste") if s in text]
    check(f"{label}: nenhum nome, data de nascimento, observação ou caminho de arquivo nos arquivos", not leaks,
          f"{leaks[:5]}")
    check(f"{label}: sem a data exata por padrão; com a opção, ISO 8601",
          ("data_hora_inicio" in heads["avaliacoes.csv"]) == opts.datas_exatas
          and all(datetime.datetime.fromisoformat(r["data_hora_inicio"]) for r in t["avaliacoes.csv"]
                  if opts.datas_exatas))

    readme = raw_bytes(folder, "LEIA-ME.md").decode("utf-8")
    check(f"{label}: LEIA-ME com os avisos de LGPD (biométrico, acesso controlado, CEP, consentimento, "
          f"pseudônimo irreversível sem o banco) e a licença a definir",
          all(k in readme for k in ("biométrico", "art. 5º, II", "acesso controlado", "Comitê de Ética",
                                    "consentimento", "não pode ser revertido sem esse banco", "a definir com o NIT")))

    # checksums
    check(f"{label}: checksums.sha256 cobre todos os arquivos e confere",
          not dataset.conferir_checksums(folder)
          and sorted(l.split("  ", 1)[1] for l in open(os.path.join(folder, "checksums.sha256"), encoding="utf-8")
                     .read().splitlines()) == [f for f in files if f != "checksums.sha256"])
    return t


# =============================================================================
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
    os.makedirs(os.path.join(tmp, "dados_locais", "pontos"))
    db = build(tmp)
    out1 = os.path.join(tmp, "exp1")
    summary = dataset.exportar(db, out1)
    t = check_export(out1, db, "banco de teste", dataset.Opcoes())

    ev = {r["medidas_origem"]: r for r in t["avaliacoes.csv"]}
    check("avaliação sem pontos: medidas salvas, sem quadros nem repetições, método não registrado",
          ev["salvas"]["metodo_goniometria"] == "nao_registrado" and ev["salvas"]["confere_com_salvo"] == ""
          and not any(r["id_avaliacao"] == ev["salvas"]["id_avaliacao"] for r in t["repeticoes.csv"]))
    ana = next(p for p in db.pacientes("") if p["sexo"] == "feminino")
    rows = [r for r in t["avaliacoes.csv"] if r["id_pesquisa"] == ana["id_pesquisa"]]
    # idade calculada à mão: 1971-03-12 -> 2026-03-12 = 55 anos = 55 x 365 + 14 dias bissextos (29/02 de
    # 1972 a 2024) = 20.089 dias; 2026-03-12 -> 2026-09-24 = 19 + 30 + 31 + 30 + 31 + 31 + 24 = 196 dias;
    # total 20.285 dias / 365,25 = 55,537 -> 55.5. Uma semana depois (2026-10-01): 20.292 / 365,25 = 55,556 -> 55.6
    check("idade_na_avaliacao_anos confere com o cálculo à mão (55.5 e 55.6) e é fixa por avaliação",
          [r["idade_na_avaliacao_anos"] for r in rows] == ["55.5", "55.6"]
          and dataset.idade_anos("1971-03-12", datetime.date(2026, 9, 24)) == 55.5, f"{[r['idade_na_avaliacao_anos'] for r in rows]}")
    check("data relativa: dias desde a 1ª avaliação do paciente (0 e 7) e dias desde a lesão",
          [r["dia_relativo"] for r in rows] == ["0", "7"] and [r["dias_desde_lesao"] for r in rows] == ["35", "42"])
    check("reteste: linhas de dedos com etapa = reteste, recalculadas dos pontos",
          sum(1 for r in t["dedos.csv"] if r["etapa"] == "reteste") == 5
          and any(r["etapa"] == "reteste" for r in t["repeticoes.csv"]))
    check("pacientes.csv: sexo e mãos em minúsculas, sem condição por padrão",
          {r["sexo"] for r in t["pacientes.csv"]} == {"feminino", "masculino"}
          and "condicao" not in t["pacientes.csv"][0])
    ref = next(r for r in t["avaliacoes.csv"] if r["filtro_nas_medidas"] == "1" and r["medidas_origem"] != "salvas")
    check("gravação de referência: filtro nas medidas registrado, fonte sem o caminho, fps efetivo ~31",
          ref["filtro_modo"] == "ema_kalman" and ref["fonte"] == "gravacao" and 29 < float(ref["fps_efetivo"]) < 33
          and ref["quadros_descartados"] == "3", f"{ref['fps_efetivo']} {ref['quadros_descartados']}")

    # mesmo banco -> mesmos bytes (menos o LEIA-ME e os checksums, que têm a data)
    out2 = os.path.join(tmp, "exp2")
    dataset.exportar(db, out2)
    same = all(open(os.path.join(out1, *f.split("/")), "rb").read() == open(os.path.join(out2, *f.split("/")), "rb").read()
               for f in all_files(out1) if f not in ("LEIA-ME.md", "checksums.sha256"))
    check("reprodutível: exportar de novo gera os mesmos bytes nos CSV e .csv.gz", same)

    # checksums detectam alteração
    with open(os.path.join(out2, "dedos.csv"), "ab") as fh:
        fh.write(b"x")
    check("checksums detectam um arquivo alterado", dataset.conferir_checksums(out2) == ["dedos.csv"])

    # opções: texto livre, datas exatas e imagem
    out3 = os.path.join(tmp, "exp3")
    opts = dataset.Opcoes(incluir_texto_livre=True, datas_exatas=True, incluir_imagem=True)
    dataset.exportar(db, out3, opts)
    t3 = check_export(out3, db, "com as opções", opts)
    check("opções: condição só com texto livre marcado; coordenadas da imagem só com a opção",
          any(r["condicao"] == PATIENTS[0]["condicao"] for r in t3["pacientes.csv"])
          and "lm20_img_y" in raw_bytes(out3, next(f for f in all_files(out3) if f.startswith("quadros/")))
          .split(b"\n", 1)[0].decode() and "lm20_img_y" not in str(t["avaliacoes.csv"][0]))
    try:
        dataset.exportar(db, out3)
        refused = False
    except FileExistsError:
        refused = True
    check("não grava por cima de uma exportação existente", refused)

    # código fixo: apagar uma avaliação não renumera as outras (a exclusão apaga os pontos
    # da pasta do banco temporário, nunca de dados_locais)
    first = [r["id_avaliacao"] for r in t["avaliacoes.csv"] if r["id_pesquisa"] == ana["id_pesquisa"]]
    db.excluir_sessao(next(s["id"] for s in db.sessoes(ana["id"]) if s["codigo"] == "A01"))
    out4 = os.path.join(tmp, "exp4")
    dataset.exportar(db, out4)
    after = [r["id_avaliacao"] for r in table(out4, "avaliacoes.csv") if r["id_pesquisa"] == ana["id_pesquisa"]]
    check("id_avaliacao fixo: apagar a A01 não muda o código da A02 (nem o nome do arquivo de quadros)",
          first == [f"{ana['id_pesquisa']}-A01", f"{ana['id_pesquisa']}-A02"]
          and after == [f"{ana['id_pesquisa']}-A02"]
          and os.path.exists(os.path.join(out4, "quadros", f"{ana['id_pesquisa']}-A02.csv.gz")), f"{first} -> {after}")
    db.con.close()

    # cópia do banco real (opcional)
    real = os.path.join(ROOT, "dados_locais", "avaliacoes.sqlite")
    if "--copia-do-banco" in sys.argv and os.path.exists(real):
        copy_root = os.path.join(tmp, "copia")
        shutil.copytree(os.path.join(ROOT, "dados_locais"), os.path.join(copy_root, "dados_locais"))
        cdb = Banco(os.path.join(copy_root, "dados_locais", "avaliacoes.sqlite"))
        s = dataset.exportar(cdb, os.path.join(tmp, "exp_copia"), root=copy_root)
        check_export(os.path.join(tmp, "exp_copia"), cdb, "cópia de dados_locais", dataset.Opcoes(),
                     expect_match=False)
        print(f"cópia de dados_locais: {s['avaliacoes']} avaliações, {s['conferem']} conferem com o salvo; "
              f"não conferem: {s['nao_conferem']}")
        cdb.con.close()

print(f"\n(pandas {'usado: ' + pd.__version__ if pd is not None else 'não instalado: leitura feita com o módulo csv'})")
print("\n" + ("Todos os testes passaram." if not failures else f"{len(failures)} falha(s): {failures}"))
sys.exit(1 if failures else 0)
