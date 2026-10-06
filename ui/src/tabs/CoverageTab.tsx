import { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api, type CoverageReport, type RunRecord, type CoverageDelta } from "../api";
import { Card, Badge } from "../components/ui";


type SortKey = "class" | "line_pct" | "branch_pct" | "instruction_pct";

export default function CoverageTab() {
  const [coverage, setCoverage] = useState<CoverageReport | null>(null);
  const [history, setHistory] = useState<RunRecord[]>([]);
  const [delta, setDelta] = useState<CoverageDelta | null>(null);
  const [jacoco, setJacoco] = useState<{ exists: boolean; url: string | null }>({ exists: false, url: null });
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("line_pct");
  const [sortAsc, setSortAsc] = useState(true);
  const [reportLinks, setReportLinks] = useState<Record<string, string | null>>({});
  const [reportNotice, setReportNotice] = useState<string | null>(null);


  const refresh = () => {
    api.getCoverage().then(setCoverage).catch(() => setCoverage(null));
    api.getCoverageHistory().then(setHistory).catch(() => setHistory([]));
    api.getCoverageDelta().then(setDelta).catch(() => setDelta(null));
    api.getJacocoReportInfo().then(setJacoco).catch(() => setJacoco({ exists: false, url: null }));
  };

  useEffect(() => { refresh(); }, []);

  const chartData = history.map((r, i) => ({
    idx: i + 1,
    line: r.overall_line_pct,
    branch: r.overall_branch_pct,
    label: r.mode + (r.pr_id ? `#${r.pr_id}` : ""),
  }));

  const deltaByClass = useMemo(() => {
    const m = new Map<string, number>();
    delta?.per_class_changes.forEach((c) => m.set(c.class, c.delta));
    return m;
  }, [delta]);

  const filteredSorted = useMemo(() => {
    const classes = coverage?.classes ?? [];
    const filtered = search.trim()
      ? classes.filter((c) => c.class.toLowerCase().includes(search.trim().toLowerCase()))
      : classes;
    const sorted = [...filtered].sort((a, b) => {
      const av = sortKey === "class" ? a.class : a[sortKey];
      const bv = sortKey === "class" ? b.class : b[sortKey];
      const cmp = typeof av === "string" ? av.localeCompare(bv as string) : (av as number) - (bv as number);
      return sortAsc ? cmp : -cmp;
    });
    return sorted;
  }, [coverage, search, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else { setSortKey(key); setSortAsc(key === "class"); }
  };

  const openJacocoIndex = () => {
    if (jacoco.url) window.open(`http://127.0.0.1:8090${jacoco.url}`, "_blank");
  };

  const openClassReport = async (className: string) => {
    const cached = reportLinks[className];
    if (cached) { window.open(`http://127.0.0.1:8090${cached}`, "_blank"); return; }
    if (cached === null) {
      setReportNotice(`No JaCoCo HTML page for "${className}" - likely an annotation/interface with no instrumented lines.`);
      return;
    }
    try {
      const res = await api.getClassReportUrl(className);
      setReportLinks((prev) => ({ ...prev, [className]: res.url }));
      if (res.url) {
        window.open(`http://127.0.0.1:8090${res.url}`, "_blank");
      } else {
        setReportNotice(`No JaCoCo HTML page for "${className}" - likely an annotation/interface with no instrumented lines.`);
      }
    } catch {
      setReportNotice(`Could not resolve a report link for "${className}".`);
    }
  };


  return (
    <div style={{ padding: 20, overflowY: "auto", height: "100%" }}>
      <div className="ui-toolbar" style={{ marginBottom: 4 }}>
        <h2 style={{ margin: 0 }}>Coverage</h2>
        <button onClick={refresh}>↻ Refresh</button>
        <button
          className={jacoco.exists ? "btn-primary" : ""}
          onClick={openJacocoIndex}
          disabled={!jacoco.exists}
          title={jacoco.exists ? "Open sut/target/site/jacoco/index.html" : "Not generated yet - run the pipeline or mvn test"}
          style={{ marginLeft: "auto" }}
        >
          Open full JaCoCo report ↗
        </button>
      </div>
      <p style={{ fontSize: 11, color: "var(--color-text-faint)", marginTop: 0, marginBottom: 20 }}>
        The gauges/table below are a quick summary of jacoco.xml. For the authoritative, line-by-line
        green/red source view, use "Open full JaCoCo report" above, or the "Report" link on any row below.
      </p>

      {reportNotice && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            background: "var(--color-warning-light)",
            border: "1px solid #fde68a",
            color: "#854d0e",
            borderRadius: "var(--radius-sm)",
            padding: "8px 12px",
            fontSize: 12.5,
            marginBottom: 16,
          }}
        >
          <span>⚠ {reportNotice}</span>
          <button className="btn-ghost" onClick={() => setReportNotice(null)} style={{ padding: "2px 8px", fontSize: 11 }}>
            Dismiss
          </button>
        </div>
      )}

      {coverage && !coverage.error ? (
        <Card style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", gap: 24, padding: 20, justifyContent: "space-around" }}>
            <Gauge label="Line" value={coverage.overall_line_pct} />
            <Gauge label="Branch" value={coverage.overall_branch_pct} />
            <Gauge label="Instruction" value={coverage.overall_instruction_pct} />
          </div>
        </Card>
      ) : (
        <p>No coverage report yet - run the pipeline or `mvn test` first.</p>
      )}

      {delta && (
        <Card title="Latest Delta" style={{ marginBottom: 20 }}>
          <div style={{ padding: 16 }}>
            <p style={{ marginBottom: delta.per_class_changes.length > 0 ? 10 : 0 }}>
              Line: <strong style={{ color: delta.overall_line_delta >= 0 ? "var(--color-success)" : "var(--color-danger)" }}>
                {delta.overall_line_delta >= 0 ? "+" : ""}{delta.overall_line_delta} pts
              </strong>
              &nbsp;|&nbsp;
              Branch: <strong style={{ color: delta.overall_branch_delta >= 0 ? "var(--color-success)" : "var(--color-danger)" }}>
                {delta.overall_branch_delta >= 0 ? "+" : ""}{delta.overall_branch_delta} pts
              </strong>
            </p>
            {delta.per_class_changes.length > 0 && (
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5 }}>
                {delta.per_class_changes.map((c) => (
                  <li key={c.class} style={{ marginBottom: 4 }}>
                    {c.class}: {c.before}% &rarr; {c.after}%{" "}
                    <Badge tone={c.delta >= 0 ? "success" : "danger"}>{c.delta >= 0 ? "+" : ""}{c.delta}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      )}

      {chartData.length > 1 && (
        <Card title="Run History" style={{ marginBottom: 20 }}>
          <div style={{ height: 240, padding: 16 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="idx" />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="line" stroke="#2563eb" name="Line %" strokeWidth={2} />
                <Line type="monotone" dataKey="branch" stroke="#16a34a" name="Branch %" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      <Card title="Per-Class Coverage" padded={false}>
        <div className="ui-toolbar" style={{ padding: "12px 16px", borderBottom: "1px solid var(--color-border)" }}>
          <input
            placeholder="Filter by class name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ padding: 4, width: 240 }}
          />
          <span style={{ fontSize: 12, color: "var(--color-text-faint)" }}>
            {filteredSorted.length} / {coverage?.classes?.length ?? 0} classes
          </span>
        </div>
        <div style={{ maxHeight: 480, overflowY: "auto" }}>
          <table style={{ width: "100%", fontSize: 12.5, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid var(--color-border)", background: "#f8fafc" }}>
                <SortableHeader label="Class" sortKey="class" activeKey={sortKey} asc={sortAsc} onClick={toggleSort} />
                <SortableHeader label="Line %" sortKey="line_pct" activeKey={sortKey} asc={sortAsc} onClick={toggleSort} />
                <SortableHeader label="Branch %" sortKey="branch_pct" activeKey={sortKey} asc={sortAsc} onClick={toggleSort} />
                <SortableHeader label="Instruction %" sortKey="instruction_pct" activeKey={sortKey} asc={sortAsc} onClick={toggleSort} />
                <th>Δ</th>
                <th>Report</th>
              </tr>
            </thead>
            <tbody>
              {filteredSorted.map((c) => {
                const d = deltaByClass.get(c.class);
                return (
                  <tr key={c.class} className="ui-table-row" style={{ borderBottom: "1px solid var(--color-border)" }}>
                    <td>{c.class}</td>
                    <td><CoverageBar pct={c.line_pct} /></td>
                    <td>{c.branch_pct}</td>
                    <td>{c.instruction_pct}</td>
                    <td>
                      {d === undefined ? (
                        <span style={{ color: "var(--color-text-faint)" }}>-</span>
                      ) : (
                        <Badge tone={d >= 0 ? "success" : "danger"}>{d >= 0 ? "+" : ""}{d}</Badge>
                      )}
                    </td>
                    <td>
                      {reportLinks[c.class] === null ? (
                        <span style={{ fontSize: 11, color: "var(--color-text-faint)" }} title="No JaCoCo HTML page for this class (e.g. annotation/interface with no instrumented lines)">
                          n/a
                        </span>
                      ) : (
                        <button
                          onClick={() => openClassReport(c.class)}
                          disabled={!jacoco.exists}
                          style={{ fontSize: 11, padding: "2px 8px" }}
                        >
                          view ↗
                        </button>
                      )}
                    </td>

                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function CoverageBar({ pct }: { pct: number }) {
  const color = pct >= 90 ? "var(--color-success)" : pct >= 70 ? "var(--color-warning)" : "var(--color-danger)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 140 }}>
      <div style={{ flex: 1, background: "#e5e7eb", borderRadius: 4, height: 8, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, background: color, height: "100%" }} />
      </div>
      <span style={{ width: 36, textAlign: "right", color, fontWeight: 600 }}>{pct}</span>
    </div>
  );
}


function SortableHeader({
  label, sortKey, activeKey, asc, onClick,
}: { label: string; sortKey: SortKey; activeKey: SortKey; asc: boolean; onClick: (k: SortKey) => void }) {
  const active = activeKey === sortKey;
  return (
    <th
      style={{
        cursor: "pointer",
        userSelect: "none",
        color: active ? "var(--color-primary-dark)" : "var(--color-text-muted)",
        fontWeight: 600,
        fontSize: 11,
        textTransform: "uppercase",
        letterSpacing: "0.03em",
      }}
      onClick={() => onClick(sortKey)}
    >
      {label} {active ? (asc ? "▲" : "▼") : ""}
    </th>
  );
}

function Gauge({ label, value }: { label: string; value: number }) {
  const color = value >= 90 ? "var(--color-success)" : value >= 70 ? "var(--color-warning)" : "var(--color-danger)";
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 32, fontWeight: 700, color }}>{value}%</div>
      <div style={{ fontSize: 12, color: "var(--color-text-muted)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</div>
    </div>
  );

}

