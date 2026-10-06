import { useCallback, useEffect, useRef, useState } from "react";
import ReactFlow, { Background, Controls } from "reactflow";
import "reactflow/dist/style.css";
import { api, API_BASE, type FlowGraph } from "../api";
import { layoutGraph, type NodeStatus } from "../graphLayout";
import { buildAgentFlowGraph, statusFromEvent, type StepStatus } from "../agentFlow";
import { Card, EmptyState, Field, SegmentedControl, type BadgeTone } from "../components/ui";


interface TimelineEvent {
  type: string;
  data: Record<string, unknown>;
}

type PanelView = "agents" | "graph";

export default function RunTab() {
  const [mode, setMode] = useState("spec");
  const [question, setQuestion] = useState(
    "write char array offset length bounds checking IndexOutOfBoundsException and append CharSequence null handling"
  );
  const [targetClass, setTargetClass] = useState("StringBuilderWriter");
  const [prId, setPrId] = useState("PR-501");
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const esRef = useRef<EventSource | null>(null);
  const [panelView, setPanelView] = useState<PanelView>("agents");
  const [logsExpanded, setLogsExpanded] = useState(true);


  const [rawGraph, setRawGraph] = useState<FlowGraph>({ nodes: [], edges: [] });
  const [nodeStatusMap, setNodeStatusMap] = useState<Record<string, NodeStatus>>({});
  const [graphLoading, setGraphLoading] = useState(false);

  const [stepStatusMap, setStepStatusMap] = useState<Record<string, StepStatus>>({});

  const loadPreviewGraph = useCallback(() => {
    if (!targetClass.trim()) {
      setRawGraph({ nodes: [], edges: [] });
      return;
    }
    setGraphLoading(true);
    api.getGraphByClass(targetClass.trim(), 1)
      .then((g) => setRawGraph(g))
      .catch(() => setRawGraph({ nodes: [], edges: [] }))
      .finally(() => setGraphLoading(false));
  }, [targetClass]);

  useEffect(() => {
    if (mode === "spec") loadPreviewGraph();
  }, [mode, loadPreviewGraph]);

  const { nodes: graphNodes, edges: graphEdges } = layoutGraph(rawGraph, nodeStatusMap);
  const { nodes: agentNodes, edges: agentEdges } = buildAgentFlowGraph(stepStatusMap);

  const markGraphNodeStatus = (label: string | undefined, status: NodeStatus) => {
    if (!label) return;
    const match = rawGraph.nodes.find(
      (n) => n.data.label === label || n.data.label.replace(/[.()]/g, "") === label
    );
    if (!match) return;
    setNodeStatusMap((prev) => ({ ...prev, [match.id]: status }));
  };

  const start = async () => {

    setEvents([]);
    setNodeStatusMap({});
    setStepStatusMap({});
    setRunning(true);
    if (mode === "spec") loadPreviewGraph();

    const { run_id } = await api.startRun({
      mode,
      question,
      target_class: targetClass || null,
      pr_id: mode === "pr" ? prId : null,
    });
    const es = new EventSource(`${API_BASE}/api/run/${run_id}/events`);
    esRef.current = es;
    es.onmessage = (msg) => {
      const parsed = JSON.parse(msg.data);
      setEvents((prev) => [...prev, { type: parsed.type, data: parsed }]);
      setStepStatusMap((prev) => statusFromEvent(prev, parsed.type, parsed));

      if (parsed.type === "planner_done") {
        const targets = (parsed.targets as { node_id: string; label: string }[]) ?? [];
        setNodeStatusMap((prev) => {
          const next = { ...prev };
          for (const t of targets) next[t.node_id] = "target";
          return next;
        });
      } else if (parsed.type === "generator_result") {
        const result = parsed.result as { status: string; class_name?: string };
        const target = parsed.target as { label?: string } | undefined;
        markGraphNodeStatus(target?.label, result.status === "accepted" ? "accepted" : "rejected");
      }

      if (parsed.type === "stream_end") {
        setRunning(false);
        es.close();
      }
    };
    es.onerror = () => {
      setRunning(false);
      es.close();
    };
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div style={{ flex: "1 1 55%", padding: 20, overflowY: "auto", minWidth: 380 }}>
        <h2>Run the AI QA Engineer Pipeline</h2>
        <p style={{ marginBottom: 16, fontSize: 13 }}>
          Configure a run below, then watch the agent flow and knowledge graph update live on the right.
        </p>
        <Card style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end", padding: 16 }}>
            <Field label="Mode">
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="spec">spec</option>
                <option value="pr">pr</option>
              </select>
            </Field>
            {mode === "pr" ? (
              <Field label="PR id">
                <input value={prId} onChange={(e) => setPrId(e.target.value)} />
              </Field>
            ) : (
              <>
                <Field label="Question" style={{ flex: 1, minWidth: 260 }}>
                  <input style={{ width: "100%" }} value={question} onChange={(e) => setQuestion(e.target.value)} />
                </Field>
                <Field label="Target class (optional override)">
                  <input
                    value={targetClass}
                    onChange={(e) => setTargetClass(e.target.value)}
                    onBlur={loadPreviewGraph}
                  />
                </Field>
              </>
            )}
            <button className="btn-primary" onClick={start} disabled={running}>
              {running ? "Running..." : "▶ Run"}
            </button>
          </div>
        </Card>

        <Card
          title={`Execution Log${events.length > 0 ? ` (${events.length})` : ""}`}
          actions={
            <button className="btn-ghost" onClick={() => setLogsExpanded((v) => !v)} style={{ fontSize: 12, padding: "4px 10px" }}>
              {logsExpanded ? "▾ Collapse" : "▸ Expand"}
            </button>
          }
          padded={false}
        >
          {logsExpanded && (
            <div style={{ padding: 16, maxHeight: 420, overflowY: "auto" }}>
              {events.length === 0 && !running && (
                <EmptyState
                  title="No run yet"
                  description="Click Run to trigger the pipeline and watch the panel on the right light up live."
                />
              )}
              {events.map((e, i) => (
                <TimelineItem key={i} event={e} />
              ))}
            </div>
          )}
        </Card>
      </div>

      <div style={{ flex: "1 1 45%", borderLeft: "1px solid var(--color-border)", position: "relative", minWidth: 320, display: "flex", flexDirection: "column", background: "var(--color-surface)" }}>
        <div style={{ display: "flex", padding: 12, borderBottom: "1px solid var(--color-border)", flexShrink: 0 }}>
          <SegmentedControl
            value={panelView}
            onChange={setPanelView}
            options={[
              { value: "agents", label: "Agent Flow" },
              { value: "graph", label: "Knowledge Graph" },
            ]}
          />
        </div>

        <div style={{ flex: 1, position: "relative" }}>
          {panelView === "agents" ? (
            <ReactFlow nodes={agentNodes} edges={agentEdges} fitView proOptions={{ hideAttribution: true }}>
              <Background />
              <Controls showInteractive={false} />
            </ReactFlow>
          ) : graphNodes.length === 0 && !graphLoading ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", padding: 24 }}>
              <EmptyState
                title="No graph nodes to show"
                description={
                  targetClass
                    ? `No graph nodes found for "${targetClass}". Rebuild the knowledge graph (run the pipeline once) or check the class name.`
                    : "Enter a target class to preview its subgraph, or switch to PR mode."
                }
              />
            </div>
          ) : (
            <>
              <div style={{ position: "absolute", top: 10, left: 10, zIndex: 5, fontSize: 12, color: "var(--color-text-muted)", background: "var(--color-surface)", padding: "3px 10px", borderRadius: 999, border: "1px solid var(--color-border)", boxShadow: "var(--shadow-sm)" }}>
                {graphLoading ? "Loading..." : `${graphNodes.length} node(s)`}
              </div>
              <ReactFlow nodes={graphNodes} edges={graphEdges} fitView>
                <Background />
                <Controls />
              </ReactFlow>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function TimelineItem({ event }: { event: TimelineEvent }) {
  const { type, data } = event;
  let text = type;
  let tone: BadgeTone = "info";

  if (type === "planner_done") {
    const targets = (data.targets as { label: string }[]) ?? [];
    text = `Planner proposed ${targets.length} target(s): ${targets.map((t) => t.label).join(", ")}`;
  } else if (type === "generator_start") {
    text = `Generator: attempting ${(data.target as { label: string })?.label}`;
  } else if (type === "generator_result") {
    const result = data.result as { status: string; class_name?: string; errors?: string[] };
    text = `Generator result: ${result.status}${result.class_name ? ` (${result.class_name})` : ""}`;
    tone = result.status === "accepted" ? "success" : "danger";
  } else if (type === "compile_check_start") {
    text = "Dry-compiling generated test...";
  } else if (type === "baseline_build_done" || type === "post_generation_build_done") {
    const cov = data.coverage as { overall_line_pct?: number; overall_branch_pct?: number };
    text = `${type}: build_success=${data.build_success} line=${cov?.overall_line_pct}% branch=${cov?.overall_branch_pct}%`;
    tone = data.build_success ? "success" : "danger";
  } else if (type === "reviewer_done") {
    const result = data.result as { should_continue?: boolean; target_met?: boolean; report_path?: string };
    text = `Reviewer verdict: should_continue=${result.should_continue} target_met=${result.target_met}`;
  } else if (type === "stream_end") {
    text = `Pipeline finished: ${data.status}`;
    tone = data.status === "done" ? "success" : "danger";
  }

  const borderColors: Record<BadgeTone, string> = {
    neutral: "var(--color-border-strong)",
    info: "var(--color-primary)",
    success: "var(--color-success)",
    warning: "var(--color-warning)",
    danger: "var(--color-danger)",
  };

  return (
    <div
      style={{
        padding: "8px 12px",
        marginBottom: 6,
        fontSize: 13,
        color: "var(--color-text)",
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderLeft: `3px solid ${borderColors[tone]}`,
        borderRadius: "var(--radius-sm)",
      }}
    >
      {text}
    </div>
  );
}


