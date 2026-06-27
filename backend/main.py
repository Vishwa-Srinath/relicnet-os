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
