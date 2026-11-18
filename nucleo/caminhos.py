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

BACKUP_DIR = os.path.join(DATA_DIR, "copias_de_seguranca")   # cópia do banco antes de cada migração


def relativo(path, root=ROOT):
    """Caminho relativo à pasta do projeto, sempre com "/" (o mesmo no Windows e no Linux)."""
    return os.path.relpath(path, root).replace(os.sep, "/")


def absoluto(rel, root=ROOT):
    """Caminho relativo salvo no banco -> caminho completo. Aceita "/" e "\\" (as avaliações
    salvas até a 1.2.0 guardaram o caminho com a barra do Windows)."""
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    return os.path.join(root, *parts)


# arquivos que acompanham o sistema ou são baixados na instalação
ASSETS_DIR = os.path.join(ROOT, "assets")
MODEL_PATH = os.path.join(ROOT, "hand_landmarker.task")   # modelo do MediaPipe
