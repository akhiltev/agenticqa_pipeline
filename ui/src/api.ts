export const API_BASE = "http://127.0.0.1:8090";

export interface FlowNode {
  id: string;
  type: string;
  data: {
    label: string;
    file_type?: string;
    source_file?: string;
    callable: boolean;
    coverage_pct: number | null;
  };
  position: { x: number; y: number };
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  data?: { confidence?: string };
  animated?: boolean;
}

export interface FlowGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

export interface SearchHit {
  id: string;
  label: string;
  source_file?: string;
}

export interface CoverageClass {
  class: string;
  line_pct: number;
  branch_pct: number;
  instruction_pct: number;
}

export interface CoverageReport {
  overall_line_pct: number;
  overall_branch_pct: number;
  overall_instruction_pct: number;
  classes: CoverageClass[];
  error?: string;
}

export interface RunRecord {
  timestamp: string;
  mode: string;
  pr_id: string | null;
  overall_line_pct: number;
  overall_branch_pct: number;
  per_class: Record<string, number>;
}

export interface CoverageDelta {
  prev_timestamp: string;
  curr_timestamp: string;
  overall_line_delta: number;
  overall_branch_delta: number;
  per_class_changes: { class: string; before: number; after: number; delta: number }[];
}

export interface ReportListItem {
  name: string;
  modified: number;
}

export interface DemoState {
  generated_test_files: string[];
  coverage: { line_pct: number; branch_pct: number } | null;
  report_count: number;
  run_count: number;
  rag_present: boolean;
  graph: { nodes: number; edges: number; has_report: boolean; has_html: boolean } | null;
}

async function getJSON<T>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`);
  if (!resp.ok) throw new Error(`${path} -> ${resp.status}`);
  return resp.json();
}

export interface GraphifyCliResult {
  returncode: number;
  stdout: string;
  stderr: string;
}

async function postJSON<T>(path: string, body: unknown = {}): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`${path} -> ${resp.status}`);
  return resp.json();
}

export const api = {
  getGraph: (godNodes = 8, depth = 1) =>
    getJSON<FlowGraph>(`/api/graph?god_nodes=${godNodes}&depth=${depth}`),
  expandGraph: (nodeId: string, depth = 1) =>
    getJSON<FlowGraph>(`/api/graph/expand?node_id=${encodeURIComponent(nodeId)}&depth=${depth}`),
  searchGraph: (q: string) => getJSON<SearchHit[]>(`/api/graph/search?q=${encodeURIComponent(q)}`),
  getGraphByClass: (className: string, depth = 1) =>
    getJSON<FlowGraph>(`/api/graph/by-class?class_name=${encodeURIComponent(className)}&depth=${depth}`),

  graphifyRebuild: () => postJSON<GraphifyCliResult & { graph_path: string }>("/api/graphify/rebuild"),
  graphifyCluster: () =>
    postJSON<GraphifyCliResult & { has_report: boolean; has_html: boolean }>("/api/graphify/cluster"),
  graphifyReport: () => getJSON<{ content: string }>("/api/graphify/report"),
  graphifyHtmlUrl: () => getJSON<{ exists: boolean; url: string | null }>("/api/graphify/html-url"),
  graphifyGodNodes: (top = 10) => postJSON<GraphifyCliResult>("/api/graphify/god-nodes", { top }),
  graphifyExplain: (query: string) => postJSON<GraphifyCliResult>("/api/graphify/explain", { query }),
  graphifyPath: (a: string, b: string) => postJSON<GraphifyCliResult>("/api/graphify/path", { a, b }),
  graphifyAffected: (query: string) => postJSON<GraphifyCliResult>("/api/graphify/affected", { query }),
  graphifyQuery: (query: string) => postJSON<GraphifyCliResult>("/api/graphify/query", { query }),

  getCoverage: () => getJSON<CoverageReport>("/api/coverage"),

  getCoverageHistory: () => getJSON<RunRecord[]>("/api/coverage/history"),
  getCoverageDelta: () => getJSON<CoverageDelta | null>("/api/coverage/delta"),
  getJacocoReportInfo: () => getJSON<{ exists: boolean; url: string | null }>("/api/coverage/jacoco-report"),
  getClassReportUrl: (className: string) =>
    getJSON<{ url: string | null }>(`/api/coverage/class-report-url?class_name=${encodeURIComponent(className)}`),

  listReports: () => getJSON<ReportListItem[]>("/api/reports"),
  getReport: (name: string) => getJSON<{ name: string; content: string }>(`/api/reports/${name}`),

  getState: () => getJSON<DemoState>("/api/state"),

  startRun: async (body: {
    mode: string;
    question?: string;
    target_class?: string | null;
    pr_id?: string | null;
  }): Promise<{ run_id: string }> => {
    const resp = await fetch(`${API_BASE}/api/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(`start_run -> ${resp.status}`);
    return resp.json();
  },

  reset: async (baselineBuild = true, keepReports = false): Promise<{ log: string }> => {
    const resp = await fetch(`${API_BASE}/api/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ baseline_build: baselineBuild, keep_reports: keepReports }),
    });
    if (!resp.ok) throw new Error(`reset -> ${resp.status}`);
    return resp.json();
  },
};
