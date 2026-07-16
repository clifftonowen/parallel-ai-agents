import { c, font, hairline, hairlineSoft } from "../theme";

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
    <table style={{ width: "100%", borderCollapse: "collapse", border: hairline }}>
      <thead>
        <tr style={{ backgroundColor: c.paperCard }}>
          <th style={thStyle}>Metric</th>
          <th style={{ ...thStyle, color: c.inkSoft }}>Original</th>
          <th style={{ ...thStyle, color: c.reagent }}>ADK</th>
          {showAsync && <th style={{ ...thStyle, color: c.reagentSoft }}>Async</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} style={{ backgroundColor: i % 2 === 0 ? c.paper : c.paperCard }}>
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
  fontFamily: font.mono,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  color: c.inkFaint,
  borderBottom: hairline,
};

const tdStyle: React.CSSProperties = {
  padding: "9px 12px",
  fontSize: 12,
  color: c.inkSoft,
  borderBottom: hairlineSoft,
};

const tdLabelStyle: React.CSSProperties = {
  ...tdStyle,
  color: c.ink,
  fontWeight: 500,
};
