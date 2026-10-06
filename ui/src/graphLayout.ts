import dagre from "dagre";
import { MarkerType, Position, type Edge, type Node } from "reactflow";
import type { FlowGraph } from "./api";

export type NodeStatus = "target" | "accepted" | "rejected";

const STATUS_COLOR: Record<NodeStatus, { bg: string; border: string }> = {
  target: { bg: "#dbeafe", border: "#2563eb" },
  accepted: { bg: "#dcfce7", border: "#16a34a" },
  rejected: { bg: "#fee2e2", border: "#dc2626" },
};

const COVERAGE_COLOR = { high: "#dcfce7", mid: "#fef9c3", low: "#fee2e2" };
const COVERAGE_BORDER = { high: "#16a34a", mid: "#ca8a04", low: "#dc2626" };
const DEFAULT_COLOR = { bg: "#f8fafc", border: "#94a3b8" };

function truncateLabel(label: string, max = 26): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}

export function layoutGraph(
  graph: FlowGraph,
  statusMap: Record<string, NodeStatus> = {}
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 56, ranksep: 130, marginx: 20, marginy: 20 });
  g.setDefaultEdgeLabel(() => ({}));
  const width = 200, height = 50;
  graph.nodes.forEach((n) => g.setNode(n.id, { width, height }));
  graph.edges.forEach((e) => {
    if (graph.nodes.some((n) => n.id === e.source) && graph.nodes.some((n) => n.id === e.target)) {
      g.setEdge(e.source, e.target);
    }
  });
  dagre.layout(g);

  const nodes: Node[] = graph.nodes.map((n) => {
    const pos = g.node(n.id);
    const status = statusMap[n.id];
    const coverage = n.data.coverage_pct;
    let bg = DEFAULT_COLOR.bg;
    let border = DEFAULT_COLOR.border;
    if (status) {
      bg = STATUS_COLOR[status].bg;
      border = STATUS_COLOR[status].border;
    } else if (coverage !== null && coverage !== undefined) {
      if (coverage >= 90) { bg = COVERAGE_COLOR.high; border = COVERAGE_BORDER.high; }
      else if (coverage >= 70) { bg = COVERAGE_COLOR.mid; border = COVERAGE_BORDER.mid; }
      else { bg = COVERAGE_COLOR.low; border = COVERAGE_BORDER.low; }
    }
    const isCallable = n.data.callable;
    return {
      id: n.id,
      position: { x: pos?.x ?? 0, y: pos?.y ?? 0 },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      data: { label: truncateLabel(n.data.label), raw: n },
      style: {
        background: bg,
        border: `${status ? 2 : 1.5}px solid ${border}`,
        borderRadius: 8,
        fontSize: 11.5,
        fontWeight: isCallable ? 600 : 500,
        padding: "8px 10px",
        width,
        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.08)",
        color: "#0f172a",
        textAlign: "center" as const,
      },
      title: n.data.label,
    };
  });

  const edges: Edge[] = graph.edges.map((e) => {
    const inferred = e.data?.confidence === "INFERRED";
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label,
      type: "smoothstep",
      animated: e.animated,
      style: { stroke: inferred ? "#94a3b8" : "#64748b", strokeWidth: 1.4, strokeDasharray: inferred ? "5 4" : undefined },
      labelStyle: { fontSize: 9.5, fill: "#475569", fontWeight: 500 },
      labelBgStyle: { fill: "#ffffff", fillOpacity: 0.85 },
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: inferred ? "#94a3b8" : "#64748b" },
    };
  });

  return { nodes, edges };
}

export function mergeGraphs(a: FlowGraph, b: FlowGraph): FlowGraph {
  return {
    nodes: [...a.nodes, ...b.nodes].filter((n, i, arr) => arr.findIndex((x) => x.id === n.id) === i),
    edges: [...a.edges, ...b.edges].filter((e, i, arr) => arr.findIndex((x) => x.id === e.id) === i),
  };
}

export function flowNodesToGraph(nodes: Node[], edges: Edge[]): FlowGraph {
  return {
    nodes: nodes.map((n) => n.data.raw as FlowGraph["nodes"][number]),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label as string,
      animated: e.animated,
      data: {},
    })),
  };
}

