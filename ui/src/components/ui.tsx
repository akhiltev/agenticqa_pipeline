import type { CSSProperties, ReactNode } from "react";

/** Generic surface container used across tabs for grouped content. */
export function Card({
  title,
  actions,
  children,
  style,
  bodyStyle,
  padded = true,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  style?: CSSProperties;
  bodyStyle?: CSSProperties;
  padded?: boolean;
}) {
  return (
    <div className="ui-card" style={style}>
      {(title || actions) && (
        <div className="ui-card-header">
          {title && <div className="ui-card-title">{title}</div>}
          {actions && <div className="ui-card-actions">{actions}</div>}
        </div>
      )}
      <div className={padded ? "ui-card-body" : undefined} style={bodyStyle}>
        {children}
      </div>
    </div>
  );
}

export type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info";

/** Small colored status pill. */
export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return <span className={`ui-badge ui-badge-${tone}`}>{children}</span>;
}

/** Centered placeholder for empty/blank states. */
export function EmptyState({ title, description }: { title: string; description?: ReactNode }) {
  return (
    <div className="ui-empty-state">
      <div className="ui-empty-state-title">{title}</div>
      {description && <div className="ui-empty-state-desc">{description}</div>}
    </div>
  );
}

/** Row of label + control, matching the existing `.field` convention. */
export function Field({ label, children, style }: { label: string; children: ReactNode; style?: CSSProperties }) {
  return (
    <div className="field" style={style}>
      <label>{label}</label>
      {children}
    </div>
  );
}

/** Segmented toggle control (replaces ad-hoc inline-styled button groups). */
export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="ui-segmented">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          className={opt.value === value ? "ui-segmented-btn active" : "ui-segmented-btn"}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
