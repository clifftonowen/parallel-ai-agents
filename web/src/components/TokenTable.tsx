import { c, font, hairline, hairlineSoft, size, space } from "../theme";

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
    <div style={scroller}>
      <table style={tableStyle}>
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
              <td style={tdStyle}>{row.original != null ? String(row.original) : "n/a"}</td>
              <td style={tdStyle}>{row.adk != null ? String(row.adk) : "n/a"}</td>
              {showAsync && <td style={tdStyle}>{row.async != null ? String(row.async) : "n/a"}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const scroller: React.CSSProperties = { overflowX: "auto" };

const tableStyle: React.CSSProperties = {
  width: "100%",
  minWidth: 420,
  borderCollapse: "collapse",
  border: hairline,
};

const thStyle: React.CSSProperties = {
  padding: `${space.sm}px ${space.md}px`,
  textAlign: "left",
  fontFamily: font.mono,
  fontSize: size.micro,
  fontWeight: 700,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  color: c.inkFaint,
  borderBottom: hairline,
};

const tdStyle: React.CSSProperties = {
  padding: `${space.sm}px ${space.md}px`,
  fontSize: size.small,
  color: c.inkSoft,
  borderBottom: hairlineSoft,
};

const tdLabelStyle: React.CSSProperties = {
  ...tdStyle,
  color: c.ink,
  fontWeight: 500,
};
