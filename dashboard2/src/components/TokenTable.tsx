interface Row {
  label: string;
  original?: string | number;
  adk?: string | number;
  async?: string | number;
}

interface Props {
  rows: Row[];
  showAsync?: boolean;
}

export default function TokenTable({ rows, showAsync = false }: Props) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", borderRadius: 8, overflow: "hidden", border: "1px solid #334155" }}>
      <thead>
        <tr style={{ backgroundColor: "#1e293b" }}>
          <th style={thStyle}>Metric</th>
          <th style={{ ...thStyle, color: "#f59e0b" }}>Original</th>
          <th style={{ ...thStyle, color: "#6366f1" }}>ADK</th>
          {showAsync && <th style={{ ...thStyle, color: "#14b8a6" }}>Async</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} style={{ backgroundColor: i % 2 === 0 ? "#0f172a" : "#1e293b" }}>
            <td style={tdLabelStyle}>{row.label}</td>
            <td style={tdStyle}>{row.original != null ? String(row.original) : "—"}</td>
            <td style={tdStyle}>{row.adk != null ? String(row.adk) : "—"}</td>
            {showAsync && <td style={tdStyle}>{row.async != null ? String(row.async) : "—"}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const thStyle: React.CSSProperties = {
  padding: "9px 12px",
  textAlign: "left",
  fontSize: 12,
  fontWeight: 700,
  color: "#94a3b8",
  borderBottom: "1px solid #334155",
};

const tdStyle: React.CSSProperties = {
  padding: "9px 12px",
  fontSize: 12,
  color: "#cbd5e1",
  borderBottom: "1px solid #1e293b",
};

const tdLabelStyle: React.CSSProperties = {
  ...tdStyle,
  color: "#94a3b8",
  fontWeight: 500,
};
