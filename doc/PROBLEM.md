# Zeta-26 Universe Routing — Complete Problem Specification
> **LAUNCH26 Hackathon · The Relic Ring Protocol**  
> Organised by IEEE Computer Society Chapter, University of Kelaniya

---

## 1. What You Are Building

A backend routing engine for the fictional **Zeta-26 universe**. The universe contains 6 planets connected via **void (space) travel**. Each planet has a ring of signal **towers** connected by fibre cable. A packet must travel:

```
[Source Tower] → ring fibre on source planet
              → void hop (space)
              → ring fibre on intermediate planet(s)  ← zero or more times
              → void hop
              → ring fibre on destination planet
              → [Destination Tower]
```

Your engine must find the **minimum-latency route** between any two planets and compute the exact latency breakdown.

---

## 2. Universe Configuration (`universe-config.json`)

### `universe_metadata`

| Field | Value | Meaning |
|---|---|---|
| `system_name` | `"Zeta-26"` | Universe name |
| `speed_of_light_kms` (C) | `300000.0` | km/s — used in all formulas |
| `max_void_hop_distance_km` | `50000000.0` | Max allowed L per hop (50 M km) |
| `coordinate_scale_unit_km` (S) | `100000.0` | Each grid unit = 100,000 km |
| `tower_processing_delay_ms` (Δt) | `7.0` | ms per distinct tower hit |
| `fiber_speed_fraction` (f) | `0.67` | Fibre runs at 67% of light speed |

### `nodes` (Planets)

| id | codex | x | y | radius_km (r) | active_towers (N) | atmosphere_thickness_km (h) | refraction_index (n) |
|---|---|---|---|---|---|---|---|
| Aegis   | 8  | 0   | 0   | 6371   | 8  | 120 | 1.0003 |
| Boreas  | 5  | 150 | 100 | 3389   | 4  | 85  | 1.0520 |
| Dawn    | 6  | 350 | 50  | 1500   | 6  | 30  | 1.0110 |
| Elysium | 10 | 300 | 350 | 6051   | 12 | 250 | 1.1850 |
| Fenix   | 16 | 500 | -100| 1200   | 4  | 15  | 1.0050 |
| Caelum  | 14 | 650 | 200 | 58232  | 16 | 500 | 1.3210 |

> **`codex`** is the planet's identifier number used in routing protocols.

---

## 3. Complete Formulas (Verified from Source)

### Formula 1 — Void Distance `L` (km)

```
L = √((x₂ - x₁)² + (y₂ - y₁)²) × S − (R₁ + h₁) − (R₂ + h₂)
```

- `(x, y)` — planet centre coordinates from config (grid units)
- `S` — `coordinate_scale_unit_km` = 100,000 km/grid-unit
- `R₁, R₂` — `radius_km` of origin / destination
- `h₁, h₂` — `atmosphere_thickness_km` of origin / destination

**Validity rule:** `0 < L ≤ max_void_hop_distance_km` — if L ≤ 0 the planets overlap (invalid); if L > 50,000,000 km the hop is out of range (forbidden).

---

### Formula 2 — Void Travel Time `Tv` (seconds → convert to ms)

```
Tv [s] = ((h₁ × n₁) + (h₂ × n₂) + L) / C
Tv [ms] = Tv [s] × 1000
```

- `n₁, n₂` — `refraction_index` of origin / destination  
- `C` — `speed_of_light_kms` = 300,000 km/s  
- The atmosphere of each planet adds `h × n` effective km of optical path.

---

### Formula 3 — Internal Crust Transit Time `Tp`

```
Tp [s]  = (2π × r × s) / (N × f × C)  +  m × Δt / 1000
Tp [ms] = ((2π × r × s) / (N × f × C)) × 1000  +  m × Δt
```

**Symbols:**

| Symbol | Source | Meaning |
|---|---|---|
| `r` | `radius_km` | Planet radius (km) |
| `N` | `active_towers` | Total towers on the ring |
| `s` | computed | Segments travelled on ring (integer ≥ 0) |
| `m` | computed | Distinct towers hit = `s + 1`; if `s = 0` then `m = 1` |
| `f` | `fiber_speed_fraction` | 0.67 |
| `C` | `speed_of_light_kms` | 300,000 km/s |
| `Δt` | `tower_processing_delay_ms` | 7 ms |

**How s is computed:**

Towers 0, 1, …, N-1 are equally spaced around the ring (each gap = 360°/N).  
Given an `entry_tower` index and `exit_tower` index:

```
cw  = (exit_tower - entry_tower) % N      # clockwise segments
ccw = (entry_tower - exit_tower) % N      # counter-clockwise segments
s   = min(cw, ccw)                        # always take the shorter arc
```

If `entry_tower == exit_tower`: `s = 0`, `m = 1`.

---

### Formula 4 — Total End-to-End Latency

For a route through planets **P₁ → P₂ → … → Pₖ** (k planets, k-1 hops):

```
Total Latency [ms] = Σᵢ₌₁ᵏ  Tp(Pᵢ) [ms]
                   + Σᵢ₌₁ᵏ⁻¹ Tv(Pᵢ, Pᵢ₊₁) [ms]
```

**Core rules (from spec):**
- **One Tp per planet visited** (handles ring fibre + tower processing).
- **One Tv per void hop** between consecutive planets.
- **No double-counting** — atmosphere `h` only appears inside `Tv`.
- Tower processing (`Δt`) only enters via `m × Δt` inside `Tp`.

---

## 4. Tower Selection Logic

Towers are arranged uniformly on the planet's ring. Tower index `k` sits at angle:

```
θₖ = k × (2π / N)   radians   (tower 0 at angle 0°)
```

**Best exit tower** on planet A when sending toward planet B:

```python
θ = atan2(y_B - y_A, x_B - x_A)                   # direction A→B
exit_tower = round(θ * N_A / (2 * π)) % N_A
```

**Best entry tower** on planet B when receiving from planet A:

```python
θ_back = atan2(y_A - y_B, x_A - x_B)              # direction B→A (facing back)
entry_tower = round(θ_back * N_B / (2 * π)) % N_B
```

Note: entry tower faces the *incoming* direction (back toward the sender).

---

## 5. Tp at Source and Destination

- **Source planet P₁**: Packet originates at the exit tower facing the first hop. `entry = exit`, so `s = 0`, `m = 1`. `Tp(P₁) = Δt = 7 ms`.
- **Destination planet Pₖ**: Packet arrives at the entry tower (facing the last sender). No onward exit. `s = 0`, `m = 1`. `Tp(Pₖ) = Δt = 7 ms`.
- **Intermediate planet Pᵢ**: Entry from Pᵢ₋₁, exit toward Pᵢ₊₁. Compute `s` between those two towers. `m = s + 1`. `Tp(Pᵢ)` uses full formula.

---

## 6. Constraints & Validity

| Constraint | Rule |
|---|---|
| Hop validity | `0 < L(A, B) ≤ 50,000,000 km` |
| Route must be a valid sequence | Each consecutive pair must be a valid hop |
| No revisiting planets | Optimal routes never cycle (positive latency = no negative edges) |
| Planet codex values | Must be used as identifiers in protocol headers |

---

## 7. Example Calculation — Aegis → Boreas (Direct)

**L (Aegis → Boreas):**
```
dx = 150, dy = 100
grid_dist = √(150² + 100²) = 180.278 grid_units
km_dist = 180.278 × 100,000 = 18,027,756 km
L = 18,027,756 − (6371 + 120) − (3389 + 85) = 18,017,791 km   ✓ (<50M)
```

**Tv (Aegis → Boreas):**
```
Tv = ((120 × 1.0003) + (85 × 1.0520) + 18,017,791) / 300,000
   = (120.036 + 89.42 + 18,017,791) / 300,000
   = 60,060.002 ms  ≈ 60.06 s
```

**Tp (Aegis, source, s=0):** `= 7 ms`  
**Tp (Boreas, dest, s=0):** `= 7 ms`  

**Total = 7 + 60,060.002 + 7 = 60,074.002 ms**

---

## 8. API Contract (Suggested)

### `GET /route?source=Aegis&dest=Elysium`

Response:
```json
{
  "source": "Aegis",
  "destination": "Elysium",
  "route": ["Aegis", "Boreas", "Elysium"],
  "total_latency_ms": 123456.78,
  "hops": [
    {
      "from": "Aegis",
      "to": "Boreas",
      "L_km": 18017791.0,
      "Tv_ms": 60060.0,
      "Tp_from_ms": 7.0,
      "exit_tower": 1,
      "entry_tower": 2
    },
    {
      "from": "Boreas",
      "to": "Elysium",
      "L_km": ...,
      "Tv_ms": ...,
      "Tp_from_ms": ...,
      "exit_tower": ...,
      "entry_tower": ...
    }
  ],
  "Tp_destination_ms": 7.0
}
```

### `GET /universe`
Returns the full graph: all nodes + all valid edges with precomputed L and Tv.

### `POST /validate`
Body: `{ "route": ["Aegis", "Boreas", "Elysium"] }` → Validates the route and returns exact latency breakdown.

---

## 9. Competition Context

- **Event**: LAUNCH26, national-level inter-university hackathon by IEEE CS Chapter, University of Kelaniya
- **Stage**: 24-hour development phase (Relic Ring Protocol)
- **Submission**: GitHub repo (public after deadline) + 15-min demo video
- **Deadline**: Commits after 8:00 AM on the 28th = **disqualification**
- **Tech stack**: Free choice; containerisation highly encouraged
- **AI tools**: Allowed as assistive development tools
- **Grading**: Correctness of routing + latency formula, code quality, commit history, demo quality

---

## 10. Key Numbers to Remember

```
C  = 300,000 km/s
S  = 100,000 km/grid unit
f  = 0.67
Δt = 7 ms
max_hop = 50,000,000 km

Aegis towers:    8  (every 45°)
Boreas towers:   4  (every 90°)
Dawn towers:     6  (every 60°)
Elysium towers: 12  (every 30°)
Fenix towers:    4  (every 90°)
Caelum towers:  16  (every 22.5°)
```
