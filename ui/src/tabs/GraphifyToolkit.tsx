import { useState } from "react";
import { api } from "../api";
import ReactMarkdown from "react-markdown";
import { Card } from "../components/ui";


type ActionKey = "rebuild" | "cluster" | "god-nodes" | "explain" | "path" | "affected" | "query";

export default function GraphifyToolkit({ onGraphChanged }: { onGraphChanged: () => void }) {
  const [busy, setBusy] = useState<ActionKey | null>(null);
  const [output, setOutput] = useState<string>("");
  const [reportContent, setReportContent] = useState<string | null>(null);
  const [htmlAvailable, setHtmlAvailable] = useState(false);

  const [explainQuery, setExplainQuery] = useState("CDL");
  const [pathA, setPathA] = useState("CDL");
  const [pathB, setPathB] = useState("JSONException");
  const [affectedQuery, setAffectedQuery] = useState("CDL");
  const [queryText, setQueryText] = useState("how does CDL relate to JSONException?");
  const [godTop, setGodTop] = useState(10);

  const run = async (key: ActionKey, fn: () => Promise<{ stdout: string; stderr: string }>) => {
    setBusy(key);
    setOutput("");
    try {
      const res = await fn();
      setOutput(res.stdout || res.stderr || "(no output)");
    } catch (err) {
      setOutput(`Error: ${String(err)}`);
    } finally {
      setBusy(null);
    }
  };

  const rebuild = () =>
    run("rebuild", async () => {
      const res = await api.graphifyRebuild();
      onGraphChanged();
      return res;
    });

  const cluster = () =>
    run("cluster", async () => {
      const res = await api.graphifyCluster();
      setHtmlAvailable(res.has_html);
      onGraphChanged();
      return res;
    });

  const loadReport = async () => {
    try {
      const res = await api.graphifyReport();
      setReportContent(res.content);
    } catch {
      setReportContent("GRAPH_REPORT.md not generated yet. Click 'cluster-only' first.");
    }
  };

  const openHtml = async () => {
    const info = await api.graphifyHtmlUrl();
    if (info.exists && info.url) {
      window.open(`http://127.0.0.1:8090${info.url}`, "_blank");
    } else {
      setOutput("graph.html not generated yet. Click 'cluster-only' first.");
    }
  };

  return (
    <div style={{ padding: 16, overflowY: "auto", height: "100%", fontSize: 13 }}>
      <h3 style={{ marginTop: 0 }}>Graphify Toolkit</h3>

      <Card title="Update & Cluster" style={{ marginBottom: 14 }}>
        <div style={{ padding: 14 }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
            <button className="btn-primary" onClick={rebuild} disabled={busy !== null}>
              {busy === "rebuild" ? "Rebuilding..." : "graphify update --no-cluster (fast)"}
            </button>
            <button className="btn-primary" onClick={cluster} disabled={busy !== null}>
              {busy === "cluster" ? "Clustering..." : "graphify cluster-only (report + html)"}
            </button>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button onClick={loadReport}>View GRAPH_REPORT.md</button>
            <button onClick={openHtml}>Open interactive graph.html</button>
          </div>
        </div>
      </Card>

      <Card title="Explore Queries" style={{ marginBottom: 14 }}>
        <div style={{ padding: 14 }}>
          <div className="field" style={{ marginBottom: 10 }}>
            <label>god-nodes --top</label>
            <div style={{ display: "flex", gap: 6 }}>
              <input
                type="number"
                style={{ width: 70 }}
                value={godTop}
                onChange={(e) => setGodTop(Number(e.target.value))}
              />
              <button onClick={() => run("god-nodes", () => api.graphifyGodNodes(godTop))} disabled={busy !== null}>
                Run
              </button>
            </div>
          </div>

          <div className="field" style={{ marginBottom: 10 }}>
            <label>explain "name"</label>
            <div style={{ display: "flex", gap: 6 }}>
              <input style={{ flex: 1 }} value={explainQuery} onChange={(e) => setExplainQuery(e.target.value)} />
              <button onClick={() => run("explain", () => api.graphifyExplain(explainQuery))} disabled={busy !== null}>
                Run
              </button>
            </div>
          </div>

          <div className="field" style={{ marginBottom: 10 }}>
            <label>path "A" "B"</label>
            <div style={{ display: "flex", gap: 6 }}>
              <input style={{ flex: 1 }} value={pathA} onChange={(e) => setPathA(e.target.value)} placeholder="A" />
              <input style={{ flex: 1 }} value={pathB} onChange={(e) => setPathB(e.target.value)} placeholder="B" />
              <button onClick={() => run("path", () => api.graphifyPath(pathA, pathB))} disabled={busy !== null}>
                Run
              </button>
            </div>
          </div>

          <div className="field" style={{ marginBottom: 10 }}>
            <label>affected "name"</label>
            <div style={{ display: "flex", gap: 6 }}>
              <input style={{ flex: 1 }} value={affectedQuery} onChange={(e) => setAffectedQuery(e.target.value)} />
              <button onClick={() => run("affected", () => api.graphifyAffected(affectedQuery))} disabled={busy !== null}>
                Run
              </button>
            </div>
          </div>

          <div className="field">
            <label>query "question"</label>
            <div style={{ display: "flex", gap: 6 }}>
              <input style={{ flex: 1 }} value={queryText} onChange={(e) => setQueryText(e.target.value)} />
              <button onClick={() => run("query", () => api.graphifyQuery(queryText))} disabled={busy !== null}>
                Run
              </button>
            </div>
          </div>
        </div>
      </Card>

      {output && <pre className="ui-console">{output}</pre>}

      {reportContent && (
        <Card style={{ marginTop: 14 }}>
          <div style={{ padding: 16, maxHeight: 320, overflowY: "auto" }}>
            <ReactMarkdown>{reportContent}</ReactMarkdown>
          </div>
        </Card>
      )}
      {htmlAvailable && (
        <p style={{ color: "var(--color-success)", fontSize: 12, marginTop: 10 }}>
          graph.html regenerated - click "Open interactive graph.html" above.
        </p>
      )}
    </div>
  );
}


