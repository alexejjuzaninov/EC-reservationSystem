"""C03 L2: kontrola architektonických pravidel z G2, G3 a ADR-01 nad zdrojovým kódem (bez spuštění).

Pravidla:
1. SQLAlchemy a psycopg zná jen Reservation Store (store.py).
2. FastAPI, Starlette a Pydantic zná jen Reservation API (api.py).
3. Povolené závislosti uvnitř balíčku odpovídají G2; main.py je composition root a smí vše.
4. Stav rezervace (přiřazení `x.state = ...`) mění jen Reservation Management (service.py).
"""
import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "reservations"

ALLOWED_INTERNAL = {  # modul -> moduly balíčku, na kterých smí záviset (G2)
    "domain": set(),
    "service": {"domain"},
    "store": {"domain"},
    "notifications": set(),
    "api": {"domain", "service"},
}
ONLY_IN = {"sqlalchemy": "store", "psycopg": "store", "fastapi": "api", "starlette": "api", "pydantic": "api"}


def modules():
    return {p.stem: ast.parse(p.read_text(encoding="utf-8")) for p in PACKAGE.glob("*.py") if p.stem != "__init__"}


def imports(tree):
    """(top-level název externího balíčku | None, název interního modulu | None) pro každý import."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0], None
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relativní import uvnitř balíčku: from .domain import ...
                yield None, (node.module or "").split(".")[0]
            else:
                yield node.module.split(".")[0], None


def test_external_frameworks_are_used_only_by_their_owner():
    violations = [
        f"{name}.py importuje {ext} (smí jen {ONLY_IN[ext]}.py)"
        for name, tree in modules().items()
        for ext, _ in imports(tree)
        if ext in ONLY_IN and name not in (ONLY_IN[ext], "main")
    ]
    assert violations == []


def test_internal_dependencies_follow_g2():
    violations = [
        f"{name}.py závisí na {internal}.py"
        for name, tree in modules().items()
        if name in ALLOWED_INTERNAL
        for _, internal in imports(tree)
        if internal and internal not in ALLOWED_INTERNAL[name]
    ]
    assert violations == []


def test_only_reservation_management_changes_reservation_state():
    violations = [
        f"{name}.py:{node.lineno} přiřazuje .state"
        for name, tree in modules().items()
        if name != "service"
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Attribute) and target.attr == "state"
    ]
    assert violations == []


def test_the_check_sees_every_module():
    """Pojistka proti tichému selhání: kontrola musí opravdu číst všechny prvky z G2."""
    assert set(ALLOWED_INTERNAL) | {"main"} == set(modules())
