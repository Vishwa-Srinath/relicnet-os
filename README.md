# RelicNet OS — ZETA-26 Mission Control

Interplanetary packet-routing simulator. Computes per-link latency from physical
parameters (void distance, fiber, towers, atmosphere), routes packets with
Dijkstra, encodes payloads through each planet's codex base, and reroutes live
when nodes are killed.

## Quick start

```bash
docker compose up --build
```

- UI:  http://localhost:3000
- API: http://localhost:8000  (`/universe`, `/route`, `/kill`, `/restore`, `/reset`)

## Run without Docker

**Backend**
```bash
cd backend
pip install -r requirements.txt
python verify.py                 # math sanity-check
uvicorn main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Replace the physics with your exact formulas

Open `backend/engine.py` and edit the helpers in the **PHYSICS** block:

- `void_latency_ms`
- `fiber_latency_ms`
- `tower_latency_ms`
- `atmosphere_latency_ms`

Each returns milliseconds. The default implementations use plausible physics
(speed of light = 299,792.458 km/s, fiber = 200,000 km/s). Replace with the
exact equations from your `Equations.pdf`.

## Replace the universe

Drop your real `universe-config.json` at the repo root. Expected schema:

```json
{
  "planets": [
    { "id": "P1", "name": "...", "codex": 16, "radius": 6371, "towers": 4,
      "atmosphere": 100, "refraction": 1.0003,
      "coordinates": { "x": 0, "y": 0, "z": 0 } }
  ],
  "links": []   // optional: omit to fully-connect all planets
}
```

## Layout

```
relicnet-os/
├── backend/                 FastAPI + NetworkX engine
│   ├── engine.py            Physics, graph, Dijkstra, codex
│   ├── main.py              API routes
│   ├── verify.py            CLI sanity check (prints latency math)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                Next.js 14 + React Flow + Framer Motion
│   ├── app/page.tsx         Mission Control UI
│   ├── app/layout.tsx
│   ├── app/globals.css
│   └── Dockerfile
├── universe-config.json     Sample 7-planet network
└── docker-compose.yml
```

## Features delivered

- ✅ Exact latency math per link (void/fiber/tower/atmosphere breakdown)
- ✅ Dijkstra lowest-latency routing
- ✅ ASCII ↔ Binary ↔ Base-N codex per planet
- ✅ `/route` returns hop-by-hop payload (encoding + breakdown)
- ✅ `/kill` removes a node and triggers graph rebuild
- ✅ React Flow visualization, dead nodes flash red
- ✅ Highlighted path + animated packet
- ✅ Click any hop → inspector panel with math + codex steps
- ✅ Live rerouting when an in-path node is killed
- ✅ Demo mode button (auto: route → inspect → kill → reroute)
- ✅ One-command `docker compose up`
