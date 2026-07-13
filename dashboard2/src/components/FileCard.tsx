import { useState } from "react";
import { downloadFile, fetchFileText } from "../api/client";

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
          <span style={{ fontSize: 22 }}>{icon}</span>
          <span style={{ color: "#f1f5f9", fontWeight: 600, fontSize: 14 }}>{label}</span>
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
        {error && <p style={{ color: "#f87171", fontSize: 11, marginTop: 6 }}>{error}</p>}
      </div>

      {/* Preview dialog */}
      {previewOpen && (
        <div
          style={overlayStyle}
          onClick={(e) => e.target === e.currentTarget && setPreviewOpen(false)}
        >
          <div style={dialogStyle}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ color: "#f1f5f9", fontSize: 16 }}>{label}</h3>
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
  backgroundColor: "#1e293b",
  borderRadius: 10,
  padding: 14,
  marginBottom: 8,
  border: "1px solid #334155",
};

const previewBtnStyle: React.CSSProperties = {
  flex: 1,
  backgroundColor: "#334155",
  color: "#94a3b8",
  border: "none",
  borderRadius: 6,
  padding: "8px 12px",
  fontSize: 13,
  fontWeight: 600,
};

const dlBtnStyle: React.CSSProperties = {
  flex: 1,
  backgroundColor: "#6366f1",
  color: "#fff",
  border: "none",
  borderRadius: 6,
  padding: "8px 12px",
  fontSize: 13,
  fontWeight: 600,
};

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  backgroundColor: "rgba(0,0,0,0.7)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 1000,
  padding: 20,
};

const dialogStyle: React.CSSProperties = {
  backgroundColor: "#1e293b",
  borderRadius: 12,
  padding: 24,
  width: "100%",
  maxWidth: 800,
  maxHeight: "80vh",
  display: "flex",
  flexDirection: "column",
  border: "1px solid #334155",
};

const preStyle: React.CSSProperties = {
  flex: 1,
  overflow: "auto",
  color: "#cbd5e1",
  fontSize: 12,
  lineHeight: 1.7,
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
};

const closeBtnStyle: React.CSSProperties = {
  backgroundColor: "transparent",
  color: "#6366f1",
  border: "none",
  fontSize: 14,
  fontWeight: 600,
};
