"""
Banco, gravação dos pontos e rastreabilidade (correções da 1.3.0). Tudo em pastas
temporárias: nada aqui toca em dados_locais.

    .venv\\Scripts\\python.exe tests\\test_banco.py
"""

import csv
import datetime
import json
import os
import sqlite3
import sys
import tempfile

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from app import versao  # noqa: E402
from app.avaliador import Avaliador, analisar  # noqa: E402
from app.dados import banco as banco_mod, exportacao, recalculo  # noqa: E402
from app.dados import resultados as res  # noqa: E402
from app.dados.banco import Banco  # noqa: E402
from nucleo import caminhos, capture  # noqa: E402

RECORDING = os.path.join(ROOT, "tests", "dados", "gravacao_referencia.npz")
failures = []


def check(name, ok, detail=""):
    print(f"[{'ok' if ok else 'FALHOU'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


# esquema como era até a 1.2.0 (sem versão, sem sexo nem id_pesquisa)
OLD_SCHEMA = """
CREATE TABLE pacientes (id INTEGER PRIMARY KEY AUTOINCREMENT, identificacao TEXT NOT NULL, nascimento TEXT,
    mao_dominante TEXT, mao_avaliada TEXT, condicao TEXT, data_lesao TEXT, profissional TEXT, observacoes TEXT,
    situacao TEXT, data_alta TEXT, criado_em TEXT NOT NULL);
CREATE TABLE sessoes (id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE, inicio TEXT NOT NULL,
    duracao_s INTEGER, mao TEXT, resultados TEXT NOT NULL, observacoes TEXT, criado_em TEXT NOT NULL);
"""

rows = capture.load_recording(RECORDING)
out = analisar(rows).results(rows[-1]["t"], "gravação de teste")

# ---------------------------------------------------------------- migração
# (as exclusões apagam pontos pela pasta do projeto: aponta para a temporária)
_root = caminhos.ROOT
with tempfile.TemporaryDirectory() as tmp:
    caminhos.ROOT = tmp
    path = os.path.join(tmp, "antigo.sqlite")
    con = sqlite3.connect(path)
    con.executescript(OLD_SCHEMA)
    old_json = json.dumps({k: v for k, v in out.items() if k not in ("versao_app", "goniometria", "fuso_utc")},
                          ensure_ascii=False)
    for i in range(3):
        con.execute("INSERT INTO pacientes (identificacao, nascimento, criado_em) VALUES (?, ?, ?)",
                    (f"Paciente {i}", "1980-01-0" + str(i + 1), "2026-01-01T10:00:00"))
        con.execute("INSERT INTO sessoes (paciente_id, inicio, duracao_s, mao, resultados, criado_em) "
                    "VALUES (?, ?, ?, ?, ?, ?)", (i + 1, "2026-02-01T10:00:00", 30, "Right", old_json,
                                                   "2026-02-01T10:01:00"))
    # paciente com 3 avaliações gravadas fora da ordem das datas (o código segue a data)
    con.execute("INSERT INTO pacientes (identificacao, criado_em) VALUES ('Quarto', '2026-01-01T10:00:00')")
    for day in ("2026-03-10", "2026-03-01", "2026-03-20"):
        con.execute("INSERT INTO sessoes (paciente_id, inicio, duracao_s, mao, resultados, criado_em) "
                    "VALUES (4, ?, 30, 'Right', ?, ?)", (day + "T10:00:00", old_json, day + "T10:01:00"))
    con.commit()
    con.close()
    con = sqlite3.connect(path)
    before = list(con.iterdump())
    con.close()

    db = Banco(path)
    pats = db.pacientes("")
    codes = [p["id_pesquisa"] for p in pats]
    check("migração: banco antigo vai para o esquema 1 com sexo e id_pesquisa",
          db.schema_version() == banco_mod.SCHEMA_VERSION == 1 and all("sexo" in p for p in pats))
    check("migração: pseudônimos únicos no formato P-XXXXXX, sem o nome",
          len(set(codes)) == 4 and all(len(c) == 8 and c.startswith("P-") for c in codes)
          and not any(p["identificacao"].split()[0].upper() in p["id_pesquisa"] for p in pats), f"{codes}")
    check("migração: nenhum dado salvo muda (resultados idênticos)",
          all(json.dumps(s["resultados"], ensure_ascii=False) == old_json for s in db.todas_sessoes()))
    bk = db.last_backup
    ok_backup = bk is not None and os.path.exists(bk)
    if bk:
        bcon = sqlite3.connect(bk)
        ok_backup &= list(bcon.iterdump()) == before
        ok_backup &= bcon.execute("PRAGMA user_version").fetchone()[0] == 0
        bcon.close()
    check("migração: cópia de segurança antes de migrar (mesmo conteúdo do original, esquema 0)", ok_backup,
          f"{bk}")
    db.con.close()

    db = Banco(path)
    by_day = {s["inicio"][:10]: s["codigo"] for s in db.sessoes(4)}
    check("migração: código fixo das avaliações existentes na ordem atual (data), um por paciente",
          by_day == {"2026-03-01": "A01", "2026-03-10": "A02", "2026-03-20": "A03"}
          and {s["codigo"] for s in db.sessoes(1)} == {"A01"} and db.paciente(4)["ultimo_codigo"] == 3,
          f"{by_day}")
    db.con.close()

    db = Banco(path)                                  # de novo: nada muda, nenhuma cópia nova
    check("migração idempotente: códigos das avaliações iguais ao reabrir",
          {s["inicio"][:10]: s["codigo"] for s in db.sessoes(4)} == by_day)
    sid4 = db.salvar_sessao(4, dict(out, inicio="2026-04-01T10:00:00"))
    check("avaliação nova recebe o próximo código (A04)", db.sessao(sid4)["codigo"] == "A04")
    a02 = next(s["id"] for s in db.sessoes(4) if s["codigo"] == "A02")
    a03 = next(s["id"] for s in db.sessoes(4) if s["codigo"] == "A03")
    db.excluir_sessao(a02)
    check("apagar a A02 não muda o código da A03 (fica um buraco)", db.sessao(a03)["codigo"] == "A03"
          and [s["codigo"] for s in db.sessoes(4)] == ["A01", "A03", "A04"])
    db.excluir_sessao(sid4)
    sid5 = db.salvar_sessao(4, dict(out, inicio="2026-04-08T10:00:00"))
    check("código nunca é reaproveitado: depois de apagar a última (A04), a nova é A05",
          db.sessao(sid5)["codigo"] == "A05")
    check("migração e códigos não alteram nenhuma medida",
          all(json.dumps(s["resultados"], ensure_ascii=False) == old_json for s in db.sessoes(4)
              if s["id"] != sid5))
    db.con.close()

    db = Banco(path)
    check("migração idempotente: reabrir não muda os pseudônimos nem faz outra cópia",
          [p["id_pesquisa"] for p in db.pacientes("")] == codes and db.last_backup is None
          and len(os.listdir(os.path.join(tmp, "copias_de_seguranca"))) == 1)
    pid = db.salvar_paciente({"identificacao": "Novo", "sexo": "feminino"})
    p = db.paciente(pid)
    check("paciente novo ganha pseudônimo e guarda o sexo", p["id_pesquisa"] not in codes
          and p["id_pesquisa"].startswith("P-") and p["sexo"] == "feminino")
    db.con.close()

    fresh = Banco(os.path.join(tmp, "novo.sqlite"))
    check("banco novo: esquema 1 direto, sem cópia de segurança",
          fresh.schema_version() == 1 and fresh.last_backup is None)
    fresh.con.close()
    caminhos.ROOT = _root

# ------------------------------------------------------- caminhos portáveis
check("caminho de pontos salvo com a barra do Windows funciona em qualquer sistema",
      caminhos.absoluto("dados_locais\\pontos\\x.npz", "R") == os.path.join("R", "dados_locais", "pontos", "x.npz")
      and caminhos.absoluto("dados_locais/pontos/x.npz", "R") == os.path.join("R", "dados_locais", "pontos", "x.npz"))
check("caminho novo dos pontos é gravado com '/'", "\\" not in Avaliador().points_path()
      and Avaliador().points_path().startswith("dados_locais/pontos/sessao_"))

# ------------------------------------------------------- gravação atômica
with tempfile.TemporaryDirectory() as tmp:
    target = os.path.join(tmp, "pontos", "a.npz")
    capture.save_recording(target, rows[:50])
    good = open(target, "rb").read()
    real = np.savez_compressed

    def broken(fh, **kw):
        fh.write(b"PK\x03\x04 metade do arquivo")
        raise OSError("disco cheio (simulado)")
    np.savez_compressed = broken
    try:
        capture.save_recording(target, rows)
        raised = False
    except OSError:
        raised = True
    finally:
        np.savez_compressed = real
    check("pontos: falha no meio da gravação não estraga o arquivo anterior nem deixa temporário",
          raised and open(target, "rb").read() == good and os.listdir(os.path.dirname(target)) == ["a.npz"])
    back = capture.load_recording(target)
    check("pontos: gravação lida de volta igual (50 quadros)", len(back) == 50
          and np.allclose(back[10]["world"], np.asarray(rows[10]["world"], np.float32)))

# ------------------------------------- salvar: pontos antes, banco depois
with tempfile.TemporaryDirectory() as tmp:
    old_root = caminhos.ROOT
    caminhos.ROOT = tmp
    try:
        db = Banco(os.path.join(tmp, "b.sqlite"))
        pid = db.salvar_paciente({"identificacao": "X"})
        rel = "dados_locais/pontos/sessao_teste.npz"
        seen = {}

        def writer(r):
            seen["rows_before"] = db.con.execute("SELECT COUNT(*) FROM sessoes").fetchone()[0]
            capture.save_recording(caminhos.absoluto(r, tmp), rows[:30])
        sid = db.salvar_sessao(pid, dict(out, pontos=rel), "", gravar_pontos=writer)
        check("salvar: pontos gravados antes da linha no banco", seen.get("rows_before") == 0
              and os.path.exists(caminhos.absoluto(rel, tmp)) and db.sessao(sid) is not None)

        rel2 = "dados_locais/pontos/sessao_falha.npz"
        try:
            db.salvar_sessao(9999, dict(out, pontos=rel2), "", gravar_pontos=writer)   # paciente inexistente
            failed = False
        except sqlite3.IntegrityError:
            failed = True
        check("salvar: se o banco recusa, o arquivo de pontos novo é apagado (nada órfão)",
              failed and not os.path.exists(caminhos.absoluto(rel2, tmp))
              and db.con.execute("SELECT COUNT(*) FROM sessoes").fetchone()[0] == 1)

        # excluir: banco primeiro, arquivos depois
        os.makedirs(caminhos.absoluto("dados_locais/pontos/pasta.npz", tmp))      # não pode ser removido
        sid2 = db.salvar_sessao(pid, dict(out, pontos="dados_locais/pontos/pasta.npz"))
        left = db.excluir_paciente(pid)
        check("excluir paciente: sessões e pontos apagados; arquivo que não sai é informado, sem desfazer o banco",
              db.paciente(pid) is None and db.sessao(sid) is None and db.sessao(sid2) is None
              and not os.path.exists(caminhos.absoluto(rel, tmp)) and len(left) == 1, f"{left}")
        db.con.close()
    finally:
        caminhos.ROOT = old_root

# ---------------------------------------------------- versão e método
check("resultado registra a versão do ManuMetria, o método dos ângulos e o fuso",
      out["versao"] == 3 and out["versao_app"] == versao.VERSAO and out["goniometria"] == versao.GONIOMETRIA
      and len(out["fuso_utc"]) == 6 and out["fuso_utc"][0] in "+-", f"{out['fuso_utc']}")
off = res.utc_offset(datetime.datetime(2026, 7, 1, 12, 0))
check("fuso no formato ISO 8601 (±hh:mm)", len(off) == 6 and off[3] == ":")
old = {k: v for k, v in out.items() if k not in ("versao_app", "goniometria", "fuso_utc")}
old["pontos"] = os.path.relpath(RECORDING, ROOT)
new = recalculo._recalculate(old, rows)
check("recálculo registra a versão atual e não inventa fuso para avaliação antiga",
      new["versao_app"] == versao.VERSAO and "fuso_utc" not in new and new["dedos"] == out["dedos"])

# ------------------------------------------- planilha para o Excel (sem quebrar)
with tempfile.TemporaryDirectory() as tmp:
    old_root = caminhos.ROOT
    try:
        db = Banco(os.path.join(tmp, "c.sqlite"))
        pid = db.salvar_paciente({"identificacao": "Y", "nascimento": "1990-01-01"})
        db.salvar_sessao(pid, out)
        db.salvar_sessao(pid, old)
        path, n = exportacao.export_research(db, os.path.join(tmp, "exp"))
        with open(path, encoding="utf-8-sig", newline="") as fh:
            table = list(csv.reader(fh, delimiter=";"))
        before = ([c for c, _, _ in exportacao.SESSION_COLUMNS] + res.CSV_HEADER
                  + [c for c, _, _ in exportacao.RETEST_COLUMNS])
        head = table[0]
        check("planilha: colunas anteriores na mesma ordem; versão e método no fim",
              head[:len(before)] == before and head[len(before):] == ["versao_calculo", "metodo_goniometria"])
        col = head.index("versao_calculo")
        check("planilha: versão preenchida na avaliação nova e vazia (não registrada) na antiga",
              {r[col] for r in table[1:6]} == {versao.VERSAO} and {r[col] for r in table[6:11]} == {""})
        with open(os.path.join(tmp, "exp", "dicionario_de_dados.csv"), encoding="utf-8-sig", newline="") as fh:
            names = {r[0] for r in csv.reader(fh, delimiter=";") if r}
        check("planilha: dicionário cobre todas as colunas", set(head) <= names)
        text = open(path, encoding="utf-8-sig").read()
        check("planilha identificada: sem a coluna nem o caminho do arquivo de pontos",
              "arquivo_pontos" not in head and "arquivo_pontos" not in names and ".npz" not in text
              and "Y" in [r[head.index("paciente_codigo")] for r in table[1:]])
        db.con.close()
    finally:
        caminhos.ROOT = old_root

print("\n" + ("Todos os testes passaram." if not failures else f"{len(failures)} falha(s): {failures}"))
sys.exit(1 if failures else 0)
