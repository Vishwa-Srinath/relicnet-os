"""Sanity check — prints latency between the first two planets."""
from engine import RelicNetEngine

e = RelicNetEngine()
ids = list(e.planets.keys())
if len(ids) < 2:
    print("Need at least 2 planets in universe-config.json"); raise SystemExit
a, b = ids[0], ids[1]
print(f"Planets: {a}  ↔  {b}")
bd = e.total_link_latency(e.planets[a], e.planets[b])
for k, v in bd.items(): print(f"  {k:>20s}: {v} ms")
print()
print(f"Best route {a} → {ids[-1]}:")
import json; print(json.dumps(e.route(a, ids[-1]), indent=2)[:1500])
