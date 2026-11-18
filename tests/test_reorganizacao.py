"""
Não regressão dos números: a gravação de referência (tests/dados/gravacao_referencia.npz)
passa pelo motor da avaliação e o resultado tem de ser IDÊNTICO ao guardado em
tests/dados/referencia_resultados.json (todas as medidas, de todos os dedos), com a
suavização padrão e com EMA + Kalman também nas medidas.

Ficam de fora só os campos do momento em que roda: "inicio" e "fuso_utc" (relógio),
"pontos" (caminho do arquivo) e "versao_app" (versão do ManuMetria). Qualquer mudança
de cálculo aparece aqui; se ela for intencional, o arquivo de referência é gerado de novo
e a mudança é documentada (docs/AUDITORIA_CALCULOS.md).

    .venv\\Scripts\\python.exe tests\\test_reorganizacao.py
"""

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from manumetria.avaliacao.motor import analisar  # noqa: E402
from manumetria.calculo import filtros  # noqa: E402
from manumetria.captura import gravacao  # noqa: E402

DATA = os.path.join(ROOT, "tests", "dados")
VOLATILE = ("inicio", "fuso_utc", "pontos", "versao_app")
failures = []


def check(name, ok, detail=""):
    print(f"[{'ok' if ok else 'FALHOU'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def differences(a, b, path=""):
    """Caminhos (ex.: dedos.index.qualidade.sparc) em que os dois valores diferem."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = [f"{path}.{k}".lstrip(".") + " (falta de um lado)" for k in sorted(set(a) ^ set(b))]
        for k in sorted(set(a) & set(b)):
            out += differences(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in differences(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path.lstrip('.')}: {a!r} != {b!r}"]


with open(os.path.join(DATA, "referencia_resultados.json"), encoding="utf-8") as fh:
    reference = json.load(fh)
rows = gravacao.load_recording(os.path.join(DATA, "gravacao_referencia.npz"))
modes = {"padrao": filtros.PADRAO, "ema_kalman_medidas": filtros.registro(filtros.CASCATA, nas_medidas=True)}
for name, filt in modes.items():
    res = analisar(rows, filtro=filt).results(rows[-1]["t"], "gravação de referência")
    res = json.loads(json.dumps({k: v for k, v in res.items() if k not in VOLATILE}))
    diff = differences(reference[name], res)
    check(f"gravação de referência ({name}): resultado idêntico ao de referência", not diff,
          "; ".join(diff[:5]) + (f" ... (+{len(diff) - 5})" if len(diff) > 5 else ""))

print("\n" + ("Todos os testes passaram." if not failures else f"{len(failures)} falha(s): {failures}"))
sys.exit(1 if failures else 0)
