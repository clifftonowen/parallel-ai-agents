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
          <span style={{ fontSize: size.title }}>{icon}</span>
          <span style={{ color: c.ink, fontWeight: 600, fontSize: size.body }}>{label}</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {previewable && (
            <button
              onClick={handlePreview}
              disabled={previewLoading}
              style={previewBtnStyle}
            >
              {previewLoading ? "Loading..." : "Preview"}
            </button>
          )}
          <button onClick={handleDownload} style={dlBtnStyle}>
            ↓ Download
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

const previewBtnStyle: React.CSSProperties = {
  flex: 1,
  backgroundColor: "transparent",
  color: c.inkSoft,
  border: `1px solid ${c.rule}`,
  padding: "8px 12px",
  fontSize: size.small,
  fontWeight: 600,
};

const dlBtnStyle: React.CSSProperties = {
  flex: 1,
  backgroundColor: c.reagent,
  color: c.paper,
  padding: "8px 12px",
  fontSize: size.small,
  fontWeight: 600,
};

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  backgroundColor: "rgba(23,21,15,0.7)",
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
