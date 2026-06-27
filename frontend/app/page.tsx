"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, {
  Background, Controls, MiniMap, MarkerType,
  useNodesState, useEdgesState, Node, Edge, ReactFlowProvider,
} from "reactflow";
import "reactflow/dist/style.css";
import { motion, AnimatePresence } from "framer-motion";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Planet = {
  id: string; name: string; codex: number; radius: number;
  towers: number; atmosphere: number; refraction: number;
  coordinates: { x: number; y: number; z: number };
};
type LinkEdge = { source: string; target: string; latency_ms: number; breakdown: Record<string, number> };
type Universe = { nodes: Planet[]; edges: LinkEdge[]; dead_nodes: string[]; all_planet_ids: string[] };
type Hop = {
  index: number; node: string; name: string; codex_base: number;
  radius_km: number; towers: number; atmosphere_km: number; refraction: number;
  encoded_payload: { ascii: string; binary: string; base: number; encoded: string; steps: { label: string; value: string }[] };
  entry_tower?: number | null;
  exit_tower?: number | null;
  next_link?: { to: string; latency_ms: number; breakdown_ms: Record<string, number>; exit_tower: number; entry_tower: number };
};
type RouteResult = {
  origin: string; destination: string; path: string[];
  total_latency_ms: number; hop_count: number; hops: Hop[];
};

function layoutPositions(planets: Planet[]) {
  const N = planets.length;
  const R = Math.max(260, 60 * N);
  const cx = 520, cy = 380;
  const pos: Record<string, { x: number; y: number }> = {};
  planets.forEach((p, i) => {
    const a = (2 * Math.PI * i) / N - Math.PI / 2;
    pos[p.id] = { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) };
  });
  return pos;
}

function Inspector({ hop, onClose }: { hop: Hop; onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 40 }}
      className="absolute top-4 right-4 w-96 bg-panel/95 backdrop-blur border border-cyan-900/50 rounded-lg shadow-2xl shadow-cyan-500/10 z-20"
    >
      <div className="flex items-center justify-between px-4 py-2 border-b border-cyan-900/50">
        <div className="text-cyan-400 text-sm tracking-widest">▸ HOP INSPECTOR · {hop.node}</div>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-200">✕</button>
      </div>
      <div className="p-4 text-xs space-y-3">
        <div>
          <div className="text-slate-500 uppercase tracking-wider mb-1">Planet</div>
          <div className="text-slate-200">{hop.name} · Base {hop.codex_base}</div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 mt-2 text-slate-400">
            <div>Radius: <span className="text-slate-200">{hop.radius_km} km</span></div>
            <div>Towers: <span className="text-slate-200">{hop.towers}</span></div>
            <div>Atmos.: <span className="text-slate-200">{hop.atmosphere_km} km</span></div>
            <div>Refract: <span className="text-slate-200">{hop.refraction}</span></div>
          </div>
        </div>

        {/* Core Physical Variables */}
        <div className="space-y-1 bg-cyan-950/20 p-2.5 rounded border border-cyan-900/30">
          <div className="text-[10px] text-cyan-400 font-bold uppercase tracking-wider mb-2">▸ Physical Parameters</div>
          {hop.next_link ? (
            <>
              <div className="flex justify-between">
                <span className="text-slate-400">Void Distance (L):</span>
                <span className="text-slate-200 font-mono">{(hop.next_link.breakdown_ms.void * 300).toLocaleString(undefined, {maximumFractionDigits: 0})} km</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Void Travel Time (Tv):</span>
                <span className="text-slate-200 font-mono">{(hop.next_link.breakdown_ms.void + hop.next_link.breakdown_ms.atmosphere_origin + hop.next_link.breakdown_ms.atmosphere_dest).toFixed(2)} ms</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Internal Transit (Tp):</span>
                <span className="text-slate-200 font-mono">{(hop.next_link.breakdown_ms.fiber_origin + hop.next_link.breakdown_ms.tower_origin).toFixed(2)} ms</span>
              </div>
              {hop.entry_tower !== undefined && hop.entry_tower !== null && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Entry Tower (current):</span>
                  <span className="text-amber-400 font-bold font-mono">Tower {hop.entry_tower}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-400">Exit Tower (current):</span>
                <span className="text-amber-400 font-bold font-mono">Tower {hop.exit_tower}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Entry Tower (next):</span>
                <span className="text-amber-400 font-bold font-mono">Tower {hop.next_link.entry_tower}</span>
              </div>
            </>
          ) : (
            <>
              <div className="flex justify-between">
                <span className="text-slate-400">Internal Transit (Tp):</span>
                <span className="text-slate-200 font-mono">7.00 ms (Destination Arrival)</span>
              </div>
              {hop.entry_tower !== undefined && hop.entry_tower !== null && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Entry Tower (current):</span>
                  <span className="text-amber-400 font-bold font-mono">Tower {hop.entry_tower}</span>
                </div>
              )}
            </>
          )}
        </div>

        <div>
          <div className="text-slate-500 uppercase tracking-wider mb-1">Codex Transform</div>
          {hop.encoded_payload.steps.map((s, i) => (
            <div key={i} className="mb-1">
              <div className="text-cyan-500">{s.label}</div>
              <div className="text-amber-300 break-all">{s.value}</div>
            </div>
          ))}
        </div>

        {hop.next_link && (
          <div>
            <div className="text-slate-500 uppercase tracking-wider mb-1">Outbound Link → {hop.next_link.to}</div>
            <div className="text-emerald-400 text-base mb-1">Link Latency: {hop.next_link.latency_ms.toFixed(2)} ms</div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-slate-400">
              {Object.entries(hop.next_link.breakdown_ms).map(([k, v]) => (
                <div key={k}>{k}: <span className="text-slate-200">{Number(v).toFixed(2)}</span></div>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

export default function MissionControl() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [universe, setUniverse] = useState<Universe | null>(null);
  const [origin, setOrigin] = useState("");
  const [dest, setDest] = useState("");
  const [payload, setPayload] = useState("Hello");
  const [route, setRoute] = useState<RouteResult | null>(null);
  const [routeError, setRouteError] = useState<string | null>(null);
  const [inspect, setInspect] = useState<Hop | null>(null);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const positionsRef = useRef<Record<string, { x: number; y: number }>>({});

  const pushLog = (s: string) =>
    setLog((l) => [...l.slice(-50), `[${new Date().toLocaleTimeString()}] ${s}`]);

  // Fetch universe
  const loadUniverse = useCallback(async () => {
    try {
      const r = await fetch(`${API}/universe`);
      const u: Universe = await r.json();
      setUniverse(u);
      if (Object.keys(positionsRef.current).length === 0 && u.nodes.length) {
        positionsRef.current = layoutPositions(u.nodes);
      }
      // Backfill positions for any new node IDs that appear later
      u.nodes.forEach((p) => {
        if (!positionsRef.current[p.id]) {
          const angle = Math.random() * Math.PI * 2;
          positionsRef.current[p.id] = { x: 520 + 300 * Math.cos(angle), y: 380 + 300 * Math.sin(angle) };
        }
      });
    } catch (e) {
      pushLog(`✖ universe fetch failed`);
    }
  }, []);

  useEffect(() => { loadUniverse(); }, [loadUniverse]);

  // Build React Flow nodes / edges
  useEffect(() => {
    if (!universe) return;
    const pathEdgeIds = new Set<string>();
    if (route) {
      for (let i = 0; i < route.path.length - 1; i++) {
        const a = route.path[i], b = route.path[i + 1];
        pathEdgeIds.add(`${a}->${b}`); pathEdgeIds.add(`${b}->${a}`);
      }
    }
    const dead = new Set(universe.dead_nodes);
    const isOnPath = (id: string) => route?.path.includes(id);

    const flowNodes: Node[] = universe.nodes.map((p) => {
      const onPath = isOnPath(p.id);
      const bg = dead.has(p.id) ? "#7f1d1d"
        : p.id === origin ? "#0ea5e9"
        : p.id === dest   ? "#8b5cf6"
        : onPath ? "#059669" : "#064e3b";
      const border = onPath ? "#fbbf24" : "rgba(148,163,184,0.3)";
      return {
        id: p.id,
        position: positionsRef.current[p.id] || { x: 0, y: 0 },
        data: {
          label: (
            <div className="text-center leading-tight">
              <div className="text-[11px] font-bold text-white">{p.id}</div>
              <div className="text-[9px] text-cyan-200 opacity-80">{p.name}</div>
              <div className="text-[9px] text-amber-300">B{p.codex}</div>
            </div>
          ),
        },
        style: {
          background: `radial-gradient(circle at 30% 30%, ${bg} 0%, #020617 100%)`,
          color: "#fff",
          border: `2px solid ${border}`,
          borderRadius: "50%",
          width: 78, height: 78,
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: onPath ? "0 0 24px rgba(251,191,36,0.5)" : dead.has(p.id) ? "0 0 16px rgba(239,68,68,0.6)" : "0 0 12px rgba(34,211,238,0.15)",
          opacity: dead.has(p.id) ? 0.55 : 1,
        },
      };
    });

    const flowEdges: Edge[] = universe.edges.map((e) => {
      const id = `${e.source}->${e.target}`;
      const onPath = pathEdgeIds.has(id);
      return {
        id,
        source: e.source, target: e.target,
        label: `${e.latency_ms < 1000 ? e.latency_ms.toFixed(1) : (e.latency_ms / 1000).toFixed(1) + "k"} ms`,
        animated: onPath,
        style: {
          stroke: onPath ? "#fbbf24" : "#1e293b",
          strokeWidth: onPath ? 3 : 1,
          opacity: onPath ? 1 : 0.35,
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: onPath ? "#fbbf24" : "#334155" },
      };
    });

    setNodes(flowNodes); setEdges(flowEdges);
  }, [universe, route, origin, dest, setNodes, setEdges]);

  const sendPacket = async () => {
    if (!origin || !dest || origin === dest) { pushLog("✖ pick origin ≠ destination"); return; }
    setBusy(true); setInspect(null); setRouteError(null);
    pushLog(`► routing ${origin} → ${dest}`);
    try {
      const r = await fetch(`${API}/route`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ origin, destination: dest, payload }),
      });
      if (!r.ok) {
        pushLog(`✖ ${r.status} no route`);
        setRoute(null);
        setRouteError(`${origin} to ${dest} is unreachable. Nodes are physically isolated (distance exceeds maximum hop range of 50M km).`);
        return;
      }
      const data: RouteResult = await r.json();
      setRoute(data);
      setRouteError(null);
      pushLog(`✓ ${data.hop_count} hops · ${data.total_latency_ms.toFixed(1)} ms`);
    } catch (e) {
      pushLog(`✖ network/server error`);
      setRoute(null);
      setRouteError("Network error occurred while communicating with Sector telemetry service.");
    } finally { setBusy(false); }
  };

  const killNode = async (id: string) => {
    pushLog(`☠ killing ${id}`);
    await fetch(`${API}/kill`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ node_id: id }),
    });
    await loadUniverse();
    if (route && route.path.includes(id)) {
      pushLog(`⟳ rerouting`);
      await sendPacket();
    }
  };

  const restoreAll = async () => {
    await fetch(`${API}/reset`, { method: "POST" });
    pushLog("✓ all nodes restored");
    await loadUniverse();
  };

  const handleConfigUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    pushLog(`📁 Loading custom configuration: ${file.name}`);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const r = await fetch(`${API}/config`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });
      if (!r.ok) {
        pushLog(`✖ Configuration upload failed: ${r.statusText}`);
        return;
      }
      pushLog(`✓ Configuration uploaded successfully!`);
      setRoute(null);
      setRouteError(null);
      setOrigin("");
      setDest("");
      await loadUniverse();
    } catch (err: any) {
      pushLog(`✖ Failed to parse configuration: ${err.message}`);
    }
  };

  const onNodeClick = (_: any, n: Node) => {
    const hop = route?.hops.find((h) => h.node === n.id);
    if (hop) setInspect(hop);
  };

  // DEMO MODE
  const runDemo = async () => {
    if (!universe || universe.nodes.length < 3) return;
    setBusy(true);
    await fetch(`${API}/reset`, { method: "POST" });
    await loadUniverse();
    const ids = universe.all_planet_ids;
    const o = ids[0], d = ids[ids.length - 1];
    setOrigin(o); setDest(d); setPayload("RELIC");
    pushLog(`🎬 DEMO: ${o} → ${d}`);
    await new Promise((r) => setTimeout(r, 600));
    // initial route
    const r1 = await fetch(`${API}/route`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origin: o, destination: d, payload: "RELIC" }),
    }).then((x) => x.json());
    setRoute(r1); pushLog(`✓ initial ${r1.total_latency_ms.toFixed(0)}ms`);
    await new Promise((r) => setTimeout(r, 2000));
    if (r1.path.length > 2) {
      const victim = r1.path[1];
      setInspect(r1.hops[0]);
      await new Promise((r) => setTimeout(r, 1800));
      setInspect(null);
      await killNodeDemo(victim);
      await new Promise((r) => setTimeout(r, 800));
      const r2 = await fetch(`${API}/route`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ origin: o, destination: d, payload: "RELIC" }),
      }).then((x) => x.json());
      setRoute(r2); pushLog(`✓ rerouted ${r2.total_latency_ms.toFixed(0)}ms`);
    }
    setBusy(false);
  };
  const killNodeDemo = async (id: string) => {
    pushLog(`☠ DEMO killing ${id}`);
    await fetch(`${API}/kill`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ node_id: id }),
    });
    await loadUniverse();
  };

  // Packet animation (SVG dot along path)
  const packetSegments = useMemo(() => {
    if (!route || !universe) return [];
    const segs: { from: { x: number; y: number }; to: { x: number; y: number } }[] = [];
    for (let i = 0; i < route.path.length - 1; i++) {
      const a = positionsRef.current[route.path[i]];
      const b = positionsRef.current[route.path[i + 1]];
      if (a && b) segs.push({ from: a, to: b });
    }
    return segs;
  }, [route, universe]);

  return (
    <div className="h-screen w-screen flex bg-bg text-slate-200 overflow-hidden">
      {/* SIDEBAR */}
      <aside className="w-[360px] shrink-0 border-r border-cyan-900/40 bg-panel/80 backdrop-blur flex flex-col">
        <div className="p-4 border-b border-cyan-900/40">
          <div className="text-cyan-400 text-[10px] tracking-[0.3em]">RELICNET · OS</div>
          <div className="text-xl font-bold text-slate-100 mt-1">ZETA-26 MISSION CONTROL</div>
          <div className="text-[10px] text-slate-500 mt-1">
            {universe ? `${universe.nodes.length} active · ${universe.dead_nodes.length} dead` : "loading…"}
          </div>
        </div>

        {/* Transmission */}
        <div className="p-4 border-b border-cyan-900/40 space-y-2">
          <div className="text-[10px] text-cyan-500 tracking-widest">▸ TRANSMISSION</div>
          <div className="grid grid-cols-2 gap-2">
            <select value={origin} onChange={(e) => setOrigin(e.target.value)}
              className="bg-bg border border-slate-700 rounded px-2 py-1.5 text-xs">
              <option value="">Origin</option>
              {universe?.all_planet_ids.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select value={dest} onChange={(e) => setDest(e.target.value)}
              className="bg-bg border border-slate-700 rounded px-2 py-1.5 text-xs">
              <option value="">Destination</option>
              {universe?.all_planet_ids.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <input value={payload} onChange={(e) => setPayload(e.target.value)} placeholder="payload"
            className="w-full bg-bg border border-slate-700 rounded px-2 py-1.5 text-xs"/>
          <div className="flex gap-2">
            <button onClick={sendPacket} disabled={busy}
              className="flex-1 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white text-xs font-bold py-2 rounded tracking-wider">
              ► SEND PACKET
            </button>
            <button onClick={runDemo} disabled={busy}
              className="bg-amber-600 hover:bg-amber-500 disabled:bg-slate-700 text-white text-xs font-bold py-2 px-3 rounded tracking-wider">
              ▶ DEMO
            </button>
          </div>
        </div>

        {/* Load Configuration */}
        <div className="p-4 border-b border-cyan-900/40 space-y-2">
          <div className="text-[10px] text-cyan-500 tracking-widest">▸ LOAD CONFIGURATION</div>
          <label className="flex flex-col items-center justify-center border border-dashed border-cyan-800/40 hover:border-cyan-500/60 rounded p-4 cursor-pointer hover:bg-cyan-950/10 transition-colors">
            <span className="text-[10px] text-slate-400 font-bold">↑ UPLOAD UNIVERSE FILE</span>
            <span className="text-[9px] text-slate-500 mt-0.5">Select a universe-config.json file</span>
            <input type="file" accept=".json" onChange={handleConfigUpload} className="hidden" />
          </label>
        </div>

        {/* Route result */}
        <AnimatePresence>
        {route && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
            className="p-4 border-b border-cyan-900/40 overflow-hidden">
            <div className="text-[10px] text-emerald-500 tracking-widest">▸ ROUTE ACQUIRED</div>
            <div className="text-2xl text-emerald-400 mt-1 font-bold">{route.total_latency_ms.toFixed(2)} ms</div>
            <div className="text-[10px] text-slate-400 mt-0.5">{route.hop_count} hops · click planet for details</div>
            <div className="mt-2 text-xs text-amber-300 break-all">{route.path.join(" → ")}</div>
          </motion.div>
        )}
        {routeError && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
            className="p-4 border-b border-red-900/40 bg-red-950/20 overflow-hidden">
            <div className="text-[10px] text-red-500 tracking-widest font-bold">☠ ROUTE UNAVAILABLE</div>
            <div className="text-sm text-red-400 mt-1 font-bold">ISOLATED NODE DETECTED</div>
            <div className="text-[10px] text-slate-400 mt-1 leading-snug">{routeError}</div>
          </motion.div>
        )}
        </AnimatePresence>

        {/* Kill switch */}
        <div className="p-4 border-b border-cyan-900/40">
          <div className="flex items-center justify-between mb-2">
            <div className="text-[10px] text-red-500 tracking-widest">▸ CHAOS ENGINE</div>
            <button onClick={restoreAll} className="text-[10px] text-cyan-400 hover:text-cyan-300">⟳ reset</button>
          </div>
          <div className="flex flex-wrap gap-1">
            {universe?.all_planet_ids.map((id) => {
              const dead = universe.dead_nodes.includes(id);
              return (
                <button key={id} onClick={() => killNode(id)} disabled={dead}
                  className={`px-2 py-1 rounded text-[10px] tracking-wide ${
                    dead ? "bg-red-900/40 text-red-300/50 line-through" : "bg-slate-800 hover:bg-red-700 text-slate-200"
                  }`}>
                  {dead ? "✖" : "☠"} {id}
                </button>
              );
            })}
          </div>
        </div>

        {/* Log */}
        <div className="flex-1 overflow-auto p-4">
          <div className="text-[10px] text-slate-500 tracking-widest mb-2">▸ EVENT LOG</div>
          <div className="space-y-0.5 text-[10px] font-mono">
            {log.length === 0 && <div className="text-slate-600">awaiting commands…</div>}
            {log.slice().reverse().map((l, i) => (
              <div key={i} className="text-slate-400 leading-snug">{l}</div>
            ))}
          </div>
        </div>
      </aside>

      {/* CANVAS */}
      <main className="flex-1 relative scan-line">
        <ReactFlowProvider>
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView fitViewOptions={{ padding: 0.25 }}
            proOptions={{ hideAttribution: true }}
            nodesDraggable
          >
            <Background color="#1e293b" gap={32} size={1} />
            <Controls position="bottom-right" showInteractive={false} />
            <MiniMap nodeColor={(n) => (universe?.dead_nodes.includes(n.id) ? "#ef4444" : "#10b981")}
                     maskColor="rgba(5,7,13,0.8)" pannable zoomable />
          </ReactFlow>

          {/* SVG packet overlay */}
          {route && packetSegments.length > 0 && (
            <svg className="absolute inset-0 pointer-events-none w-full h-full" style={{ zIndex: 5 }}>
              <PacketDot segments={packetSegments} />
            </svg>
          )}
        </ReactFlowProvider>

        <AnimatePresence>
          {inspect && <Inspector hop={inspect} onClose={() => setInspect(null)} />}
        </AnimatePresence>

        {/* Header overlay */}
        <div className="absolute top-4 left-4 z-10 pointer-events-none">
          <div className="text-[10px] tracking-[0.3em] text-cyan-500">SECTOR ZETA-26 · LIVE TELEMETRY</div>
        </div>
      </main>
    </div>
  );
}

/** Animated packet dot — visual only; positions are in React-Flow viewport coords.
 *  Note: when the user pans/zooms, the dot won't track perfectly — kept as a
 *  decorative pulse along the straight-line segments. */
function PacketDot({ segments }: { segments: { from: { x: number; y: number }; to: { x: number; y: number } }[] }) {
  const [seg, setSeg] = useState(0);
  useEffect(() => {
    if (segments.length === 0) return;
    setSeg(0);
    const id = setInterval(() => setSeg((s) => (s + 1) % segments.length), 1400);
    return () => clearInterval(id);
  }, [segments]);
  const s = segments[seg]; if (!s) return null;
  return (
    <motion.circle
      key={seg}
      r={6} fill="#fbbf24"
      filter="drop-shadow(0 0 8px #fbbf24)"
      initial={{ cx: s.from.x, cy: s.from.y }}
      animate={{ cx: s.to.x, cy: s.to.y }}
      transition={{ duration: 1.2, ease: "linear" }}
    />
  );
}
