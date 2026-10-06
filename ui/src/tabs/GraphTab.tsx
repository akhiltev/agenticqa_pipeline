import { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background, Controls, MiniMap,
  type Node, useEdgesState, useNodesState,
} from "reactflow";
import "reactflow/dist/style.css";
import { api, type FlowGraph, type SearchHit } from "../api";
import { layoutGraph, mergeGraphs, flowNodesToGraph } from "../graphLayout";
import GraphifyToolkit from "./GraphifyToolkit";
import { EmptyState } from "../components/ui";



export default function GraphTab() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [selected, setSelected] = useState<Node | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showToolkit, setShowToolkit] = useState(false);


  const loadDefault = useCallback(() => {
    setLoading(true);
    api.getGraph()
      .then((g) => {
        const { nodes: n, edges: e } = layoutGraph(g);
        setNodes(n);
        setEdges(e);
        setError(null);
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [setNodes, setEdges]);

  useEffect(() => { loadDefault(); }, [loadDefault]);

  const onSearch = useCallback((q: string) => {
    setQuery(q);
    if (q.trim().length < 2) { setHits([]); return; }
    api.searchGraph(q).then(setHits).catch(() => setHits([]));
  }, []);

  const expandOn = useCallback((nodeId: string) => {
    api.expandGraph(nodeId, 1).then((g) => {
      const merged = mergeGraphs(flowNodesToGraph(nodes, edges), g);
      const { nodes: n, edges: ed } = layoutGraph(merged);
      setNodes(n);
      setEdges(ed);
    });
  }, [nodes, edges, setNodes, setEdges]);

  const onNodeClick = useCallback((_: unknown, node: Node) => {
    setSelected(node);
    expandOn(node.id);
  }, [expandOn]);

  const selectedRaw = useMemo(
    () => selected?.data.raw as FlowGraph["nodes"][number] | undefined,
    [selected]
  );

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div style={{ flex: 1, position: "relative", background: "#f8fafc" }}>
        <div className="graph-search-panel">
          <input
            placeholder="🔎 Search class (e.g. StringBuilderWriter)"
            value={query}
            onChange={(e) => onSearch(e.target.value)}
            style={{ width: "100%", padding: 6 }}
          />
          {hits.length > 0 && (
            <ul style={{ listStyle: "none", margin: "6px 0 0", padding: 0, maxHeight: 160, overflowY: "auto", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)" }}>
              {hits.map((h) => (
                <li key={h.id} style={{ padding: "6px 8px", cursor: "pointer", fontSize: 12, borderBottom: "1px solid var(--color-border)" }}
                  onClick={() => { setQuery(""); setHits([]); expandOn(h.id); }}>
                  {h.label} <span style={{ color: "var(--color-text-faint)" }}>({h.source_file})</span>
                </li>
              ))}
            </ul>
          )}
          <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
            <button onClick={loadDefault} style={{ flex: 1 }}>Reset to god nodes</button>
            <button onClick={() => setShowToolkit((v) => !v)} style={{ flex: 1 }}>
              {showToolkit ? "Hide Toolkit" : "Toolkit (CLI)"}
            </button>
          </div>
          {loading && <div style={{ fontSize: 11, color: "var(--color-text-faint)", marginTop: 6 }}>Loading graph...</div>}
          {error && <div style={{ fontSize: 11, color: "var(--color-danger)", marginTop: 6 }}>{error}</div>}
        </div>

        {!loading && !error && nodes.length === 0 ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }}>
            <EmptyState
              title="No graph data yet"
              description='Click "Reset to god nodes" above, or run the pipeline once to build the knowledge graph.'
            />
          </div>
        ) : (
          <>
            <div className="graph-legend">
              <span className="graph-legend-title">Node color</span>
              <LegendDot color="#dcfce7" border="#16a34a" label="High coverage / accepted" />
              <LegendDot color="#fef9c3" border="#ca8a04" label="Medium coverage" />
              <LegendDot color="#fee2e2" border="#dc2626" label="Low coverage / rejected" />
              <LegendDot color="#dbeafe" border="#2563eb" label="Planner target" />
              <LegendDot color="#f8fafc" border="#94a3b8" label="No coverage data" />
            </div>
            <div className="graph-node-count">{nodes.length} node(s) &middot; {edges.length} edge(s)</div>
          </>
        )}

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          fitView
          minZoom={0.1}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#cbd5e1" gap={20} />
          <Controls />
          <MiniMap pannable zoomable style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }} />
        </ReactFlow>
      </div>
      {showToolkit && (
        <div style={{ width: 340, borderLeft: "1px solid var(--color-border)", background: "var(--color-surface)" }}>
          <GraphifyToolkit onGraphChanged={loadDefault} />
        </div>
      )}
      {!showToolkit && selectedRaw && (
        <div style={{ width: 280, borderLeft: "1px solid var(--color-border)", padding: 16, overflowY: "auto", background: "var(--color-surface)" }}>
          <h3 style={{ marginTop: 0 }}>{selectedRaw.data.label}</h3>
          <p style={{ fontSize: 12, wordBreak: "break-all" }}>{selectedRaw.data.source_file}</p>
          <p style={{ fontSize: 12 }}>
            Coverage:{" "}
            <strong style={{ color: "var(--color-text)" }}>
              {selectedRaw.data.coverage_pct !== null
                ? `${selectedRaw.data.coverage_pct}%`
                : "n/a (not a whole-class node, or no report yet)"}
            </strong>
          </p>
          <p style={{ fontSize: 11, color: "var(--color-text-faint)" }}>Clicking a node expands its neighbors.</p>
        </div>
      )}
    </div>
  );
}

function LegendDot({ color, border, label }: { color: string; border: string; label: string }) {
  return (
    <span className="graph-legend-item">
      <span className="graph-legend-swatch" style={{ background: color, borderColor: border }} />
      {label}
    </span>
  );
}


