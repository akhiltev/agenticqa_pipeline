import { useEffect, useState } from "react";
import GraphTab from "./tabs/GraphTab";
import CoverageTab from "./tabs/CoverageTab";
import RunTab from "./tabs/RunTab";
import ReportsTab from "./tabs/ReportsTab";
import { api, type DemoState } from "./api";
import "./App.css";

type TabKey = "run" | "graph" | "coverage" | "reports";
const TABS: TabKey[] = ["run", "graph", "coverage", "reports"];

function App() {
  const [tab, setTab] = useState<TabKey>("run");
  const [state, setState] = useState<DemoState | null>(null);
  const [resetting, setResetting] = useState(false);

  const refreshState = () => {
    api.getState().then(setState).catch(() => setState(null));
  };

  useEffect(() => {
    refreshState();
    const interval = setInterval(refreshState, 5000);
    return () => clearInterval(interval);
  }, []);

  const doReset = async () => {
    setResetting(true);
    try {
      await api.reset(true, false);
      refreshState();
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">
          <span className="app-brand-mark">QA</span>
          <span>Agentic QA Pipeline</span>
        </div>
        <nav>
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={tab === t ? "tab-active" : ""}
              style={{ textTransform: "capitalize" }}
            >
              {t}
            </button>
          ))}
        </nav>
        <div className="app-status">
          {state && (
            <>
              <span className="app-status-chip">
                Coverage: <strong>{state.coverage ? `${state.coverage.line_pct}%` : "n/a"}</strong>
              </span>
              <span className="app-status-chip">
                Generated tests: <strong>{state.generated_test_files.length}</strong>
              </span>
              <span className="app-status-chip">
                Reports: <strong>{state.report_count}</strong>
              </span>
              <span className="app-status-chip">
                Graph: <strong>{state.graph ? `${state.graph.nodes} nodes` : "not built"}</strong>
              </span>
            </>
          )}
          <button className="btn-danger" onClick={doReset} disabled={resetting}>
            {resetting ? "Resetting..." : "Reset Demo State"}
          </button>
        </div>
      </header>
      <main className="app-main">
        {tab === "run" && <RunTab />}
        {tab === "graph" && <GraphTab />}
        {tab === "coverage" && <CoverageTab />}
        {tab === "reports" && <ReportsTab />}
      </main>
    </div>
  );
}

export default App;

