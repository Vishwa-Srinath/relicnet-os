# Zeta-26 Interplanetary Packet Routing — Engine Documentation

Welcome to the **Zeta-26 Mission Control Engine Guide**. This documentation describes the physics formulas, routing algorithm, API endpoints, and configuration options implemented in the RelicNet OS.

---

## 1. Physics Model & Equations

The latency of sending a packet between planets is split into **Void Latency** ($T_v$) and **Crust Latency** ($T_p$).

### A. Void Distance ($L$)
The actual distance the signal travels through space between the outer boundaries of the atmospheres of planet $A$ and planet $B$:
$$L = \text{EuclideanDistance}(A, B) \times S - (R_A + h_A) - (R_B + h_B)$$

Where:
*   $S$ is the coordinate scaling unit in km/grid (default: $100,000.0$ km/unit).
*   $R_A, R_B$ are the radii of the planets (km).
*   $h_A, h_B$ are the thickness of the planet atmospheres (km).

*Note: If $L \le 0$ (planets overlap) or $L > 50,000,000$ km (out of link range), the hop is invalid and excluded from the network.*

### B. Void Travel Time ($T_v$)
The travel time of the light signal through vacuum space and refractive atmospheres:
$$T_v\text{ [ms]} = \frac{(h_A \times n_A) + (h_B \times n_B) + L}{C} \times 1000$$

Where:
*   $n_A, n_B$ are the refraction indices of the atmospheres (default: $1.0$).
*   $C$ is the speed of light (default: $300,000.0$ km/s).
*   Atmospheric traversal adds a penalty of $h \times n$ effective kilometers of optical path.

### C. Ring Crust Transit ($T_p$)
Once a packet arrives on a planet, it traverses the internal ring backbone fiber to align from its entry tower to the exit tower:
$$T_p\text{ [ms]} = \frac{2\pi \times r \times s}{N \times f \times C} \times 1000 + m \times \Delta t$$

Where:
*   $r$ is the planet radius (km).
*   $N$ is the active tower count on the planet's ring.
*   $f$ is the fiber speed fraction (default: $0.67$).
*   $\Delta t$ is the tower processing delay (default: $7.0$ ms per distinct hit).
*   $s$ is the shortest arc distance in segments:
    $$s = \min((exit - entry) \pmod N, (entry - exit) \pmod N)$$
*   $m$ is the count of distinct towers hit: $s + 1$ (if $s > 0$ else $1$).

**Special Cases:**
*   **Source Planet:** The packet starts at the exit tower facing the first link. $s = 0, m = 1 \implies T_p = \Delta t = 7.0$ ms.
*   **Destination Planet:** The packet arrives at the entry tower and completes its journey. $s = 0, m = 1 \implies T_p = \Delta t = 7.0$ ms.

---

## 2. Optimal Routing: State-Expanded Dijkstra

### The Challenge of Simple Dijkstra
The cost of traversing an intermediate planet depends on the **angle of entry** (where the signal came from) and the **angle of exit** (where the signal is heading next). In a standard graph where edge weights are constant, Dijkstra cannot optimize sequence-dependent node costs.

### The Solution: State-Expanded Search
To find the global minimum latency route, the routing engine expands each node in the pathfinder search queue to a state representing `(current_planet, came_from_planet)`.
*   During Dijkstra exploration, when moving from state $(B, A)$ to planet $C$, the engine calculates the entry tower on $B$ (facing $A$), the exit tower on $B$ (facing $C$), and adds the corresponding crust transit time $T_p(B)$ to the cost.
*   With 6 planets, the state space size is extremely small ($\le 36$), allowing the search to complete in microseconds.

---

## 3. End-to-End Latency Verification Example

### Route: Aegis → Dawn → Caelum

1.  **Hop 1: Aegis → Dawn**
    *   **Distance ($L$):** $\approx 35,347,318$ km.
    *   **Void Travel ($T_v$):** $117,824.3935$ ms.
    *   **Crust Transit ($T_p(Aegis)$):** Source startup $= 7.0$ ms.
    *   **Exit Tower (Aegis):** $0$
    *   **Entry Tower (Dawn):** $3$
    *   *Link Latency:* $117,831.3935$ ms.

2.  **Hop 2: Dawn → Caelum**
    *   **Distance ($L$):** $\approx 33,480,758$ km.
    *   **Void Travel ($T_v$):** $111,607.2498$ ms.
    *   **Crust Transit ($T_p(Dawn)$):**
        *   Segments: $s = \min((0-3)\%6, (3-0)\%6) = \min(3, 3) = 3$.
        *   Towers hit: $m = 4$.
        *   Fiber Travel time: $23.5245$ ms.
        *   Transit $T_p(Dawn) = 23.5245 + 4 \times 7 = 51.5245$ ms.
    *   **Exit Tower (Dawn):** $0$
    *   **Entry Tower (Caelum):** $9$

3.  **Destination Caelum**
    *   **Crust Transit ($T_p(Caelum)$):** Destination arrival $= 7.0$ ms.

**Total Path Latency:**
$$\text{Total} = 7.0\text{ (Aegis)} + 117,824.3935\text{ (Hop 1 Void)} + 51.5245\text{ (Dawn Transit)} + 111,607.2498\text{ (Hop 2 Void)} + 7.0\text{ (Caelum)} = 229,497.1678\text{ ms}$$

---

## 4. API Endpoints

### `GET /universe`
Returns the active configuration schema containing all node metadata and pre-calculated valid space edges with their default latency breakdowns.

### `POST /route`
Computes the optimal state-expanded shortest path and encodes the message payload.
*   **Request Body:**
    ```json
    {
      "origin": "Aegis",
      "destination": "Caelum",
      "payload": "Hello"
    }
    ```
*   **Response Body:** Returns the exact path list, total latency, and a detailed hop breakdown detailing entry/exit towers, transit, and void components.

### `POST /kill`
Simulates a node failure. Takes a `{ "node_id": "Dawn" }` body, removes it from the routing graph, and triggers a live network rebuild.

### `POST /restore`
Restores a dead node back to the active network graph.

### `POST /reset`
Resets the Chaos Engine, restoring all dead nodes to the universe.
