import { c, font, size } from "../theme";

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

const SERIES = {
  original: c.inkSoft,
  adk: c.reagent,
  async: c.reagentSoft,
};

export default function BarChart({ label, original, adk, async: asyncVal, maxValue }: Props) {
  const origPct  = original  != null ? Math.max((original  / maxValue) * 100, 2) : 0;
  const adkPct   = adk       != null ? Math.max((adk       / maxValue) * 100, 2) : 0;
  const asyncPct = asyncVal  != null ? Math.max((asyncVal  / maxValue) * 100, 2) : 0;

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontFamily: font.mono, color: c.inkFaint, fontSize: size.micro, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>
        {label}
      </div>
      {original != null && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ fontFamily: font.mono, color: SERIES.original, fontSize: size.micro, fontWeight: 700, width: 32 }}>Orig</span>
          <div style={{ flex: 1, height: 14, backgroundColor: c.paperCard, overflow: "hidden" }}>
            <div style={{ width: `${origPct}%`, height: "100%", backgroundColor: SERIES.original, transition: "width 0.5s ease" }} />
          </div>
          <span style={{ fontFamily: font.mono, color: c.inkSoft, fontSize: size.micro, width: 42, textAlign: "right" }}>{fmt(original)}</span>
        </div>
      )}
      {adk != null && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: asyncVal != null ? 4 : 0 }}>
          <span style={{ fontFamily: font.mono, color: SERIES.adk, fontSize: size.micro, fontWeight: 700, width: 32 }}>ADK</span>
          <div style={{ flex: 1, height: 14, backgroundColor: c.paperCard, overflow: "hidden" }}>
            <div style={{ width: `${adkPct}%`, height: "100%", backgroundColor: SERIES.adk, transition: "width 0.5s ease" }} />
          </div>
          <span style={{ fontFamily: font.mono, color: c.inkSoft, fontSize: size.micro, width: 42, textAlign: "right" }}>{fmt(adk)}</span>
        </div>
      )}
      {asyncVal != null && (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontFamily: font.mono, color: SERIES.async, fontSize: size.micro, fontWeight: 700, width: 32 }}>Asyn</span>
          <div style={{ flex: 1, height: 14, backgroundColor: c.paperCard, overflow: "hidden" }}>
            <div style={{ width: `${asyncPct}%`, height: "100%", backgroundColor: SERIES.async, transition: "width 0.5s ease" }} />
          </div>
          <span style={{ fontFamily: font.mono, color: c.inkSoft, fontSize: size.micro, width: 42, textAlign: "right" }}>{fmt(asyncVal)}</span>
        </div>
      )}
    </div>
  );
}
