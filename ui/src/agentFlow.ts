import type { Edge, Node } from "reactflow";

export type StepStatus = "pending" | "active" | "done" | "error";

export interface AgentStep {
  id: string;
  label: string;
}

export const AGENT_STEPS: AgentStep[] = [
  { id: "graphify", label: "Graphify\n(rebuild knowledge graph)" },
  { id: "rag", label: "RAG\n(index requirements)" },
  { id: "baseline", label: "Baseline Build\n(mvn test + JaCoCo)" },
  { id: "planner", label: "Planner Agent\n(A2A)" },
  { id: "generator", label: "Generator Agent\n+ Guardrails (A2A)" },
  { id: "postbuild", label: "Re-run Tests\n(mvn test + JaCoCo)" },
  { id: "reviewer", label: "Reviewer Agent\n(A2A)" },
  { id: "done", label: "Done" },
];

const COLORS: Record<StepStatus, { bg: string; border: string }> = {
  pending: { bg: "#f1f5f9", border: "#cbd5e1" },
  active: { bg: "#dbeafe", border: "#2563eb" },
  done: { bg: "#dcfce7", border: "#16a34a" },
  error: { bg: "#fee2e2", border: "#dc2626" },
};

export function buildAgentFlowGraph(
  statusMap: Record<string, StepStatus>
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = AGENT_STEPS.map((step, i) => {
    const status = statusMap[step.id] ?? "pending";
    const c = COLORS[status];
    return {
      id: step.id,
      position: { x: 40, y: i * 100 },
      data: { label: step.label },
      style: {
        background: c.bg,
        border: `2px solid ${c.border}`,
        borderRadius: 8,
        fontSize: 12,
        padding: 10,
        width: 220,
        whiteSpace: "pre-line" as const,
        textAlign: "center" as const,
        fontWeight: status === "active" ? 600 : 400,
      },
    };
  });

  const edges: Edge[] = [];
  for (let i = 0; i < AGENT_STEPS.length - 1; i++) {
    const from = AGENT_STEPS[i].id;
    const to = AGENT_STEPS[i + 1].id;
    edges.push({
      id: `e-${from}-${to}`,
      source: from,
      target: to,
      animated: statusMap[from] === "active",
      style: { stroke: statusMap[to] && statusMap[to] !== "pending" ? "#16a34a" : "#94a3b8" },
    });
  }
  edges.push({
    id: "e-loop-back",
    source: "reviewer",
    target: "planner",
    type: "smoothstep",
    label: "iterate",
    labelStyle: { fontSize: 10 },
    style: { strokeDasharray: "4 4", stroke: "#94a3b8" },
  });

  return { nodes, edges };
}

export function statusFromEvent(
  prev: Record<string, StepStatus>,
  type: string,
  data: Record<string, unknown>
): Record<string, StepStatus> {
  const next = { ...prev };
  switch (type) {
    case "setup_graph_start": next.graphify = "active"; break;
    case "setup_graph_done": next.graphify = "done"; break;
    case "setup_rag_start": next.rag = "active"; break;
    case "setup_rag_done": next.rag = "done"; break;
    case "baseline_build_start": next.baseline = "active"; break;
    case "baseline_build_done": next.baseline = data.build_success ? "done" : "error"; break;
    case "iteration_start":
      next.planner = "active";
      next.generator = "pending";
      next.postbuild = "pending";
      next.reviewer = "pending";
      break;
    case "planner_done": next.planner = "done"; break;
    case "no_targets": next.planner = "done"; next.done = "done"; break;
    case "generator_start": next.generator = "active"; break;
    case "compile_check_start": next.generator = "active"; break;
    case "post_generation_build_start": next.generator = "done"; next.postbuild = "active"; break;
    case "post_generation_build_done": next.postbuild = data.build_success ? "done" : "error"; break;
    case "reviewer_start": next.reviewer = "active"; break;
    case "reviewer_done": next.reviewer = "done"; break;
    case "pipeline_done": next.done = "done"; break;
    default: break;
  }
  return next;
}
