import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api, type ReportListItem } from "../api";
import { EmptyState } from "../components/ui";

export default function ReportsTab() {
  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");

  const refresh = () => {
    api.listReports().then((list) => {
      setReports(list);
      if (list.length > 0 && !selected) setSelected(list[0].name);
    });
  };

  useEffect(() => { refresh(); }, []);

  useEffect(() => {
    if (selected) {
      api.getReport(selected).then((r) => setContent(r.content)).catch(() => setContent("(failed to load)"));
    }
  }, [selected]);

  return (
    <div style={{ display: "flex", height: "100%", background: "var(--color-bg)" }}>
      <div style={{ width: 260, borderRight: "1px solid var(--color-border)", overflowY: "auto", padding: 12, background: "var(--color-surface)" }}>
        <button onClick={refresh} style={{ width: "100%", marginBottom: 10 }}>↻ Refresh</button>
        {reports.length === 0 && (
          <EmptyState title="No reports yet" description="Run the pipeline to generate a QA report." />
        )}
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {reports.map((r) => (
            <li
              key={r.name}
              onClick={() => setSelected(r.name)}
              style={{
                padding: "8px 10px",
                cursor: "pointer",
                fontSize: 12.5,
                background: selected === r.name ? "var(--color-primary-light)" : undefined,
                color: selected === r.name ? "var(--color-primary-dark)" : "var(--color-text)",
                fontWeight: selected === r.name ? 600 : 400,
                borderRadius: "var(--radius-sm)",
                marginBottom: 2,
                wordBreak: "break-word",
              }}
            >
              📄 {r.name}
            </li>
          ))}
        </ul>
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
        <div style={{ maxWidth: 860, margin: "0 auto", background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: "var(--radius-md)", padding: 28, boxShadow: "var(--shadow-sm)" }}>
          {content ? <ReactMarkdown>{content}</ReactMarkdown> : <EmptyState title="Select a report" description="Choose a report from the list on the left to view its contents." />}
        </div>
      </div>
    </div>
  );
}

