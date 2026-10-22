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

# arquivos que acompanham o sistema ou são baixados na instalação
ASSETS_DIR = os.path.join(ROOT, "assets")
MANO_DIR = os.path.join(ASSETS_DIR, "mano")
MODEL_PATH = os.path.join(ROOT, "hand_landmarker.task")   # modelo do MediaPipe
