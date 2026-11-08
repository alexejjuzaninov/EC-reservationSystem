"""Jednoduché opakovatelné měření lokálního API pro C04."""
import datetime as dt
import json
from pathlib import Path
import statistics
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:18080/api"
OUT = Path(__file__).resolve().parent.parent / "zadani" / "dukazy"
OUT.mkdir(exist_ok=True)


def request(path):
    begin = time.perf_counter()
    with urllib.request.urlopen(BASE + path, timeout=30) as response:
        response.read()
        assert response.status == 200
    return round((time.perf_counter() - begin) * 1000, 1)


def measure(path):
    request(path)  # Zahřátí cache a JVM.
    values = [request(path) for _ in range(20)]
    values.sort()
    return {"samples": 20, "median_ms": round(statistics.median(values), 1),
            "p95_ms": values[18], "max_ms": values[-1], "values_ms": values}


now = dt.datetime.now(dt.timezone.utc)
start = (now + dt.timedelta(days=100)).replace(hour=12, minute=0, second=0, microsecond=0)
end = start + dt.timedelta(hours=1)
qs = urllib.parse.urlencode({"startAt": start.isoformat().replace("+00:00", "Z"),
                             "endAt": end.isoformat().replace("+00:00", "Z")})
result = {
    "measured_at_utc": now.isoformat(),
    "environment": "lokální prototyp; zahřátá cache; sekvenční požadavky",
    "map_prague": measure("/map/explore?country=CZ&west=14.20&south=49.95&east=14.65&north=50.22&zoom=11"),
    "availability": measure("/stations/20000000-0000-0000-0000-000000000002/availability?" + qs),
}
path = OUT / "mereni_lokalni_api.json"
path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: {m: v for m, v in value.items() if m != "values_ms"} if isinstance(value, dict) else value
                  for k, value in result.items()}, ensure_ascii=False, indent=2))
