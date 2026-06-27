# RelicNet OS — Mission Control System

RelicNet OS is a high-performance interplanetary packet-routing simulator and visual dashboard for space network topologies. It calculates optimal communication paths across star systems using a custom sequence-dependent physical latency model and a **State-Expanded Dijkstra** routing engine.



## 🪐 Mathematical Physics Model

The communication latency between any two planetary terminals in the universe is calculated dynamically using physical equations divided into two main categories: **Void (Space) Latency** ($T_v$) and **Crust (Fiber/Tower) Latency** ($T_p$).

### 1. Void Travel Distance ($L$)
The actual distance in space traversed by the laser signal between the outer boundaries of the atmosphere of planet $A$ and planet $B$:
$$L = \text{EuclideanDistance}(A, B) \times S - (R_A + h_A) - (R_B + h_B)$$

Where:
*   $S$ is the scale coefficient mapping coordinates to physical kilometers (default: $100,000.0$ km/unit).
*   $R_A, R_B$ are the radii of the planets (km).
*   $h_A, h_B$ are the thicknesses of the planetary atmospheres (km).

### 2. Void Travel Latency ($T_v$)
The light signal's time-of-flight through space, adjusted for the refractive index ($n$) of both atmospheres:
$$T_v\text{ [ms]} = \frac{(h_A \times n_A) + (h_B \times n_B) + L}{C} \times 1000$$

Where:
*   $C$ is the speed of light ($300,000.0$ km/s).
*   $n_A, n_B$ are the refractive indexes of the atmospheres.

### 3. Crust Ring Transit ($T_p$)
Once a packet arrives on a planet's internal fiber ring, it travels to the next exit tower. Standard node transit latency is calculated as:
$$T_p\text{ [ms]} = \frac{2\pi \times r \times s}{N \times f \times C} \times 1000 + m \times \Delta t$$

Where:
*   $r$ is the planet's radius (km).
*   $N$ is the active tower count on the planet's ring.
*   $f$ is the fiber speed fraction ($0.67$ of vacuum speed of light).
*   $\Delta t$ is the tower processing delay ($7.0$ ms).
*   $s$ is the shortest arc distance in segments:
    $$s = \min((exit - entry) \pmod N, (entry - exit) \pmod N)$$
*   $m$ is the count of distinct towers hit: $s + 1$ (if $s > 0$ else $1$).

**Special Cases:**
*   **Origin Node:** The packet starts directly at the exit tower. $s = 0, m = 1 \implies T_p = \Delta t = 7.0$ ms.
*   **Destination Node:** The packet terminates at the entry tower. $s = 0, m = 1 \implies T_p = \Delta t = 7.0$ ms.

---

## 🧠 Routing Engine: State-Expanded Dijkstra

### The Challenge of Simple Dijkstra
Because the crust transit time ($T_p$) on intermediate planets depends entirely on which direction the signal came from (entry tower angle) and where it is heading next (exit tower angle), simple node-based shortest path routing fails. The cost of a node is sequence-dependent.

### State Space Expansion
To solve this, the routing engine transforms the search space. Each state in the pathfinding priority queue represents:
$$\text{State} = (\text{Current Planet}, \text{Came From Planet})$$

This model calculates the optimal entrance and exit alignment for every step dynamically.
*   **Precompute edges:** $O(P^2)$ where $P$ is the number of planets.
*   **Dijkstra Query Complexity:** $O(P^2 \log P)$ operations, solving in microseconds.

---

## 🛠️ Quick Start

### Run with Docker (Recommended)
Build and start the application in one command:
```bash
sudo docker compose up --build
```

### Run Locally (Without Docker)

**1. Start Backend API Server**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python verify.py                      # Run automated physics math validation
uvicorn main:app --reload --port 8000
```

**2. Start Frontend UI**
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

---

## 📂 Project Structure
```
relicnet-os/
├── backend/                 Python FastAPI Server
│   ├── engine.py            Physics Equations & State-Expanded Dijkstra
│   ├── main.py              API Route Controller
│   ├── verify.py            CLI Latency Validation Tool
│   ├── universe-config.json Default Node coordinates and metadata
│   └── Dockerfile
├── frontend/                Next.js React Dashboard
│   ├── app/page.tsx         Dashboard UI with React Flow & Framer Motion
│   └── Dockerfile
├── doc/
│   └── ENGINE_GUIDE.md      In-depth architectural design guide
├── docker-compose.yml
└── README.md
```

---

## 💎 Features Checklist

- [x] **Flexible Schema Normalization:** Auto-detects and normalizes coordinate layouts (direct properties or nested, radius_km, active_towers).
- [x] **Robust Base Encoding:** Safely processes Base-N translations and falls back gracefully for invalid bases (e.g. Base 1 on Prime).
- [x] **Interactive Configuration Loader:** Upload any universe `.json` configuration directly in the sidebar to rebuild the map.
- [x] **Physical Parameter Inspector:** Click on any node/path to view raw metrics ($L$, $T_v$, $T_p$, Entry/Exit Towers).
- [x] **Isolated Node Warning:** Prominent warning banners show if routing is physically impossible due to range limits.
- [x] **Dynamic Chaos Engine:** Terminate planet nodes to see real-time automatic rerouting.
