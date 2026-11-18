"""
Gera o pacote do código-fonte do ManuMetria para o registro de software (INPI).

    .venv\\Scripts\\python.exe tools\\gerar_hash_registro.py
    (ou dois cliques em gerar_hash_registro.bat)

Rode SOMENTE depois da aprovação final do orientador, com a versão definitiva.

O que faz:
  1. monta um ZIP só com o código-fonte e a documentação: os arquivos
     versionados no Git (git ls-files) ou, sem Git, os arquivos da pasta,
     sempre sem .git, .venv, __pycache__, dados_locais/ (pacientes), relatórios,
     gravações, cópias de segurança e o modelo baixado do MediaPipe;
  2. calcula o SHA-512 do ZIP;
  3. salva o ZIP e um .txt (hash, data e lista de arquivos com o SHA-256 de
     cada um) na pasta REGISTRO_INPI, AO LADO da pasta do projeto (fora do
     repositório).

O ZIP é reprodutível: arquivos em ordem alfabética e com data fixa dentro do
ZIP, então gerar de novo com os mesmos arquivos dá o mesmo hash. Mesmo assim,
o ZIP gerado NUNCA mais deve ser alterado: guarde-o em mais de um lugar.
"""

import datetime
import fnmatch
import hashlib
import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(os.path.dirname(ROOT), "REGISTRO_INPI")
NAME = "manumetria"

# nunca entram no pacote: pastas em qualquer nível, pastas de dados do usuário na raiz do projeto
# (manumetria/relatorios/ é código e entra) e padrões de arquivo
EXCLUDED_DIRS = {".git", ".venv", "venv", "__pycache__", "copias_de_seguranca", ".vscode", ".idea", ".claude"}
EXCLUDED_ROOT_DIRS = {"dados_locais", "relatorios", "gravacoes", "REGISTRO_INPI"}
EXCLUDED_FILES = ["*.pyc", "*.sqlite", "*.sqlite-journal", "hand_landmarker.task", "*.gravando", "Thumbs.db",
                  "desktop.ini", ".DS_Store", "*.zip"]
ZIP_DATE = (2026, 1, 1, 0, 0, 0)               # data fixa dentro do ZIP (reprodutível)


def excluded(rel):
    """True se o arquivo fica fora do pacote (pasta ou nome excluídos)."""
    parts = rel.replace("\\", "/").split("/")
    if any(p in EXCLUDED_DIRS for p in parts[:-1]) or (len(parts) > 1 and parts[0] in EXCLUDED_ROOT_DIRS):
        return True
    return any(fnmatch.fnmatch(parts[-1], pat) for pat in EXCLUDED_FILES)


def list_files():
    """Arquivos versionados no Git; sem Git, todos os arquivos da pasta."""
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
        files = [f for f in out.decode("utf-8").split("\0") if f]
        source = "git ls-files"
    except (OSError, subprocess.CalledProcessError):
        files = []
        for base, dirs, names in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS
                       and not (base == ROOT and d in EXCLUDED_ROOT_DIRS)]
            files += [os.path.relpath(os.path.join(base, n), ROOT) for n in names]
        source = "pasta do projeto"
    files = sorted({f.replace("\\", "/") for f in files
                    if not excluded(f) and os.path.isfile(os.path.join(ROOT, f))})
    return files, source


def sha(path, algo):
    """Hash do arquivo com o algoritmo `algo`, lido em blocos de 1 MB."""
    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    """Gera o ZIP e o arquivo com os hashes em REGISTRO_INPI. Devolve o código de saída."""
    files, source = list_files()
    if not files:
        print("Nenhum arquivo encontrado para o pacote.")
        return 1
    now = datetime.datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    os.makedirs(OUT_DIR, exist_ok=True)
    zip_path = os.path.join(OUT_DIR, f"{NAME}_codigo_fonte_{stamp}.zip")
    txt_path = os.path.join(OUT_DIR, f"{NAME}_codigo_fonte_{stamp}_SHA512.txt")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in files:
            info = zipfile.ZipInfo(f"{NAME}/{rel}", date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(os.path.join(ROOT, rel), "rb") as fh:
                z.writestr(info, fh.read(), compresslevel=9)

    digest = sha(zip_path, "sha512")
    commit = ""
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                check=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                               check=True, text=True).stdout.strip()
        if dirty:
            commit += "  (ATENÇÃO: havia alterações não commitadas)"
    except (OSError, subprocess.CalledProcessError):
        pass

    lines = [
        "ManuMetria - Avaliação cinemática da mão por visão computacional",
        "Pacote do código-fonte para o registro de software (INPI)",
        "",
        f"Arquivo:            {os.path.basename(zip_path)}",
        f"Tamanho:            {os.path.getsize(zip_path)} bytes",
        "Algoritmo:          SHA-512",
        f"Hash (SHA-512):     {digest}",
        f"Gerado em:          {now.strftime('%d/%m/%Y %H:%M:%S')} (horário local)",
        f"Commit do Git:      {commit or '(sem Git)'}",
        f"Origem da lista:    {source}",
        f"Arquivos incluídos: {len(files)}",
        "",
        "Este ZIP não pode ser alterado: qualquer mudança muda o hash.",
        "Guarde o ZIP e este arquivo em mais de um lugar.",
        "",
        "Lista de arquivos (SHA-256 de cada arquivo  tamanho em bytes  caminho):",
    ]
    for rel in files:
        path = os.path.join(ROOT, rel)
        lines.append(f"{sha(path, 'sha256')}  {os.path.getsize(path):>9}  {rel}")
    with open(txt_path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"ZIP:   {zip_path}")
    print(f"Hash:  {txt_path}")
    print(f"SHA-512: {digest}")
    print(f"{len(files)} arquivos incluídos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
