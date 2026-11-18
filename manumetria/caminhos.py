"""Pastas e arquivos do projeto, num lugar só. Tudo é relativo à pasta do projeto,
então o sistema funciona de qualquer lugar onde for descompactado."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# dados locais: nunca vão para o Git (veja o .gitignore)
DATA_DIR = os.path.join(ROOT, "dados_locais")
DB_PATH = os.path.join(DATA_DIR, "avaliacoes.sqlite")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
POINTS_DIR = os.path.join(DATA_DIR, "pontos")        # pontos da mão de cada avaliação salva
REPORTS_DIR = os.path.join(ROOT, "relatorios")


def pastas_do_banco(db_path):
    """(pasta base dos caminhos relativos, pasta dos pontos) de um arquivo de banco.

    O banco padrão usa a pasta do projeto e dados_locais/pontos. Outro banco usa a pasta
    em que ele está e a subpasta pontos/ ao lado dele: os caminhos salvos continuam
    valendo se essa pasta for copiada para outro lugar ou estiver em outro disco."""
    if os.path.normcase(os.path.abspath(db_path)) == os.path.normcase(os.path.abspath(DB_PATH)):
        return ROOT, POINTS_DIR
    base = os.path.dirname(os.path.abspath(db_path))
    return base, os.path.join(base, "pontos")


def relativo(path, root=ROOT):
    """Caminho relativo à pasta do projeto, sempre com "/" (o mesmo no Windows e no Linux)."""
    return os.path.relpath(path, root).replace(os.sep, "/")


def absoluto(rel, root=ROOT):
    """Caminho relativo salvo no banco -> caminho completo. Aceita "/" e "\\" (caminhos
    gravados com a barra do Windows)."""
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    return os.path.join(root, *parts)


# arquivos que acompanham o sistema ou são baixados na instalação
RESOURCES_DIR = os.path.join(ROOT, "manumetria", "recursos")
MODEL_PATH = os.path.join(RESOURCES_DIR, "hand_landmarker.task")   # modelo do MediaPipe (fora do Git)
