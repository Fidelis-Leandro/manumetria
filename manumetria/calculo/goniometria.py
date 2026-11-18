"""
Goniometria dos dedos: nomes, articulações, valores normais da literatura e
ângulos de flexão por decomposição por osso (recomendação ISB, Wu et al. 2005).

  - ângulos MCP / PIP / DIP (polegar: MCP / IP) com sinal: positivo = flexão,
    negativo = hiperextensão
  - TAM (Total Active Motion) normal da literatura (~260° nos dedos longos, ~140° no
    polegar) e a classificação do % do normal (ruim / regular / bom)
  - plausibilidade do quadro (ângulo impossível = erro do MediaPipe) e vista da mão
    (palma de frente ou de lado)

Numpy puro, sem interface.
"""

import numpy as np

FINGERS = ["thumb", "index", "middle", "ring", "pinky"]
SHORT = {"thumb": "POL", "index": "IND", "middle": "MÉD", "ring": "ANE", "pinky": "MÍN"}
NAME = {"thumb": "Polegar", "index": "Indicador", "middle": "Médio",
        "ring": "Anelar", "pinky": "Mínimo"}

# Articulações de cada dedo: (sigla, (landmark antes, vértice, landmark depois))
# Índices MediaPipe: 0 punho; 1-4 polegar; 5-8 indicador; 9-12 médio; 13-16 anelar; 17-20 mínimo
JOINTS = {
    "thumb": [("MCP", (1, 2, 3)), ("IP", (2, 3, 4))],
    "index": [("MCP", (0, 5, 6)), ("PIP", (5, 6, 7)), ("DIP", (6, 7, 8))],
    "middle": [("MCP", (0, 9, 10)), ("PIP", (9, 10, 11)), ("DIP", (10, 11, 12))],
    "ring": [("MCP", (0, 13, 14)), ("PIP", (13, 14, 15)), ("DIP", (14, 15, 16))],
    "pinky": [("MCP", (0, 17, 18)), ("PIP", (17, 18, 19)), ("DIP", (18, 19, 20))],
}

# Flexão ativa normal (graus), valores típicos da literatura.
# TAM normal = soma: ~260° nos dedos longos, ~140° no polegar.
_LONG = {"MCP": 85.0, "PIP": 105.0, "DIP": 70.0}
NORMAL_JOINT = {"thumb": {"MCP": 60.0, "IP": 80.0}, "index": _LONG, "middle": _LONG,
                "ring": _LONG, "pinky": _LONG}


def normal_tam(finger):
    """TAM normal do dedo (°): soma das flexões normais das articulações (NORMAL_JOINT)."""
    return sum(NORMAL_JOINT[finger].values())


# Classificação do TAM ativo em % do normal (no estilo ASSH):
# < 50% ruim, 50% até abaixo de 75% regular, >= 75% bom (faixas no estilo da ASSH,
# fonte secundária; a ASSH também tem "excelente" = normal, aqui junto com "bom").
GRADE_FAIR = 0.50
GRADE_GOOD = 0.75

def grade(pct):
    """% do normal -> "ruim" | "regular" | "bom" (None sem dados)."""
    if pct is None:
        return None
    if pct < GRADE_FAIR:
        return "ruim"
    return "regular" if pct < GRADE_GOOD else "bom"


# Ângulo fora desta faixa não é da mão, é erro do MediaPipe (pontos trocados
# ou escondidos ao girar a mão). O frame inteiro é DESCARTADO, como uma falha
# de detecção; nenhum valor é corrigido, e o quadro não entra na suavização. Na gravação de
# referência, 3 de 1.550 quadros com mão (num giro rápido) davam até -102° de
# "hiperextensão" e estragariam máximos e mínimos da sessão.
PLAUSIBLE_RANGE = (-60.0, 130.0)


def plausible(angles):
    """True se todos os ângulos estão em PLAUSIBLE_RANGE (fora dela o quadro é descartado)."""
    lo, hi = PLAUSIBLE_RANGE
    return all(((v >= lo) & (v <= hi)).all() for v in angles.values())


# Vista da mão: com a mão de lado o MediaPipe erra mais os ângulos (na gravação
# de referência, os 3 quadros com ângulo impossível tinham a mão a 75-128° da
# palma de frente). Só frames até VIEW_MAX_DEG da palma de frente entram nas
# medições (limite escolhido, sem fonte).
# (180 desliga a regra.)
VIEW_MAX_DEG = 60.0


def view_angle(world, hand):
    """Ângulo entre a palma e a câmera: 0° = palma de frente, 90° = de lado,
    180° = dorso de frente. hand = mão real ("Right"/"Left")."""
    P = np.asarray(world, dtype=np.float64)
    n = np.cross(P[5] - P[0], P[17] - P[0])
    n /= np.linalg.norm(n) + 1e-12
    # conferido com a simulação: mão real direita com a palma para a câmera
    # tem n = (0, 0, +1); a esquerda, o oposto
    cos = n[2] * (1.0 if hand == "Right" else -1.0)
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def good_view(world, hand):
    """True se a palma está a até VIEW_MAX_DEG da câmera; sem o lado da mão, não julga."""
    return hand not in ("Right", "Left") or view_angle(world, hand) <= VIEW_MAX_DEG


# =============================================================================
# Ângulos: decomposição por osso, recomendação da ISB para a mão (Wu et al., J Biomech 2005)
# =============================================================================
# Porte fiel do goniômetro da versão web (C:\sistema-mao-web\core\goniometro.js, função
# gonio, idêntica ao Hand Filter Lab). Cada osso ganha eixos próprios: Y ao longo do osso,
# Z lateral, volar = Z x Y. A flexão de uma articulação é o ângulo do osso distal no plano
# sagital (Y, volar) do osso proximal; a parte lateral (abdução) fica de fora.
#   - metacarpo de cada dedo longo: punho -> base do dedo (o MediaPipe não marca a base do
#     metacarpo); Z = linha base do indicador -> base do mínimo, tirada a parte ao longo do osso;
#   - falanges: o Z do osso anterior, tirada a parte ao longo do osso seguinte (o eixo lateral é
#     levado ao longo da cadeia);
#   - polegar (MCP e IP): eixo de dobra = normal da palma, tirada a parte ao longo do
#     metacarpo do polegar (o mesmo eixo para as duas articulações).
# A rotação axial dos dedos não aparece nos 21 pontos (eles ficam sobre o eixo dos ossos).
# Conferido contra o JavaScript original na gravação de referência e no autoteste do lab
# (tests/test_auditoria.py; docs/AUDITORIA_CALCULOS.md).
LONG_BASES = {"index": 5, "middle": 9, "ring": 13, "pinky": 17}


def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else np.zeros(3)


def _orth(v, axis):
    """v sem a parte ao longo de `axis` (unitário), normalizado."""
    return _unit(v - axis * (v @ axis))


def _flex(d, y, z):
    """Flexão (°) do segmento d em relação ao osso de eixo y e eixo lateral z: ângulo no
    plano sagital (y, volar = z x y). Positivo = flexão (para o lado volar)."""
    return float(np.degrees(np.arctan2(d @ np.cross(z, y), d @ y)))


def left_chirality(world, hand):
    """worldToLab da referência, sem a escala: inverte y e z (giro de 180° em torno de x,
    não muda ângulos) e espelha x na geometria de mão direita. A imagem é espelhada antes
    da detecção: a mão REAL direita aparece com geometria de mão esquerda (não espelha) e
    a esquerda real, com geometria de direita (espelha). Resultado: sempre a quiralidade de
    mão esquerda, em que a flexão sai positiva."""
    P = np.asarray(world, dtype=np.float64)
    sx = -1.0 if hand == "Left" else 1.0
    return np.column_stack([sx * P[:, 0], -P[:, 1], -P[:, 2]])


def isb_angles(lm):
    """21 pontos na quiralidade de mão esquerda -> {dedo: flexões (°) com sinal}."""
    lm = np.asarray(lm, dtype=np.float64)
    lat = _unit(lm[17] - lm[5])
    n_palm = _unit(np.cross(lm[5] - lm[0], lm[17] - lm[0]))
    out = {}
    t1, t2, t3 = _unit(lm[2] - lm[1]), _unit(lm[3] - lm[2]), _unit(lm[4] - lm[3])
    k1 = _orth(n_palm, t1)

    def bend(a, d, k):                     # ângulo de a até d em torno de k (d projetado)
        dp = _orth(d, k)
        return float(np.degrees(np.arctan2(np.cross(a, dp) @ k, a @ dp)))
    out["thumb"] = np.array([bend(t1, t2, k1), bend(t2, t3, k1)])
    for f, b in LONG_BASES.items():
        ym = _unit(lm[b] - lm[0])
        zm = _orth(lat, ym)                                    # metacarpo
        d1 = _unit(lm[b + 1] - lm[b])
        z1 = _orth(zm, d1)                                     # falange proximal
        d2 = _unit(lm[b + 2] - lm[b + 1])
        z2 = _orth(z1, d2)                                     # falange média
        d3 = _unit(lm[b + 3] - lm[b + 2])
        out[f] = np.array([_flex(d1, ym, zm), _flex(d2, d1, z1), _flex(d3, d2, z2)])
    return {f: out[f] for f in FINGERS}


def joint_angles(world, hand=None):
    """21 landmarks 3D -> {dedo: array com a flexão de cada articulação (°)}.

    hand = mão REAL ("Right"/"Left", imagem espelhada): flexão COM SINAL (positivo =
    flexão, negativo = hiperextensão), pela decomposição por osso (isb_angles). Mão
    esquerda e mão direita espelhada dão os mesmos ângulos.

    Sem hand: ângulo 3D sem sinal entre os segmentos (sempre >= 0) - usado só antes
    de se saber qual é a mão.
    """
    if hand in ("Right", "Left"):
        return isb_angles(left_chirality(world, hand))
    P = np.asarray(world, dtype=np.float64)
    out = {}
    for f in FINGERS:
        values = []
        for _, (a, b, c) in JOINTS[f]:
            u, v = P[b] - P[a], P[c] - P[b]
            cos = u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-12)
            values.append(float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))))
        out[f] = np.array(values)
    return out
