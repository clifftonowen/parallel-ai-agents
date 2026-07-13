interface Props {
  label: string;
  original?: number;
  adk?: number;
  async?: number;
  maxValue: number;
}

function fmt(v?: number) {
  return v != null ? `${v.toFixed(1)}s` : "—";
}

export default function BarChart({ label, original, adk, async: asyncVal, maxValue }: Props) {
  const origPct  = original  != null ? Math.max((original  / maxValue) * 100, 2) : 0;
  const adkPct   = adk       != null ? Math.max((adk       / maxValue) * 100, 2) : 0;
  const asyncPct = asyncVal  != null ? Math.max((asyncVal  / maxValue) * 100, 2) : 0;

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ color: "#64748b", fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.3px", marginBottom: 5 }}>
        {label}
      </div>
      {original != null && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ color: "#f59e0b", fontSize: 10, fontWeight: 700, width: 32 }}>Orig</span>
          <div style={{ flex: 1, height: 14, backgroundColor: "#1e293b", borderRadius: 7, overflow: "hidden" }}>
            <div style={{ width: `${origPct}%`, height: "100%", backgroundColor: "#f59e0b", borderRadius: 7, transition: "width 0.5s ease" }} />
          </div>
          <span style={{ color: "#cbd5e1", fontSize: 11, width: 42, textAlign: "right" }}>{fmt(original)}</span>
        </div>
      )}
      {adk != null && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: asyncVal != null ? 4 : 0 }}>
          <span style={{ color: "#6366f1", fontSize: 10, fontWeight: 700, width: 32 }}>ADK</span>
          <div style={{ flex: 1, height: 14, backgroundColor: "#1e293b", borderRadius: 7, overflow: "hidden" }}>
            <div style={{ width: `${adkPct}%`, height: "100%", backgroundColor: "#6366f1", borderRadius: 7, transition: "width 0.5s ease" }} />
          </div>
          <span style={{ color: "#cbd5e1", fontSize: 11, width: 42, textAlign: "right" }}>{fmt(adk)}</span>
        </div>
      )}
      {asyncVal != null && (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: "#14b8a6", fontSize: 10, fontWeight: 700, width: 32 }}>Asyn</span>
          <div style={{ flex: 1, height: 14, backgroundColor: "#1e293b", borderRadius: 7, overflow: "hidden" }}>
            <div style={{ width: `${asyncPct}%`, height: "100%", backgroundColor: "#14b8a6", borderRadius: 7, transition: "width 0.5s ease" }} />
          </div>
          <span style={{ color: "#cbd5e1", fontSize: 11, width: 42, textAlign: "right" }}>{fmt(asyncVal)}</span>
        </div>
      )}
    </div>
  );
}
