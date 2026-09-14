import { useState } from "react";
import { downloadFile, fetchFileText } from "../api/client";
import { c, font, hairline, size } from "../theme";

interface Props {
  run_id: string;
  label: string;
  filename: string;
  icon: string;
  previewable?: boolean;
}

export default function FileCard({ run_id, label, filename, icon, previewable }: Props) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePreview = async () => {
    setPreviewLoading(true);
    setError(null);
    try {
      const text = await fetchFileText(run_id, filename);
      setPreviewContent(text);
      setPreviewOpen(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDownload = () => {
    try {
      downloadFile(run_id, filename);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Download failed");
    }
  };

  return (
    <>
      <div style={cardStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
          <span style={fileKind}>{icon}</span>
          <span style={{ color: c.ink, fontWeight: 600, fontSize: size.body }}>{label}</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {previewable && (
            <button
              className="btn btn-secondary"
              onClick={handlePreview}
              disabled={previewLoading}
              style={{ flex: 1 }}
            >
              {previewLoading ? "Loading…" : "Preview"}
            </button>
          )}
          <button className="btn btn-secondary" onClick={handleDownload} style={dlBtnStyle}>
            Download
          </button>
        </div>
        {error && <p style={{ color: c.flag, fontSize: size.micro, marginTop: 6 }}>{error}</p>}
      </div>

      {/* Preview dialog */}
      {previewOpen && (
        <div
          style={overlayStyle}
          onClick={(e) => e.target === e.currentTarget && setPreviewOpen(false)}
        >
          <div style={dialogStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ fontFamily: font.display, color: c.ink, fontSize: size.lead, fontWeight: 600 }}>{label}</h3>
              <button onClick={() => setPreviewOpen(false)} style={closeBtnStyle}>✕ Close</button>
            </div>
            <pre style={preStyle}>{previewContent}</pre>
          </div>
        </div>
      )}
    </>
  );
}

const cardStyle: React.CSSProperties = {
  backgroundColor: c.paperCard,
  border: hairline,
  padding: 14,
  marginBottom: 8,
};

/** Secondary, not primary. This was a filled accent bar, which was survivable
 *  on paper and is not on a dark ground: the outputs tab lists five files, so
 *  the page rendered five full-width cyan bars and read as five primary
 *  actions. theme.ts's accent rule does permit "a list of equivalent actions"
 *  to count as one use, but permitting it and it looking right are different
 *  questions. The accent survives as the label colour. */
const dlBtnStyle: React.CSSProperties = {
  flex: 1,
  color: "var(--color-accent-fg)",
};

/** The file kind, set as a mono tag rather than an emoji. Reads at a glance,
 *  matches the mono-for-technical-metadata rule, and does not carry meaning in
 *  a glyph that renders differently on every platform. */
const fileKind: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.micro,
  letterSpacing: "0.06em",
  color: c.inkFaint,
  border: hairline,
  borderRadius: 2,
  padding: "2px 6px",
  flex: "none",
};

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  backgroundColor: "var(--color-scrim)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 1000,
  padding: 20,
};

const dialogStyle: React.CSSProperties = {
  backgroundColor: c.paperCard,
  padding: 24,
  width: "100%",
  maxWidth: 800,
  maxHeight: "80vh",
  display: "flex",
  flexDirection: "column",
  border: hairline,
};

const preStyle: React.CSSProperties = {
  flex: 1,
  overflow: "auto",
  color: c.inkSoft,
  fontFamily: font.mono,
  fontSize: size.small,
  lineHeight: 1.7,
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
};

const closeBtnStyle: React.CSSProperties = {
  backgroundColor: "transparent",
  color: c.reagent,
  fontSize: size.body,
  fontWeight: 600,
};
