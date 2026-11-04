"""Mutační kontrola testů aplikace C02 (`reservation.py`) a testů C05 (`tests/`).

Ověřuje, že testy pravidla skutečně hlídají: každá mutace je kopie kódu, ve které je
záměrně pokažené jedno pravidlo. Mutace se dělá v dočasné složce, repozitář se nemění.
Testy musí každou mutaci odhalit (ZABITO); pokud všechny projdou, mutace PŘEŽILA a pravidlo
není testy chráněné.

Spuštění z kořene repozitáře:  python tools/mutation_check.py
Návratový kód 0 = kontrolní běh prošel a všechny mutace byly zabity.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DISPATCH_AFTER_LOCK = '''        with self._lock:
            pending, self._outbox = self._outbox, []
        for mail in pending:
            status = "SENT"
            try:
                self.notifier.send(mail["to"], mail["subject"], mail["body"])
            except Exception:  # NotificationUnavailable, timeout, chyba sítě...
                status = "FAILED"
            entry = {k: mail[k] for k in ("reservation_id", "event", "to", "subject")}
            entry["status"] = status
            with self._lock:
                self.notifications.append(entry)'''
DISPATCH_UNDER_LOCK = '''        with self._lock:
            pending, self._outbox = self._outbox, []
            for mail in pending:
                status = "SENT"
                try:
                    self.notifier.send(mail["to"], mail["subject"], mail["body"])
                except Exception:  # NotificationUnavailable, timeout, chyba sítě...
                    status = "FAILED"
                entry = {k: mail[k] for k in ("reservation_id", "event", "to", "subject")}
                entry["status"] = status
                self.notifications.append(entry)'''
STATION_CHECK = '''        if not station.active:
            return AllocationDecision.deny("INACTIVE_STATION")
'''
DAILY_LIMIT_CHECK = '''        if same_day:
            return AllocationDecision.deny("DAILY_LIMIT", same_day)
'''

# název mutace -> seznam náhrad (původní text, pokažený text); původní text musí být v kódu právě jednou
MUTATIONS = {
    "C02 bez zámku (REQ-04)": [
        ("import threading", "import contextlib\nimport threading"),
        ("self._lock = threading.Lock()", "self._lock = contextlib.nullcontext()"),
    ],
    "C02 bez denního limitu (BR-04)": [(DAILY_LIMIT_CHECK, "")],
    "C02 uzavřené intervaly <= (BR-01)": [
        ("return a_start < b_end and b_start < a_end", "return a_start <= b_end and b_start <= a_end"),
    ],
    "C02 dostupnost bez kontroly provozu (REQ-02)": [
        ("if not station.active or self._confirmed_overlaps", "if self._confirmed_overlaps"),
    ],
    "C05 e-mail odeslaný pod zámkem": [(DISPATCH_AFTER_LOCK, DISPATCH_UNDER_LOCK)],
    "C05 zachycena jen NotificationUnavailable": [
        ("except Exception:  # NotificationUnavailable, timeout", "except NotificationUnavailable:  # timeout"),
    ],
    "C05 provoz stanice až za BR-04": [
        (STATION_CHECK, ""),
        (DAILY_LIMIT_CHECK, DAILY_LIMIT_CHECK + STATION_CHECK),
    ],
}


def run(cmd: list, cwd: Path) -> str:
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def failures(source: str) -> list:
    """Spustí příklady ověření i unit testy nad danou verzí `reservation.py` a vrátí, co selhalo."""
    with tempfile.TemporaryDirectory(prefix="mutation_") as tmp:
        tmp = Path(tmp)
        (tmp / "reservation.py").write_text(source, encoding="utf-8")
        shutil.copytree(REPO / "tests", tmp / "tests")
        spec = run([sys.executable, "reservation.py", "test"], tmp)
        unit = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], tmp)
    failed = [f"příklad: {line.split('[FAIL]', 1)[1].strip()}" for line in spec.splitlines() if "[FAIL]" in line]
    failed += [f"unit test: {name}" for name in re.findall(r"^(?:FAIL|ERROR): (\w+)", unit, flags=re.M)]
    if "TIMEOUT" in (spec, unit):
        failed.append("TIMEOUT")
    return failed


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    original = (REPO / "reservation.py").read_text(encoding="utf-8")

    control = failures(original)
    print("Kontrolní běh bez mutace:", "OK" if not control else "SELHAL")
    for item in control:
        print("   ", item)
    if control:
        return 1

    survived = 0
    for name, replacements in MUTATIONS.items():
        mutated = original
        for old, new in replacements:
            if mutated.count(old) != 1:
                print(f"{name}: původní text se v kódu nenašel právě jednou, mutaci nelze provést")
                return 1
            mutated = mutated.replace(old, new)
        failed = failures(mutated)
        survived += not failed
        print(f"{'ZABITO ' if failed else 'PŘEŽILO'}  {name}")
        for item in failed:
            print("           ", item)

    print(f"\n{len(MUTATIONS) - survived}/{len(MUTATIONS)} mutací zabito.")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
