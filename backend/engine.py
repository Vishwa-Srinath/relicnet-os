"""RelicNet OS — Physics, Graph, Routing, and Codex Engine."""
import json
import math
import heapq
from typing import Optional, List, Dict, Any, Tuple
import networkx as nx


class RelicNetEngine:
    def __init__(self, config_path: str = "universe-config.json"):
        with open(config_path) as f:
            self.config = json.load(f)
        self.planets = {p["id"]: p for p in self.config["planets"]}
        self.links   = self.config.get("links", [])
        self.dead_nodes: set[str] = set()
        self.graph = nx.Graph()
        
        # Resolve metadata parameters with spec defaults
        self.meta = self.config.get("universe_metadata", {})
        self.C = float(self.meta.get("speed_of_light_kms", 300000.0))
        self.f = float(self.meta.get("fiber_speed_fraction", 0.67))
        self.delta_t = float(self.meta.get("tower_processing_delay_ms", 7.0))
        self.max_void_hop = float(self.meta.get("max_void_hop_distance_km", 50000000.0))

        # Detect S coordinate scale
        if "coordinate_scale_unit_km" in self.meta:
            self.S = float(self.meta["coordinate_scale_unit_km"])
        else:
            # Check maximum coordinate value in config to guess S
            max_coord = 0.0
            for p in self.planets.values():
                coords = p.get("coordinates", {})
                max_coord = max(max_coord, abs(coords.get("x", 0)), abs(coords.get("y", 0)))
            self.S = 1.0 if max_coord > 10000 else 100000.0

        self._build_graph()

    # ── PHYSICS Helpers ──────────────────────────────────────────────

    def _radius_km(self, p: dict) -> float:
        return float(p.get("radius_km") or p.get("radius") or 0.0)

    def _towers(self, p: dict) -> int:
        return int(p.get("active_towers") or p.get("towers") or 0)

    def _atmosphere_thickness_km(self, p: dict) -> float:
        return float(p.get("atmosphere_thickness_km") or p.get("atmosphere") or 0.0)

    def _refraction_index(self, p: dict) -> float:
        return float(p.get("refraction_index") or p.get("refraction") or 1.0)

    def _distance_km(self, a: dict, b: dict) -> float:
        ca, cb = a["coordinates"], b["coordinates"]
        dx = cb["x"] - ca["x"]
        dy = cb["y"] - ca["y"]
        # Use z if present and non-zero in at least one coordinate
        if "z" in ca and "z" in cb and (ca["z"] != 0.0 or cb["z"] != 0.0):
            dz = cb["z"] - ca["z"]
            dist_scaled = math.sqrt(dx*dx + dy*dy + dz*dz)
        else:
            dist_scaled = math.sqrt(dx*dx + dy*dy)
        
        dist_km = dist_scaled * self.S
        r_a = self._radius_km(a)
        r_b = self._radius_km(b)
        h_a = self._atmosphere_thickness_km(a)
        h_b = self._atmosphere_thickness_km(b)
        
        return dist_km - (r_a + h_a) - (r_b + h_b)

    def void_travel_time_ms(self, a: dict, b: dict, L: float) -> float:
        h_a = self._atmosphere_thickness_km(a)
        h_b = self._atmosphere_thickness_km(b)
        n_a = self._refraction_index(a)
        n_b = self._refraction_index(b)
        numerator = (h_a * n_a) + (h_b * n_b) + L
        return (numerator / self.C) * 1000.0

    def compute_tp(self, planet: dict, entry_tower: int, exit_tower: int) -> float:
        r = self._radius_km(planet)
        N = self._towers(planet)
        if N <= 0:
            return 0.0
            
        cw = (exit_tower - entry_tower) % N
        ccw = (entry_tower - exit_tower) % N
        s = min(cw, ccw)
        m = s + 1 if s > 0 else 1
        
        arc_km = (2.0 * math.pi * r * s) / N
        fiber_time_ms = (arc_km / (self.f * self.C)) * 1000.0
        
        return fiber_time_ms + m * self.delta_t

    def align_towers(self, a: dict, b: dict) -> Tuple[int, int]:
        ca, cb = a["coordinates"], b["coordinates"]
        dx = cb["x"] - ca["x"]
        dy = cb["y"] - ca["y"]
        N_a = self._towers(a)
        N_b = self._towers(b)
        
        theta_ab = math.atan2(dy, dx)
        theta_ba = math.atan2(-dy, -dx)
        
        exit_tower = round(theta_ab * N_a / (2.0 * math.pi)) % N_a if N_a > 0 else 0
        entry_tower = round(theta_ba * N_b / (2.0 * math.pi)) % N_b if N_b > 0 else 0
        
        return exit_tower, entry_tower

    def total_link_latency(self, a: dict, b: dict) -> dict:
        L = self._distance_km(a, b)
        if L <= 0:
            L = 0.1
        tv = self.void_travel_time_ms(a, b, L)
        weight = tv + self.delta_t * 2.0
        h_a = self._atmosphere_thickness_km(a)
        h_b = self._atmosphere_thickness_km(b)
        n_a = self._refraction_index(a)
        n_b = self._refraction_index(b)
        return {
            "void": round(L / self.C * 1000.0, 4),
            "fiber_origin": 0.0,
            "fiber_dest": 0.0,
            "tower_origin": self.delta_t,
            "tower_dest": self.delta_t,
            "atmosphere_origin": round(h_a * n_a / self.C * 1000.0, 4),
            "atmosphere_dest": round(h_b * n_b / self.C * 1000.0, 4),
            "total": round(weight, 4),
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
                    L = self._distance_km(active[s], active[t])
                    if 0 < L <= self.max_void_hop:
                        bd = self.total_link_latency(active[s], active[t])
                        self.graph.add_edge(s, t, weight=bd["total"], breakdown=bd)
        else:
            ids = list(active.keys())
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    s, t = ids[i], ids[j]
                    L = self._distance_km(active[s], active[t])
                    if 0 < L <= self.max_void_hop:
                        bd = self.total_link_latency(active[s], active[t])
                        self.graph.add_edge(s, t, weight=bd["total"], breakdown=bd)

    # ── ROUTING ──────────────────────────────────────────────────────

    def find_optimal_route(self, source: str, dest: str) -> Optional[dict]:
        if source not in self.graph or dest not in self.graph:
            return None
            
        if source == dest:
            return {
                "path": [source],
                "total_latency_ms": self.delta_t,
                "hop_edges": []
            }

        neighbors = {}
        for node in self.graph.nodes:
            neighbors[node] = []
            for nbr in self.graph.neighbors(node):
                L = self._distance_km(self.planets[node], self.planets[nbr])
                if 0 < L <= self.max_void_hop:
                    tv = self.void_travel_time_ms(self.planets[node], self.planets[nbr], L)
                    exit_t, entry_t = self.align_towers(self.planets[node], self.planets[nbr])
                    neighbors[node].append({
                        "id": nbr,
                        "L": L,
                        "Tv": tv,
                        "exit_tower": exit_t,
                        "entry_tower": entry_t
                    })

        INF = float("inf")
        dist = {}
        prev = {}
        pq = []
        
        for nbr_info in neighbors.get(source, []):
            nbr = nbr_info["id"]
            tp_source = self.delta_t
            tv = nbr_info["Tv"]
            
            cost = tp_source + tv
            state = (nbr, source)
            
            dist[state] = cost
            prev[state] = (None, {
                "from": source,
                "to": nbr,
                "exit_tower": nbr_info["exit_tower"],
                "entry_tower": nbr_info["entry_tower"],
                "Tp_from_ms": tp_source,
                "Tv_ms": tv,
                "L_km": nbr_info["L"]
            })
            heapq.heappush(pq, (cost, nbr, source))
            
        best_cost = INF
        best_state = None
        
        while pq:
            cost, current, came_from = heapq.heappop(pq)
            
            if cost > dist.get((current, came_from), INF):
                continue
                
            if current == dest:
                total = cost + self.delta_t
                if total < best_cost:
                    best_cost = total
                    best_state = (current, came_from)
                continue
                
            for nbr_info in neighbors.get(current, []):
                nbr = nbr_info["id"]
                if nbr == came_from:
                    continue
                    
                came_from_entry_tower = prev[(current, came_from)][1]["entry_tower"]
                exit_tower = nbr_info["exit_tower"]
                
                tp_current = self.compute_tp(self.planets[current], came_from_entry_tower, exit_tower)
                tv_next = nbr_info["Tv"]
                
                new_cost = cost + tp_current + tv_next
                new_state = (nbr, current)
                
                if new_cost < dist.get(new_state, INF):
                    dist[new_state] = new_cost
                    prev[new_state] = ((current, came_from), {
                        "from": current,
                        "to": nbr,
                        "exit_tower": exit_tower,
                        "entry_tower": nbr_info["entry_tower"],
                        "Tp_from_ms": tp_current,
                        "Tv_ms": tv_next,
                        "L_km": nbr_info["L"]
                    })
                    heapq.heappush(pq, (new_cost, nbr, current))
                    
        if best_state is None:
            return None
            
        path_planets = []
        hop_infos = []
        state = best_state
        
        while state is not None:
            prev_state, hop_info = prev[state]
            path_planets.append(hop_info["to"])
            hop_infos.append(hop_info)
            state = prev_state
            
        path_planets.append(source)
        path_planets.reverse()
        hop_infos.reverse()
        
        return {
            "path": path_planets,
            "total_latency_ms": best_cost,
            "hop_edges": hop_infos
        }

    def route(self, origin: str, dest: str, payload: str = "Hello") -> Optional[dict]:
        res = self.find_optimal_route(origin, dest)
        if not res:
            return None
            
        path = res["path"]
        total_latency_ms = res["total_latency_ms"]
        hop_edges = res.get("hop_edges", [])
        
        hops = []
        for i, node in enumerate(path):
            planet = self.planets[node]
            hop = {
                "index": i,
                "node": node,
                "name": planet.get("name", node),
                "codex_base": planet.get("codex", 10),
                "radius_km": self._radius_km(planet),
                "towers": self._towers(planet),
                "atmosphere_km": self._atmosphere_thickness_km(planet),
                "refraction": self._refraction_index(planet),
                "encoded_payload": self.encode_message(payload, planet.get("codex", 10)),
            }
            
            if i < len(path) - 1:
                edge_info = hop_edges[i]
                latency_ms = edge_info["Tp_from_ms"] + edge_info["Tv_ms"]
                
                h_a = self._atmosphere_thickness_km(self.planets[node])
                h_b = self._atmosphere_thickness_km(self.planets[path[i+1]])
                n_a = self._refraction_index(self.planets[node])
                n_b = self._refraction_index(self.planets[path[i+1]])
                
                # Fiber portion of Tp calculation
                N_towers = self._towers(self.planets[node])
                cw = (edge_info["exit_tower"] - edge_info["entry_tower"]) % N_towers if N_towers > 0 else 0
                ccw = (edge_info["entry_tower"] - edge_info["exit_tower"]) % N_towers if N_towers > 0 else 0
                s = min(cw, ccw)
                m = s + 1 if s > 0 else 1
                tower_part = m * self.delta_t
                fiber_part = max(0.0, edge_info["Tp_from_ms"] - tower_part)
                
                bd = {
                    "void": round(edge_info["L_km"] / self.C * 1000.0, 4),
                    "atmosphere_origin": round(h_a * n_a / self.C * 1000.0, 4),
                    "atmosphere_dest": round(h_b * n_b / self.C * 1000.0, 4),
                    "fiber_origin": round(fiber_part, 4),
                    "fiber_dest": 0.0,
                    "tower_origin": round(tower_part, 4),
                    "tower_dest": 0.0,
                    "total": round(latency_ms, 4)
                }
                
                hop["next_link"] = {
                    "to": path[i + 1],
                    "latency_ms": round(latency_ms, 4),
                    "breakdown_ms": bd,
                    "exit_tower": edge_info["exit_tower"],
                    "entry_tower": edge_info["entry_tower"]
                }
            hops.append(hop)
            
        return {
            "origin": origin,
            "destination": dest,
            "path": path,
            "total_latency_ms": round(total_latency_ms, 4),
            "hop_count": len(path),
            "hops": hops,
            "Tp_destination_ms": self.delta_t
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
