"""RelicNet OS — FastAPI surface."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from engine import RelicNetEngine

app = FastAPI(title="RelicNet OS", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = RelicNetEngine()


class RouteReq(BaseModel):
    origin: str
    destination: str
    payload: str = "Hello"


class NodeReq(BaseModel):
    node_id: str


@app.get("/")
def health():
    return {"service": "RelicNet OS", "status": "online", "planets": len(engine.planets)}


@app.get("/universe")
def universe():
    nodes = []
    for nid, d in engine.graph.nodes(data=True):
        nodes.append({
            "id": nid,
            "name": d.get("name", nid),
            "codex": d.get("codex"),
            "radius": d.get("radius"),
            "towers": d.get("towers"),
            "atmosphere": d.get("atmosphere"),
            "refraction": d.get("refraction"),
            "coordinates": d.get("coordinates"),
        })
    edges = [
        {
            "source": u,
            "target": v,
            "latency_ms": d["weight"],
            "breakdown": d["breakdown"],
        }
        for u, v, d in engine.graph.edges(data=True)
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "dead_nodes": sorted(engine.dead_nodes),
        "all_planet_ids": sorted(engine.planets.keys()),
    }


@app.post("/route")
def route(req: RouteReq):
    result = engine.route(req.origin, req.destination, req.payload)
    if not result:
        raise HTTPException(404, f"No path from {req.origin} to {req.destination}")
    return result


@app.post("/kill")
def kill(req: NodeReq):
    if req.node_id not in engine.planets:
        raise HTTPException(404, "Unknown planet")
    engine.kill_node(req.node_id)
    return {"status": "killed", "node": req.node_id, "dead_nodes": sorted(engine.dead_nodes)}


@app.post("/restore")
def restore(req: NodeReq):
    engine.restore_node(req.node_id)
    return {"status": "restored", "node": req.node_id, "dead_nodes": sorted(engine.dead_nodes)}


@app.post("/reset")
def reset():
    engine.dead_nodes.clear()
    engine._build_graph()
    return {"status": "reset"}


@app.post("/config")
def load_config(req: dict):
    import json
    engine.config = req
    engine.planets = {}
    planets_list = req.get("nodes") or req.get("planets") or []
    for p in planets_list:
        pid = p["id"]
        normalized = p.copy()
        if "coordinates" not in normalized:
            normalized["coordinates"] = {
                "x": float(p.get("x", 0.0)),
                "y": float(p.get("y", 0.0)),
                "z": float(p.get("z", 0.0))
            }
        normalized["name"] = p.get("name", pid)
        normalized["radius"] = float(p.get("radius") or p.get("radius_km") or 0.0)
        normalized["towers"] = int(p.get("towers") or p.get("active_towers") or 0)
        normalized["atmosphere"] = float(p.get("atmosphere") or p.get("atmosphere_thickness_km") or 0.0)
        normalized["refraction"] = float(p.get("refraction") or p.get("refraction_index") or 1.0)
        engine.planets[pid] = normalized
        
    engine.links = req.get("links", [])
    engine.dead_nodes.clear()
    
    # Resolve metadata parameters
    engine.meta = req.get("universe_metadata", {})
    engine.C = float(engine.meta.get("speed_of_light_kms", 300000.0))
    engine.f = float(engine.meta.get("fiber_speed_fraction", 0.67))
    engine.delta_t = float(engine.meta.get("tower_processing_delay_ms", 7.0))
    engine.max_void_hop = float(engine.meta.get("max_void_hop_distance_km", 50000000.0))
    
    # Detect S coordinate scale
    if "coordinate_scale_unit_km" in engine.meta:
        engine.S = float(engine.meta["coordinate_scale_unit_km"])
    else:
        max_coord = 0.0
        for p in engine.planets.values():
            coords = p.get("coordinates", {})
            max_coord = max(max_coord, abs(coords.get("x", 0)), abs(coords.get("y", 0)))
        engine.S = 1.0 if max_coord > 10000 else 100000.0
        
    engine._build_graph()
    
    try:
        with open("universe-config.json", "w") as f:
            json.dump(req, f, indent=2)
    except Exception:
        pass
        
    return {"status": "success", "planets": len(engine.planets)}
