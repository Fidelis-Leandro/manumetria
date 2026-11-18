"""
Arquitetura em camadas (docs/ARQUITETURA.md), conferida pelos imports (análise do código,
sem executar nada):

    calculo -> captura -> avaliacao -> dados -> relatorios -> interface

Cada camada só importa as anteriores e os utilitários da raiz do pacote (caminhos,
versao, formato), que não importam nenhuma camada. Só relatorios e interface usam o
PyQt5. Nenhum arquivo importa app/ ou nucleo/ (nomes fora desta estrutura).

    .venv\\Scripts\\python.exe tests\\test_arquitetura.py
"""

import ast
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "manumetria")
LAYERS = ["calculo", "captura", "avaliacao", "dados", "relatorios", "interface"]
UTILS = {"caminhos", "versao", "formato"}
QT = ("PyQt5", "pyqtgraph")
QT_LAYERS = {"relatorios", "interface"}
failures = []


def check(name, ok, detail=""):
    print(f"[{'ok' if ok else 'FALHOU'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def python_files(folder):
    for base, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".venv", ".git")]
        for n in names:
            if n.endswith(".py"):
                yield os.path.join(base, n)


def imports(path):
    """Módulos importados pelo arquivo (inclusive dentro de funções), com o número da linha."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), path)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(a.name, node.lineno) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                out.append(("." * node.level + (node.module or ""), node.lineno))
                continue
            out.append((node.module, node.lineno))
            # "from manumetria import caminhos" / "from manumetria.calculo import goniometria"
            out += [(f"{node.module}.{a.name}", node.lineno) for a in node.names
                    if node.module.split(".")[0] == "manumetria"]
    return out


def layer_of(module):
    """Camada de um módulo do pacote: nome da camada, "util" ou None (o próprio pacote)."""
    parts = module.split(".")
    if parts[0] != "manumetria" or len(parts) < 2:
        return None
    if parts[1] in UTILS:
        return "util"
    return parts[1] if parts[1] in LAYERS else "?"


modules = {}
for path in python_files(PKG):
    rel = os.path.relpath(path, ROOT)[:-3].replace(os.sep, ".").replace(".__init__", "")
    modules[rel] = path

unknown = sorted(m for m in modules if layer_of(m) == "?")
check("todo módulo do pacote está numa camada ou é utilitário", not unknown, unknown)

violations, relative, qt = [], [], []
for mod, path in sorted(modules.items()):
    mine = layer_of(mod)
    for target, line in imports(path):
        where = f"{os.path.relpath(path, ROOT)}:{line} importa {target}"
        if target.startswith("."):
            relative.append(where)
            continue
        if target.split(".")[0] in QT and mine not in QT_LAYERS:
            qt.append(where)
        theirs = layer_of(target)
        if theirs is None or theirs == "util":
            if mine == "util" and theirs == "util" and target.split(".")[1] != mod.split(".")[1]:
                violations.append(where + " (utilitário importando outro módulo do pacote)")
            continue
        if theirs == "?":
            continue
        if mine == "util" or (mine in LAYERS and LAYERS.index(theirs) > LAYERS.index(mine)):
            violations.append(where)
check("nenhuma camada importa uma camada posterior (nem os utilitários importam camadas)",
      not violations, "; ".join(violations))
check("imports absolutos (from manumetria...), sem imports relativos", not relative, "; ".join(relative))
check("PyQt5 só em relatorios e interface (cálculo, captura, avaliação e dados sem interface)",
      not qt, "; ".join(qt))

old = []
star = []
for path in python_files(ROOT):
    for target, line in imports(path):
        if target.split(".")[0] in ("app", "nucleo"):
            old.append(f"{os.path.relpath(path, ROOT)}:{line} {target}")
    with open(path, encoding="utf-8") as fh:
        for i, text in enumerate(fh, 1):
            if text.lstrip().startswith("from ") and text.rstrip().endswith("import *"):
                star.append(f"{os.path.relpath(path, ROOT)}:{i}")
check("ninguém importa os pacotes app/ ou nucleo/", not old, "; ".join(old))
check("sem 'import *' (dependências explícitas)", not star, "; ".join(star))

# a própria regra é conferida: um import proibido seria apanhado
fake = [("manumetria.calculo.goniometria", "manumetria.interface.tema"),
        ("manumetria.dados.banco", "manumetria.relatorios.pdf"),
        ("manumetria.caminhos", "manumetria.calculo.filtros")]
caught = all(layer_of(t) in LAYERS and (layer_of(m) == "util" or LAYERS.index(layer_of(t)) > LAYERS.index(layer_of(m)))
             for m, t in fake)
check("a verificação apanha imports proibidos (exemplos montados)", caught)

print(f"\n{len(modules)} módulos em {len(LAYERS)} camadas + utilitários")
print("\n" + ("Todos os testes passaram." if not failures else f"{len(failures)} falha(s): {failures}"))
sys.exit(1 if failures else 0)
