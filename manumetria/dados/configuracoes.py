"""Configurações: relatório (instituição, logotipo, título, profissional padrão),
tema da interface, suavização do sinal e se as dicas da avaliação já foram vistas."""

import json
import os

from manumetria.calculo import filtros
from manumetria.caminhos import CONFIG_PATH, DATA_DIR, ROOT

LOGO_DIR = DATA_DIR     # o logotipo escolhido em Configurações é copiado para cá (dado do usuário)
DEFAULT_LOGO = "manumetria/recursos/logo_relatorio.png"   # o que acompanha o sistema (nunca é sobrescrito)
# outro caminho aceito para o logotipo padrão: config.json gravado com a pasta assets/
DEFAULT_LOGO_ALIASES = {"assets/logo_relatorio.png"}
DEFAULTS = {
    "instituicao": "UFCSPA — Universidade Federal de Ciências da Saúde de Porto Alegre",
    "titulo": "Relatório de avaliação cinemática da mão",
    "logo": DEFAULT_LOGO,       # relativo à pasta do projeto; trocado em Configurações
    "profissional_padrao": "",
    "tema": "escuro",           # "escuro" ou "claro" (lido ao abrir o programa)
    "escala": 1.0,              # tamanho da interface: 1.0, 1.15 ou 1.3 (idem)
    "dicas_vistas": False,      # as dicas da avaliação já apareceram uma vez
    "suavizacao": filtros.PADRAO,   # filtro dos ângulos nas próximas avaliações (calculo/filtros.py)
    "suavizacao_medidas": False,    # True: o filtro entra também nas medidas
}


def load():
    """Configurações salvas (config.json) sobre os padrões; sem arquivo ou com erro, os padrões."""
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg):
    """Grava as configurações em dados_locais/config.json."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=1)


def logo_path(cfg):
    """Caminho absoluto do logotipo, se o arquivo existir."""
    path = cfg.get("logo") or ""
    if path.replace("\\", "/") in DEFAULT_LOGO_ALIASES:
        path = DEFAULT_LOGO
    if path and not os.path.isabs(path):
        path = os.path.join(ROOT, path)
    return path if path and os.path.exists(path) else None
