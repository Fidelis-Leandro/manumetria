"""
Banco local (SQLite, um arquivo só) com pacientes e sessões.

Dado de saúde é dado pessoal sensível (LGPD, art. 11): no uso com pacientes
reais, o computador precisa de controle de acesso, criptografia do disco e
consentimento dos participantes (o banco fica só nesta máquina).
"""

import datetime
import json
import os
import secrets
import sqlite3

from nucleo import caminhos
from nucleo.caminhos import DB_PATH

FIELDS = ["identificacao", "nascimento", "sexo", "mao_dominante", "mao_avaliada", "condicao",
          "data_lesao", "profissional", "observacoes", "situacao", "data_alta"]

# Versão do esquema (PRAGMA user_version). _migrate leva o banco até SCHEMA_VERSION numa
# transação só, depois de copiar o arquivo para copias_de_seguranca/ (ao lado do banco).
# As migrações só acrescentam (nada é apagado e nenhum valor salvo muda) e podem rodar
# de novo sem efeito (idempotentes).
#   0 -> 1 (ManuMetria 1.3.0): pacientes.sexo e pacientes.id_pesquisa (pseudônimo
#          aleatório e estável para a exportação de pesquisa); sessoes.codigo (código
#          FIXO da avaliação no paciente, "A01", "A02"..., preenchido uma vez na ordem das
#          avaliações existentes) e pacientes.ultimo_codigo (último número usado: apagar
#          uma avaliação deixa um buraco e o número nunca é reaproveitado); índices.
SCHEMA_VERSION = 1
SEXES = ("feminino", "masculino")                    # vazio = não informado
_PSEUDO_CHARS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"   # sem 0/O e 1/I

SCHEMA = """
CREATE TABLE IF NOT EXISTS pacientes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    identificacao TEXT NOT NULL,          -- código ou nome FICTÍCIO
    nascimento    TEXT,                   -- aaaa-mm-dd
    sexo          TEXT,                   -- "feminino", "masculino" ou vazio (não informado)
    mao_dominante TEXT,
    mao_avaliada  TEXT,
    condicao      TEXT,                   -- condição / diagnóstico
    data_lesao    TEXT,                   -- data da lesão ou cirurgia, aaaa-mm-dd
    profissional  TEXT,
    observacoes   TEXT,
    situacao      TEXT,                   -- "alta" ou vazio (= em tratamento)
    data_alta     TEXT,                   -- aaaa-mm-dd
    id_pesquisa   TEXT,                   -- pseudônimo aleatório (exportação de pesquisa), único
    ultimo_codigo INTEGER,                -- último número de avaliação usado (sessoes.codigo)
    criado_em     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessoes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id  INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    inicio       TEXT NOT NULL,           -- aaaa-mm-ddThh:mm:ss (hora local; fuso em resultados.fuso_utc)
    duracao_s    INTEGER,
    mao          TEXT,                    -- "Right" / "Left" (mão real detectada)
    resultados   TEXT NOT NULL,           -- JSON (app/dados/resultados.py)
    observacoes  TEXT,                    -- texto do profissional, vai para o relatório
    codigo       TEXT,                    -- código fixo da avaliação no paciente ("A01"), nunca renumerado
    criado_em    TEXT NOT NULL
);
"""


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _code(n):
    """Número da avaliação no paciente -> código fixo ("A01", ..., "A99", "A100")."""
    return f"A{n:02d}"


class Banco:
    def __init__(self, path=DB_PATH, backup_dir=None):
        """backup_dir = onde copiar o banco antes de uma migração (padrão: a pasta
        copias_de_seguranca ao lado do banco)."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        self.backup_dir = backup_dir or os.path.join(os.path.dirname(os.path.abspath(path)),
                                                     "copias_de_seguranca")
        self.last_backup = None           # cópia feita na abertura (migração), se houve
        self.con = sqlite3.connect(path)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        existed = self.con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'pacientes'").fetchone()
        if existed and self.schema_version() < SCHEMA_VERSION:   # cópia antes de qualquer mudança
            self.last_backup = self.backup(f"antes_do_esquema_v{SCHEMA_VERSION}")
        self.con.executescript(SCHEMA)
        self._migrate()

    # ------------------------------------------------------------- migração
    def schema_version(self):
        return self.con.execute("PRAGMA user_version").fetchone()[0]

    def _migrate(self):
        if self.schema_version() >= SCHEMA_VERSION:
            return
        self.con.execute("BEGIN")
        try:
            columns = {r["name"] for r in self.con.execute("PRAGMA table_info(pacientes)")}
            # situacao/data_alta: bancos anteriores ao controle de versão; sexo/id_pesquisa: v1
            for col in ("situacao", "data_alta", "sexo", "id_pesquisa"):
                if col not in columns:
                    self.con.execute(f"ALTER TABLE pacientes ADD COLUMN {col} TEXT")
            if "ultimo_codigo" not in columns:
                self.con.execute("ALTER TABLE pacientes ADD COLUMN ultimo_codigo INTEGER")
            if "codigo" not in {r["name"] for r in self.con.execute("PRAGMA table_info(sessoes)")}:
                self.con.execute("ALTER TABLE sessoes ADD COLUMN codigo TEXT")
            for (pid,) in self.con.execute("SELECT id FROM pacientes WHERE id_pesquisa IS NULL").fetchall():
                self.con.execute("UPDATE pacientes SET id_pesquisa = ? WHERE id = ?",
                                 (self._new_pseudonym(), pid))
            # código fixo das avaliações existentes, na ordem atual (data, depois id); uma vez só
            for (pid,) in self.con.execute("SELECT id FROM pacientes").fetchall():
                used = self.con.execute("SELECT ultimo_codigo FROM pacientes WHERE id = ?", (pid,)).fetchone()[0] or 0
                for (sid,) in self.con.execute("SELECT id FROM sessoes WHERE paciente_id = ? AND codigo IS NULL "
                                               "ORDER BY inicio, id", (pid,)).fetchall():
                    used += 1
                    self.con.execute("UPDATE sessoes SET codigo = ? WHERE id = ?", (_code(used), sid))
                self.con.execute("UPDATE pacientes SET ultimo_codigo = ? WHERE id = ?", (used, pid))
            self.con.execute("CREATE UNIQUE INDEX IF NOT EXISTS pacientes_id_pesquisa ON pacientes(id_pesquisa)")
            self.con.execute("CREATE UNIQUE INDEX IF NOT EXISTS sessoes_codigo ON sessoes(paciente_id, codigo)")
            self.con.execute("CREATE INDEX IF NOT EXISTS sessoes_paciente ON sessoes(paciente_id, inicio)")
            self.con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self.con.commit()
        except Exception:
            self.con.rollback()
            raise

    def backup(self, label):
        """Cópia consistente do banco (API de backup do SQLite). Devolve o caminho."""
        os.makedirs(self.backup_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = os.path.splitext(os.path.basename(self.path))[0]
        dest = os.path.join(self.backup_dir, f"{name}_{stamp}_{label}.sqlite")
        out = sqlite3.connect(dest)
        try:
            self.con.backup(out)
        finally:
            out.close()
        return dest

    def _new_pseudonym(self):
        """Código aleatório (não segue a ordem de cadastro), ex.: "P-7K3Q9X"."""
        while True:
            code = "P-" + "".join(secrets.choice(_PSEUDO_CHARS) for _ in range(6))
            if not self.con.execute("SELECT 1 FROM pacientes WHERE id_pesquisa = ?", (code,)).fetchone():
                return code

    # ------------------------------------------------------------ pacientes
    def pacientes(self, busca="", situacao=None):
        """Lista com nº de sessões e data da última, mais recentes primeiro.
        situacao = "tratamento", "alta" ou None (todos)."""
        like = f"%{busca.strip()}%"
        only = {"alta": "AND p.situacao = 'alta'",
                "tratamento": "AND IFNULL(p.situacao, '') <> 'alta'"}.get(situacao, "")
        rows = self.con.execute(
            f"""SELECT p.*, COUNT(s.id) AS n_sessoes, MAX(s.inicio) AS ultima_sessao
                FROM pacientes p LEFT JOIN sessoes s ON s.paciente_id = p.id
                WHERE (p.identificacao LIKE ? OR IFNULL(p.condicao, '') LIKE ?) {only}
                GROUP BY p.id
                ORDER BY (ultima_sessao IS NULL), ultima_sessao DESC, p.identificacao""",
            (like, like))
        return [dict(r) for r in rows]

    def paciente(self, pid):
        row = self.con.execute("SELECT * FROM pacientes WHERE id = ?", (pid,)).fetchone()
        return dict(row) if row else None

    def salvar_paciente(self, dados, pid=None):
        values = [dados.get(f) or None for f in FIELDS]
        if pid is None:
            cur = self.con.execute(
                f"INSERT INTO pacientes ({', '.join(FIELDS)}, id_pesquisa, criado_em) "
                f"VALUES ({', '.join('?' * len(FIELDS))}, ?, ?)", values + [self._new_pseudonym(), _now()])
            pid = cur.lastrowid
        else:
            self.con.execute(f"UPDATE pacientes SET {', '.join(f + ' = ?' for f in FIELDS)} WHERE id = ?",
                             values + [pid])
        self.con.commit()
        return pid

    def excluir_paciente(self, pid):
        """Apaga o paciente, as sessões e as gravações ligadas a elas. Primeiro o banco
        (uma transação); depois os arquivos: se o programa fechar no meio, nenhuma
        avaliação fica apontando para um arquivo apagado. Devolve os arquivos que não
        puderam ser apagados (normalmente nenhum)."""
        files = [s["resultados"].get("pontos") for s in self.sessoes(pid)]
        self.con.execute("DELETE FROM pacientes WHERE id = ?", (pid,))
        self.con.commit()
        return self._apagar_arquivos(files)

    @staticmethod
    def _apagar_arquivos(paths):
        """Arquivos de pontos da mão (caminhos relativos salvos nas sessões)."""
        failed = []
        for rel in paths:
            if not rel:
                continue
            path = caminhos.absoluto(rel, caminhos.ROOT)
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                failed.append(path)
        return failed

    # -------------------------------------------------------------- sessões
    def _sessao(self, row):
        d = dict(row)
        d["resultados"] = json.loads(d["resultados"])
        return d

    def sessoes(self, pid):
        """Sessões do paciente, da mais antiga para a mais recente."""
        rows = self.con.execute("SELECT * FROM sessoes WHERE paciente_id = ? ORDER BY inicio", (pid,))
        return [self._sessao(r) for r in rows]

    def sessao(self, sid):
        row = self.con.execute("SELECT * FROM sessoes WHERE id = ?", (sid,)).fetchone()
        return self._sessao(row) if row else None

    def todas_sessoes(self):
        """Todas as sessões de todos os pacientes (erro de medida, exportação)."""
        rows = self.con.execute("SELECT * FROM sessoes ORDER BY paciente_id, inicio")
        return [self._sessao(r) for r in rows]

    def salvar_sessao(self, pid, resultados, observacoes="", gravar_pontos=None):
        """gravar_pontos(caminho relativo) grava o arquivo de pontos ANTES da linha no
        banco: uma avaliação salva nunca aponta para pontos que não existem. Se o banco
        falhar, o arquivo recém-gravado é apagado."""
        points = resultados.get("pontos")
        if gravar_pontos is not None and points:
            gravar_pontos(points)
        try:                              # código e linha na mesma transação
            row = self.con.execute("SELECT ultimo_codigo FROM pacientes WHERE id = ?", (pid,)).fetchone()
            n = ((row[0] if row else 0) or 0) + 1
            self.con.execute("UPDATE pacientes SET ultimo_codigo = ? WHERE id = ?", (n, pid))
            cur = self.con.execute(
                "INSERT INTO sessoes (paciente_id, inicio, duracao_s, mao, resultados, observacoes, codigo,"
                " criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (pid, resultados["inicio"], resultados["duracao_s"], resultados["mao"],
                 json.dumps(resultados, ensure_ascii=False), observacoes, _code(n), _now()))
            self.con.commit()
        except Exception:
            self.con.rollback()
            if gravar_pontos is not None and points:
                self._apagar_arquivos([points])
            raise
        return cur.lastrowid

    def atualizar_resultados(self, sid, resultados):
        """Troca os resultados de uma sessão (recálculo a partir dos pontos gravados)."""
        self.con.execute("UPDATE sessoes SET resultados = ?, mao = ? WHERE id = ?",
                         (json.dumps(resultados, ensure_ascii=False), resultados["mao"], sid))
        self.con.commit()

    def atualizar_observacoes(self, sid, texto):
        self.con.execute("UPDATE sessoes SET observacoes = ? WHERE id = ?", (texto, sid))
        self.con.commit()

    def excluir_sessao(self, sid):
        """Apaga a sessão (banco primeiro) e o arquivo de pontos dela."""
        s = self.sessao(sid)
        self.con.execute("DELETE FROM sessoes WHERE id = ?", (sid,))
        self.con.commit()
        return self._apagar_arquivos([s["resultados"].get("pontos")] if s else [])
