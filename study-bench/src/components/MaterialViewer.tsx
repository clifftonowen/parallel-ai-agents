import { useEffect, useState } from "react";
import { downloadFile, fetchFileText, fileUrl } from "../api/client";
import Markdown, { markdownStyles } from "./Markdown";
import { c, font, eyebrow } from "../theme";

// A download option offered on a material (e.g. Markdown, PDF, or the mp4 itself).
export interface DownloadOption {
  label: string;
  filename: string;
}

export interface Material {
  key: string;
  title: string;
  blurb: string;
  kind: "doc" | "video";
  // For docs: the .md filename to render. For video: the .mp4 filename to play.
  sourceFilename: string;
  downloads: DownloadOption[];
}

interface Props {
  run_id: string;
  material: Material;
  onClose: () => void;
}

// The signature moment: the chosen material surfaces into focus, like a print coming
// up in a developing tray. Everything else on the site is quiet so this can breathe.
export default function MaterialViewer({ run_id, material, onClose }: Props) {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  useEffect(() => {
    if (material.kind !== "doc") return;
    let live = true;
    fetchFileText(run_id, material.sourceFilename)
      .then((t) => live && setText(t))
      .catch((e: unknown) => live && setError(e instanceof Error ? e.message : "Couldn't open this."));
    return () => {
      live = false;
    };
  }, [run_id, material]);

  const single = material.downloads.length === 1;

  return (
    <div style={overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <style>{markdownStyles}</style>
      <div role="dialog" aria-label={`${material.title}`} style={sheet} className="animate-material">
        {/* Header — title, one-line description, and the actions. */}
        <div style={header}>
          <div style={{ minWidth: 0 }}>
            <div style={eyebrow}>{material.kind === "video" ? "Watching" : "Reading"}</div>
            <h2 style={titleStyle}>{material.title}</h2>
          </div>

          <div style={actions}>
            {single ? (
              <button onClick={() => downloadFile(run_id, material.downloads[0].filename)} style={dlBtn}>
                Download {material.downloads[0].label}
              </button>
            ) : (
              <div style={{ position: "relative" }}>
                <button onClick={() => setMenuOpen((o) => !o)} style={dlBtn} aria-expanded={menuOpen}>
                  Download ▾
                </button>
                {menuOpen && (
                  <div style={menu} onMouseLeave={() => setMenuOpen(false)}>
                    {material.downloads.map((d) => (
                      <button
                        key={d.filename}
                        onClick={() => {
                          downloadFile(run_id, d.filename);
                          setMenuOpen(false);
                        }}
                        style={menuItem}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            <button onClick={onClose} style={closeBtn} aria-label="Close">
              Close ✕
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={body}>
          {material.kind === "video" ? (
            <video controls autoPlay preload="metadata" style={video} src={fileUrl(run_id, material.sourceFilename)}>
              Your browser can't play this video. Use Download to save it.
            </video>
          ) : error ? (
            <p style={errText}>{error}</p>
          ) : text == null ? (
            <p style={loadingText}>Bringing it into focus…</p>
          ) : (
            <Markdown source={text} />
          )}
        </div>
      </div>
    </div>
  );
}

// ── styles ────────────────────────────────────────────────────────────────────

const overlay: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  backgroundColor: "rgba(23, 21, 15, 0.62)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 1000,
  padding: "clamp(12px, 4vw, 40px)",
};

const sheet: React.CSSProperties = {
  backgroundColor: c.paper,
  border: `1px solid ${c.ink}`,
  width: "100%",
  maxWidth: 800,
  maxHeight: "90vh",
  display: "flex",
  flexDirection: "column",
};

const header: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: 16,
  padding: "18px 22px",
  borderBottom: `1px solid ${c.rule}`,
  flexWrap: "wrap",
};

const titleStyle: React.CSSProperties = {
  fontFamily: font.display,
  fontSize: "clamp(24px, 4vw, 32px)",
  fontWeight: 600,
  color: c.ink,
  marginTop: 2,
  lineHeight: 1.05,
};

const actions: React.CSSProperties = { display: "flex", alignItems: "center", gap: 10, flexShrink: 0 };

const dlBtn: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  backgroundColor: c.ink,
  color: c.paper,
  padding: "9px 14px",
};

const menu: React.CSSProperties = {
  position: "absolute",
  top: "calc(100% + 4px)",
  right: 0,
  backgroundColor: c.paper,
  border: `1px solid ${c.ink}`,
  minWidth: 190,
  maxWidth: "80vw", // never spill past the screen edge on a narrow phone
  zIndex: 5,
  display: "flex",
  flexDirection: "column",
};
const menuItem: React.CSSProperties = {
  textAlign: "left",
  padding: "10px 14px",
  fontFamily: font.body,
  fontSize: 14,
  color: c.ink,
  borderBottom: `1px solid ${c.ruleSoft}`,
};

const closeBtn: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  fontWeight: 700,
  letterSpacing: "0.08em",
  color: c.ink,
};

const body: React.CSSProperties = { overflowY: "auto", padding: "24px 26px" };

const video: React.CSSProperties = { width: "100%", display: "block", backgroundColor: "#000" };
const loadingText: React.CSSProperties = { fontFamily: font.mono, fontSize: 13, color: c.inkFaint };
const errText: React.CSSProperties = { fontFamily: font.mono, fontSize: 13, color: c.flag };
