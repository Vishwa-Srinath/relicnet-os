"""RelicNet OS — Physics, Graph, Routing, and Codex Engine."""
import json
import math
from typing import Optional
import networkx as nx


SPEED_OF_LIGHT_KMS = 299_792.458       # km/s — void propagation
FIBER_SPEED_KMS    = 200_000.0          # km/s — fiber (≈ c * 2/3)


class RelicNetEngine:
    def __init__(self, config_path: str = "universe-config.json"):
        with open(config_path) as f:
            self.config = json.load(f)
        self.planets = {p["id"]: p for p in self.config["planets"]}
        self.links   = self.config.get("links", [])
        self.dead_nodes: set[str] = set()
        self.graph = nx.Graph()
        self._build_graph()

    # ── PHYSICS ──────────────────────────────────────────────────────
    # NOTE: Replace these with the exact formulas from Equations.pdf.
    # All helpers return milliseconds (ms).

    @staticmethod
    def _distance_km(a: dict, b: dict) -> float:
        ca, cb = a["coordinates"], b["coordinates"]
        return math.sqrt(
            (ca["x"] - cb["x"]) ** 2
            + (ca["y"] - cb["y"]) ** 2
            + (ca["z"] - cb["z"]) ** 2
        )

    def void_latency_ms(self, a: dict, b: dict) -> float:
        return (self._distance_km(a, b) / SPEED_OF_LIGHT_KMS) * 1000.0

    def fiber_latency_ms(self, planet: dict) -> float:
        # signal traverses 2 * radius of fiber backbone on the planet
        return (2.0 * planet.get("radius", 0) / FIBER_SPEED_KMS) * 1000.0

    def tower_latency_ms(self, planet: dict) -> float:
        # each tower hop adds processing delay
        return planet.get("towers", 0) * 1.2 + 3.0

    def atmosphere_latency_ms(self, planet: dict) -> float:
        h = planet.get("atmosphere", 0)        # km
        n = planet.get("refraction", 1.0)
        # extra optical path through refractive medium → time penalty
        return (h * (n - 1.0)) / SPEED_OF_LIGHT_KMS * 1000.0

    def total_link_latency(self, a: dict, b: dict) -> dict:
        void = self.void_latency_ms(a, b)
        fiber_a = self.fiber_latency_ms(a)
        fiber_b = self.fiber_latency_ms(b)
        tower_a = self.tower_latency_ms(a)
        tower_b = self.tower_latency_ms(b)
        atm_a   = self.atmosphere_latency_ms(a)
        atm_b   = self.atmosphere_latency_ms(b)
        total = void + fiber_a + fiber_b + tower_a + tower_b + atm_a + atm_b
        return {
            "void": round(void, 4),
            "fiber_origin": round(fiber_a, 4),
            "fiber_dest":   round(fiber_b, 4),
            "tower_origin": round(tower_a, 4),
            "tower_dest":   round(tower_b, 4),
            "atmosphere_origin": round(atm_a, 4),
            "atmosphere_dest":   round(atm_b, 4),
            "total": round(total, 4),
        }

    # ── GRAPH ────────────────────────────────────────────────────────

    def _build_graph(self):
        self.graph.clear()
        active = {pid: p for pid, p in self.planets.items() if pid not in self.dead_nodes}
        for pid, data in active.items():
            self.graph.add_node(pid, **data)

        if self.links:
            for link in self.links:
                s, t = link["source"], link["target"]
                if s in active and t in active:
                    bd = self.total_link_latency(active[s], active[t])
                    self.graph.add_edge(s, t, weight=bd["total"], breakdown=bd)
        else:
            # fully connected fallback
            ids = list(active.keys())
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    a, b = active[ids[i]], active[ids[j]]
                    bd = self.total_link_latency(a, b)
                    self.graph.add_edge(ids[i], ids[j], weight=bd["total"], breakdown=bd)

    # ── ROUTING ──────────────────────────────────────────────────────

    def route(self, origin: str, dest: str, payload: str = "Hello") -> Optional[dict]:
        if origin not in self.graph or dest not in self.graph:
            return None
        try:
            path = nx.dijkstra_path(self.graph, origin, dest, weight="weight")
            total = nx.dijkstra_path_length(self.graph, origin, dest, weight="weight")
        except nx.NetworkXNoPath:
            return None

        hops = []
        for i, node in enumerate(path):
            planet = self.graph.nodes[node]
            hop = {
                "index": i,
                "node": node,
                "name": planet.get("name", node),
                "codex_base": planet.get("codex", 10),
                "radius_km": planet.get("radius"),
                "towers": planet.get("towers"),
                "atmosphere_km": planet.get("atmosphere"),
                "refraction": planet.get("refraction"),
                "encoded_payload": self.encode_message(payload, planet.get("codex", 10)),
            }
            if i < len(path) - 1:
                edge_data = self.graph.edges[node, path[i + 1]]
                hop["next_link"] = {
                    "to": path[i + 1],
                    "latency_ms": edge_data["weight"],
                    "breakdown_ms": edge_data["breakdown"],
                }
            hops.append(hop)

        return {
            "origin": origin,
            "destination": dest,
            "path": path,
            "total_latency_ms": round(total, 4),
            "hop_count": len(path),
            "hops": hops,
        }

    def kill_node(self, node_id: str):
        if node_id in self.planets:
            self.dead_nodes.add(node_id)
            self._build_graph()

    def restore_node(self, node_id: str):
        self.dead_nodes.discard(node_id)
        self._build_graph()

    # ── CODEX (ASCII ↔ Binary ↔ Base-N) ──────────────────────────────

    DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

    @classmethod
    def to_base(cls, number: int, base: int) -> str:
        if base < 2 or base > len(cls.DIGITS):
            raise ValueError(f"Base {base} out of range")
        if number == 0:
            return "0"
        out = []
        while number > 0:
            out.append(cls.DIGITS[number % base])
            number //= base
        return "".join(reversed(out))

    @classmethod
    def from_base(cls, s: str, base: int) -> int:
        return int(s, base) if base <= 36 else sum(
            cls.DIGITS.index(ch) * (base ** i) for i, ch in enumerate(reversed(s))
        )

    @classmethod
    def ascii_to_binary(cls, text: str) -> str:
        return " ".join(format(ord(c), "08b") for c in text)

    @classmethod
    def binary_to_ascii(cls, binary: str) -> str:
        return "".join(chr(int(b, 2)) for b in binary.split() if b)

    @classmethod
    def encode_message(cls, text: str, base: int) -> dict:
        binary = cls.ascii_to_binary(text)
        based  = " ".join(cls.to_base(ord(c), base) for c in text)
        return {
            "ascii": text,
            "binary": binary,
            "base": base,
            "encoded": based,
            "steps": [
                {"label": "ASCII",            "value": text},
                {"label": "→ Binary (Base 2)", "value": binary},
                {"label": f"→ Base {base}",    "value": based},
            ],
        }
